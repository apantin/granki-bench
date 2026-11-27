"""Привязка первичной шапки к телу и строго типизированные служебные вставки."""
import re
from urllib.parse import urlsplit


def has(node, token):
    return token in node.get('class', '').split()


def unique(nodes):
    return nodes[0] if len(nodes) == 1 else None


def bind(tree, host):
    """Не угадываем по тексту заголовка и не берём соседнюю публикацию."""
    if host == 'xakep.ru':
        root = unique(tree.xpath('//*[@id="warp"]'))
        post = unique([n for n in tree.xpath('//article') if has(n, 'hentry')])
        head = unique([n for n in tree.xpath('//div') if has(n, 'bdaia-post-style7-head')])
        header = unique([n for n in tree.xpath('//header') if has(n, 'bdaia-post-header')])
        if any(n is None for n in [root, post, head, header]):
            return None
        if (root not in post.iterancestors() or root not in head.iterancestors()
                or head not in header.iterancestors() or post.getparent().get('id') != 'content'
                or not re.fullmatch(r'post-[0-9]+', post.get('id', '')) or not has(post, post.get('id'))):
            return None
        title = unique(header.xpath('.//h1'))
        body = unique([n for n in post.xpath('.//div') if has(n, 'bdaia-post-content')])
        if (title is None or body is None or len(head.xpath('.//h1')) != 1
                or not has(title, 'post-title') or not has(title, 'entry-title') or not title.text_content().strip()):
            return None
        nested = post.xpath('.//article')
        if nested and (len(nested) != 1 or not has(nested[0], 'xmd') or body not in nested[0].iterancestors()):
            return None
        return dict(main=body, title=title, lead=None, method='profile:xakep-primary-publication')
    if host == 'zavtra.ru':
        region = unique(tree.xpath('//div[@id="content_blogs"]'))
        block = unique([n for n in tree.xpath('//div') if has(n, 'contentblock')])
        header = unique(tree.xpath('//div[@id="article__header"]'))
        body = unique([n for n in tree.xpath('//div') if has(n, 'article__content')])
        if any(n is None for n in [region, block, header, body]):
            return None
        if (region not in block.iterancestors() or header.getparent() is not block
                or body.getparent() is not block or block.xpath('.//article')):
            return None
        titles = [n for n in header if has(n, 'header__title')]
        title = unique(titles[0].xpath('./h1')) if len(titles) == 1 else None
        leads = [n for n in header if has(n, 'header__anonse')]
        if title is None or not title.text_content().strip() or len(header.xpath('.//h1')) != 1 or len(leads) > 1:
            return None
        return dict(main=body, title=title, lead=leads[0] if leads else None, method='profile:zavtra-primary-publication')
    return None


def issue_widget(node, host):
    labels = node.xpath('./small')
    links = node.xpath('.//a[@href]')
    if len(labels) != 1 or ' '.join(labels[0].text_content().split()) != 'Другие статьи в выпуске:' or not links:
        return False
    issues = set()
    for link in links:
        try:
            target = urlsplit(link.get('href'))
            port = target.port
        except ValueError:
            return False
        if target.scheme not in {'', 'http', 'https'} or (target.hostname or host).removeprefix('www.') != host or target.query or target.fragment or target.username or target.password or port:
            return False
        path = target.path.rstrip('/')
        if re.fullmatch(r'/issues/xa/[0-9]+', path):
            issues.add(path)
        elif path != '/about':
            return False
    if len(issues) != 1 or node.xpath('.//p|.//pre|.//table|.//blockquote|.//article'):
        return False
    residual = ''.join(node.xpath('.//text()[not(ancestor::a or ancestor::small or ancestor::style or ancestor::script)]'))
    return not residual.strip()


def repair(main, host):
    counts = dict(removed_issue_widgets=0, unresolved_issue_widgets=0, removed_cms_image_placeholders=0)
    if host == 'xakep.ru':
        for node in list(main.xpath('.//*[@id="current_issue_box"]')):
            if issue_widget(node, host):
                node.drop_tree()
                counts['removed_issue_widgets'] += 1
            else:
                counts['unresolved_issue_widgets'] += 1
    if host == 'zavtra.ru':
        for node in list(main.xpath('.//p[contains(concat(" ",normalize-space(@class)," ")," pgzeditchange ")]')):
            editor = node.getparent()
            photo = editor.getparent() if editor is not None else None
            spans = node.xpath('./span[@type-bloc="onep"]')
            if (editor is None or photo is None or not has(editor, 'onepzedit') or not has(photo, 'onephoto')
                    or photo.get('contenteditable') != 'false' or not photo.get('data-pg') or not photo.xpath('.//img')
                    or len(spans) != 1 or len(node) != 1 or len(spans[0]) or (node.text or '').strip() or (spans[0].tail or '').strip()):
                continue
            if ' '.join(spans[0].text_content().casefold().split()) == 'двойной клик - редактировать изображение':
                node.drop_tree()
                counts['removed_cms_image_placeholders'] += 1
    return counts
