from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bench.candidates import keyboard_chords
from bench.candidates.publication_policy import POLICY
import test_cc_clean_version as legacy
from test_publication_body import xakep


class PublicationPolicyBuildTests(unittest.TestCase):
    def test_primary_advertorial_excluded_before_cleaning_and_quota(self):
        source = xakep('<p>Рекламный материал.</p>').replace('class="hentry ', 'class="hentry category-advert ', 1)
        with patch.object(keyboard_chords, 'extract', side_effect=AssertionError('advertorial cleaned')):
            docs, summary, _, _, _ = legacy.CleanVersionBuildTest().run_build(
                keyboard_chords.VERSION, source=source, config_extra={'publication_policy':POLICY})
        self.assertEqual(docs, [])
        self.assertEqual(summary['publication_role:explicit-advertorial'], 1)
        self.assertEqual(summary['publication_policy'], POLICY)
        self.assertFalse(summary['target_met'])

    def test_optional_policy_keeps_legacy_and_saves_nonadmission_diagnostics(self):
        source = xakep('<p>Сравнение свойств устройств и собственные выводы.</p>')
        docs, summary, _, _, _ = legacy.CleanVersionBuildTest().run_build(keyboard_chords.VERSION, source=source)
        self.assertNotIn('publication_review', docs[0])
        self.assertNotIn('publication_policy', summary)
        docs, _, _, _, _ = legacy.CleanVersionBuildTest().run_build(
            keyboard_chords.VERSION, source=source, config_extra={'publication_policy':POLICY})
        self.assertEqual(docs[0]['publication_review']['status'], 'no-explicit-marker')
        self.assertFalse(docs[0]['publication_review']['admitted'])

    def test_invalid_policy_fails_before_network_or_outputs(self):
        for policy in [None, True, 'future', [], {}]:
            with self.subTest(policy=policy), tempfile.TemporaryDirectory() as folder, \
                    patch.object(legacy.build, 'HTTP', side_effect=AssertionError('network initialized')):
                with self.assertRaisesRegex(ValueError, 'политика роли публикации'):
                    legacy.build.build(dict(clean_version=keyboard_chords.VERSION,publication_policy=policy), [], Path(folder))
                self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
