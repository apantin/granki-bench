"""Подтверждённые служебные границы; авторская проза остаётся на месте."""
import re
from urllib.parse import urlsplit

from lxml import html

from .technical_markup import extract as previous
from .publication_cleanup import local_path, normalized
from ..html_structure import SKIP, choose_main, choose_editorial_main, decode
from ..publication_body import bind, has

VERSION = 'clean-v21-editorial-roles-candidate'
JOBS = r'(?:руководитель|директор|менеджер|эксперт|редактор|специалист|основатель)'


def sole_link(node):
    links = node.xpath('./a')
    if (len(node) != 1 or len(links) != 1 or (node.text or '').strip()
            or (links[0].tail or '').strip() or not links[0].text_content().strip()
            or links[0].xpath('.//p|.//div|.//ul|.//img|.//pre|.//table')):
        return None
    return links[0]


def blog_link(link, host):
    path = local_path(link.get('href', ''), host)
    return bool(path and re.fullmatch(r'/blog/[^/]+\.html', path))


def related(main, counts):
    for node in list(main.xpath('.//div')):
        single = has(node, 'readblogmore')
        collection = has(node, 'incut') and has(node, 'read')
        if not (single or collection):
            continue
        valid = False
        if single:
            link = sole_link(node)
            valid = link is not None and blog_link(link, 'texterra.ru')
        elif len(node) == 2 and node[0].tag == 'p' and node[1].tag == 'ul':
            label, items = node[0], list(node[1])
            valid = (not len(label) and normalized(label.text_content()) == 'статьи по теме:'
                     and not (node.text or '').strip() and not (label.tail or '').strip()
                     and not (node[1].tail or '').strip() and not (node[1].text or '').strip()
                     and bool(items))
            for item in items:
                link = sole_link(item)
                valid = (valid and item.tag == 'li' and not (item.tail or '').strip()
                         and link is not None and blog_link(link, 'texterra.ru'))
        if valid:
            node.drop_tree()
            counts['removed_related_widgets'] += 1
        else:
            counts['unresolved_related_widgets'] += 1


def series_prefix(main, url, counts):
    if normalized(main.text or '') != 'посты серии:':
        return
    prefix, links = [], []
    for node in main:
        if node.tag not in {'a', 'br'}:
            break
        if node.tag == 'a':
            if len(node) or not node.text_content().strip() or (node.tail or '').strip():
                counts['unresolved_series_prefixes'] += 1
                return
            path = local_path(node.get('href', ''), 'habr.com')
            if not path or not re.fullmatch(r'/ru/post/[0-9]+/?', path):
                counts['unresolved_series_prefixes'] += 1
                return
            links.append(path.rstrip('/'))
        elif len(node) or (node.text or '').strip():
            counts['unresolved_series_prefixes'] += 1
            return
        prefix.append(node)
        if (node.tail or '').strip():
            break
    path = local_path(url, 'habr.com')
    if len(links) < 2 or path is None or path.rstrip('/') not in links:
        counts['unresolved_series_prefixes'] += 1
        return
    # Последний br несёт начало собственной прозы в tail: не теряем его.
    tail = prefix[-1].tail
    prefix[-1].tail = None
    for node in prefix:
        node.drop_tree()
    main.text = tail or ''
    counts['removed_series_prefixes'] += 1
    counts['removed_series_links'] += len(links)


def terminal(node, *, zen=False):
    if (node.tail or '').strip():
        return False
    return all(not isinstance(n.tag, str) or n.tag in SKIP
               or (zen and has(n, 'zen_inv')) or not n.text_content().strip()
               for n in node.itersiblings())


def publication_credit(main, counts):
    for node in list(main.xpath('./p')):
        if not normalized(node.text_content()).startswith('публикация:'):
            continue
        strong = node[0] if len(node) == 1 and node[0].tag == 'strong' else None
        link = sole_link(strong) if strong is not None else None
        valid = (link is not None and not (node.text or '').strip()
                 and not (strong.tail or '').strip() and terminal(node, zen=True))
        try:
            target = urlsplit(link.get('href', '')) if link is not None else None
            valid = (valid and target.scheme in {'http', 'https'} and bool(target.hostname)
                     and not target.username and not target.password and not target.port
                     and normalized(link.text_content()).startswith('публикация:'))
        except ValueError:
            valid = False
        if valid:
            node.drop_tree()
            counts['removed_publication_credits'] += 1
        else:
            counts['unresolved_publication_credits'] += 1


