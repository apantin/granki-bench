"""Счёт по голосам и разброс между моделями. Чистые функции, без вызовов моделей."""
from __future__ import annotations

import statistics


def vote_value(winner: str) -> int:
    return 1 if winner == 'A' else -1 if winner == 'B' else 0


def winner(answer: str, order: str) -> str:
    """Ответ судьи «1», «2» или «=» в порядке показа → победитель A, B или «=»."""
    answer = str(answer).strip()
    first, second = ('A', 'B') if order == 'ab' else ('B', 'A')
    return {'1': first, '2': second}.get(answer, '=')


def pair_score(votes: list[dict], criteria: list[str]) -> dict:
    """(за A − за B) / число голосов по каждому критерию, как в протоколе v1."""
    n = len(votes)
    return {k: round(sum(vote_value(v['votes'].get(k, '=')) for v in votes) / n, 2) if n else None for k in criteria}


def pair_spread(votes: list[dict], criteria: list[str]) -> dict:
    """Разброс между моделями: счёт каждой модели (среднее её голосов) и стандартное отклонение по моделям.

    0 — все модели судят одинаково; 1 — модели расходятся полностью (например, одна всегда за A, другая всегда за B).
    """
    by_model: dict[str, list[dict]] = {}
    for v in votes:
        by_model.setdefault(v['judge'], []).append(v)
    out = {}
    for k in criteria:
        per_model = {m: round(sum(vote_value(v['votes'].get(k, '=')) for v in vs) / len(vs), 2) for m, vs in by_model.items()}
        values = list(per_model.values())
        out[k] = {'per_model': per_model, 'stdev': round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0}
    return out


def absolute_mean(table: dict, criteria: list[str]) -> dict:
    """Среднее по судьям, ответившим числом, как в протоколе v1."""
    mean = {}
    for k in criteria:
        values = [t[k] for t in table.values() if isinstance(t.get(k), (int, float))]
        mean[k] = round(sum(values) / max(1, len(values)), 2)
    return mean


def absolute_spread(table: dict, criteria: list[str]) -> dict:
    out = {}
    for k in criteria:
        values = [t[k] for t in table.values() if isinstance(t.get(k), (int, float))]
        out[k] = round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0
    return out
