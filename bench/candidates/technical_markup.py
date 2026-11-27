"""Явные HTML-индексы и типизированные листинги; прежние очистки неизменны."""
from urllib.parse import urlsplit

from lxml import html

from .publication_cleanup import extract as previous
from ..html_structure import SKIP, choose_main, choose_editorial_main, decode
from ..publication_body import bind, has

VERSION = 'clean-v20-technical-markup-candidate'


def visible(node, main, *, code=False):
    excluded = (SKIP - {'table'}) | {'pre', 'code'}
    if code:
        excluded |= {'table', 'p', 'span', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
    for parent in node.iterancestors():
        if parent is main:
            return True
        if parent.tag in excluded:
            return False
    return False


def highlighted_listing(node):
    """code.highlight → один wrapper → нумерованные строки, без соседней прозы."""
    if (not has(node, 'highlight') or len(node) != 1 or (node.text or '').strip()
            or node[0].tag != 'div' or not has(node[0], 'wrapper')
            or (node[0].text or '').strip() or (node[0].tail or '').strip()):
        return False
    lines = list(node[0])
    if not lines or not node.text_content().strip():
        return False
    for index, line in enumerate(lines, 1):
        if (line.tag != 'div' or set(line.get('class', '').split()) != {'l', f'l{index}'}
                or (line.tail or '').strip()
                or any(child.tag not in {'span', 'wbr', 'br'} for child in line.iterdescendants())):
            return False
    return True


def repair(main):
    counts = dict(masked_highlighted_code=0, unresolved_highlighted_code=0,
                  preserved_superscripts=0, preserved_subscripts=0, unresolved_super_subscript_nodes=0)
    if main is None:
        return counts
    for node in list(main.xpath('.//code')):
        if not visible(node, main, code=True):
            continue
        if highlighted_listing(node):
            # Дальнейшие обработчики видят обычный типизированный блок кода.
            # Его исходник остаётся в HTML; в корпусе код заменяется одним [КОД].
            node.tag = 'pre'
            for child in list(node):
                node.remove(child)
            node.text = '[КОД]'
            counts['masked_highlighted_code'] += 1
        elif node.xpath('.//div|.//p|.//pre') or len([s for s in node.text_content().splitlines() if s.strip()]) > 1:
            counts['unresolved_highlighted_code'] += 1
    for node in main.xpath('.//sup|.//sub'):
        if not visible(node, main):
            continue
        value = (node.text or '').strip()
        if len(node) or not value or '\n' in value or '\r' in value:
            counts['unresolved_super_subscript_nodes'] += 1
            continue
        counter = 'preserved_superscripts' if node.tag == 'sup' else 'preserved_subscripts'
        marker = '^' if node.tag == 'sup' else '_'
        node.tag = 'span'
        node.text = marker + '(' + value + ')'
        counts[counter] += 1
    return counts


def extract(content: bytes | str, url: str = ''):
    """Opt-in: сохраняем смысл над-/подстрочного текста, маскируем явный код."""
    tree = html.fromstring(decode(content))
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    publication = bind(tree, host)
    if publication is not None:
        main, method = publication['main'], publication['method']
    else:
        main, method = choose_main(tree, host)
        if main is None:
            main, method = choose_editorial_main(tree, host)
    counts = repair(main)
    counts['unresolved_technical_markup_scope'] = int(main is None and bool(tree.xpath('//sup|//sub|//code[.//div or .//p]')))
    changed = any(value for key, value in counts.items() if not key.startswith('unresolved_'))
    clean, metadata = previous(html.tostring(tree, encoding='unicode') if changed else content, url)
    return clean, metadata | counts | dict(clean_version=VERSION, technical_markup_scope=method)
