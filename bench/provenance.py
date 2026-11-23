"""Кандидат происхождения по первичной RSDN-шапке; без изменения clean-v3."""
from urllib.parse import urlsplit
from .html_structure import decode

def rsdn_primary_header(content: bytes | str,url: str) -> dict:
    """Отдельные роли автора/переводчика; неизвестное не означает оригинал."""
    unknown=dict(translation_status='unknown-primary-header',author_status='unknown',authors=[])
    host=(urlsplit(url).hostname or '').removeprefix('www.')
    if host!='rsdn.org':return unknown|dict(translation_status='not-applicable',author_status='not-applicable')
    from lxml import html
    source=decode(content)
    if not source.strip():return unknown
    tree=html.fromstring(source);headers=[]
    text=lambda node:' '.join(' '.join(node.itertext()).split())
    for node in tree.xpath('//body/h5[span[contains(concat(" ",normalize-space(@class)," ")," title ")]]'):
        fields=[]
        for label in node.xpath('./span[contains(concat(" ",normalize-space(@class)," ")," title ")]'):
            value=label.getnext()
            if value is not None and value.tag=='span' and 'value' in value.get('class','').split():fields.append((text(label).casefold(),value))
        authors=[(label,value) for label,value in fields if label in {'автор:','авторы:'}]
        if authors:headers.append((node,fields,authors))
    if len(headers)!=1:return unknown
    node,fields,authors=headers[0]
    if len(authors)!=1 or not text(authors[0][1]) or node.xpath('.//script|.//style|.//template|.//noscript'):return unknown
    translations=[value for label,value in fields if label=='перевод:']
    if len(translations)>1:return unknown
    result=unknown|dict(translation_status='explicit-translation' if translations and text(translations[0]) else 'no-explicit-translation-in-header')
    label,value=authors[0];links=value.xpath('./a[@href]')
    if label=='авторы:':
        if (len(links)<2 or any(n.tag not in {'a','br'} for n in value)
                or ''.join(value.xpath('./text()')).strip() or len(value.xpath('.//a'))!=len(links)):return result
        names=[text(a).casefold() for a in links]
        if any(not name or len(name)>200 for name in names) or len(set(names))!=len(names):return result
        return result|dict(author_status='explicit-coauthors',authors=names)
    if value.xpath('.//br') or len(value.xpath('.//a'))>1:return result
    name=text(value).casefold()
    if len(name)>200:return result
    return result|dict(author_status='primary-author-field',authors=[name])
