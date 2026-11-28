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
from extraction import author_identity,metadata_exclusion,response_body
from bench.provenance import rsdn_primary_header,rsdn_profile_constraints,rsdn_translation_marker,habr_translation_marker
from bench.habr_provenance import habr_source_marker
from bench.kontur_author_origin import kontur_author_origin,kontur_coauthors
from bench.liveinternet_provenance import liveinternet_source_marker
from bench.liveinternet_series_provenance import liveinternet_series_source_marker


def canonical(url):
    parsed=urlsplit(url)
    return urlunsplit(('https',(parsed.hostname or '').removeprefix('www.'),parsed.path,'',''))


def build(config:dict,domains:list[dict],work:Path,*,max_seconds:int=14400,max_bytes:int=2*1024**3):
    work=work.resolve()
    if work.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Рабочие тексты должны находиться за пределами открытого репозитория')
    if config['clean_version']==VERSION:
        extractor=html_article
    else:
        from bench.candidates import technical_markup,editorial_roles,keyboard_chords
        if config['clean_version']==technical_markup.VERSION:
            extractor=technical_markup.extract
        elif config['clean_version']==editorial_roles.VERSION:
            extractor=editorial_roles.extract
        elif config['clean_version']==keyboard_chords.VERSION:
            extractor=keyboard_chords.extract
        else:
            raise ValueError('Неизвестная версия очистки в рецепте')
    provenance_policy=config.get('provenance_policy')
    if 'provenance_policy' in config and provenance_policy not in {'rsdn-primary-header-v1','rsdn-primary-header-profile-v2','rsdn-primary-header-profile-translation-v3','primary-header-rsdn-habr-v4','primary-source-rsdn-habr-v5','primary-source-rsdn-habr-kontur-v6','primary-source-rsdn-habr-kontur-liveinternet-v7','primary-source-series-v8'}:raise ValueError('Неизвестная политика происхождения')
    completeness_policy=config.get('completeness_policy')
    if 'completeness_policy' in config:
        if completeness_policy!='explicit-source-cut-v1' or config['clean_version'] not in ('clean-v20-technical-markup-candidate','clean-v21-editorial-roles-candidate','clean-v22-keyboard-chords-candidate'):
            raise ValueError('Неизвестная политика полноты или несовместимая очистка')
    publication_policy=config.get('publication_policy')
    if 'publication_policy' in config:
        from bench.candidates.publication_policy import POLICY,review as publication_review
        if publication_policy!=POLICY:
            raise ValueError('Неизвестная политика роли публикации')
    language_review=None
    if 'language_policy' in config:
        from bench.candidates.language_review import load_review
        language_review=load_review(config['language_policy'])
    limits=config.get('candidate_limits',{})
    if set(limits)-{r['domain'] for r in domains} or any(type(v) is not int or not 1<=v<=config['max_records'] for v in limits.values()):
        raise ValueError('Неверный доменный предел кандидатов')
    paused=config.get('paused_domains',[])
    if not isinstance(paused,list) or any(not isinstance(host,str) or host not in {r['domain'] for r in domains} for host in paused) or len(set(paused))!=len(paused):
        raise ValueError('Пауза источников должна содержать разные домены из рецепта')
    actual={name:package_version(name) for name in config['dependencies']}
    if actual!=config['dependencies']:raise ValueError('Версии зависимостей не совпадают с рецептом')
    run_dir=work/'cc-rebuild/runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run_dir.mkdir(parents=True,exist_ok=False)
    commit=subprocess.run(['git','-C',str(Path(__file__).resolve().parents[2]),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    (run_dir/'run.json').write_text(json.dumps(dict(config=config,domains=domains,dependencies=actual,bench_commit=commit,
                                                  max_seconds=max_seconds,max_bytes=max_bytes),ensure_ascii=False,indent=2)+'\n')
    http=HTTP(work/'raw/cc/http-cache',delay=.3,timeout=20)
    docs=[]
    failures=[]
    counts=Counter()
    start=time.monotonic()
    considered=set()
    for domain in domains:
        if domain['domain'] in paused:
            counts['paused_domain:'+domain['domain']]+=1
            continue
        if counts['budget_stop']:break
        for snapshot in sorted(domain['snapshots'].split(';')):
            if time.monotonic()-start>max_seconds or http.bytes>=max_bytes:
                counts['budget_stop']+=1
                break
            if counts['warc_attempts']>=config['max_records']:
                break
            try:
                selected=candidates(http,snapshot,domain['domain'],seed=config['seed'],
                                    max_blocks=config['max_blocks'],path_prefix=domain.get('path_prefix',''))
            except Exception as exc:
                counts['index_error:'+type(exc).__name__]+=1
                print(json.dumps(dict(counts,domain=domain['domain'],snapshot=snapshot)),flush=True)
                continue
            selected=[r for r in selected if re.search(domain['url_pattern'],r['url']) and
                      (not r.get('languages') or 'rus' in r['languages'])]
            for record in selected[:limits.get(domain['domain'],config['candidate_limit'])]:
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
                    provenance=rsdn_primary_header(payload,record['url']) if provenance_policy else None
                    if provenance_policy in {'primary-source-rsdn-habr-v5','primary-source-rsdn-habr-kontur-v6','primary-source-rsdn-habr-kontur-liveinternet-v7','primary-source-series-v8'}:
                        origin=habr_source_marker(payload,record['url'])
                        if origin['status'] in {'explicit-translation','explicit-reprint'}:
                            counts['habr_source:'+origin['status']]+=1
                            counts['habr_source_role:'+origin['role']]+=1
                            continue
                    coauthors=None
                    if provenance_policy in {'primary-source-rsdn-habr-kontur-v6','primary-source-rsdn-habr-kontur-liveinternet-v7','primary-source-series-v8'}:
                        origin=kontur_author_origin(payload,record['url'])
                        if origin['status']=='unbound-preview-credit':
                            counts['kontur_unbound_preview_credit']+=1;continue
                        coauthors=kontur_coauthors(payload,record['url'])
                        if coauthors['status']!='not-applicable':counts['kontur_coauthors:'+coauthors['status']]+=1
                    if provenance_policy=='primary-header-rsdn-habr-v4' and habr_translation_marker(payload,record['url'])=='explicit-translation':
                        counts['habr_primary_header_translation']+=1;continue
                    translation=(rsdn_translation_marker(payload,record['url']) if provenance_policy in {'rsdn-primary-header-profile-translation-v3','primary-header-rsdn-habr-v4','primary-source-rsdn-habr-v5','primary-source-rsdn-habr-kontur-v6','primary-source-rsdn-habr-kontur-liveinternet-v7','primary-source-series-v8'}
                                 else provenance['translation_status'] if provenance else None)
                    if translation=='explicit-translation':
                        if provenance['translation_status']!='explicit-translation':counts['primary_header_translation_without_author']+=1
                        counts['primary_header_translation']+=1;continue
                    publication=None
                    if publication_policy is not None:
                        publication=publication_review(payload,record['url'])
                        counts['publication_role:'+publication['status']]+=1
                        if publication['status']=='explicit-advertorial':continue
                    clean,metadata=extractor(payload,record['url'])
                    if completeness_policy is not None:
                        markers=metadata.get('source_incomplete_markers')
                        if not isinstance(markers,list) or any(not isinstance(m,str) or not m.strip() for m in markers):
                            raise ValueError('Нет корректной диагностики полноты источника')
                        if markers:
                            counts['incomplete_source']+=1
                            for marker in set(markers):counts['incomplete_source:'+marker]+=1
                            continue
                    if provenance_policy in {'primary-source-rsdn-habr-kontur-liveinternet-v7','primary-source-series-v8'}:
                        marker=liveinternet_series_source_marker if provenance_policy=='primary-source-series-v8' else liveinternet_source_marker
                        origin=marker(payload,record['url'],extracted_raw=clean.raw)
                        if origin['status']!='not-applicable':counts['liveinternet_source:'+origin['status']]+=1
                        if origin['status'] in {'explicit-reprint','extracted-comment'}:
                            counts['liveinternet_source_role:'+origin['role']]+=1;continue
                    author=author_identity(record['url'],metadata)
                    members=None;profile_keys=[]
                    if provenance and provenance['author_status']!='not-applicable':
                        members=sorted({author_identity(record['url'],{'author':a}) for a in provenance['authors']}) or ['domain:rsdn.org']
                        author='; '.join(members)
                        counts['author_provenance:'+provenance['author_status']]+=1
                        if provenance_policy in {'rsdn-primary-header-profile-v2','rsdn-primary-header-profile-translation-v3','primary-header-rsdn-habr-v4','primary-source-rsdn-habr-v5','primary-source-rsdn-habr-kontur-v6','primary-source-rsdn-habr-kontur-liveinternet-v7','primary-source-series-v8'}:
                            profile_keys=rsdn_profile_constraints(payload,record['url'])
                            if profile_keys:counts['profile_constrained_documents']+=1
                    elif coauthors and coauthors['status']=='explicit-coauthors':
                        members=sorted({author_identity(record['url'],{'author':a}) for a in coauthors['authors']})
                        author='; '.join(members)
                    if metadata_exclusion(author):
                        counts['metadata_spam']+=1;continue
                    features=text_features(clean.norm)
                    if not config['min_words']<=features['words']<=config['max_words'] or features['cyrillic']<config['min_cyrillic']:
                        counts['filter']+=1;continue
                    if re.search(r'(?i)(перевод\s*[:—]|перев[её]л[а]?\s*[:—]|перепечатано)',clean.raw):
                        counts['translation_or_reprint']+=1;continue
                    language=None
                    if language_review is not None:
                        language=language_review.check(clean.norm)
                        counts['language:'+language['language']]+=1
                        if language['review_required']:
                            counts['language_review_required']+=1;continue
                    rid=hashlib.sha256((snapshot+'\0'+record['url']).encode()).hexdigest()[:24]
                    folder=work/'cc-rebuild'/snapshot/domain['domain']
                    folder.mkdir(parents=True,exist_ok=True)
                    path,raw_path=folder/(rid+'.md'),folder/(rid+'.raw.md')
                    path.write_text(clean.norm);raw_path.write_text(clean.raw)
                    doc=dict(id=rid,url=url,snapshot=snapshot,domain=domain['domain'],
                                     subgenre=domain['subgenre'],author=author,
                                     sha256=hashlib.sha256(path.read_bytes()).hexdigest(),text=clean.norm,
                                     raw_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                                     path=str(path),raw_path=str(raw_path),record=record,
                                     warc_sha256=hashlib.sha256(compressed).hexdigest(),author_method=metadata.get('author_method'))
                    if members is not None:doc.update(authors=members,author_method=provenance_policy+':'+(coauthors['status'] if coauthors and coauthors['status']=='explicit-coauthors' else provenance['author_status']))
                    if profile_keys:doc['author_quota_keys']=profile_keys
                    if config['clean_version']!=VERSION:
                        doc.update(clean_version=config['clean_version'],extraction_metadata=metadata)
                    if language is not None:doc['language_review']=language
                    if publication is not None:doc['publication_review']=publication
                    docs.append(doc)
                    counts['accepted']+=1
                except Exception as exc:
                    counts['error:'+type(exc).__name__]+=1
                    failures.append(dict(domain=domain['domain'],snapshot=snapshot,record=record,
                                         error=type(exc).__name__,http_status=getattr(exc,'code',None)))
            print(json.dumps(dict(counts,domain=domain['domain'],snapshot=snapshot,bytes=http.bytes)),flush=True)
    unique,duplicates=deduplicate(docs,config['dedup_threshold'])
    selected=quota(unique,seed=config['seed'],target=config['target'],subgenres=config['subgenres'],
                   domain_cap=config['domain_cap'],author_cap=config['author_cap'])
    groups=group_hashes(selected)
    output=work/'cc-rebuild'
    output.mkdir(parents=True,exist_ok=True)
    # Только локальный промежуточный реестр; не публикуется вместе с агрегатами.
    (output/'selected.json').write_text(json.dumps([{k:v for k,v in d.items() if k!='text'} for d in selected],ensure_ascii=False,indent=2)+'\n')
    (output/'failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2)+'\n')
    complete=len(selected)==config['target'] and not counts['budget_stop'] and not any(k.startswith(('index_error:','error:')) for k in counts)
    version_fields={} if config['clean_version']==VERSION else dict(clean_version=config['clean_version'])
    if completeness_policy is not None:version_fields['completeness_policy']=completeness_policy
    if publication_policy is not None:version_fields['publication_policy']=publication_policy
    if language_review is not None:version_fields['language_review']=language_review.fingerprint
    (output/'summary.json').write_text(json.dumps(dict(counts,unique=len(unique),selected=len(selected),duplicates=len(duplicates),
                                                    elapsed_seconds=round(time.monotonic()-start,2),transferred_bytes=http.bytes,requests=http.requests,
                                                    target_met=len(selected)==config['target'],complete=complete,**version_fields),ensure_ascii=False,indent=2)+'\n')
    import shutil
    shutil.copyfile(output/'selected.json',run_dir/'selected.json')
    shutil.copyfile(output/'summary.json',run_dir/'summary.json')
    shutil.copyfile(output/'failures.json',run_dir/'failures.json')
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
