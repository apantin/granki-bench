#!/usr/bin/env python3
"""Воспроизводимый отбор метаданных из отсортированного CDX-индекса Common Crawl.

Без AWS-аккаунта и публичного CDX API: бинарный поиск по cluster.idx через Range,
затем только выбранные gzip-блоки. Тексты и список URL сохраняются по параметру.
"""
from __future__ import annotations
import argparse
import bisect
import gzip
import hashlib
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = 'https://data.commoncrawl.org/'
USER_AGENT = 'granki-bench-research/0.1'


class HTTP:
    def __init__(self, cache: Path, *, delay: float = .25, timeout: float = 30):
        self.cache, self.delay, self.timeout = cache, delay, timeout
        self.cache.mkdir(parents=True, exist_ok=True)
        self.bytes = 0
        self.requests = 0
        self.last = 0.0

    def get(self, url: str, start: int | None = None, length: int | None = None) -> bytes:
        key = hashlib.sha256(f'{url}\0{start}\0{length}'.encode()).hexdigest()
        target = self.cache / key
        if target.exists():
            return target.read_bytes()
        headers = {'User-Agent': USER_AGENT}
        if start is not None:
            if length is None or length <= 0:
                raise ValueError('Нужна положительная длина диапазона')
            headers['Range'] = f'bytes={start}-{start + length - 1}'
        for attempt in range(2):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
            try:
                self.requests += 1
                with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                    if start is not None and response.status != 206:
                        raise ValueError('Сервер не поддержал диапазон; полная загрузка запрещена')
                    data = response.read((length + 1) if length else 64 * 1024 * 1024)
                    if start is not None and len(data) != length:
                        raise ValueError('Длина диапазона не совпала')
                self.bytes += len(data)
                target.write_bytes(data)
                self.last = time.monotonic()
                return data
            except (HTTPError, URLError, TimeoutError):
                self.last = time.monotonic()
                if attempt:
                    raise
                time.sleep(1)
        raise RuntimeError('Unreachable')


def domain_prefix(domain: str) -> str:
    return ','.join(reversed(domain.lower().split('.')))


def blocks_for_domain(http: HTTP, snapshot: str, domain: str, *, include_subdomains: bool = True,
                      path_prefix: str = '') -> list[tuple]:
    url = f'{BASE}cc-index/collections/{snapshot}/indexes/cluster.idx'
    with urlopen(Request(url, method='HEAD', headers={'User-Agent': USER_AGENT}), timeout=http.timeout) as r:
        size = int(r.headers['Content-Length'])
    prefix = domain_prefix(domain)
    lower = prefix if include_subdomains else prefix + ')'
    upper = prefix + ('-' if include_subdomains else '*')
    if path_prefix:
        lower = prefix + ')' + path_prefix
        upper = lower + '\uffff'
    # SURT домена заканчивается ')' либо ',' для поддоменов; оба меньше '-'.
    lo, hi, best = 0, size, 0
    while hi - lo > 65536:
        pos = (lo + hi) // 2
        chunk = http.get(url, pos, min(65536, size - pos))
        end = chunk.find(b'\n')
        rest = chunk[end + 1:]
        first = rest.split(b'\n', 1)[0]
        key = first.split(b' ', 1)[0].decode()
        if key < lower:
            best = pos
            lo = pos + end + 1
        else:
            hi = pos
    start = max(0, min(best, lo) - 65536)
    found = []
    previous = None
    done = False
    # Домены с миллионами страниц: поток индекса ограничен; блоки отбираются ниже.
    carry = b''
    first_chunk = True
    while start < size and not done:
        length = min(1024 * 1024, size - start)
        chunk = carry + http.get(url, start, length)
        lines = chunk.split(b'\n')
        carry = lines.pop()
        if first_chunk and start:
            lines = lines[1:]  # Диапазон начинается внутри строки, это не запись индекса.
        first_chunk = False
        for line in lines:
            cols = line.decode(errors='replace').split('\t')
            if len(cols) < 4:
                continue
            key = cols[0].split(' ', 1)[0]
            block = (cols[1], int(cols[2]), int(cols[3]))
            if key < lower:
                previous = block
                continue
            if not found and previous:
                found.append(previous)
            if key > upper:
                done = True
                break
            found.append(block)
        start += length
    return list(dict.fromkeys(found))


def candidates(http: HTTP, snapshot: str, domain: str, *, seed: str, max_blocks: int = 8,
               include_subdomains: bool = True, path_prefix: str = '') -> list[dict]:
    blocks = blocks_for_domain(http, snapshot, domain, include_subdomains=include_subdomains,
                              path_prefix=path_prefix)
    chosen = sorted(blocks, key=lambda b: hashlib.sha256(f'{seed}\0{b}'.encode()).digest())[:max_blocks]
    prefix = domain_prefix(domain)
    result = []
    for filename, offset, length in chosen:
        url = f'{BASE}cc-index/collections/{snapshot}/indexes/{filename}'
        content = gzip.decompress(http.get(url, offset, length))
        for line in content.splitlines():
            cols = line.split(b' ', 2)
            if len(cols) != 3:
                continue
            key = cols[0].decode()
            if not (key.startswith(prefix + ')') or key.startswith(prefix + ',')):
                continue
            row = json.loads(cols[2])
            if path_prefix:
                from urllib.parse import urlsplit
                if not urlsplit(row['url']).path.startswith(path_prefix):
                    continue
            if not include_subdomains:
                from urllib.parse import urlsplit
                if (urlsplit(row['url']).hostname or '').removeprefix('www.') != domain.removeprefix('www.'):
                    continue
            if row.get('status') == '200' and row.get('mime', '').startswith('text/html'):
                row['snapshot'] = snapshot
                row['timestamp'] = cols[1].decode()
                result.append(row)
    return sorted(result, key=lambda r: hashlib.sha256(f"{seed}\0{r['url']}".encode()).digest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', required=True)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', default='article-blog-v1')
    parser.add_argument('--max-blocks', type=int, default=8)
    args = parser.parse_args()
    http = HTTP(args.cache)
    result = candidates(http, args.snapshot, args.domain, seed=args.seed, max_blocks=args.max_blocks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in result))
    print(json.dumps({'candidates': len(result), 'requests': http.requests, 'bytes': http.bytes}))


if __name__ == '__main__':
    main()
