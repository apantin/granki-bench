"""Узкие явные source-отказы; отсутствие маркера не означает общий допуск."""
import re
from urllib.parse import urlsplit

from lxml import html

from .html_structure import choose_editorial_main, choose_main, decode
from .publication_body import bind

POLICY = 'explicit-primary-text-v1'
HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
FOREIGN_SCOPES = {'blockquote', 'q', 'pre', 'code', 'aside', 'nav'}


def text(node):
    return ' '.join(node.text_content().split())


def classes(node):
    return set(node.get('class', '').split())


def service(node, url):
    if node.tag in {'script', 'style', 'meta', 'link'}:
        return True
    if {'incut', 'read'} <= classes(node):
        headings, lists = node.xpath('./p'), node.xpath('./ul')
        return (len(node) == 2 and len(headings) == len(lists) == 1
                and text(headings[0]).casefold() in {'читайте статьи по теме:', 'читайте также:'}
                and linked_list(lists[0]) and not (node.text or '').strip()
                and not any((child.tail or '').strip() for child in node))
    if 'share_footer_blog' in classes(node):
        return not ''.join(node.xpath('.//text()[not(ancestor::script or ancestor::style)]')).strip()
    slug = urlsplit(url).path.rstrip('/').rsplit('/', 1)[-1].removesuffix('.html')
    return node.tag == 'span' and not len(node) and bool(slug) and text(node) == slug


def translation_credit(main, host, url):
    inline = {'a', 'b', 'strong', 'em', 'i', 'span', 'small', 'br'}
    for node in main.xpath('.//p'):
        if node.getparent() is not main or any(n.tag not in inline for n in node.iterdescendants()):
            continue
        if any(n.tag in FOREIGN_SCOPES for n in node.iterancestors() if n is not main):
            continue
        value = text(node)
        if not re.match(r'^(?:Адаптация материала\s+)?Перевод(?:\s+и\s+адаптация)?\s+(?:материала|статьи|текста)\s+\S', value, re.I):
            continue
        emphasis = node.xpath('./i|./em')
        if not emphasis or not any('перевод' in text(n).casefold() for n in emphasis):
            continue
        links = node.xpath('.//a[@href]')
        external = False
        for link in links:
            try:
                target = urlsplit(link.get('href', ''))
            except ValueError:
                continue
            if target.scheme in {'http', 'https'} and target.hostname and target.hostname.removeprefix('www.') != host:
                external = True
        if not external or (node.tail or '').strip():
            continue
        if all(not isinstance(n.tag, str) or service(n, url) or not text(n) for n in list(node.itersiblings())):
            return main.getroottree().getpath(node)
    return None


def linked_list(node):
    links = node.xpath('.//a[@href]')
    return (node.tag in {'ul', 'ol'} and bool(links)
            and not ''.join(node.xpath('.//text()[not(ancestor::a)]')).strip())


def webinar_outline(main, title, url):
    if title is None or not re.match(r'^(?:\[\s*Запись вебинара\s*\]|Запись вебинара\s*:)', text(title), re.I):
        return False
    if (main.text or '').strip():
        return False
    plan = False; related = False; lists = 0
    for node in main:
        if (node.tail or '').strip():
            return False
        if not isinstance(node.tag, str) or service(node, url) or not text(node):
            continue
        value = text(node)
        if node is title:
            continue
        if node.tag in HEADINGS:
            if value.casefold().rstrip(':') == 'план вебинара' and not plan:
                plan = True
            elif plan and value.casefold().rstrip(':') == 'ссылки на полезные материалы по теме':
                related = True
            else:
                return False
        elif related:
            if not linked_list(node):
                return False
        elif plan and node.tag in {'ul', 'ol'}:
            lists += 1
        elif (not plan and value.casefold().startswith('скачать презентацию')
              and bool(node.xpath('.//a[@href]'))):
            continue
        else:
            return False
    return plan and lists > 0


def review(content, url):
    result = dict(policy=POLICY, status='not-applicable', markers=[], admitted=False)
    decoded = decode(content)
    if not decoded.strip():
        return result
    tree = html.fromstring(decoded); host = (urlsplit(url).hostname or '').removeprefix('www.')
    publication = bind(tree, host)
    if publication is not None:
        main, title = publication['main'], publication['title']
    else:
        main, _ = choose_main(tree, host)
        if main is None:
            main, _ = choose_editorial_main(tree, host)
        titles = tree.xpath('//h1'); title = titles[0] if len(titles) == 1 else None
    if main is None:
        return result
    credit = translation_credit(main, host, url)
    if credit:
        return result | dict(status='explicit-translation-credit', markers=['terminal-emphasized-external-original-credit'], evidence_xpath=credit)
    if webinar_outline(main, title, url):
        return result | dict(status='explicit-webinar-outline', markers=['recording-title-and-plan-without-independent-prose'])
    return result | dict(status='no-explicit-marker')
