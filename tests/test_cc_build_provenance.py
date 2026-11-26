"""Прохождение первичного маркера через сборщик до очистки и квот."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from bench.cleaning import CleanText, VERSION

CC = Path(__file__).resolve().parents[1]/'scripts/cc'
with patch.object(sys, 'path', [str(CC), *sys.path]):
    spec = importlib.util.spec_from_file_location('cc_build_provenance_test', CC/'build.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

V5 = 'rsdn-primary-header-profile-v2'
V6 = 'rsdn-primary-header-profile-translation-v3'
V7 = 'primary-header-rsdn-habr-v4'
V8 = 'primary-source-rsdn-habr-v5'
V9 = 'primary-source-rsdn-habr-kontur-v6'
V10 = 'primary-source-rsdn-habr-kontur-liveinternet-v7'
V11 = 'primary-source-series-v8'


class BuildProvenanceTest(unittest.TestCase):
    def run_build(self, source, policy, host='rsdn.org',url=None,paused_domains=None):
        source = ('<html>'+source+'</html>').encode()
        config = dict(clean_version=VERSION, dependencies={}, max_records=5, candidate_limit=5,
                      seed='test', max_blocks=1, min_words=1, max_words=100, min_cyrillic=.5,
                      dedup_threshold=.85, target=1, subgenres=['technical'], domain_cap=1, author_cap=5)
        if policy is not None:
            config['provenance_policy'] = policy
        if paused_domains is not None:
            config['paused_domains'] = paused_domains
        domain = dict(domain=host, snapshots='snapshot', url_pattern='.*', subgenre='technical')
        record = dict(url=url or 'https://'+host+'/article/example', filename='example.warc.gz', offset='0', length='1')
        http = SimpleNamespace(bytes=0, requests=0, get=lambda *args: b'compressed')
        clean = CleanText('Это синтетический текст для проверки сборщика.', 'Это синтетический текст для проверки сборщика.')
        with tempfile.TemporaryDirectory() as temporary, patch.object(build, 'HTTP', return_value=http), \
             patch.object(build, 'candidates', return_value=[record]), patch.object(build, 'response_body', return_value=source), \
             patch.object(build, 'html_article', return_value=(clean, {})) as extract, contextlib.redirect_stdout(io.StringIO()):
            folder = Path(temporary)
            groups = build.build(config, [domain], folder)
            selected = json.loads((folder/'cc-rebuild/selected.json').read_text())
            summary = json.loads((folder/'cc-rebuild/summary.json').read_text())
            return selected, summary, groups, extract.call_count

    def test_new_recipe_rejects_translation_before_cleaning(self):
        source = '<body><h5><span class="title">Перевод:</span><span class="value">Переводчик</span></h5><p>Текст.</p></body>'
        for legacy in [None, V5]:
            selected, _, _, calls = self.run_build(source, legacy)
            self.assertEqual((len(selected), calls), (1, 1))
        selected, summary, groups, calls = self.run_build(source, V6)
        self.assertEqual((selected, groups, calls), ([], [], 0))
        self.assertEqual(summary['primary_header_translation_without_author'], 1)
        self.assertEqual(summary['primary_header_translation'], 1)
        self.assertEqual(summary['accepted'] if 'accepted' in summary else 0, 0)

    def test_new_recipe_keeps_existing_author_and_profile_constraints(self):
        source = '<body><h5><span class="title">Автор:</span><span class="value"><a href="/account/info/1">Первый Автор</a></span></h5><p>Текст.</p></body>'
        before, _, groups_before, _ = self.run_build(source, V5)
        after, _, groups_after, _ = self.run_build(source, V6)
        self.assertEqual(groups_before, groups_after)
        for field in ['authors', 'author', 'author_quota_keys', 'sha256', 'raw_sha256']:
            self.assertEqual(before[0][field], after[0][field])
        self.assertEqual(after[0]['author_quota_keys'], ['rsdn-profile:1'])
        self.assertTrue(after[0]['author_method'].startswith(V6+':'))

    def test_source_only_header_stays_unknown_and_uses_domain_quota(self):
        source = '<body><h5><span class="title">Источник:</span><span class="value">Журнал</span></h5><p>Текст.</p></body>'
        selected, summary, _, calls = self.run_build(source, V6)
        self.assertEqual((len(selected), calls), (1, 1))
        self.assertEqual(selected[0]['authors'], ['domain:rsdn.org'])
        self.assertEqual(summary.get('primary_header_translation_without_author', 0), 0)

    def test_v7_habr_translation_is_rejected_before_cleaning_only_in_new_recipe(self):
        source = '<body><article class="tm-article-presenter__content"><div class="tm-article-presenter__header"><div class="tm-article-presenter__snippet"><h1>Тестовая статья</h1><div class="tm-article-snippet__labels"><div class="tm-article-snippet__label tm-article-snippet__label_variant-translation">Перевод</div></div></div></div><div id="post-content-body">Текст.</div></article></body>'
        before, summary_before, _, calls_before = self.run_build(source, V6, 'habr.com')
        self.assertEqual((len(before),calls_before),(1,1))
        self.assertNotIn('habr_primary_header_translation',summary_before)
        after, summary, groups, calls = self.run_build(source, V7, 'habr.com')
        self.assertEqual((after,groups,calls),([],[],0))
        self.assertEqual(summary['habr_primary_header_translation'],1)
        self.assertNotIn('primary_header_translation_without_author',summary)

    def test_v7_unknown_habr_header_is_not_blanket_excluded(self):
        source = '<body><article><h1>Тестовая статья</h1><div id="post-content-body"><p>Перевод слова в примере.</p></div></article></body>'
        before, _, before_groups, _ = self.run_build(source,V6,'habr.com')
        after, summary, groups, calls = self.run_build(source,V7,'habr.com')
        self.assertEqual((len(after),calls),(1,1))
        self.assertEqual(before_groups,groups)
        self.assertEqual({k:v for k,v in before[0].items() if k not in {'path','raw_path'}},
                         {k:v for k,v in after[0].items() if k not in {'path','raw_path'}})
        self.assertNotIn('habr_primary_header_translation',summary)

    def test_v7_preserves_rsdn_translation_and_profile_guards(self):
        source = '<body><h5><span class="title">Перевод:</span><span class="value">Переводчик</span></h5><p>Текст.</p></body>'
        after, summary, groups, calls = self.run_build(source,V7)
        self.assertEqual((after,groups,calls),([],[],0))
        self.assertEqual(summary['primary_header_translation_without_author'],1)
        self.assertNotIn('habr_primary_header_translation',summary)
        source = '<body><h5><span class="title">Автор:</span><span class="value"><a href="/account/info/1">Первый Автор</a></span></h5><p>Текст.</p></body>'
        before, _, before_groups, _ = self.run_build(source,V6)
        after, _, groups, _ = self.run_build(source,V7)
        self.assertEqual(before_groups,groups)
        for field in ['authors','author','author_quota_keys','sha256','raw_sha256']:
            self.assertEqual(before[0][field],after[0][field])
        self.assertTrue(after[0]['author_method'].startswith(V7+':'))

    def test_v8_all_confirmed_habr_roles_are_rejected_before_cleaning_only_in_new_policy(self):
        def page(body,label=''):return '<body><article class="post post_full"><div class="post__wrapper"><h1>Тест</h1>'+label+'<div id="post-content-body">'+body+'</div></div></article></body>'
        label='<ul class="post__marks"><li class="inline-list__item_post-type"><span class="post__type-label" title="Перевод">Перевод</span></li></ul>'
        variants=[(page('Авторский текст.',label),'explicit-translation','legacy-header'),
                  (page('<p>Предлагаю перевод интересной статьи о тестовом формате.</p>'),'explicit-translation','opening-declaration'),
                  (page('<p>Текст.</p><p>P.S. Оригинал тут https://example.org/original, не могу опубликовать топик-ссылку.</p>'),'explicit-reprint','closing-repost-declaration')]
        for source,status,role in variants:
            with self.subTest(role=role):
                old,_,_,calls=self.run_build(source,V7,'habr.com');self.assertEqual((len(old),calls),(1,1))
                new,summary,groups,calls=self.run_build(source,V8,'habr.com');self.assertEqual((new,groups,calls),([],[],0))
                self.assertEqual(summary['habr_source:'+status],1);self.assertEqual(summary['habr_source_role:'+role],1)
                self.assertNotIn('primary_header_translation_without_author',summary)

    def test_v8_keeps_unknown_and_mixed_sources_outside_explicit_gate(self):
        for source in ['<body><h1>Пример</h1><p>Перевод термина.</p></body>',
                       '<body><article class="post post_full"><div class="post__wrapper"><h1>Пример</h1><div id="post-content-body"><p>Предлагаю перевод интересной статьи с моими комментариями.</p></div></div></article></body>']:
            before,_,before_groups,_=self.run_build(source,V7,'habr.com');after,summary,groups,calls=self.run_build(source,V8,'habr.com')
            self.assertEqual((len(after),calls),(1,1));self.assertEqual(before_groups,groups)
            self.assertFalse(any(k.startswith('habr_source:') for k in summary))
            for field in ['sha256','raw_sha256','author']:self.assertEqual(before[0][field],after[0][field])

    def test_v8_rsdn_translation_and_profile_constraints_stay_unchanged(self):
        source='<body><h5><span class="title">Перевод:</span><span class="value">Переводчик</span></h5><p>Текст.</p></body>'
        after,summary,groups,calls=self.run_build(source,V8);self.assertEqual((after,groups,calls),([],[],0));self.assertEqual(summary['primary_header_translation_without_author'],1)
        source='<body><h5><span class="title">Автор:</span><span class="value"><a href="/account/info/1">Первый Автор</a></span></h5><p>Текст.</p></body>'
        before,_,before_groups,_=self.run_build(source,V7);after,_,groups,_=self.run_build(source,V8);self.assertEqual(before_groups,groups)
        for field in ['author','authors','author_quota_keys','sha256','raw_sha256']:self.assertEqual(before[0][field],after[0][field])

    def test_v9_rejects_only_proven_unbound_preview_before_cleaning(self):
        data=json.dumps({'@type':'Article','headline':'Пример','author':{'@type':'Organization','name':'Компания'}},ensure_ascii=False)
        source='<head><title>Пример</title><script type="application/ld+json">'+data+'</script></head><body><div class="content-block_article-announce"><h1>Пример</h1></div><div id="ArticleItem"><p>Авторский текст.</p></div><article class="tile_articlePreview"><span class="byLineBlock-author">Антон Примеров</span></article></body>'
        before,_,_,calls=self.run_build(source,V8,'kontur.ru');self.assertEqual((len(before),calls),(1,1))
        for policy in [V9,V10,V11]:
            after,summary,groups,calls=self.run_build(source,policy,'kontur.ru')
            self.assertEqual((after,groups,calls),([],[],0));self.assertEqual(summary['kontur_unbound_preview_credit'],1)
        source=source.replace('<h1>Пример</h1>','<h1>Пример</h1><span class="article-announce-autor-block__name">Антон Примеров</span>')
        for policy in [V9,V10,V11]:
            after,summary,_,calls=self.run_build(source,policy,'kontur.ru')
            self.assertEqual((len(after),calls),(1,1));self.assertNotIn('kontur_unbound_preview_credit',summary)

    def test_v9_joint_credit_sets_each_quota_member_without_changing_cleaned_bytes(self):
        source='<body><div class="content-block_article-announce"><h1>Пример</h1><span class="article-announce-autor-block__name">Ирина Проверова</span></div><div id="ArticleItem"><p><em>Ирина Проверова и Михаил Тестов, эксперты системы интернет-отчетности Контур.Экстерн</em></p></div></body>'
        before,_,_,_=self.run_build(source,V8,'kontur.ru')
        for policy in [V9,V10,V11]:
            after,summary,_,calls=self.run_build(source,policy,'kontur.ru')
            self.assertEqual((len(after),calls),(1,1))
            self.assertEqual(after[0]['authors'],['ирина проверова','михаил тестов'])
            self.assertEqual(after[0]['author'],'ирина проверова; михаил тестов')
            self.assertEqual(summary['kontur_coauthors:explicit-coauthors'],1)
            self.assertEqual(after[0]['author_method'],policy+':explicit-coauthors')
            for key in ['sha256','raw_sha256']:self.assertEqual(before[0][key],after[0][key])

    def test_v9_preserves_rsdn_habr_gates_and_existing_profile_constraints(self):
        variants=[('rsdn.org','<body><h5><span class="title">Перевод:</span><span class="value">Переводчик</span></h5></body>','primary_header_translation'),
                  ('habr.com','<body><article class="post post_full"><div class="post__wrapper"><h1>Пример</h1><div id="post-content-body"><p>Предлагаю перевод интересной статьи о формате.</p></div></div></article></body>','habr_source:explicit-translation')]
        for host,source,counter in variants:
            for policy in [V9,V10,V11]:
                with self.subTest(host=host,policy=policy):
                    after,summary,groups,calls=self.run_build(source,policy,host)
                    self.assertEqual((after,groups,calls),([],[],0));self.assertEqual(summary[counter],1)
        source='<body><h5><span class="title">Автор:</span><span class="value"><a href="/account/info/1">Первый Автор</a></span></h5><p>Текст.</p></body>'
        before,_,_,_=self.run_build(source,V8)
        for policy in [V9,V10,V11]:
            after,_,_,_=self.run_build(source,policy)
            for field in ['author','authors','author_quota_keys','sha256','raw_sha256']:self.assertEqual(before[0][field],after[0][field])

    def liveinternet(self,main,comments=''):
        return ('<body><div class="CONBL" id="post42"><h1 class="ZAG">Пример</h1>'
                '<span class="GL_MAR5B"><a href="/journal_post.php?fjid=1&amp;fpid=42&amp;action=q_add">Цитировать</a></span>'
                '<div class="MESS">'+main+'</div></div>'+comments+'</body>')

    def whole_quote(self,identity='2',account='other'):
        return ('<div class="MESS QUOT_T"><div class="QUOT_B"><b>Цитата сообщения '
                '<a href="/users/'+account+'/profile">Автор</a></b><a href="/users/'+account+'/post41/">Прочитать целиком</a>'
                '<a href="/journal_post.php?fjid='+identity+'&amp;fpid=41&amp;action=q_add">Цитировать</a>'
                '<p>Это синтетический текст для проверки сборщика.</p></div></div>')

    def run_liveinternet(self,main,comments='',policy=V10):
        return self.run_build(self.liveinternet(main,comments),policy,'liveinternet.ru',url='https://www.liveinternet.ru/users/example/post42/')

    def test_paused_sources_do_not_reach_index_network_or_extraction(self):
        for host in ['telegra.ph','teletype.in']:
            with self.subTest(host=host), patch.object(build,'candidates',side_effect=AssertionError('index requested')), \
                 patch.object(build,'response_body',side_effect=AssertionError('WARC requested')):
                selected,summary,groups,calls=self.run_build('<body>Пример.</body>',V11,host,paused_domains=[host])
                self.assertEqual((selected,groups,calls),([],[],0))
                self.assertEqual(summary['paused_domain:'+host],1)
                self.assertEqual(summary.get('warc_attempts',0),0)
        before,_,groups_before,_=self.run_build('<body>Пример.</body>',V10)
        after,_,groups_after,_=self.run_build('<body>Пример.</body>',V11,paused_domains=[])
        self.assertEqual(groups_before,groups_after)
        self.assertEqual(before[0]['sha256'],after[0]['sha256'])

    def test_invalid_pause_fails_before_network(self):
        for value in ['rsdn.org',[True],['unknown.org'],['rsdn.org','rsdn.org'],[{}]]:
            with self.subTest(value=value), patch.object(build,'HTTP',side_effect=AssertionError('network initialized')):
                with self.assertRaises(ValueError):
                    self.run_build('<body>Пример.</body>',V11,paused_domains=value)

    def test_v11_series_navigation_does_not_hide_whole_reprint(self):
        footer=('<blockquote><b>Серия сообщений "<a href="/users/example/rubric/7/">Серия</a>":</b><br>'
                'Часть 1 - <a href="/users/example/post40/">Другой пост</a><br>'
                'Часть 2 - Пример<br></blockquote>')
        main=self.whole_quote()+footer
        old,_,_,calls=self.run_liveinternet(main,policy=V10)
        self.assertEqual((len(old),calls),(1,1))
        selected,summary,groups,calls=self.run_liveinternet(main,policy=V11)
        self.assertEqual((selected,groups,calls),([],[],1))
        self.assertEqual(summary['liveinternet_source:explicit-reprint'],1)
        self.assertEqual(summary['liveinternet_source_role:whole-quoted-post-of-other-publisher-id; known-series-navigation-only'],1)
        for guarded in ['<p>Мои замечания.</p>'+main,self.whole_quote('1','example')+footer]:
            before,_,before_groups,_=self.run_liveinternet(guarded,policy=V10)
            after,_,after_groups,calls=self.run_liveinternet(guarded,policy=V11)
            self.assertEqual((len(after),calls),(1,1))
            self.assertEqual(before_groups,after_groups)
            self.assertEqual(before[0]['raw_sha256'],after[0]['raw_sha256'])

    def test_v10_whole_foreign_post_is_rejected_only_in_new_policy(self):
        for policy in [None,V5,V6,V7,V8,V9]:
            selected,summary,_,calls=self.run_liveinternet(self.whole_quote(),policy=policy)
            self.assertEqual((len(selected),calls),(1,1));self.assertNotIn('liveinternet_source:explicit-reprint',summary)
        selected,summary,groups,calls=self.run_liveinternet(self.whole_quote())
        self.assertEqual((selected,groups,calls),([],[],1));self.assertEqual(summary['liveinternet_source:explicit-reprint'],1)

    def test_v10_entire_old_extraction_in_comment_is_rejected_without_second_extractor(self):
        comment='<div class="COMR">Это синтетический текст для проверки сборщика.</div>'
        before,_,_,_=self.run_liveinternet('<p>Свой короткий пост.</p>',comment,policy=V9)
        selected,summary,groups,calls=self.run_liveinternet('<p>Свой короткий пост.</p>',comment)
        self.assertEqual(len(before),1);self.assertEqual((selected,groups,calls),([],[],1))
        self.assertEqual(summary['liveinternet_source:extracted-comment'],1)

    def test_v10_primary_copy_self_quote_and_unknown_boundary_are_not_blanket_excluded(self):
        text='Это синтетический текст для проверки сборщика.'
        cases=[('<p>'+text+'</p>','<div class="COMR">'+text+'</div>','no-explicit-source-marker'),
               (self.whole_quote('1','example'),'','self-quoted-post'),
               ('<p>Свои замечания.</p>'+self.whole_quote(),'','unresolved'),
               ('<div class="MESS">Неизвестная вложенность.</div>','<div class="COMR">'+text+'</div>','unresolved')]
        for main,comments,status in cases:
            with self.subTest(status=status):
                before,_,before_groups,_=self.run_liveinternet(main,comments,policy=V9)
                after,summary,groups,calls=self.run_liveinternet(main,comments)
                self.assertEqual((len(after),calls),(1,1));self.assertEqual(before_groups,groups)
                self.assertEqual(summary['liveinternet_source:'+status],1)
                for field in ['author','sha256','raw_sha256']:self.assertEqual(before[0][field],after[0][field])


if __name__=='__main__':
    unittest.main()
