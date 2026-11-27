"""Проверенные издательские роли поверх неизменного кандидата первичного тела."""
import copy
import re
from urllib.parse import urlsplit

from lxml import html

from ..cleaning import html_article_publication_body_candidate
from ..html_structure import decode
from ..publication_body import bind, has, issue_widget

VERSION = 'clean-v19-publication-cleanup-candidate'
PLACEHOLDER = 'двойной клик - редактировать изображение'


def normalized(value):
    return ' '.join(value.casefold().split())


def local_path(value, host):
    """Только собственный обычный URL без логина, порта и скрытого маршрута."""
    try:
        target = urlsplit(value)
        if (target.scheme not in {'', 'http', 'https'} or (target.scheme and not target.hostname)
                or (target.hostname or host).removeprefix('www.') != host
                or target.port or target.username or target.password or target.query or target.fragment):
            return None
    except ValueError:
        return None
    return target.path


def repeated_lead(lead, main):
    """Убираем анонс целиком только при полном совпадении внутри одного абзаца."""
    value = normalized(lead.text_content())
    # Различие лишь в конечной точке типично для отдельного поля анонса.
    # Многоточие не сокращаем: оно может обозначать пропущенные сведения.
    if value.endswith('.') and not value.endswith('..'):
        value = value[:-1]
    if not value:
        return False
    for paragraph in main.xpath('.//p'):
        if any(parent.tag in {'blockquote', 'figure', 'pre', 'table', 'script', 'style'}
               for parent in paragraph.iterancestors() if parent is not main):
            continue
        text = normalized(paragraph.text_content())
        for match in re.finditer(re.escape(value), text):
            start, end = match.span()
            if ((start and text[start - 1].isalnum() and value[0].isalnum())
                    or (end < len(text) and text[end].isalnum() and value[-1].isalnum())):
                continue
            return True
    return False


def series_panel(node, title, host):
    lists = node.xpath('./ul')
    if len(lists) != 1 or node.xpath('.//p[normalize-space()]|.//pre|.//table|.//blockquote|.//img'):
        return False
    if ''.join(node.xpath('.//text()[not(ancestor::ul)]')).strip():
        return False
    items = list(lists[0])
    if len(items) < 2 or any(item.tag != 'li' for item in items):
        return False
    current = 0
    for item in items:
        links = item.xpath('.//a')
        label = normalized(item.text_content())
        if not label:
            return False
        if not links:
            heading = normalized(title.text_content())
            if (not heading.startswith(label)
                    or (len(heading) > len(label) and heading[len(label)].isalnum())):
                return False
            current += 1
        elif (len(links) != 1 or normalized(links[0].text_content()) != label
              or not re.fullmatch(r'/[0-9]{4}/[0-9]{2}/[0-9]{2}/[^/]+/?',
                                  local_path(links[0].get('href', ''), host) or '')):
            return False
        if item.xpath('.//p|.//pre|.//table|.//blockquote|.//ul|.//ol'):
            return False
    return current == 1


def extended_issue(node, host):
    labels = node.xpath('./small')
    if (len(labels) != 1 or len(labels[0])
            or ' '.join(labels[0].text_content().split()) != 'Рекомендуем почитать:'):
        return False
    candidate = copy.deepcopy(node)
    candidate.xpath('./small')[0].text = 'Другие статьи в выпуске:'
    return issue_widget(candidate, host)


def image_link(node, host):
    links = node.xpath('./a')
    if (len(node) != 1 or len(links) != 1 or len(links[0])
            or (node.text or '').strip() or (links[0].tail or '').strip()
            or not links[0].text_content().strip()):
        return False
    path = local_path(links[0].get('href', ''), host)
    return bool(path and re.fullmatch(r'/wp-content/uploads/.+\.(?:jpg|jpeg|png|webp|gif)', path, re.I))


