"""Opt-in расширение происхождения: целая цитата с навигацией серии CMS."""
import re
import unicodedata
from urllib.parse import urlsplit
from .html_structure import decode
from .liveinternet_body import bind,has
from .liveinternet_provenance import liveinternet_source_marker,quoted_origin


def text(value):return ' '.join(unicodedata.normalize('NFC',value or '').split())


def local_target(link,owner,kind):
    if link.tag!='a' or set(link.attrib)!={'href'} or len(link) or not text(link.text):return None
    try:target=urlsplit(link.get('href',''))
    except ValueError:return None
    if (target.scheme not in {'','http','https'} or target.netloc.casefold() not in {'','liveinternet.ru','www.liveinternet.ru'}
            or target.query or target.fragment):return None
    match=re.fullmatch(re.escape(owner)+'/'+kind+r'([1-9][0-9]*)/?',target.path)
    return match[1] if match else None


def series_navigation(node,bound,url):
    """Полная известная форма CMS, включая нелинкованную текущую часть/h1."""
    title=bound['title'];owner=bound['owner_path']
    if (title is None or node.tag!='blockquote' or node.attrib or text(node.text) or len(node)<3):return False
    head=node[0]
    if (head.tag!='b' or head.attrib or len(head)!=1 or text(head.text)!='Серия сообщений "'
            or text(head[0].tail)!='":' or text(head.tail)
            or local_target(head[0],owner,'rubric/') is None):return False
    # Не собираем text_content(): иначе произвольная вложенная проза станет
    # похожа на служебные строки. Каждый a/br и весь хвост проверяются явно.
    if node[1].tag!='br' or node[1].attrib or len(node[1]) or text(node[1].text):return False
    lines=[];prefix=node[1].tail or '';link=None;suffix=''
    for child in list(node)[2:]:
        if child.tag=='br' and not child.attrib and not len(child) and not text(child.text):
            lines.append((text(prefix),link,text(suffix)))
            prefix=child.tail or '';link=None;suffix=''
        elif child.tag=='a' and link is None:
            link=child;suffix=child.tail or ''
        else:return False
    if text(prefix) or link is not None or text(suffix):lines.append((text(prefix),link,text(suffix)))
    numbers=[];targets=set();current=0;ellipsis=0
    current_number=re.fullmatch(r'/users/[^/]+/post([0-9]+)/?',urlsplit(url).path)[1]
    for i,(prefix,link,suffix) in enumerate(lines):
        if prefix=='...' and link is None and not suffix:
            ellipsis+=1
            if ellipsis>1 or i==0 or i==len(lines)-1:return False
            continue
        match=re.fullmatch(r'Часть ([1-9][0-9]*) -(?: (.*))?',prefix)
        if match is None or suffix:return False
        number=int(match[1])
        if numbers and number<=numbers[-1]:return False
        numbers.append(number)
        if link is None:
            if match[2]!=text(title.text_content()):return False
            current+=1
        else:
            target=local_target(link,owner,'post')
            if match[2] is not None or target is None or target==current_number or target in targets:return False
            targets.add(target)
    return current==1 and bool(targets)


def liveinternet_series_source_marker(content:bytes|str,url:str,*,extracted_raw:str|None=None)->dict:
    """V1 неизменён; только mixed-цитата плюс строго распознанная навигация.

    Не меняет очистку или атрибуцию; extracted_raw — зарегистрированный v3.
    Чужой издатель по-прежнему требует всех проверок quoted_origin V1.
    """
    previous=liveinternet_source_marker(content,url,extracted_raw=extracted_raw)
    if previous.get('role')!='mixed-primary-and-quoted-post':return previous
    from lxml import html
    tree=html.fromstring(decode(content))
    for node in tree.xpath('//comment()'):
        if node.getparent() is not None:node.drop_tree()
    bound=bind(tree,'liveinternet.ru',url)
    if bound is None:return previous
    main=bound['main']
    quotes=[n for n in main if has(n,'MESS') and has(n,'QUOT_T')]
    footers=main.xpath('./blockquote')
    if (len(quotes)!=1 or len(footers)!=1 or main.index(footers[0])<=main.index(quotes[0])
            or not series_navigation(footers[0],bound,url)):return previous
    footers[0].drop_tree()  # Сохраняет хвост: собственный вывод не исчезнет.
    result=quoted_origin(bound,url)
    if result is None or result['status']!='explicit-reprint':return previous
    return result|dict(role='whole-quoted-post-of-other-publisher-id; known-series-navigation-only')
