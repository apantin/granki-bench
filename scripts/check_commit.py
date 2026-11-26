#!/usr/bin/env python3
"""Проверка перед коммитом: в открытый репозиторий не уходит лишнее.

- файлы только в разрешённых папках;
- файлы данных — только в anchors/, в results/ — только результаты bench;
- в добавленном тексте нет локальных путей и адресов почты;
- файлы не больше 5 МБ;
- наборы эталонов сходятся со своими манифестами;
- замороженные промпты не изменены.

Включить: git config core.hooksPath .githooks
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ALLOWED_DIRS = {'bench', 'protocols', 'anchors', 'results', 'scripts', 'tests', 'docs', 'rules', 'norms', '.githooks'}
ALLOWED_FILES = {'README.md', 'LICENSE', 'NOTICE.md', '.gitignore', 'pyproject.toml'}
MAX_BYTES = 5 * 1024 * 1024
# Файлы данных — только в наборах эталонов (anchors/), где их сверяет манифест.
DATA_EXT = {'.csv', '.tsv', '.jsonl', '.txt', '.parquet', '.xlsx', '.xls', '.xml', '.html', '.epub', '.fb2',
            '.pdf', '.docx', '.doc', '.rtf', '.zip', '.gz', '.xz', '.bz2', '.tar', '.7z'}
# Profile.aspx?uid= — старый веб-маршрут, не домашняя папка macOS.
# Исключение только для этого точного маршрута; обычные /Users/... не ослаблены.
PRIVATE = re.compile(r'/home/[a-z]|/Users/(?!Profile\.aspx\?uid=)[A-Za-z]|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(?:com|ru|me|org|net)\b')


def staged() -> list[str]:
    out = subprocess.run(['git', '-C', str(ROOT), 'diff', '--cached', '--name-only', '--diff-filter=ACMR'],
                         capture_output=True, text=True, check=True).stdout
    return [line for line in out.splitlines() if line]


def staged_blob(path: str) -> bytes:
    return subprocess.run(['git', '-C', str(ROOT), 'show', f':{path}'], capture_output=True, check=True).stdout


def is_result(path: str, data: bytes) -> bool:
    if not path.endswith('.json'):
        return False
    try:
        return json.loads(data).get('kind') in {'pairwise', 'absolute'}
    except (ValueError, AttributeError):
        return False


def norm_problems(path: str, data: bytes) -> list[str]:
    """Норма содержит рецепт и агрегаты, без отдельных текстов и деления."""
    import csv
    import io
    name = Path(path).name
    fields = {
        'domains.csv': ['domain', 'subgenre', 'url_pattern', 'path_prefix', 'author_rule', 'snapshots'],
        'groups.csv': ['domain', 'snapshot', 'subgenre', 'documents', 'sha256'],
    }
    if len(Path(path).parts) != 3 or name not in {*fields, 'recipe.md', 'config.json'}:
        return ['недопустимый файл нормы']
    if name in fields:
        reader = csv.DictReader(io.StringIO(data.decode('utf-8')))
        if reader.fieldnames != fields[name]:
            return ['неверные колонки нормы']
        for row in reader:
            if not re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}', row.get('domain', '')):
                return ['домен должен быть общим именем площадки без URL и автора']
            if name=='domains.csv':
                if row.get('author_rule')!='metadata-or-host':
                    return ['неизвестное общее правило авторства']
                if any(row['domain'].endswith('.'+p) for p in ('livejournal.com','blogspot.com','liveinternet.ru','diary.ru','teletype.in')):
                    return ['нельзя публиковать домен отдельного автора платформы']
                if re.search(r'/@\w+',row['url_pattern']):
                    return ['шаблон не должен содержать имя автора']
            if name == 'groups.csv':
                if not row['documents'].isdigit() or not re.fullmatch('[0-9a-f]{64}', row['sha256']):
                    return ['неверный агрегат нормы']
    if name == 'config.json':
        try:
            config = json.loads(data)
        except ValueError:
            return ['неверный JSON конфигурации']
        allowed = {'version', 'seed', 'snapshots', 'target', 'min_words', 'max_words', 'min_cyrillic',
                   'domain_cap', 'author_cap', 'dedup_threshold', 'clean_version', 'max_records',
                   'index_method', 'candidate_limit', 'candidate_limits', 'max_blocks', 'subgenres', 'dependencies', 'provenance_policy'}
        if not isinstance(config, dict) or set(config) - allowed:
            return ['недопустимые поля конфигурации нормы']
        if 'provenance_policy' in config and config['provenance_policy'] not in {'rsdn-primary-header-v1','rsdn-primary-header-profile-v2','rsdn-primary-header-profile-translation-v3','primary-header-rsdn-habr-v4','primary-source-rsdn-habr-v5','primary-source-rsdn-habr-kontur-v6','primary-source-rsdn-habr-kontur-liveinternet-v7'}:
            return ['неизвестная политика происхождения нормы']
        limits=config.get('candidate_limits',{})
        if not isinstance(limits,dict) or any(not re.fullmatch(r'[a-z0-9.-]+\.[a-z]{2,}',k) or
                any(k.endswith('.'+p) for p in ('livejournal.com','blogspot.com','liveinternet.ru','diary.ru','teletype.in')) or
                type(v) is not int or v<1 for k,v in limits.items()):
            return ['доменные пределы должны содержать только общие домены и положительные целые числа']
    if re.search(r'"(?:salt|split|split_key|author_id|source_url|validation_exclusion)"\s*:', data.decode()):
        return ['приватное поле в норме']
    return []


def main() -> int:
    problems = []
    for path in staged():
        top = path.split('/', 1)[0]
        if '/' in path and top not in ALLOWED_DIRS or '/' not in path and path not in ALLOWED_FILES:
            problems.append(f'{path}: вне разрешённых путей')
            continue
        data = staged_blob(path)
        suffix = Path(path).suffix.lower()
        if top == 'norms':
            problems += [f'{path}: {p}' for p in norm_problems(path, data)]
        if suffix in DATA_EXT and top not in {'anchors', 'norms'} and not (top == 'protocols' and suffix == '.txt'):  # промпты — .txt
            problems.append(f'{path}: файл данных вне anchors/ — данные только в наборах эталонов с манифестом')
        if top == 'results' and Path(path).name != 'README.md' and not is_result(path, data):
            problems.append(f'{path}: в results/ — только JSON результатов bench (поле kind: pairwise или absolute)')
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