def repair_cms(main, counts):
    for node in list(main.xpath('.//p[contains(concat(" ",normalize-space(@class)," ")," pgzeditchange ")]')):
        if normalized(node.text_content()) != PLACEHOLDER:
            continue
        editor = node.getparent()
        photo = editor.getparent() if editor is not None else None
        spans = node.xpath('./span[@type-bloc="onep"]')
        valid = (editor is not None and photo is not None and has(editor, 'onepzedit')
                 and has(photo, 'onephoto') and photo.get('contenteditable') == 'false'
                 and photo.get('data-pg') and photo.xpath('.//img') and len(spans) == 1
                 and not len(spans[0]) and normalized(spans[0].text_content()) == PLACEHOLDER)
        if not valid:
            counts['unresolved_publisher_placeholders'] += 1
        elif len(node) > 1:
            # Только пустое оформление рядом с единственным типизированным span.
            if all(child is spans[0] or (child.tag in {'em', 'span', 'br'}
                                        and not child.text_content().strip()) for child in node):
                node.drop_tree()
                counts['removed_extended_cms_placeholders'] += 1
            else:
                counts['unresolved_publisher_placeholders'] += 1


def illustration_credit(node, main):
    if (len(node) != 1 or node[0].tag not in {'strong', 'em'} or len(node[0])
            or (node.text or '').strip() or (node[0].tail or '').strip()
            or not main.xpath('.//img')):
        return False
    # Роль подписи, а не предложение о рисе или упоминание художника в прозе.
    if not re.fullmatch(r'Рис\.\s+[А-ЯЁ][а-яё]+(?:-[А-ЯЁа-яё]+)?\s+[А-ЯЁ][а-яё]+(?:-[А-ЯЁа-яё]+)?',
                        ' '.join(node.text_content().split())):
        return False
    if (node.tail or '').strip():
        return False
    return all(not isinstance(sibling.tag, str) or sibling.tag in {'script', 'style'} or has(sibling, 'zen_inv')
               or not sibling.text_content().strip() for sibling in node.itersiblings())


def extract(content: bytes | str, url: str = ''):
    """Opt-in: ремонт ролей, без сетевых запросов и без корпусного допуска."""
    tree = html.fromstring(decode(content))
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    publication = bind(tree, host)
    counts = dict(deduplicated_overlapping_leads=0, removed_publisher_series_panels=0,
                  unresolved_publisher_series_panels=0, removed_extra_issue_widgets=0,
                  removed_link_image_captions=0, removed_terminal_illustration_credits=0,
                  removed_extended_cms_placeholders=0, unresolved_publisher_placeholders=0)
    if publication is not None:
        main = publication['main']
        lead = publication['lead']
        if lead is not None and repeated_lead(lead, main):
            for child in list(lead):
                lead.remove(child)
            lead.text = None
            counts['deduplicated_overlapping_leads'] += 1
        if host == 'xakep.ru':
            for node in list(main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," panel ") and contains(concat(" ",normalize-space(@class)," ")," default ")]')):
                if not node.xpath('.//a'):
                    continue  # Собственная врезка без ссылок не является навигацией.
                if series_panel(node, publication['title'], host):
                    node.drop_tree()
                    counts['removed_publisher_series_panels'] += 1
                else:
                    counts['unresolved_publisher_series_panels'] += 1
            for node in list(main.xpath('.//*[@id="current_issue_box"]')):
                if extended_issue(node, host):
                    node.drop_tree()
                    counts['removed_extra_issue_widgets'] += 1
            for node in list(main.xpath('.//p')):
                if image_link(node, host):
                    node.drop_tree()
                    counts['removed_link_image_captions'] += 1
        if host == 'zavtra.ru':
            repair_cms(main, counts)
            for node in list(main.xpath('./p')):
                if illustration_credit(node, main):
                    node.drop_tree()
                    counts['removed_terminal_illustration_credits'] += 1
    changed = any(value for key, value in counts.items() if not key.startswith('unresolved_'))
    clean, metadata = html_article_publication_body_candidate(
        html.tostring(tree, encoding='unicode') if changed else content, url)
    return clean, metadata | counts | dict(clean_version=VERSION)
