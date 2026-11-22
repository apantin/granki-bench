"""Протоколы оценки: загрузка, хеши промптов, общие утилиты."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOLS = ROOT / 'protocols'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def words(text: str) -> int:
    return len(re.findall(r'\w+', text))


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def bench_commit() -> str | None:
    """Коммит bench, из которого запущен прогон; с пометкой, если рабочая копия изменена."""
    try:
        head = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain'], capture_output=True, text=True, check=True).stdout.strip()
        return head + ('+dirty' if dirty else '')
    except (OSError, subprocess.CalledProcessError):
        return None


class Protocol:
    """Версия протокола: критерии, промпты, судьи, команды запуска."""

    def __init__(self, version: str):
        self.dir = PROTOCOLS / version
        if not (self.dir / 'protocol.json').is_file():
            known = sorted(p.name for p in PROTOCOLS.iterdir() if (p / 'protocol.json').is_file())
            raise SystemExit(f'Нет протокола {version}; есть: {", ".join(known)}')
        self.spec = json.loads((self.dir / 'protocol.json').read_text(encoding='utf-8'))
        self.version = self.spec['version']

    def prompt(self, kind: str) -> tuple[str, str]:
        """Шаблон промпта и его sha256."""
        path = self.dir / self.spec[kind]['prompt']
        data = path.read_bytes()
        digest = sha256_bytes(data)
        expected = self.spec[kind].get('prompt_sha256')
        if self.spec.get('status') == 'frozen' and expected and digest != expected:
            raise SystemExit(f'Промпт {path.name} протокола {self.version} изменён, а протокол заморожен: правка — только новой версией')
        return data.decode('utf-8'), digest

    def criteria(self, kind: str) -> list[str]:
        return self.spec[kind]['criteria']

    @property
    def judges(self) -> list[str]:
        return self.spec['judges']
