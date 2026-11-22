"""Прогоны: парное сравнение и абсолютная оценка. Каждый результат несёт полные метаданные."""
from __future__ import annotations

import concurrent.futures as cf
from pathlib import Path

from . import models, scoring
from .protocol import Protocol, bench_commit, now, sha256_file, words


def text_meta(path: Path) -> dict:
    path = Path(path)
    return {'path': str(path), 'sha256': sha256_file(path), 'words': words(path.read_text(encoding='utf-8'))}


def base_meta(protocol: Protocol, kind: str, judges: list[str]) -> dict:
    _, prompt_sha = protocol.prompt(kind)
    return {
        'kind': kind,
        'protocol': protocol.version,
        'prompt_sha256': prompt_sha,
        'created': now(),
        'bench_commit': bench_commit(),
        'judges': judges,
        'cli': models.cli_versions(judges),
        'imported': False,
    }


def pairwise(protocol: Protocol, a: Path, b: Path, posts: Path, reader: str, judges: list[str] | None = None) -> dict:
    """Слепое парное сравнение: каждый судья дважды, в порядке AB и BA."""
    judges = judges or protocol.judges
    template, _ = protocol.prompt('pairwise')
    spec = protocol.spec['pairwise']
    ta, tb = Path(a).read_text(encoding='utf-8'), Path(b).read_text(encoding='utf-8')
    posts_text = Path(posts).read_text(encoding='utf-8')
    jobs = []
    for judge in judges:
        for order in spec['orders']:
            t1, t2 = (ta, tb) if order == 'ab' else (tb, ta)
            jobs.append((judge, order, template.format(reader=reader, posts=posts_text, t1=t1, t2=t2)))
    with cf.ThreadPoolExecutor(len(jobs)) as ex:
        answers = list(ex.map(lambda job: models.call(protocol.spec['runner'], job[0], job[2]), jobs))
    votes = []
    for (judge, order, _), res in zip(jobs, answers):
        answer = res.get('answer', {})
        votes.append({
            'judge': judge,
            'model_id': res.get('model_id'),
            'order': order,
            'votes': {k: scoring.winner(answer.get(k, ''), order) for k in spec['criteria']},
            'why': str(answer.get('why', res.get('error', '')))[:300],
            'error': 'error' in res,
            'cost_usd': res.get('cost_usd'),
        })
    result = base_meta(protocol, 'pairwise', judges)
    result['inputs'] = {'a': text_meta(a), 'b': text_meta(b), 'posts': text_meta(posts), 'reader': reader}
    result['votes'] = votes
    result['a_minus_b'] = scoring.pair_score(votes, spec['criteria'])
    result['spread'] = scoring.pair_spread(votes, spec['criteria'])
    return result


def absolute(protocol: Protocol, article: Path, posts: Path, claims: Path, reader: str, judges: list[str] | None = None) -> dict:
    """Абсолютная оценка по шкале протокола; каждый судья — один раз."""
    judges = judges or protocol.judges
    template, _ = protocol.prompt('absolute')
    spec = protocol.spec['absolute']
    prompt = template.format(reader=reader, posts=Path(posts).read_text(encoding='utf-8'),
                             claims=Path(claims).read_text(encoding='utf-8'),
                             article=Path(article).read_text(encoding='utf-8'))
    with cf.ThreadPoolExecutor(len(judges)) as ex:
        answers = dict(zip(judges, ex.map(lambda j: models.call(protocol.spec['runner'], j, prompt), judges)))
    details = {j: (r['answer'] if 'answer' in r else {'error': r.get('error')}) for j, r in answers.items()}
    table = {j: {k: d.get(k) for k in spec['criteria']} for j, d in details.items()}
    result = base_meta(protocol, 'absolute', judges)
    result['inputs'] = {'article': text_meta(article), 'posts': text_meta(posts), 'claims': text_meta(claims), 'reader': reader}
    result['model_ids'] = {j: r.get('model_id') for j, r in answers.items()}
    result['scores'] = table
    result['mean'] = scoring.absolute_mean(table, spec['criteria'])
    result['spread'] = scoring.absolute_spread(table, spec['criteria'])
    result['details'] = details
    return result


def recompute(result: dict, protocol: Protocol) -> dict:
    """Пересчёт итога по сохранённым голосам или баллам; возвращает расхождения с записанным итогом."""
    kind = result['kind']
    criteria = protocol.criteria(kind)
    if kind == 'pairwise':
        fresh = scoring.pair_score(result['votes'], criteria)
        stored = result['a_minus_b']
    else:
        fresh = scoring.absolute_mean(result['scores'], criteria)
        stored = result['mean']
    return {k: (stored.get(k), fresh[k]) for k in criteria if stored.get(k) != fresh[k]}
