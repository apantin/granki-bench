import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('commit_guard', Path(__file__).resolve().parents[1] / 'scripts/check_commit.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class NormGuardTest(unittest.TestCase):
    def test_only_named_provenance_policy_is_allowed(self):
        import json
        def check(policy):return guard.norm_problems('norms/article-blog/config.json',json.dumps(dict(provenance_policy=policy)).encode())
        self.assertEqual(check('rsdn-primary-header-v1'),[])
        for policy in (None,True,'private-file','unknown'):
            self.assertTrue(check(policy))

    def test_domain_limits_do_not_publish_personal_profiles(self):
        import json
        def check(value):return guard.norm_problems('norms/article-blog/config.json',json.dumps({'candidate_limits':value}).encode())
        self.assertEqual(check({'example.org':600}),[])
        for value in [{'writer.livejournal.com':600},{'example.org/@writer':600},{'example.org':True},{'example.org':0}]:
            self.assertTrue(check(value))

    def test_norm_aggregates_only(self):
        self.assertEqual(guard.norm_problems('norms/article-blog/groups.csv',
            b'domain,snapshot,subgenre,documents,sha256\nexample.org,CC-MAIN-2021-04,column,10,' + b'a'*64 + b'\n'), [])
        for path, data in [('norms/article-blog/texts.csv', b'text'),
                           ('norms/article-blog/config.json', b'{"salt":"private"}'),
                           ('norms/article-blog/domains.csv', b'domain,source_url\n')]:
            self.assertTrue(guard.norm_problems(path, data))

    def test_results_still_checked(self):
        self.assertTrue(guard.is_result('result.json', b'{"kind":"pairwise"}'))
        self.assertFalse(guard.is_result('result.json', b'{"text":"x"}'))


if __name__ == '__main__':
    unittest.main()
