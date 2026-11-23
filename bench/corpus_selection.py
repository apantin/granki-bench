"""Отбор нормы без приватной соли, просмотренных групп и назначения частей."""
from __future__ import annotations
import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from .cleaning import words


def rank(seed: str, doc: dict) -> bytes:
    return hashlib.sha256((seed + '\0' + doc['snapshot'] + '\0' + doc['url']).encode()).digest()


def shingles(text: str, size: int = 5) -> set[tuple[str, ...]]:
    tokens = [w.casefold() for w in words(text)]
    return {tuple(tokens[i:i+size]) for i in range(max(0,len(tokens)-size+1))}


def deduplicate(documents: list[dict], threshold: float = .85) -> tuple[list[dict], dict[str,str]]:
    """Компоненты сходства; представитель — ранний снимок, URL, хеш. Части не читаются."""
    from datasketch import MinHash, MinHashLSH
    ordered = sorted(documents,key=lambda d:(d['snapshot'],d['url'],d['sha256']))
    parent = list(range(len(ordered)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def union(a,b):
        a,b=find(a),find(b)
        parent[max(a,b)] = min(a,b)
    lsh = MinHashLSH(threshold=threshold,num_perm=128)
    signatures = []
    hashes = {}
    urls = {}
    for i,doc in enumerate(ordered):
        if doc['sha256'] in hashes: union(i,hashes[doc['sha256']])
        else: hashes[doc['sha256']]=i
        if doc['url'] in urls: union(i,urls[doc['url']])
        else: urls[doc['url']]=i
        sh = shingles(doc['text'])
        signatures.append(sh)
        mh = MinHash(num_perm=128,seed=42)
        for item in sorted(sh): mh.update('\0'.join(item).encode())
        if sh:
            for key in lsh.query(mh):
                j = int(key)
                other = signatures[j]
                if len(sh & other)/len(sh | other) >= threshold:
                    union(i,j)
            lsh.insert(str(i),mh)
    keep, duplicates = [], {}
    for i,doc in enumerate(ordered):
        representative=find(i)
        if representative==i: keep.append(doc)
        else: duplicates[doc['id']]=ordered[representative]['id']
    return keep,duplicates


def quota(documents: list[dict], *, seed: str, target: int, subgenres: list[str],
          domain_cap: float, author_cap: int) -> list[dict]:
    if not subgenres or target<=0 or not 0<domain_cap<=1 or author_cap<1:
        raise ValueError('Неверные параметры квот')
    per_subgenre=target//len(subgenres)
    per_domain=int(per_subgenre*domain_cap)
    counts,domains,authors=Counter(),Counter(),Counter()
    result=[]
    for doc in sorted(documents,key=lambda d:rank(seed,d)):
        sub=doc['subgenre']
        if sub not in subgenres: continue
        members=doc.get('authors',[doc['author']])
        if not isinstance(members,list) or not members or any(not isinstance(a,str) or not a.strip() for a in members):raise ValueError('Нужен непустой список авторских групп')
        members=set(members)
        if counts[sub]>=per_subgenre or domains[sub,doc['domain']]>=per_domain or any(authors[sub,a]>=author_cap for a in members):
            continue
        result.append(doc)
        counts[sub]+=1;domains[sub,doc['domain']]+=1
        for author in members:authors[sub,author]+=1
    return result


def group_hashes(documents: list[dict]) -> list[dict]:
    groups=defaultdict(list)
    for doc in documents:
        groups[doc['domain'],doc['snapshot'],doc['subgenre']].append(doc['sha256'])
    return [dict(domain=key[0],snapshot=key[1],subgenre=key[2],documents=len(values),
                 sha256=hashlib.sha256(''.join(v+'\n' for v in sorted(values)).encode()).hexdigest())
            for key,values in sorted(groups.items())]
