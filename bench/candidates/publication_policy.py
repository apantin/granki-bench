"""Явная издательская роль первичной статьи; не общий допуск качества."""
from urllib.parse import urlsplit
from lxml import html
from ..html_structure import decode
from ..publication_body import bind
from .publication_context import publisher_context

POLICY = 'primary-advertorial-v1'


def review(content, url):
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    result = dict(policy=POLICY, status='not-applicable', markers=[], admitted=False)
    if host != 'xakep.ru':
        return result
    tree = html.fromstring(decode(content))
    publication = bind(tree, host)
    if publication is None:
        return result | dict(status='unresolved-primary-publication')
    facts = publisher_context(tree, publication['main'], publication['title'], host)
    markers = facts['primary_publication_markers']
    return result | dict(status='explicit-advertorial' if markers else 'no-explicit-marker', markers=markers)
