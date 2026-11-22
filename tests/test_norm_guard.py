import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('commit_guard', Path(__file__).resolve().parents[1] / 'scripts/check_commit.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class NormGuardTest(unittest.TestCase):
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
