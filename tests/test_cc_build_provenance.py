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


class BuildProvenanceTest(unittest.TestCase):
    def run_build(self, source, policy):
        source = ('<html>'+source+'</html>').encode()
        config = dict(clean_version=VERSION, dependencies={}, max_records=5, candidate_limit=5,
                      seed='test', max_blocks=1, min_words=1, max_words=100, min_cyrillic=.5,
                      dedup_threshold=.85, target=1, subgenres=['technical'], domain_cap=1, author_cap=5)
        if policy is not None:
            config['provenance_policy'] = policy
        domain = dict(domain='rsdn.org', snapshots='snapshot', url_pattern='.*', subgenre='technical')
        record = dict(url='https://rsdn.org/article/example', filename='example.warc.gz', offset='0', length='1')
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


if __name__=='__main__':
    unittest.main()
