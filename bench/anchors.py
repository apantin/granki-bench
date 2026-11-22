"""Наборы эталонных текстов: манифест с хешами, темы (читатель, посты, данные) и пары."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .protocol import sha256_file


class AnchorSet:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.topics = json.loads((self.root / 'topics.json').read_text(encoding='utf-8'))
        self.pairs = json.loads((self.root / 'pairs.json').read_text(encoding='utf-8'))
        with (self.root / 'manifest.csv').open(encoding='utf-8') as f:
            self.manifest = list(csv.DictReader(f))

    def path(self, rel: str) -> Path:
        return self.root / rel

    def verify(self) -> list[str]:
        """Файлы, чей хеш не совпал с манифестом, и файлы вне манифеста."""
        problems = []
        listed = set()
        for row in self.manifest:
            listed.add(row['path'])
            p = self.path(row['path'])
            if not p.is_file():
                problems.append(f'нет файла: {row["path"]}')
            elif sha256_file(p) != row['sha256']:
                problems.append(f'хеш не совпал: {row["path"]}')
        service = {'manifest.csv', 'topics.json', 'pairs.json', 'README.md'}
        for p in self.root.rglob('*'):
            rel = p.relative_to(self.root).as_posix()
            if p.is_file() and rel not in listed and rel not in service:
                problems.append(f'файл вне манифеста: {rel}')
        return problems

    def pair(self, name: str) -> dict:
        if name not in self.pairs:
            raise SystemExit(f'Нет пары {name}; есть: {", ".join(sorted(self.pairs))}')
        entry = dict(self.pairs[name])
        entry.update(self.topics[entry['topic']])
        return entry
