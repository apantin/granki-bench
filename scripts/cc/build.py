#!/usr/bin/env python3
"""Пересборка нормы только по открытому рецепту и Common Crawl.

Рабочие тексты сохраняются вне репозитория по обязательному --work-dir.
Наружу экспортируются только групповые числа и хеши. Приватное деление не читается.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
import time
import subprocess
from datetime import datetime,timezone
from importlib.metadata import version as package_version
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from bench.cleaning import VERSION,html_article,text_features
from bench.corpus_selection import deduplicate,quota,group_hashes
from index import BASE,HTTP,candidates
from extraction import author_identity,response_body


def canonical(url):
    parsed=urlsplit(url)
    return urlunsplit(('https',(parsed.hostname or '').removeprefix('www.'),parsed.path,'',''))


def build(config:dict,domains:list[dict],work:Path,*,max_seconds:int=14400,max_bytes:int=2*1024**3):
    if work.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Рабочие тексты должны находиться за пределами открытого репозитория')
    if config['clean_version']!=VERSION:
        raise ValueError('Версия очистки не совпала с рецептом')
    actual={name:package_version(name) for name in config['dependencies']}
    if actual!=config['dependencies']:raise ValueError('Версии зависимостей не совпадают с рецептом')
    run_dir=work/'cc-rebuild/runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir.mkdir(parents=True,exist_ok=False)
    commit=subprocess.run(['git','-C',str(Path(__file__).resolve().parents[2]),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    (run_dir/'run.json').write_text(json.dumps(dict(config=config,domains=domains,dependencies=actual,bench_commit=commit,
                                                  max_seconds=max_seconds,max_bytes=max_bytes),ensure_ascii=False,indent=2)+'\n')
    http=HTTP(work/'raw/cc/http-cache',delay=.3,timeout=20)
    docs=[]
    counts=Counter()
    start=time.monotonic()
    considered=set()
    for domain in domains:
        for snapshot in sorted(domain['snapshots'].split(';')):
            if counts['warc_attempts']>=config['max_records']:
                break
            selected=candidates(http,snapshot,domain['domain'],seed=config['seed'],
                                max_blocks=config['max_blocks'],path_prefix=domain.get('path_prefix',''))
            selected=[r for r in selected if re.search(domain['url_pattern'],r['url']) and
                      (not r.get('languages') or 'rus' in r['languages'])]
            for record in selected[:config['candidate_limit']]:
                if time.monotonic()-start>max_seconds or http.bytes>=max_bytes or counts['warc_attempts']>=config['max_records']:
                    counts['budget_stop']+=1
                    break
                url=canonical(record['url'])
                if url in considered:continue
                considered.add(url)
                counts['warc_attempts']+=1
                try:
                    compressed=http.get(BASE+record['filename'],int(record['offset']),int(record['length']))
                    payload=response_body(compressed)
                    clean,metadata=html_article(payload,record['url'])
                    features=text_features(clean.norm)
                    if not config['min_words']<=features['words']<=config['max_words'] or features['cyrillic']<config['min_cyrillic']:
                        counts['filter']+=1;continue
                    if re.search(r'(?i)(перевод\s*[:—]|перев[её]л[а]?\s*[:—]|перепечатано)',clean.raw):
                        counts['translation_or_reprint']+=1;continue
                    rid=hashlib.sha256((snapshot+'\0'+record['url']).encode()).hexdigest()[:24]
                    folder=work/'cc-rebuild'/snapshot/domain['domain']
                    folder.mkdir(parents=True,exist_ok=True)
                    path,raw_path=folder/(rid+'.md'),folder/(rid+'.raw.md')
                    path.write_text(clean.norm);raw_path.write_text(clean.raw)
                    docs.append(dict(id=rid,url=url,snapshot=snapshot,domain=domain['domain'],
                                     subgenre=domain['subgenre'],author=author_identity(record['url'],metadata),
                                     sha256=hashlib.sha256(path.read_bytes()).hexdigest(),text=clean.norm,
                                     path=str(path),raw_path=str(raw_path)))
                    counts['accepted']+=1
                except Exception as exc:counts['error:'+type(exc).__name__]+=1
            print(json.dumps(dict(counts,domain=domain['domain'],snapshot=snapshot,bytes=http.bytes)),flush=True)
    unique,duplicates=deduplicate(docs,config['dedup_threshold'])
    selected=quota(unique,seed=config['seed'],target=config['target'],subgenres=config['subgenres'],
                   domain_cap=config['domain_cap'],author_cap=config['author_cap'])
    groups=group_hashes(selected)
    output=work/'cc-rebuild'
    output.mkdir(parents=True,exist_ok=True)
    # Только локальный промежуточный реестр; не публикуется вместе с агрегатами.
    (output/'selected.json').write_text(json.dumps([{k:v for k,v in d.items() if k!='text'} for d in selected],ensure_ascii=False,indent=2)+'\n')
    (output/'summary.json').write_text(json.dumps(dict(counts,unique=len(unique),selected=len(selected),duplicates=len(duplicates),
                                                    complete=len(selected)==config['target']),ensure_ascii=False,indent=2)+'\n')
    import shutil
    shutil.copyfile(output/'selected.json',run_dir/'selected.json')
    shutil.copyfile(output/'summary.json',run_dir/'summary.json')
    return groups


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe-dir',type=Path,required=True)
    parser.add_argument('--work-dir',type=Path,required=True)
    parser.add_argument('--output-groups',type=Path,required=True)
    parser.add_argument('--max-seconds',type=int,default=14400)
    args=parser.parse_args()
    config=json.loads((args.recipe_dir/'config.json').read_text())
    with (args.recipe_dir/'domains.csv').open(newline='') as f:domains=list(csv.DictReader(f))
    result=build(config,domains,args.work_dir,max_seconds=args.max_seconds)
    args.output_groups.parent.mkdir(parents=True,exist_ok=True)
    with args.output_groups.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['domain','snapshot','subgenre','documents','sha256'],lineterminator='\n')
        writer.writeheader();writer.writerows(result)
    print(json.dumps({'group_count':len(result),'documents':sum(r['documents'] for r in result)}))
