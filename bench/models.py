"""Адаптеры моделей-судей: Claude Code и Codex CLI.

Каждый вызов возвращает разобранный JSON ответа и то, что удалось узнать о модели:
точный ID модели (Claude Code пишет его в modelUsage, Codex — в служебный вывод),
стоимость, если CLI её сообщает.
"""
from __future__ import annotations

import functools
import json
import re
import subprocess
import tempfile

CLAUDE_ALIASES = {'opus', 'sonnet', 'haiku'}


def parse_last_json(text: str) -> dict | None:
    """JSON из ответа, как в пилоте: жадный фрагмент от первой «{» до последней «}».

    Если в ответе два отдельных объекта, фрагмент не разберётся — так вёл себя протокол v1.
    """
    for chunk in reversed(re.findall(r'\{.*\}', text, re.S)):
        try:
            value = json.loads(chunk)
        except ValueError:
            continue
        if isinstance(value, dict):
            return value
    return None


@functools.lru_cache(maxsize=None)
def cli_version(tool: str) -> str | None:
    try:
        out = subprocess.run([tool, '--version'], capture_output=True, text=True, timeout=60)
        return (out.stdout or out.stderr).strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def family(judge: str) -> str:
    return 'claude' if judge in CLAUDE_ALIASES or judge.startswith('claude') else 'codex' if judge.startswith('codex') else 'other'


def command(runner: dict, judge: str) -> tuple[str, list[str]]:
    fam = family(judge)
    if fam == 'claude':
        return 'claude', [arg.replace('{alias}', judge) for arg in runner['claude']]
    if fam == 'codex':
        return 'codex', list(runner['codex'])
    raise SystemExit(f'Неизвестный судья: {judge}. Поддерживаются opus, sonnet, haiku, codex')


def call_once(runner: dict, judge: str, prompt: str) -> dict:
    tool, cmd = command(runner, judge)
    with tempfile.TemporaryDirectory(prefix='granki-bench-') as cwd:
        try:
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                                  timeout=runner.get('timeout_s', 1200), cwd=cwd)
        except subprocess.TimeoutExpired:
            return {'error': 'timeout', 'model_id': None}
    model_id, cost, text = None, None, proc.stdout
    if tool == 'claude':
        try:
            meta = json.loads(proc.stdout)
            text = meta.get('result', '')
            ids = sorted(meta.get('modelUsage', {}))
            model_id = ','.join(ids) or None
            cost = meta.get('total_cost_usd')
        except ValueError:
            pass
    else:
        found = re.search(r'^model:\s*(\S+)', proc.stderr, re.M)
        model_id = found.group(1) if found else None
    answer = parse_last_json(text)
    if answer is None:
        return {'error': (text or proc.stderr)[-2000:], 'model_id': model_id, 'cost_usd': cost}
    return {'answer': answer, 'model_id': model_id, 'cost_usd': cost}


def call(runner: dict, judge: str, prompt: str) -> dict:
    """Вызов с повтором: протокол задаёт число попыток."""
    result = {}
    for _ in range(runner.get('attempts', 1)):
        result = call_once(runner, judge, prompt)
        if 'error' not in result:
            break
    return result


def cli_versions(judges: list[str]) -> dict:
    tools = sorted({'claude' if family(j) == 'claude' else 'codex' for j in judges})
    return {tool: cli_version(tool) for tool in tools}
