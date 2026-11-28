"""Явный выбор очистки в реальной сборке и сохранение старого формата."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bench.candidates import technical_markup, editorial_roles, keyboard_chords
from bench.cleaning import html_article, VERSION
from test_cc_build_provenance import build, V11
from test_publication_body import xakep
from test_technical_markup import listing


class CleanVersionBuildTest(unittest.TestCase):
    def run_build(self, version, *, host='xakep.ru', source=None, paused=False, config_extra=None):
        payload = source or xakep('<p>Проверяем вероятность 0,2<sup>3</sup> и сохраняем '
                                 'собственное объяснение результата.</p>' + listing() +
                                 '<p>Здесь заканчивается полный синтетический пример автора.</p>')
        if isinstance(payload, str):
            payload = payload.encode()
        config = dict(clean_version=version, dependencies={}, max_records=5, candidate_limit=5,
                      seed='test', max_blocks=1, min_words=1, max_words=100, min_cyrillic=.3,
                      dedup_threshold=.85, target=1, subgenres=['technical'], domain_cap=1,
                      author_cap=5, provenance_policy=V11, paused_domains=[host] if paused else [])
        config.update(config_extra or {})
        domain = dict(domain=host, snapshots='snapshot', url_pattern='.*', subgenre='technical')
        record = dict(url='https://' + host + '/article/example', filename='example.warc.gz',
                      offset='0', length='1')
        http = SimpleNamespace(bytes=0, requests=0, get=lambda *args: b'compressed')
        with tempfile.TemporaryDirectory() as temporary, patch.object(build, 'HTTP', return_value=http), \
             patch.object(build, 'candidates', return_value=[record]), \
             patch.object(build, 'response_body', return_value=payload), \
             contextlib.redirect_stdout(io.StringIO()):
            folder = Path(temporary)
            build.build(config, [domain], folder)
            selected = json.loads((folder / 'cc-rebuild/selected.json').read_text())
            summary = json.loads((folder / 'cc-rebuild/summary.json').read_text())
            raw = [Path(d['raw_path']).read_text() for d in selected]
            norm = [Path(d['path']).read_text() for d in selected]
            return selected, summary, raw, norm, payload

    def test_legacy_recipe_keeps_bytes_and_document_format(self):
        selected, summary, raw, norm, payload = self.run_build(VERSION)
        expected, _ = html_article(payload, 'https://xakep.ru/article/example')
        self.assertEqual(raw, [expected.raw])
        self.assertEqual(norm, [expected.norm])
        self.assertEqual(selected[0]['raw_sha256'], hashlib.sha256(expected.raw.encode()).hexdigest())
        self.assertNotIn('clean_version', selected[0])
        self.assertNotIn('extraction_metadata', selected[0])
        self.assertNotIn('clean_version', summary)

    def test_v20_real_build_preserves_formula_masks_listing_and_records_diagnostics(self):
        with patch.object(build, 'html_article', side_effect=AssertionError('legacy dispatcher used')):
            selected, summary, raw, _, _ = self.run_build(technical_markup.VERSION)
        self.assertEqual(len(selected), 1)
        self.assertIn('0,2^(3)', raw[0])
        self.assertEqual(raw[0].count('[КОД]'), 1)
        self.assertNotIn('echo one', raw[0])
        self.assertEqual(selected[0]['clean_version'], technical_markup.VERSION)
        metadata = selected[0]['extraction_metadata']
        self.assertEqual(metadata['clean_version'], technical_markup.VERSION)
        self.assertEqual(metadata['preserved_superscripts'], 1)
        self.assertEqual(metadata['masked_highlighted_code'], 1)
        self.assertEqual(summary['clean_version'], technical_markup.VERSION)

    def test_unknown_version_fails_before_network_or_outputs(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(build, 'HTTP', side_effect=AssertionError('network initialized')):
            folder = Path(temporary)
            with self.assertRaisesRegex(ValueError, 'Неизвестная версия'):
                build.build({'clean_version': 'unknown'}, [], folder)
            self.assertEqual(list(folder.iterdir()), [])

    def test_v21_real_build_removes_related_widget_and_keeps_author_paragraphs(self):
        source = ('<html><body><h1>Основная статья</h1><section itemprop="articleBody">'
                  '<p>Своя вводка.</p><div class="readblogmore">'
                  '<a href="/blog/other.html">Другая статья</a></div><p>Свой вывод.</p>'
                  '</section></body></html>')
        selected, summary, raw, _, _ = self.run_build(editorial_roles.VERSION, host='texterra.ru', source=source)
        self.assertEqual(len(selected), 1)
        self.assertNotIn('Другая статья', raw[0])
        self.assertIn('Своя вводка.', raw[0])
        self.assertIn('Свой вывод.', raw[0])
        self.assertEqual(selected[0]['extraction_metadata']['removed_related_widgets'], 1)
        self.assertEqual(selected[0]['clean_version'], editorial_roles.VERSION)
        self.assertEqual(summary['clean_version'], editorial_roles.VERSION)

    def test_v20_keeps_translation_gate_before_cleaner(self):
        source = '<body><h5><span class="title">Перевод:</span><span class="value">Автор</span></h5></body>'
        for module in [technical_markup, editorial_roles]:
            with self.subTest(version=module.VERSION), patch.object(module, 'extract', side_effect=AssertionError('translation cleaned')):
                selected, summary, _, _, _ = self.run_build(module.VERSION, host='rsdn.org', source=source)
            self.assertEqual(selected, [])
            self.assertEqual(summary['primary_header_translation'], 1)
            self.assertEqual(summary['clean_version'], module.VERSION)

    def test_v22_real_build_recovers_original_keyboard_symbols(self):
        source = xakep('<p>Для переключения нажмите <Alt + Tab>, для закрытия <Alt + F4>.</p>')
        selected, summary, raw, _, _ = self.run_build(keyboard_chords.VERSION, source=source)
        self.assertEqual(len(selected), 1)
        self.assertIn('<Alt + Tab>', raw[0])
        self.assertIn('<Alt + F4>', raw[0])
        self.assertEqual(selected[0]['extraction_metadata']['recovered_keyboard_chord_markup'], 2)
        self.assertEqual(summary['clean_version'], keyboard_chords.VERSION)

    def test_v20_paused_source_never_reaches_cleaner(self):
        for module in [technical_markup, editorial_roles]:
            with self.subTest(version=module.VERSION), patch.object(module, 'extract', side_effect=AssertionError('paused source cleaned')):
                selected, summary, _, _, _ = self.run_build(module.VERSION, paused=True)
            self.assertEqual(selected, [])
            self.assertEqual(summary.get('warc_attempts', 0), 0)
            self.assertEqual(summary['paused_domain:xakep.ru'], 1)


if __name__ == '__main__':
    unittest.main()