def signature(main, author, counts, retained):
    for node in list(main.xpath('./p')):
        if (not len(node) or node[0].tag != 'strong' or not terminal(node)
                or not re.match(r',\s*' + JOBS + r'\b', node[0].tail or '', re.I)):
            continue
        if normalized(node.text_content()) not in normalized(retained):
            continue  # Предыдущая очистка уже убрала эту подпись.
        name = node[0]
        link = node[1] if len(node) == 2 and node[1].tag == 'a' else None
        valid = (bool(author) and normalized(name.text_content()) == normalized(author)
                 and not len(name) and not (node.text or '').strip()
                 and link is not None and not len(link) and link.text_content().strip()
                 and not (link.tail or '').strip()
                 and local_path(link.get('href', ''), 'kontur.ru')
                 and re.fullmatch(r',\s*' + JOBS + r'(?:\s+(?:продукта|команды|проекта|редакции))?\s*',
                                  normalized(name.tail or '')))
        if valid:
            node.drop_tree()
            counts['removed_author_signatures'] += 1
        else:
            counts['unresolved_author_signatures'] += 1


def introduction(main, author, counts):
    elements = [n for n in main if isinstance(n.tag, str) and n.tag not in SKIP
                and n.text_content().strip()]
    if not elements or elements[0].tag != 'p':
        return
    node = elements[0]
    text = normalized(node.text_content())
    marker = re.search(r'\bв (?:колонке|статье) для «?нетологии»? рассказывает\b', text)
    if marker is None:
        return
    prefix = text[:marker.start()].strip()
    valid = (bool(author) and prefix.endswith(normalized(author))
             and re.match(JOBS + r'\b', prefix) is not None
             and not re.search(r'[.!?]', text.rstrip('.'))
             and not node.xpath('.//blockquote|.//pre|.//img|.//table'))
    if valid:
        node.drop_tree()
        counts['removed_editorial_introductions'] += 1
    else:
        counts['unresolved_editorial_introductions'] += 1


def extract(content: bytes | str, url: str = ''):
    before, metadata = previous(content, url)
    tree = html.fromstring(decode(content))
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    publication = bind(tree, host)
    if publication is not None:
        main, method = publication['main'], publication['method']
    else:
        main, method = choose_main(tree, host)
        if main is None:
            main, method = choose_editorial_main(tree, host)
    roles = ['related_widgets', 'series_prefixes', 'publication_credits',
             'author_signatures', 'editorial_introductions']
    counts = {prefix + role: 0 for role in roles for prefix in ['removed_', 'unresolved_']}
    counts['removed_series_links'] = 0
    if main is not None:
        if host == 'texterra.ru' and main.get('itemprop') == 'articleBody':
            related(main, counts)
        if host == 'habr.com' and main.get('id') == 'post-content-body' and has(main, 'post__text'):
            series_prefix(main, url, counts)
        if host == 'zavtra.ru' and publication is not None:
            publication_credit(main, counts)
        if host == 'kontur.ru' and method == 'profile:ArticleItem-text':
            signature(main, metadata.get('author'), counts, before.raw)
        if host == 'netology.ru' and method == 'class:entry-content':
            introduction(main, metadata.get('author'), counts)
    clean = before
    if any(value for key, value in counts.items() if key.startswith('removed_')):
        clean, after = previous(html.tostring(tree, encoding='unicode'), url)
        # Удалённая подпись остаётся свидетельством исходной атрибуции.
        after.update({key: metadata[key] for key in ['author', 'title', 'date'] if key in metadata})
        metadata = after
    return clean, metadata | counts | dict(clean_version=VERSION, editorial_roles_scope=method)
