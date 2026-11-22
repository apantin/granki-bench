"""Командная строка granki-bench.

    python -m bench pair A.md B.md --posts posts.md --reader "…" --out result.json
    python -m bench pair --anchors anchors/pilot-2026-11 --pair E5-vs-E4 --out result.json
    python -m bench score ARTICLE.md --posts posts.md --claims data.csv --reader "…" --out result.json
    python -m bench markers FILE.md [FILE.md …] [--ref posts.md] [--json]
    python -m bench recompute RESULT.json […]
    python -m bench verify ANCHORS_DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import markers_v1, run
from .anchors import AnchorSet
from .protocol import Protocol


def write(result: dict, out: str | None) -> None:
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text + '\n', encoding='utf-8')
    summary = {k: result[k] for k in ('protocol', 'a_minus_b', 'mean') if k in result}
    print(json.dumps(summary, ensure_ascii=False))


def judges_arg(value: str | None) -> list[str] | None:
    return value.split(',') if value else None


def cmd_pair(x) -> int:
    protocol = Protocol(x.protocol)
    if x.pair:
        anchors = AnchorSet(Path(x.anchors))
        e = anchors.pair(x.pair)
        a, b, posts, reader = anchors.path(e['a']), anchors.path(e['b']), anchors.path(e['posts']), e['reader']
    else:
        if not (x.a and x.b and x.posts and x.reader):
            raise SystemExit('Нужны A, B, --posts и --reader, или --anchors и --pair')
        a, b, posts, reader = Path(x.a), Path(x.b), Path(x.posts), x.reader
    write(run.pairwise(protocol, a, b, posts, reader, judges_arg(x.judges)), x.out)
    return 0


def cmd_score(x) -> int:
    protocol = Protocol(x.protocol)
    write(run.absolute(protocol, Path(x.article), Path(x.posts), Path(x.claims), x.reader, judges_arg(x.judges)), x.out)
    return 0


def cmd_markers(x) -> int:
    ref = Path(x.ref).read_text(encoding='utf-8') if x.ref else None
    out = {f: markers_v1.count(Path(f).read_text(encoding='utf-8'), ref) for f in x.files}
    if x.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        for f, r in out.items():
            print(f'{r["per_1000"]:5} на 1000 слов · {r["markers"]:3} · слов {r["words"]:5} · CV длины предл. {r["sentence_len_cv"]} · копий 4-грамм {r["copied_4grams"]} · {f}')
    return 0


def cmd_recompute(x) -> int:
    bad = 0
    for f in x.results:
        result = json.loads(Path(f).read_text(encoding='utf-8'))
        diff = run.recompute(result, Protocol(result['protocol']))
        print(('ok   ' if not diff else 'DIFF ') + f + ('' if not diff else f'  {diff}'))
        bad += bool(diff)
    return 1 if bad else 0


def cmd_verify(x) -> int:
    problems = AnchorSet(Path(x.anchors)).verify()
    for p in problems:
        print(p)
    print('ok' if not problems else f'проблем: {len(problems)}')
    return 1 if problems else 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog='granki-bench', description='Оценка русского текста по зафиксированному протоколу')
    sub = p.add_subparsers(dest='cmd', required=True)

    s = sub.add_parser('pair', help='слепое парное сравнение двух текстов')
    s.add_argument('a', nargs='?'); s.add_argument('b', nargs='?')
    s.add_argument('--posts'); s.add_argument('--reader')
    s.add_argument('--anchors', help='набор эталонов'); s.add_argument('--pair', help='имя пары из pairs.json набора')
    s.add_argument('--protocol', default='v1'); s.add_argument('--judges', help='через запятую: opus,sonnet,haiku,codex')
    s.add_argument('--out')
    s.set_defaults(func=cmd_pair)

    s = sub.add_parser('score', help='абсолютная оценка текста')
    s.add_argument('article'); s.add_argument('--posts', required=True); s.add_argument('--claims', required=True)
    s.add_argument('--reader', required=True); s.add_argument('--protocol', default='v1'); s.add_argument('--judges')
    s.add_argument('--out')
    s.set_defaults(func=cmd_score)

    s = sub.add_parser('markers', help='счётчик следов нейротекста v1')
    s.add_argument('files', nargs='+'); s.add_argument('--ref'); s.add_argument('--json', action='store_true')
    s.set_defaults(func=cmd_markers)

    s = sub.add_parser('recompute', help='пересчитать итог по сохранённым голосам')
    s.add_argument('results', nargs='+')
    s.set_defaults(func=cmd_recompute)

    s = sub.add_parser('verify', help='проверить хеши набора эталонов')
    s.add_argument('anchors')
    s.set_defaults(func=cmd_verify)

    x = p.parse_args(argv)
    return x.func(x)


if __name__ == '__main__':
    sys.exit(main())
