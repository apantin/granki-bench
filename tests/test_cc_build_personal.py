import contextlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bench.cleaning import VERSION
from bench.candidates import blogspot_uniform
from bench.livejournal_provenance import POLICY
from test_livejournal_provenance import page as lj_page,credit
from test_blogspot_post import page
import test_cc_build_provenance as build_tests
import test_cc_clean_version as clean_tests

build=build_tests.build
V11=build_tests.V11


class PersonalBuildTest(unittest.TestCase):
    def test_lj_repost_is_excluded_before_cleaner_only_by_new_policy(self):
        source=lj_page(credit()+'<p>Содержимое.</p>')
        helper=build_tests.BuildProvenanceTest()
        old,_,_,old_calls=helper.run_build(source,V11,'owner.livejournal.com',url='https://owner.livejournal.com/456.html')
        new,summary,groups,calls=helper.run_build(source,POLICY,'owner.livejournal.com',url='https://owner.livejournal.com/456.html')
        self.assertEqual((len(old),old_calls),(1,1));self.assertEqual((new,groups,calls),([],[],0))
        self.assertEqual(summary['livejournal_source:explicit-repost-credit'],1)

    def test_lj_self_credit_and_unmarked_own_post_are_kept_as_candidates(self):
        helper=build_tests.BuildProvenanceTest()
        for source,status in [(lj_page(credit(author='owner',origin='owner')),'self-repost-credit'),(lj_page('<p>Своя проза.</p>'),'no-explicit-repost-credit')]:
            selected,_,_,calls=helper.run_build(source,POLICY,'owner.livejournal.com',url='https://owner.livejournal.com/456.html')
            self.assertEqual((len(selected),calls),(1,1))
            self.assertEqual(selected[0]['livejournal_source_review']['status'],status)
            self.assertFalse(selected[0]['livejournal_source_review']['admitted'])

    def test_v9_inherits_translation_and_profile_guards(self):
        source='<body><h5><span class="title">Перевод:</span><span class="value">Переводчик</span></h5><p>Текст.</p></body>'
        selected,summary,_,calls=build_tests.BuildProvenanceTest().run_build(source,POLICY)
        self.assertEqual((selected,calls),([],0));self.assertEqual(summary['primary_header_translation'],1)

    def test_v23_real_build_keeps_bound_blog_title_and_holds_ambiguous_post(self):
        helper=clean_tests.CleanVersionBuildTest()
        selected,_,raw,_,_=helper.run_build(blogspot_uniform.VERSION,host='example.blogspot.com',source=page())
        self.assertEqual(len(selected),1);self.assertTrue(raw[0].startswith('# Заголовок поста\n\n'))
        self.assertEqual(selected[0]['author'],'example.blogspot.com')
        selected,summary,_,_,_=helper.run_build(blogspot_uniform.VERSION,host='example.blogspot.com',source=page(title='<h3>Неопределённая шапка</h3>'))
        self.assertEqual(selected,[]);self.assertEqual(summary['blogspot_unbound_primary_post'],1)

    def test_domain_index_override_reaches_index_without_changing_other_defaults(self):
        config=dict(clean_version=VERSION,dependencies={},max_records=20,candidate_limit=5,
                    seed='test',max_blocks=1,min_words=1,max_words=100,min_cyrillic=.5,
                    dedup_threshold=.85,target=1,subgenres=['personal'],domain_cap=1,author_cap=5,
                    index_blocks={'blogspot.com':8})
        domains=[dict(domain=host,snapshots='snapshot',url_pattern='.*',subgenre='personal') for host in ['blogspot.com','example.org']]
        with tempfile.TemporaryDirectory() as temporary,patch.object(build,'HTTP',return_value=SimpleNamespace(bytes=0,requests=0)), \
             patch.object(build,'candidates',return_value=[]) as index,contextlib.redirect_stdout(io.StringIO()):
            build.build(config,domains,Path(temporary))
        self.assertEqual([call.kwargs['max_blocks'] for call in index.call_args_list],[8,1])

    def test_invalid_domain_index_limit_fails_before_network_and_outputs(self):
        for value in [None,[],True,{'unknown.org':1},{'example.org':True},{'example.org':0},{'example.org':21}]:
            config=dict(clean_version=VERSION,dependencies={},max_records=20,index_blocks=value)
            domains=[dict(domain='example.org')]
            with self.subTest(value=value),tempfile.TemporaryDirectory() as temporary, \
                 patch.object(build,'HTTP',side_effect=AssertionError('network')):
                folder=Path(temporary)
                with self.assertRaisesRegex(ValueError,'блоков индекса'):build.build(config,domains,folder)
                self.assertEqual(list(folder.iterdir()),[])
