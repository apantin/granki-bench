"""Явная шапка отдельного Blogspot-поста поверх неизменного v20."""
import re
from urllib.parse import urlsplit

from lxml import html

from .technical_markup import extract as previous
from ..cleaning import CleanText, extracted_text
from ..html_structure import choose_main, choose_title, decode, render
from ..publication_body import has

VERSION = 'clean-v21-blogspot-post-candidate'


def bind(tree, host):
    """Тело и соседний заголовок одного поста, без выбора по длине текста."""
    if not host.endswith('.blogspot.com'):
        return None
    main, method = choose_main(tree, host)
    if main is None or method not in {'itemprop:articleBody', 'class:entry-content'}:
        return None
    posts = [a for a in main.iterancestors() if has(a, 'post')]
    if len(posts) != 1:
        return None
    post = posts[0]
    # Вложенная копия чужого шаблона не становится основным постом.
    if any(has(n, 'post') for n in post.iterdescendants() if isinstance(n.tag, str)):
        return None
    titles = [n for n in post.iterdescendants()
              if isinstance(n.tag, str) and has(n, 'post-title') and has(n, 'entry-title')]
    if len(titles) != 1:
        return None
    title = titles[0]
    if (title.tag not in {'h1', 'h2', 'h3'} or not title.text_content().strip()
            or main in title.iterancestors() or title in main.iterancestors()):
        return None
    return dict(post=post, main=main, title=title, method=method)


def title_text(node):
    return re.sub(r'^#{1,6} ', '', render(node).strip())


def extract(content: bytes | str, url: str = ''):
    clean, metadata = previous(content, url)
    host = (urlsplit(url).hostname or '').removeprefix('www.')
    binding = bind(html.fromstring(decode(content)), host)
    counts = dict(bound_blogspot_posts=int(binding is not None),
                  unresolved_blogspot_posts=int(host.endswith('.blogspot.com') and binding is None),
                  restored_blogspot_titles=0, replaced_blogspot_site_titles=0)
    if binding is not None:
        tree = binding['post'].getroottree().getroot()
        main, title = binding['main'], binding['title']
        old_title = choose_title(tree, main, host)
        text = clean.raw
        if old_title is not title:
            # Убирается лишь точный префикс, добавленный прежним извлекателем
            # из известного внешнего h1. Заголовок внутри тела не удаляется.
            external = old_title is not None and main not in old_title.iterancestors()
            if external:
                prefix = '# ' + title_text(old_title) + '\n\n'
                if not text.startswith(prefix):
                    return clean, metadata | counts | dict(unresolved_blogspot_posts=1, clean_version=VERSION)
                text = text[len(prefix):]
                counts['replaced_blogspot_site_titles'] = 1
            text = '# ' + title_text(title) + '\n\n' + text
            clean = extracted_text(text, code_blocks=clean.code_blocks)
            clean = CleanText(clean.raw, clean.norm.replace('\u00ad', ''), clean.code_blocks)
            counts['restored_blogspot_titles'] = 1
        metadata = metadata | dict(title=' '.join(title.text_content().split()), title_source='DOM-Blogspot-post-title')
    return clean, metadata | counts | dict(clean_version=VERSION)
