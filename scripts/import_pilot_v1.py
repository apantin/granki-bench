#!/usr/bin/env python3
"""Импорт результатов пилота Granki как прогона протокола v1.

Однократный скрипт, хранится для прозрачности: по нему видно, как получены
anchors/pilot-2026-11 и results/v1-pilot-2026-11.

    python3 scripts/import_pilot_v1.py --lab <папка лаборатории пилота> \
        --trips <trips.csv> --builds <builds.csv> [--lab-git <git-репозиторий лаборатории>]

Тексты, которые видели судьи, копируются в набор эталонов с хешами; результаты
переписываются в формат bench: голоса и итог — как были, метаданные, которых
в пилоте не записывали (точные модели, версии CLI), — null.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from bench import scoring  # noqa: E402
from bench.protocol import Protocol, sha256_file, words  # noqa: E402

ANCHORS = ROOT / 'anchors' / 'pilot-2026-11'
RESULTS = ROOT / 'results' / 'v1-pilot-2026-11'

# Читатели — из скриптов оценки пилота (harness/eval_*.sh, judge_baseline.sh).
TOPICS = {
    'bike': {'posts': 'posts/bike.md', 'claims': 'data/trips.csv',
             'reader': 'городской велосипедист, который летом ездит на работу и думает, продолжать ли зимой и покупать ли шипы',
             'about': 'Серия «Зимой на велосипеде», статья 2 «Девять тысяч за шипы»'},
    'bike01': {'posts': 'posts/bike.md', 'claims': 'data/trips.csv',
               'reader': 'городской велосипедист, который летом ездит на работу и думает, продолжать ли ездить зимой',
               'about': 'Серия «Зимой на велосипеде», статья 1 «Зимой вообще можно?»'},
    'ci': {'posts': 'posts/ci.md', 'claims': 'data/builds.csv',
           'reader': 'инженеры соседних команд и техлиды, которые решают, внедрять ли кэш зависимостей в CI и чего от него ждать',
           'about': 'Статья «Кэш зависимостей в CI: что он нам дал»'},
    'solar': {'posts': 'posts/solar.md', 'claims': None,
              'reader': 'дачник, не инженер, который думает поставить солнечную станцию себе: ставить ли и какого размера',
              'about': 'Статья «Первое лето с солнечной станцией на даче» (контрольный пилот)'},
}

# Что за текст — по имени файла пилота.
VARIANTS = {
    'A-01-days.md': 'Статья 1 пилота A, исходный Granki',
    'A-01-days-catchphrase.md': 'То же с приклеенной фразой из постов автора (проверка перекоса судей)',
    'A-02-studs.md': 'Статья 2 пилота A, исходный Granki',
    'E2-02-final.md': 'E2: статья 2 заново, правки письма, после ревью',
    'E2-02-sections.md': 'E2: та же статья, разделы до ревью статьи',
    'E4-02.md': 'E4: все правки пилота, агент Opus',
    'E4-02-drafts.md': 'E4: черновики разделов до ревью',
    'E4-0102-draft.md': 'E4: разделы «Падения» и «Время», черновик',
    'E4-0102-final.md': 'E4: те же разделы после ревью',
    'E4s-02.md': 'E4-Sonnet: все правки пилота, агент Sonnet',
    'E5-02.md': 'E5: E4 + проход голоса (итоговая версия)',
    'E6-02-holistic.md': 'E6: статья целиком одним агентом, без ревью',
    'B-01-ci.md': 'Пилот B, версия 1, исходный Granki',
    'B-e3-v2.md': 'E3: версия 2 с разделом «Чего мы не знаем»',
    'b-s012.md': 'E1: разделы 00–02, исходный Granki, Opus',
    'b-opus2-s012.md': 'E1: разделы 00–02, правки пилота, Opus',
    'b-sonnet-s012.md': 'E1: разделы 00–02, правки пилота, Sonnet',
    'C-01-solar.md': 'Пилот C, контрольная тема',
    'bare-bike.md': 'База: голая модель (Opus) по брифу автора, статья 2',
    'bare-bike01.md': 'База: голая модель по брифу, статья 1',
    'statya-bike.md': 'База: скилл statya по брифу, статья 2',
    'bare-ci.md': 'База: голая модель, CI',
    'statya-ci.md': 'База: скилл statya, CI',
    'bare-solar.md': 'База: голая модель, солнечная станция',
    'statya-solar.md': 'База: скилл statya, солнечная станция',
}


def topic_of(name: str) -> str:
    if name.startswith(('A-01', 'bare-bike01')):
        return 'bike01'
    if name.startswith(('A-', 'E2', 'E4', 'E5', 'E6')) or 'bike' in name:
        return 'bike'
    if name.startswith(('B-', 'b-')) or name.endswith('-ci.md'):
        return 'ci'
    if name.startswith('C-') or 'solar' in name:
        return 'solar'
    raise SystemExit(f'Не знаю темы для {name}')


def created(lab_git: Path | None, rel: str) -> str | None:
    if not lab_git:
        return None
    ref = subprocess.run(['git', '-C', str(lab_git), 'for-each-ref', '--format=%(refname)', 'refs/heads'],
                         capture_output=True, text=True).stdout.split()
    out = subprocess.run(['git', '-C', str(lab_git), 'log', *ref[:1], '--diff-filter=A', '--format=%aI', '--', rel],
                         capture_output=True, text=True).stdout.split()
    return out[-1] if out else None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--lab', required=True, type=Path)
    p.add_argument('--trips', required=True, type=Path)
    p.add_argument('--builds', required=True, type=Path)
    p.add_argument('--lab-git', type=Path)
    x = p.parse_args()
    evals = x.lab / 'evals'
    protocol = Protocol('v1')
    _, pair_sha = protocol.prompt('pairwise')
    _, abs_sha = protocol.prompt('absolute')

    for d in (ANCHORS, RESULTS):
        if d.exists():
            shutil.rmtree(d)
    (ANCHORS / 'texts').mkdir(parents=True)
    (ANCHORS / 'posts').mkdir()
    (ANCHORS / 'data').mkdir()
    for topic in ('bike', 'ci', 'solar'):
        shutil.copy(x.lab / 'materials' / topic / 'posts.md', ANCHORS / 'posts' / f'{topic}.md')
    shutil.copy(x.trips, ANCHORS / 'data' / 'trips.csv')
    shutil.copy(x.builds, ANCHORS / 'data' / 'builds.csv')
    RESULTS.mkdir(parents=True)

    def anchor_text(ref: str) -> str | None:
        """Путь из результата пилота → путь в наборе эталонов (копирует текст)."""
        name = Path(ref).name
        if ref.endswith('materials/ci/posts.md'):
            return 'posts/ci.md'
        src = evals / Path(ref).parent.name / name
        if not src.is_file():
            return None
        dst = ANCHORS / 'texts' / name
        if not dst.exists():
            shutil.copy(src, dst)
        return f'texts/{name}'

    def meta(rel: str | None) -> dict:
        if rel is None:
            return {'path': None, 'sha256': None, 'words': None, 'note': 'текст в пилоте не сохранён'}
        f = ANCHORS / rel
        return {'path': f'anchors/pilot-2026-11/{rel}', 'sha256': sha256_file(f), 'words': words(f.read_text(encoding='utf-8'))}

    pairs, imported = {}, []
    for src in sorted(evals.rglob('*.json')):
        rel = src.relative_to(x.lab).as_posix()
        d = json.loads(src.read_text(encoding='utf-8'))
        common = {'protocol': 'v1', 'created': created(x.lab_git, rel), 'bench_commit': None,
                  'cli': {'claude': None, 'codex': None}, 'imported': True,
                  'imported_from': f'лаборатория пилота Granki: {rel}'}
        if 'votes' in d:
            name = src.stem.removeprefix('pair-')
            a, b = anchor_text(d['a']), anchor_text(d['b'])
            topic = topic_of(Path(d['a']).name)
            t = TOPICS[topic]
            votes = [{'judge': v['model'], 'model_id': None, 'order': v['order'], 'votes': v['votes'],
                      'why': v.get('why', ''), 'error': None, 'cost_usd': None} for v in d['votes']]
            judges = list(dict.fromkeys(v['judge'] for v in votes))
            result = {'kind': 'pairwise', 'prompt_sha256': pair_sha, **common, 'judges': judges,
                      'inputs': {'a': meta(a), 'b': meta(b), 'posts': meta(t['posts']), 'reader': t['reader'],
                                 'note': 'читатель и посты восстановлены по скриптам оценки пилота'},
                      'votes': votes, 'a_minus_b': d['a_minus_b'],
                      'spread': scoring.pair_spread(votes, protocol.criteria('pairwise'))}
            if name.endswith('-rerun'):
                result['note'] = 'повтор той же пары теми же судьями: проверка шума'
            if name in pairs:
                raise SystemExit(f'Повтор имени пары: {name}')
            pairs[name] = {'a': a, 'b': b, 'topic': topic, 'result': f'results/v1-pilot-2026-11/pair-{name}.json'}
            out = RESULTS / f'pair-{name}.json'
        else:
            name = src.stem
            article = anchor_text(d['article'])
            topic = 'ci' if 'ci' in name else 'bike' if 'bike' in name or name.startswith('A-') else 'ci'
            if name == 'calib-bread-example':
                topic = None
            t = TOPICS.get(topic or 'bike')
            judges = list(d['scores'])
            result = {'kind': 'absolute', 'prompt_sha256': abs_sha, **common, 'judges': judges,
                      'inputs': {'article': meta(article),
                                 'posts': meta(t['posts']) if topic else {'path': None, 'note': 'не сохранено'},
                                 'claims': meta(t['claims']) if topic else {'path': None, 'note': 'не сохранено'},
                                 'reader': t['reader'] if topic else None},
                      'model_ids': {j: None for j in judges}, 'scores': d['scores'], 'mean': d['mean'],
                      'spread': scoring.absolute_spread(d['scores'], protocol.criteria('absolute')),
                      'details': d['details']}
            if name.startswith('calib'):
                result['note'] = 'калибровка шкалы 1–10: ' + ('пример из туториала Granki' if 'bread' in name else 'посты-эталон голоса')
            out = RESULTS / f'score-{name}.json'
        out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        imported.append(out.name)

    rows = []
    for f in sorted(p for p in ANCHORS.rglob('*') if p.is_file()):
        relf = f.relative_to(ANCHORS).as_posix()
        role = 'текст' if relf.startswith('texts/') else 'посты-эталон голоса (написаны моделью)' if relf.startswith('posts/') else 'данные (вымышленные)'
        about = VARIANTS.get(f.name, '')
        topic = topic_of(f.name) if relf.startswith('texts/') else {'trips': 'bike', 'builds': 'ci'}.get(Path(relf).stem, Path(relf).stem)
        rows.append({'path': relf, 'sha256': sha256_file(f), 'words': words(f.read_text(encoding='utf-8')),
                     'role': role, 'topic': topic, 'about': about})
    with (ANCHORS / 'manifest.csv').open('w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    (ANCHORS / 'topics.json').write_text(json.dumps(TOPICS, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (ANCHORS / 'pairs.json').write_text(json.dumps(pairs, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'results': len(imported), 'pairs': len(pairs), 'anchor_files': len(rows)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
