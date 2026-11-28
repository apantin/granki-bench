from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bench.candidates import keyboard_chords
from bench.primary_text_type import POLICY
import test_cc_clean_version as legacy
from test_publication_body import xakep


class PrimaryTextBuildTest(unittest.TestCase):
    def test_translation_is_excluded_before_cleaning_and_quota(self):
        source = xakep('<p>Переведённый материал.</p><p><i>Перевод и адаптация материала Тестового автора <a href="https://source.example/original">Original title</a>.</i></p>')
        with patch.object(keyboard_chords, 'extract', side_effect=AssertionError('translation cleaned')):
            docs, summary, _, _, _ = legacy.CleanVersionBuildTest().run_build(
                keyboard_chords.VERSION, source=source, config_extra={'primary_text_policy': POLICY})
        self.assertEqual(docs, [])
        self.assertEqual(summary['primary_text_type:explicit-translation-credit'], 1)
        self.assertEqual(summary['primary_text_policy'], POLICY)

    def test_legacy_recipe_has_no_new_fields_and_optin_does_not_change_raw_norm(self):
        source = xakep('<p>Самостоятельное техническое объяснение с выводом.</p>')
        old, old_summary, _, _, _ = legacy.CleanVersionBuildTest().run_build(keyboard_chords.VERSION, source=source)
        new, _, _, _, _ = legacy.CleanVersionBuildTest().run_build(
            keyboard_chords.VERSION, source=source, config_extra={'primary_text_policy': POLICY})
        self.assertNotIn('primary_text_review', old[0])
        self.assertNotIn('primary_text_policy', old_summary)
        for key in ['sha256', 'raw_sha256', 'warc_sha256']:
            self.assertEqual(old[0][key], new[0][key])
        self.assertFalse(new[0]['primary_text_review']['admitted'])

    def test_unknown_policy_fails_before_network_or_output(self):
        for policy in [None, True, 'future', [], {}]:
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as folder, \
                    patch.object(legacy.build, 'HTTP', side_effect=AssertionError('network initialized')):
                with self.assertRaisesRegex(ValueError, 'политика типа первичного текста'):
                    legacy.build.build(dict(clean_version=keyboard_chords.VERSION, primary_text_policy=policy), [], Path(folder))
                self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
