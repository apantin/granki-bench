"""Отдельный opt-in маркер первичного происхождения Habr; старые рецепты прежние."""
import re
from urllib.parse import urlsplit
from .html_structure import decode
from .provenance import habr_translation_marker

_BLOCKED = {'blockquote','q','pre','code','script','style','template','noscript',
            'svg','math','aside','nav','footer','header','article','h1','h2','h3','h4','h5','h6'}
_INTRO = re.compile(r'^Предлагаю(?:\s+вашему\s+вниманию)?\s+перевод'
                    r'(?:\s+(?:полезной|интересной|этой|следующей|зарубежной|оригинальной)){0,2}'
                    r'\s+(?:статьи|публикации|поста|материала)\b',re.I)
_REPOST = re.compile(r'(?:^|\s)(?:P\.?S\.?|П\.?С\.?)\s*:?\s*Оригинал\s+тут\b'
                     r'.{0,400}?\bне\s+могу\s+опубликовать\s+топик[-‑ ]ссылку\b'
                     r'.{0,150}$',re.I)


def _web_address(value):
    try:
        parsed=urlsplit(value)
        return parsed.scheme in {'http','https'} and bool(parsed.hostname)
    except ValueError:return False


def habr_source_marker(content: bytes | str, url: str) -> dict:
    """Возвращает status/role, для авторского body — диапазон нормализованного текста.

    Неизвестное или отсутствие метки не доказывает оригинальность.
    Переводчики/авторы не переименовываются; текст не очищается.
    """
    result=lambda status,role:dict(status=status,role=role)
    if (urlsplit(url).hostname or '').removeprefix('www.')!='habr.com':
        return result('not-applicable','other-host')
    unknown=result('unknown-primary-article','ambiguous-or-unsupported')
    source=decode(content)
    if not source.strip():return unknown
    from lxml import html
    tree=html.fromstring(source)
    bodies=tree.xpath('//*[@id="post-content-body"]')
    if len(bodies)!=1:return unknown
    main=bodies[0]
    articles=[n for n in main.iterancestors() if n.tag=='article']
    if len(articles)!=1:return unknown
    article=articles[0];classes=article.get('class','').split()
    role=lambda name:'contains(concat(" ",normalize-space(@class)," ")," '+name+' ")'
    if 'tm-article-presenter__content' in classes:
        status=habr_translation_marker(content,url)
        if status=='explicit-translation':return result(status,'modern-header')
        if status!='no-explicit-translation-in-header':return unknown
    elif {'post','post_full'}<=set(classes):
        wrappers=article.xpath('./div['+role('post__wrapper')+']')
        if len(wrappers)!=1 or wrappers[0] not in main.iterancestors():return unknown
        wrapper=wrappers[0]
        titles=[n for n in wrapper.xpath('.//h1[normalize-space()]') if main not in n.iterancestors()]
        active=[n for n in wrapper.xpath('.//script|.//style|.//template|.//noscript') if main not in n.iterancestors()]
        marks=wrapper.xpath('./ul['+role('post__marks')+']')
        if len(titles)!=1 or active or len(marks)>1:return unknown
        labels=marks[0].xpath('./li['+role('inline-list__item_post-type')+']/span['+role('post__type-label')+']') if marks else []
        translations=[n for n in labels if n.get('title','').strip().casefold()=='перевод' or ' '.join(n.text_content().split()).casefold()=='перевод']
        if translations:
            if len(translations)!=1:return unknown
            label=translations[0]
            if label.get('title','').strip().casefold()!='перевод' or ' '.join(label.text_content().split()).casefold()!='перевод':return unknown
            return result('explicit-translation','legacy-header')
    else:return unknown

    # Границы первого/последнего авторского высказывания определяются до
    # удаления кода/цитат: их пропуск не делает следующий абзац вступлением.
    chunks=[];offset=0
    for node in main.xpath('.//text()'):
        text=' '.join(str(node).split())
        if not text:continue
        owner=node.getparent().getparent() if node.is_tail else node.getparent()
        ancestors=[]
        for ancestor in [owner,*owner.iterancestors()]:
            ancestors.append(ancestor)
            if ancestor is main:break
        blocked=any(n.tag in _BLOCKED for n in ancestors if n is not main)
        links=[n for n in ancestors if n.tag=='a' and _web_address(n.get('href',''))]
        block=next(n for n in ancestors if n is main or n.tag in {'p','li','div'})
        chunks.append(dict(start=offset,end=offset+len(text),blocked=blocked,link=bool(links),text=text,block=block))
        offset+=len(text)+1
    text=' '.join(c['text'] for c in chunks)
    safe=lambda start,end:not any(c['blocked'] and c['start']<end and c['end']>start for c in chunks)
    intro=_INTRO.match(text)
    if intro and safe(0,intro.end()):
        if re.search(r'\b(?:мо[ийяе]|моими|свои|собственн\w*)\b.{0,30}\bкомментари|\bкомментари\w*.{0,30}\b(?:мо[ийяе]|моими|свои|собственн\w*)\b',text[:600],re.I):
            return result('unknown-source-scope','mixed-source-declaration')
        return result('explicit-translation','opening-declaration')|dict(evidence_span=[0,intro.end()])
    tail_start=max(0,len(text)-800)
    trailer=_REPOST.search(text[tail_start:])
    if trailer:
        start,end=tail_start+trailer.start(),tail_start+trailer.end()
        evidence=[c for c in chunks if c['start']<end and c['end']>start]
        printed_urls=re.findall(r'https?://[^\s<>"\']+',text[start:end])
        has_address=any(c['link'] for c in evidence) or any(_web_address(u.rstrip('.,;:)')) for u in printed_urls)
        if safe(start,end) and len({c['block'] for c in evidence})==1 and has_address:
            return result('explicit-reprint','closing-repost-declaration')|dict(evidence_span=[start,end])
    return result('no-explicit-source-marker','recognized-primary-article')
