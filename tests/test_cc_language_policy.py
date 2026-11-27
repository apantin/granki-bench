"""Языковая политика действует до квот, старый рецепт её не включает."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bench.candidates.technical_markup import VERSION
from bench.candidates.language_review import POLICY
import test_cc_clean_version as legacy

build = legacy.build


class LanguagePolicyBuildTest(unittest.TestCase):
    def test_legacy_does_not_load_classifier_or_change_format(self):
        with patch('bench.candidates.language_review.load_review', side_effect=AssertionError('legacy loaded model')):
            selected, summary, _, _, _ = legacy.CleanVersionBuildTest().run_build(VERSION)
        self.assertEqual(len(selected), 1)
        self.assertNotIn('language_review', selected[0])
        self.assertNotIn('language_review', summary)

    def test_policy_holds_non_russian_before_quota_and_records_russian(self):
        for lang, held in [('uk', True), ('ru', False)]:
            result = dict(policy=POLICY, language=lang, runner_up='bg', score_gap=10.,
                          review_required=held, admitted=False)
            check = Mock(return_value=result)
            checker = SimpleNamespace(check=check, fingerprint={'policy': POLICY})
            with patch('bench.candidates.language_review.load_review', return_value=checker):
                selected, summary, _, _, _ = legacy.CleanVersionBuildTest().run_build(
                    VERSION, config_extra={'language_policy': POLICY})
            self.assertEqual(len(selected), 0 if held else 1)
            self.assertEqual(summary['language:'+lang], 1)
            self.assertEqual(summary.get('language_review_required', 0), int(held))
            self.assertEqual(summary['language_review'], checker.fingerprint)
            check.assert_called_once()
            self.assertIn('Проверяем вероятность', check.call_args.args[0])
            if selected:
                self.assertEqual(selected[0]['language_review'], result)

    def test_invalid_policy_fails_before_network_and_files(self):
        for policy in ['', None, 'unknown']:
            with tempfile.TemporaryDirectory() as folder, \
                 patch.object(build, 'HTTP', side_effect=AssertionError('network initialized')):
                with self.assertRaisesRegex(ValueError, 'политика языка'):
                    build.build({'clean_version': VERSION, 'language_policy': policy}, [], Path(folder))
                self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
