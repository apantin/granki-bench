#!/usr/bin/env python3
"""Проверка перед коммитом: в открытый репозиторий не уходит лишнее.

- файлы только в разрешённых папках;
- в добавленном тексте нет локальных путей и адресов почты;
- файлы не больше 5 МБ;
- наборы эталонов сходятся со своими манифестами;
- замороженные промпты не изменены.

Включить: git config core.hooksPath .githooks
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ALLOWED_DIRS = {'bench', 'protocols', 'anchors', 'results', 'scripts', 'tests', 'docs', 'rules', '.githooks'}
ALLOWED_FILES = {'README.md', 'LICENSE', 'NOTICE.md', '.gitignore', 'pyproject.toml'}
MAX_BYTES = 5 * 1024 * 1024
PRIVATE = re.compile(r'/home/[a-z]|/Users/[A-Za-z]|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|ru|me|org|net)\b')


def staged() -> list[str]:
    out = subprocess.run(['git', '-C', str(ROOT), 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def staged_blob(path: str) -> bytes:
    return subprocess.run(['git', '-C', str(ROOT), 'show', f':{path}'], capture_output=True, check=True).stdout


def main() -> int:
    problems = []
    for path in staged():
        top = path.split('/', 1)[0]
        if '/' in path and top not in ALLOWED_DIRS or '/' not in path and path not in ALLOWED_FILES:
            problems.append(f'{path}: вне разрешённых путей')
            continue
        data = staged_blob(path)
        if len(data) > MAX_BYTES:
            problems.append(f'{path}: больше 5 МБ')
        if path != 'scripts/check_commit.py':
            found = PRIVATE.search(data.decode('utf-8', 'ignore'))
            if found:
                problems.append(f'{path}: похоже на локальный путь или почту: {found.group(0)}')

    from bench.anchors import AnchorSet
    from bench.protocol import PROTOCOLS, Protocol
    for manifest in sorted((ROOT / 'anchors').glob('*/manifest.csv')):
        problems += [f'anchors/{manifest.parent.name}: {p}' for p in AnchorSet(manifest.parent).verify()]
    for spec in sorted(PROTOCOLS.glob('*/protocol.json')):
        p = Protocol(spec.parent.name)
        for kind in ('pairwise', 'absolute'):
            if kind in p.spec:
                p.prompt(kind)  # падает, если замороженный промпт изменён

    for p in problems:
        print(f'check_commit: {p}', file=sys.stderr)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
