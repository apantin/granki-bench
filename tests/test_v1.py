"""Протокол v1 и импорт пилота: без вызовов моделей.

    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bench import markers_v1, models, run, scoring  # noqa: E402
from bench.anchors import AnchorSet  # noqa: E402
from bench.protocol import Protocol  # noqa: E402

PILOT = ROOT / 'anchors' / 'pilot-2026-11'
RESULTS = sorted((ROOT / 'results' / 'v1-pilot-2026-11').glob('*.json'))


class ProtocolTests(unittest.TestCase):
    def test_frozen_prompts_unchanged(self):
        p = Protocol('v1')
        for kind in ('pairwise', 'absolute'):
            _, digest = p.prompt(kind)
            self.assertEqual(digest, p.spec[kind]['prompt_sha256'])

    def test_prompt_fields_format(self):
        p = Protocol('v1')
        template, _ = p.prompt('pairwise')
        text = template.format(reader='R', posts='P', t1='T1', t2='T2')
        self.assertIn('<text1>\nT1\n</text1>', text)
        self.assertIn('{"human": "1|2|="', text)


class ScoringTests(unittest.TestCase):
    def test_winner_follows_order(self):
        self.assertEqual(scoring.winner('1', 'ab'), 'A')
        self.assertEqual(scoring.winner('1', 'ba'), 'B')
        self.assertEqual(scoring.winner('2', 'ba'), 'A')
        self.assertEqual(scoring.winner('?', 'ab'), '=')

    def test_pair_score_and_spread(self):
        votes = [{'judge': 'x', 'votes': {'overall': 'A'}}, {'judge': 'x', 'votes': {'overall': 'A'}},
                 {'judge': 'y', 'votes': {'overall': 'B'}}, {'judge': 'y', 'votes': {'overall': 'B'}}]
        self.assertEqual(scoring.pair_score(votes, ['overall']), {'overall': 0.0})
        spread = scoring.pair_spread(votes, ['overall'])['overall']
        self.assertEqual(spread['per_model'], {'x': 1.0, 'y': -1.0})
        self.assertEqual(spread['stdev'], 1.0)

    def test_parse_last_json(self):
        self.assertEqual(models.parse_last_json('Вот ответ: {"a": {"b": 2}} — всё'), {'a': {'b': 2}})
        self.assertIsNone(models.parse_last_json('шум {"a": 1} и {"b": 2}'))  # поведение v1
        self.assertIsNone(models.parse_last_json('без json'))


class PilotImportTests(unittest.TestCase):
    def test_every_pilot_result_recomputes(self):
        self.assertEqual(len(RESULTS), 39)
        for f in RESULTS:
            result = json.loads(f.read_text(encoding='utf-8'))
            self.assertEqual(run.recompute(result, Protocol(result['protocol'])), {}, f.name)

    def test_anchor_hashes(self):
        self.assertEqual(AnchorSet(PILOT).verify(), [])

    def test_results_point_to_anchors(self):
        for f in RESULTS:
            result = json.loads(f.read_text(encoding='utf-8'))
            for key in ('a', 'b', 'article'):
                ref = result['inputs'].get(key)
                if ref and ref.get('path'):
                    path = ROOT / ref['path']
                    self.assertTrue(path.is_file(), f'{f.name}: {ref["path"]}')

    def test_pairs_resolve(self):
        anchors = AnchorSet(PILOT)
        self.assertEqual(len(anchors.pairs), 31)
        e = anchors.pair('E5-vs-E4')
        self.assertTrue(anchors.path(e['a']).is_file() and anchors.path(e['posts']).is_file())
        self.assertIn('шипы', e['reader'])


class MarkersTests(unittest.TestCase):
    def test_markers_v1_stable(self):
        text = (PILOT / 'texts' / 'E5-02.md').read_text(encoding='utf-8')
        ref = (PILOT / 'posts' / 'bike.md').read_text(encoding='utf-8')
        r = markers_v1.count(text, ref)
        self.assertEqual((r['words'], r['markers'], r['per_1000'], r['copied_4grams']), (749, 7, 9.3, 0))


if __name__ == '__main__':
    unittest.main()
