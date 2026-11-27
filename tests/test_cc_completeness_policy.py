"""Явный обрыв исключается до отбора, слово/похожий ID сами по себе — нет."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bench.cleaning import VERSION as LEGACY
from bench.candidates.technical_markup import VERSION
import test_cc_clean_version as legacy
from test_publication_body import xakep

POLICY = 'explicit-source-cut-v1'


class CompletenessPolicyTest(unittest.TestCase):
    def run_case(self, source, *, policy=True, host='xakep.ru'):
        return legacy.CleanVersionBuildTest().run_build(VERSION, source=source, host=host,
                   config_extra={'completeness_policy': POLICY} if policy else {})

    def test_actual_cut_is_retained_in_legacy_but_excluded_by_policy(self):
        source = xakep('<p>Доступное начало авторской публикации.</p>'
                       '<div id="xakepcut" class="xakepcut">Продолжение закрыто</div>')
        selected, summary, _, _, _ = self.run_case(source, policy=False)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['extraction_metadata']['source_incomplete_markers'], ['xakep-access-cut'])
        self.assertNotIn('completeness_policy', summary)
        selected, summary, _, _, _ = self.run_case(source)
        self.assertEqual(selected, [])
        self.assertEqual(summary['incomplete_source'], 1)
        self.assertEqual(summary['incomplete_source:xakep-access-cut'], 1)
        self.assertEqual(summary['completeness_policy'], POLICY)

    def test_text_and_similar_identifiers_do_not_establish_a_cut(self):
        for body in ['<p>Обсуждаем идентификатор xakepcut в собственном примере.</p>',
                     '<p id="xakepcut">Авторский текст без класса обрыва.</p>',
                     '<p class="xakepcut">Авторский текст без идентификатора.</p>']:
            selected, summary, _, _, _ = self.run_case(xakep(body))
            self.assertEqual(len(selected), 1)
            self.assertEqual(summary.get('incomplete_source', 0), 0)

    def test_marker_outside_article_is_not_a_cut(self):
        source = xakep('<p>Полная доступная авторская публикация.</p>')
        source = source.replace('</body>', '<aside id="xakepcut" class="xakepcut">Сервис</aside></body>')
        selected, _, _, _, _ = self.run_case(source)
        self.assertEqual(len(selected), 1)

    def test_invalid_policy_or_cleaner_refused_before_network(self):
        for version, policy in [(VERSION, None), (VERSION, True), (VERSION, 'future'), (LEGACY, POLICY)]:
            with tempfile.TemporaryDirectory() as folder, \
                 patch.object(legacy.build, 'HTTP', side_effect=AssertionError('network initialized')):
                with self.assertRaisesRegex(ValueError, 'политика полноты'):
                    legacy.build.build({'clean_version': version, 'completeness_policy': policy}, [], Path(folder))
                self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
