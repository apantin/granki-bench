"""Происхождение имени автора, без изменения прежней очистки и нормы."""
from copy import deepcopy
import json
import re
import unicodedata
from urllib.parse import urlsplit
from .html_structure import decode


def normalize(value):
    return ' '.join(unicodedata.normalize('NFC',value).casefold().split()) if isinstance(value,str) else ''


def role(token):return 'contains(concat(" ",normalize-space(@class)," ")," '+token+' ")'


def kontur_author_origin(content: bytes | str,url: str) -> dict:
    result=lambda status,why:dict(status=status,role=why)
    if (urlsplit(url).hostname or '').removeprefix('www.')!='kontur.ru':return result('not-applicable','other-host')
    unknown=lambda why:result('unresolved',why)
    source=decode(content)
    if not source.strip():return unknown('empty-source')
    from lxml import html
    from trafilatura.metadata import extract_metadata
    tree=html.fromstring(source)
    for comment in tree.xpath('//comment()'):
        if comment.getparent() is not None:comment.drop_tree()
    headers=tree.xpath('//div['+role('content-block_article-announce')+']')
    bodies=tree.xpath('//*[@id="ArticleItem"]');titles=tree.xpath('//h1')
    if (len(headers)!=1 or len(bodies)!=1 or len(titles)!=1 or not normalize(titles[0].text_content())
            or headers[0] not in titles[0].iterancestors() or headers[0] is bodies[0]
            or headers[0] in bodies[0].iterancestors() or bodies[0] in headers[0].iterancestors()):return unknown('ambiguous-primary-components')
    metadata=extract_metadata(deepcopy(tree),default_url=url);name=normalize(getattr(metadata,'author',None))
    if not name:return unknown('no-extracted-person-name')
    # Упоминание в основной прозе удерживает неоднозначность; авторство не доказано.
    if any(name in normalize(n.text_content()) or name in normalize(' '.join(n.xpath('.//@content'))) for n in headers+bodies):
        return result('primary-name-present','name-within-primary-components; authorship-not-proven')
    articles=[]
    for node in tree.xpath('//script[@type="application/ld+json"]'):
        try:value=json.loads(node.text or '')
        except (ValueError,RecursionError):continue
        if isinstance(value,dict) and value.get('@type')=='Article':articles.append(value)
    if (len(articles)!=1 or normalize(articles[0].get('headline'))!=normalize(titles[0].text_content())
            or not isinstance(articles[0].get('author'),dict) or articles[0]['author'].get('@type')!='Organization'):
        return unknown('no-matching-organization-article')
    for node in tree.xpath('//head/meta'):
        keys=' '.join(node.get(k,'') for k in ['name','property','itemprop']).casefold()
        # Twitter creator — аккаунт сайта, не связь извлечённого ФИО с автором.
        if (node.get('content','').strip() and any(k in keys for k in ['author','creator'])
                and node.get('name','').casefold()!='twitter:creator'):
            return unknown('explicit-head-credit-requires-review')
    if tree.xpath('//head/link[@rel="author"]'):return unknown('head-author-link-requires-review')
    selector='//article['+role('tile_articlePreview')+']//*['+role('byLineBlock-author')+']'
    previews=tree.xpath(selector);matching=sum(normalize(n.text_content())==name for n in previews)
    if not matching:return unknown('name-not-bound-to-preview-credit')
    masked=deepcopy(tree)
    for node in masked.xpath(selector):node.drop_tree()
    after=extract_metadata(masked,default_url=url)
    if getattr(after,'author',None):return unknown('name-survives-preview-removal')
    return result('unbound-preview-credit','organization-article; no-primary-name; preview-removal-clears-author')|dict(preview_byline_count=len(previews),matching_preview_credits=matching)


def kontur_coauthors(content: bytes | str,url: str) -> dict:
    """Явный совместный экспертный кредит для квот; не допуск всего текста."""
    result=lambda status,role,authors=():dict(status=status,role=role,authors=list(authors))
    if (urlsplit(url).hostname or '').removeprefix('www.')!='kontur.ru':
        return result('not-applicable','other-host')
    from lxml import html
    source=decode(content)
    if not source.strip():return result('unresolved','empty-source')
    tree=html.fromstring(source)
    headers=tree.xpath('//div['+role('content-block_article-announce')+']')
    bodies=tree.xpath('//*[@id="ArticleItem"]');titles=tree.xpath('//h1')
    if (len(headers)!=1 or len(bodies)!=1 or len(titles)!=1
            or not normalize(titles[0].text_content()) or headers[0] not in titles[0].iterancestors()
            or headers[0] is bodies[0] or headers[0] in bodies[0].iterancestors()
            or bodies[0] in headers[0].iterancestors()):
        return result('unresolved','ambiguous-primary-components')
    names=headers[0].xpath('.//span['+role('article-announce-autor-block__name')+']')
    if len(names)!=1 or len(names[0]):return result('unresolved','ambiguous-primary-byline')
    person=r'[а-яё]+(?:-[а-яё]+)?(?: [а-яё]+(?:-[а-яё]+)?){1,2}'
    pattern=re.compile('('+person+') и ('+person+'), эксперты системы интернет-отч[её]тности контур\\.экстерн')
    credits=[]
    for node in bodies[0].xpath('.//p/em'):
        match=pattern.fullmatch(normalize(node.text_content()))
        if match is None:continue
        paragraph=node.getparent()
        if (len(node) or node.attrib or paragraph.attrib or len(paragraph)!=1
                or (paragraph.text or '').strip() or (node.tail or '').strip()):
            return result('unresolved','mixed-credit-paragraph')
        # Известные контейнеры публикации; цитаты/таблицы/реклама не кредит автора.
        allowed={'text','js-mediator-article','lp-forms','lp-styles'}
        for ancestor in paragraph.iterancestors():
            if ancestor is bodies[0]:break
            if ancestor.tag!='div' or set(ancestor.get('class','').split())-allowed:
                return result('unresolved','credit-outside-publisher-prose')
        credits.append(match.groups())
    if not credits:return result('no-explicit-coauthors','no-supported-joint-credit')
    if (len(credits)!=1 or credits[0][0]==credits[0][1]
            or normalize(names[0].text_content()) not in credits[0]):
        return result('unresolved','ambiguous-joint-credit')
    return result('explicit-coauthors','standalone-primary-expert-credit; quotas-only',sorted(credits[0]))
