"""Явный ведущий CMS-кредит репоста в одной первичной статье LiveJournal."""
import re
from urllib.parse import urlsplit
from lxml import html
from .html_structure import decode
from .publication_body import has

POLICY='primary-source-livejournal-v9'


def text(value):return ' '.join((value or '').split())


def account(value,kind):
    try:
        target=urlsplit(value)
        if target.scheme not in {'http','https'} or target.username or target.password or target.port:return None
    except ValueError:return None
    match=re.fullmatch(r'([a-z0-9][a-z0-9-]*)\.livejournal\.com',target.hostname or '')
    if match is None or kind=='profile' and target.fragment:return None
    valid=(target.path in {'/','/profile'} and not target.query if kind=='profile'
           else re.fullmatch(r'/[0-9]+\.html',target.path) is not None)
    return match[1] if valid else None


def livejournal_source_marker(content:bytes|str,url:str)->dict:
    """Не устанавливает физическую личность или собственность аккаунтов.

    Проверяется ведущая строка CMS со связанными ljuser-профилем и permalink.
    Отсутствие такого кредита не означает содержательного допуска.
    """
    owner=account(url,'post')
    result=dict(policy=POLICY,status='not-applicable',role='other-host-or-non-post',admitted=False)
    if owner is None:return result
    try:tree=html.fromstring(decode(content))
    except (ValueError,html.etree.ParserError):return result|dict(status='unresolved-primary-publication',role='unparseable-source')
    for comment in tree.xpath('//comment()'):
        if comment.getparent() is not None:comment.drop_tree()
    bodies=[n for n in tree.xpath('//article') if has(n,'b-singlepost-body') and has(n,'entry-content')]
    if len(bodies)!=1 or any(has(p,'b-singlepost-body') for p in bodies[0].iterancestors()):
        return result|dict(status='unresolved-primary-publication',role='ambiguous-primary-article')
    node=bodies[0]
    # Допускается одна ведущая прозрачная оболочка. Поздняя ссылка/цитата в
    # собственной прозе не превращается в CMS-кредит всей публикации.
    if not text(node.text) and len(node) and node[0].tag in {'p','div'}:node=node[0]
    prefix=text(node.text)
    connector={'Оригинал взят у':'в','Originally posted by':'at'}.get(prefix)
    if connector is None:return result|dict(status='no-explicit-repost-credit',role='no-leading-cms-credit')
    unresolved=result|dict(status='unresolved-repost-credit',role='incomplete-or-conflicting-leading-credit')
    if len(node)<2:return unresolved
    badge,original=node[0],node[1]
    if (badge.tag!='span' or not has(badge,'ljuser') or not has(badge,'i-ljuser')
            or text(badge.tail)!=connector or original.tag!='a' or not text(original.text_content())):return unresolved
    declared=badge.get('data-ljuser','').casefold().replace('_','-')
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',declared):return unresolved
    profiles=[n for n in badge.xpath('.//a[@href]') if has(n,'i-ljuser-profile')]
    names=[n for n in badge.xpath('.//a[@href]') if has(n,'i-ljuser-username')]
    if (len(badge.xpath('.//a[@href]'))!=2 or len(profiles)!=1 or len(names)!=1 or account(profiles[0].get('href'),'profile')!=declared
            or account(names[0].get('href'),'profile')!=declared
            or text(names[0].text_content()).casefold().replace('_','-')!=declared):return unresolved
    origin=account(original.get('href',''),'post')
    if origin is None or (declared==owner)!=(origin==owner):return unresolved
    if declared==owner:return result|dict(status='self-repost-credit',role='same-publishing-account; authorship-not-proven')
    return result|dict(status='explicit-repost-credit',role='leading-cms-credit-to-other-publishing-account')
