"""Происхождение имени автора, без изменения прежней очистки и нормы."""
from copy import deepcopy
import json
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
