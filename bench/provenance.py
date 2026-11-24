"""Кандидат происхождения по первичной RSDN-шапке; без изменения clean-v3."""
from urllib.parse import parse_qs,urljoin,urlsplit
from .html_structure import decode


def habr_translation_marker(content: bytes | str,url: str) -> str:
    """Явная метка только в первичной шапке Habr; отсутствие не доказывает оригинал.

    Старый шаблон и неоднозначные шапки остаются unknown. Тело статьи,
    комментарии, рекомендации и упоминания переводов не классифицируются.
    """
    if (urlsplit(url).hostname or '').removeprefix('www.')!='habr.com':return 'not-applicable'
    from lxml import html
    unknown='unknown-primary-header';source=decode(content)
    if not source.strip():return unknown
    tree=html.fromstring(source)
    role=lambda name:'contains(concat(" ",normalize-space(@class)," ")," '+name+' ")'
    bodies=tree.xpath('//*[@id="post-content-body"]')
    if len(bodies)!=1:return unknown
    articles=[n for n in bodies[0].iterancestors() if n.tag=='article' and 'tm-article-presenter__content' in n.get('class','').split()]
    if len(articles)!=1:return unknown
    headers=articles[0].xpath('./div['+role('tm-article-presenter__header')+']')
    if len(headers)!=1 or headers[0].xpath('.//script|.//style|.//template|.//noscript'):return unknown
    snippets=headers[0].xpath('./div['+role('tm-article-presenter__snippet')+']')
    if len(snippets)!=1 or len(snippets[0].xpath('./h1[normalize-space()]'))!=1:return unknown
    labels=snippets[0].xpath('./div['+role('tm-article-snippet__labels')+']')
    if len(labels)>1:return unknown
    if not labels:return 'no-explicit-translation-in-header'
    markers=labels[0].xpath('./div['+role('tm-article-snippet__label')+' and '+role('tm-article-snippet__label_variant-translation')+']')
    if not markers:return 'no-explicit-translation-in-header'
    if len(markers)!=1 or ' '.join(markers[0].itertext()).strip().casefold()!='перевод':return unknown
    return 'explicit-translation'

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


def rsdn_translation_marker(content: bytes | str,url: str) -> str:
    """Дополнительный явный перевод без автора; прежний разбор v1 не меняется.

    Отсутствие поля автора мешает установить авторство, но не отменяет
    отдельное непустое поле перевода в единственной первичной шапке.
    Другие неизвестные формы остаются неизвестными.
    """
    previous=rsdn_primary_header(content,url)['translation_status']
    if previous!='unknown-primary-header':return previous
    from lxml import html
    source=decode(content)
    if not source.strip():return previous
    tree=html.fromstring(source)
    headers=tree.xpath('//body/h5[span[contains(concat(" ",normalize-space(@class)," ")," title ")]]')
    if len(headers)!=1:return previous
    node=headers[0]
    if node.xpath('.//script|.//style|.//template|.//noscript'):return previous
    labels=node.xpath('./span[contains(concat(" ",normalize-space(@class)," ")," title ")]')
    text=lambda n:' '.join(' '.join(n.itertext()).split())
    if any(text(n).casefold() in {'автор:','авторы:'} for n in labels):return previous
    translations=[n for n in labels if text(n).casefold()=='перевод:']
    if len(translations)!=1:return previous
    value=translations[0].getnext()
    if value is None or value.tag!='span' or 'value' not in value.get('class','').split() or not text(value):return previous
    return 'explicit-translation'


def _rsdn_profile_key(href: str,url: str) -> str | None:
    """Только два явных вида профильных ссылок; без сетевого разрешения/ремонта."""
    import re
    if not href or href!=href.strip() or re.search(r'\s',href):return None
    try:
        original=urlsplit(href)
        if original.scheme and not original.netloc:return None
        parsed=urlsplit(urljoin(url,href))
        if (parsed.scheme not in {'http','https'} or parsed.username or parsed.password
                or parsed.port not in {None,80,443}
                or (parsed.hostname or '').removeprefix('www.') not in {'rsdn.org','rsdn.ru'}):return None
        path=parsed.path.casefold();match=re.fullmatch(r'/account/info/([0-9]+)',path)
        values=[match.group(1)] if match else parse_qs(parsed.query,keep_blank_values=True).get('uid',[]) if path=='/users/profile.aspx' else []
        if len(values)!=1 or not re.fullmatch(r'[0-9]+',values[0]):return None
        number=values[0].lstrip('0')
        return 'rsdn-profile:'+number if number else None
    except ValueError:return None


def rsdn_profile_constraints(content: bytes | str,url: str) -> list[str]:
    """Дополнительные квотные ключи, а не допуск личности/роли или замена имени.

    Неоднозначное поле по-прежнему требует доменной квоты. Профильные ссылки
    в нём могут только усилить ограничение; переводчик/источник не учитываются.
    """
    status=rsdn_primary_header(content,url)['translation_status']
    if status not in {'explicit-translation','no-explicit-translation-in-header'}:return []
    from lxml import html
    tree=html.fromstring(decode(content));keys=set()
    for node in tree.xpath('//body/h5[span[contains(concat(" ",normalize-space(@class)," ")," title ")]]'):
        for label in node.xpath('./span[contains(concat(" ",normalize-space(@class)," ")," title ")]'):
            if ' '.join(' '.join(label.itertext()).split()).casefold() not in {'автор:','авторы:'}:continue
            value=label.getnext()
            if value is None or value.tag!='span' or 'value' not in value.get('class','').split():continue
            for link in value.xpath('.//a[@href]'):
                key=_rsdn_profile_key(link.get('href'),url)
                if key:keys.add(key)
    return sorted(keys)
