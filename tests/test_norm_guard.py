import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('commit_guard', Path(__file__).resolve().parents[1] / 'scripts/check_commit.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class NormGuardTest(unittest.TestCase):
    def test_language_policy_requires_named_policy_and_pinned_model(self):
        import json
        def check(value):
            return guard.norm_problems('norms/article-blog/config.json', json.dumps(value).encode())
        valid = dict(language_policy='py3langid-0.4.0-russian-v1', dependencies={'py3langid': '0.4.0'})
        self.assertEqual(check(valid), [])
        for value in [valid | {'language_policy': None}, valid | {'language_policy': 'future'},
                      valid | {'dependencies': {}}, valid | {'dependencies': {'py3langid': 'future'}}]:
            self.assertTrue(check(value))

    def test_completeness_policy_requires_supported_cleaner(self):
        import json
        def check(value):
            return guard.norm_problems('norms/article-blog/config.json', json.dumps(value).encode())
        valid = dict(completeness_policy='explicit-source-cut-v1', clean_version='clean-v20-technical-markup-candidate')
        self.assertEqual(check(valid), [])
        self.assertEqual(check(valid | {'clean_version': 'clean-v21-editorial-roles-candidate'}), [])
        self.assertEqual(check(valid | {'clean_version': 'clean-v22-keyboard-chords-candidate'}), [])
        self.assertEqual(check(valid | {'clean_version': 'clean-v23-blogspot-uniform-candidate'}), [])
        for value in [valid | {'completeness_policy': None}, valid | {'completeness_policy': 'future'},
                      valid | {'clean_version': []}, valid | {'clean_version': {}},
                      valid | {'clean_version': 'clean-v3'}, {'completeness_policy': 'explicit-source-cut-v1'}]:
            self.assertTrue(check(value))

    def test_publication_policy_requires_explicit_supported_value(self):
        import json
        def check(value):
            return guard.norm_problems('norms/article-blog/config.json', json.dumps({'publication_policy':value}).encode())
        self.assertEqual(check('primary-advertorial-v1'), [])
        for value in [None, True, 'future', [], {}]:
            self.assertTrue(check(value))

    def test_legacy_profile_query_is_not_a_local_home(self):
        self.assertIsNone(guard.PRIVATE.search('/Users/Profile.aspx?uid=1'))
        for suffix in ['Example/project','Example','Profile.aspx/project','Profile.aspx']:
            with self.subTest(suffix=suffix):self.assertIsNotNone(guard.PRIVATE.search('/Users/'+suffix))
        self.assertIsNotNone(guard.PRIVATE.search('/home/'+'example/project'))
        self.assertIsNotNone(guard.PRIVATE.search('/Users/Profile.aspx?uid=1/Users/'+'Example'))

    def test_primary_text_policy_cannot_contain_an_arbitrary_mask_or_private_path(self):
        import json
        def check(value):
            return guard.norm_problems('norms/article-blog/config.json', json.dumps({'primary_text_policy':value}).encode())
        self.assertEqual(check('explicit-primary-text-v1'), [])
        for value in [None, True, 'future', [], {}, {'exclude': ['one-document']}]:
            self.assertTrue(check(value))

    def test_only_named_provenance_policy_is_allowed(self):
        import json
        def check(policy):return guard.norm_problems('norms/article-blog/config.json',json.dumps(dict(provenance_policy=policy)).encode())
        self.assertEqual(check('rsdn-primary-header-v1'),[])
        self.assertEqual(check('rsdn-primary-header-profile-v2'),[])
        self.assertEqual(check('rsdn-primary-header-profile-translation-v3'),[])
        self.assertEqual(check('primary-source-rsdn-habr-kontur-v6'),[])
        self.assertEqual(check('primary-header-rsdn-habr-v4'),[])
        self.assertEqual(check('primary-source-rsdn-habr-v5'),[])
        self.assertEqual(check('primary-source-rsdn-habr-kontur-liveinternet-v7'),[])
        self.assertEqual(check('primary-source-series-v8'),[])
        self.assertEqual(check('primary-source-livejournal-v9'),[])
        for policy in (None,True,'private-file','unknown'):
            self.assertTrue(check(policy))

    def test_domain_limits_do_not_publish_personal_profiles(self):
        import json
        for field in ['candidate_limits','index_blocks']:
            def check(value):return guard.norm_problems('norms/article-blog/config.json',json.dumps({field:value}).encode())
            self.assertEqual(check({'example.org':600}),[])
            for value in [{'writer.livejournal.com':600},{'writer.wordpress.com':600},{'example.org/@writer':600},{'example.org':True},{'example.org':0}]:
                self.assertTrue(check(value))

    def test_norm_aggregates_only(self):
        self.assertEqual(guard.norm_problems('norms/article-blog/groups.csv',
            b'domain,snapshot,subgenre,documents,sha256\nexample.org,CC-MAIN-2021-04,column,10,' + b'a'*64 + b'\n'), [])
        for path, data in [('norms/article-blog/texts.csv', b'text'),
                           ('norms/article-blog/config.json', b'{"salt":"private"}'),
                           ('norms/article-blog/domains.csv', b'domain,source_url\n')]:
            self.assertTrue(guard.norm_problems(path, data))

    def test_pause_allows_only_unique_platform_domains(self):
        import json
        def check(value):return guard.norm_problems('norms/article-blog/config.json',json.dumps({'paused_domains':value}).encode())
        for value in [[],['telegra.ph','teletype.in']]:
            self.assertEqual(check(value),[])
        for value in [None,True,{},'telegra.ph',[True],[{}],['telegra.ph','telegra.ph'],
                      ['writer.livejournal.com'],['teletype.in/@writer'],['https://telegra.ph'],['.example.org']]:
            with self.subTest(value=value):self.assertTrue(check(value))

    def test_results_still_checked(self):
        self.assertTrue(guard.is_result('result.json', b'{"kind":"pairwise"}'))
        self.assertFalse(guard.is_result('result.json', b'{"text":"x"}'))


if __name__ == '__main__':
    unittest.main()
