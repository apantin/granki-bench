"""Единая очистка корпуса, генераций и входного текста; две версии типографики."""
from __future__ import annotations
import html
import re
import unicodedata
from dataclasses import dataclass

VERSION = 'clean-v3'
HTML_INLINE_VERSION = 'clean-v4-inline-candidate'
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:[-’'][A-Za-zА-Яа-яЁё]+)*|\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class CleanText:
    raw: str
    norm: str
    code_blocks: int = 0


def words(text: str) -> list[str]:
    return WORD_RE.findall(text)


def typography(text: str) -> str:
    text = unicodedata.normalize('NFC', text).replace('\u00a0', ' ').replace('\u202f', ' ')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'(?<=[ \t])[–-](?=[ \t])', '—', text)
    text = re.sub(r'^– ', '— ', text, flags=re.M)
    text = re.sub(r'[“„«]([^”»\n]+)[”»]', r'«\1»', text)
    text = re.sub(r'"([^"\n]+)"', r'«\1»', text)
    return text


def markdown(text: str) -> CleanText:
    """Структура остаётся: заголовки, абзацы, списки. Чужие блоковые цитаты удаляются."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'\A---\s*\n.*?\n---\s*\n', '', text, flags=re.S)
    text, count = re.subn(r'(?m)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$', '[КОД]', text, flags=re.S)
    text = re.sub(r'(?m)^\s*>.*(?:\n|$)', '', text)
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', text)
    text = re.sub(r'(?m)^\s*\[[^\]]+\]:.*$', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'(?<!\w)(\*\*|__|\*|_)(.+?)\1(?!\w)', r'\2', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = re.sub(r'(?m)^[ \t]*[+*][ \t]+', '- ', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
    return CleanText(text, typography(text), count)


def html_article(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Локальное извлечение HTML; библиотека не выполняет сетевых запросов."""
    return _html_article(content, url, flatten_inline=False)


def html_article_inline_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат: сохраняет порядок inline-текста, не меняет clean-v3."""
    clean, meta = _html_article(content, url, flatten_inline=True)
    return clean, meta | {'clean_version': HTML_INLINE_VERSION}


def _html_article(content: bytes | str, url: str, *, flatten_inline: bool) -> tuple[CleanText, dict]:
    from lxml import html as lhtml
    from trafilatura import extract
    from trafilatura.metadata import extract_metadata
    if isinstance(content,bytes):
        try:
            content=content.decode('utf-8-sig')
        except UnicodeDecodeError:
            # HTML5 charset может оказаться дальше зоны автодетектора libxml2.
            charset=re.search(br'charset\s*=\s*[\"\']?([A-Za-z0-9_-]+)',content[:16384],re.I)
            if charset:
                content=content.decode(charset.group(1).decode('ascii'),errors='replace')
            else:
                from charset_normalizer import from_bytes
                decoded=from_bytes(content).best()
                if decoded is None:raise ValueError('Не удалось определить кодировку HTML')
                content=str(decoded)
    tree = lhtml.fromstring(content)
    # Trafilatura 2.0 пытается менять tag комментария внутри заголовка и падает.
    for comment in tree.xpath('//comment()'):
        if comment.getparent() is not None:
            comment.drop_tree()
    metadata = extract_metadata(tree, default_url=url)
    author=getattr(metadata,'author',None)
    author_method='metadata'
    if not author:
        nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," bdaia-post-author-name ")]//a')
        if nodes:
            author=' '.join(nodes[0].text_content().split())
            author_method='bdaia-byline'
    if not author and 'rsdn.org/' in url:
        body=tree.xpath('//body')
        header=(body[0].text_content() if body else tree.text_content())[:10000]
        match=re.search(r'(?im)авторы?\s*:\s*([А-ЯЁ][а-яё]+(?:[ \t]+[А-ЯЁ][а-яё]+){1,2})',header)
        if match:
            author=match.group(1).strip()
            author_method='rsdn-author-header'
    count = 0
    for node in tree.xpath('//blockquote|//pre|//script|//style|//nav|//footer|//figcaption|//figure'):
        if node.tag == 'pre':
            count += 1
            node.tag = 'p'
            node.clear()
            node.text = '[КОД]'
        else:
            node.drop_tree()
    if flatten_inline:
        # Не трогаем ссылки меню вне содержательных блоков: их плотность нужна
        # извлекателю. drop_tag сохраняет текст и хвосты в исходном порядке.
        for node in tree.xpath('//a|//b|//strong|//em|//i|//span'):
            if node.getparent() is not None and node.xpath('ancestor::p|ancestor::li|ancestor::h1|ancestor::h2|ancestor::h3|ancestor::h4|ancestor::h5|ancestor::h6'):
                node.drop_tag()
    extracted = extract(tree, url=url or None, output_format='markdown', include_comments=False,
                        include_tables=False, include_links=False, include_images=False,
                        include_formatting=True, favor_precision=True) or ''
    clean = markdown(extracted)
    meta = {key: getattr(metadata, key, None) for key in ('title', 'author', 'date', 'sitename')}
    meta.update(author=author,author_method=author_method if author else 'domain-fallback')
    return CleanText(clean.raw, clean.norm, count + clean.code_blocks), meta


def text_features(text: str) -> dict:
    tokens = words(text)
    letters = re.findall(r'[A-Za-zА-Яа-яЁё]', text)
    cyrillic = len(re.findall(r'[А-Яа-яЁё]', text)) / max(1, len(letters))
    return {'words': len(tokens), 'cyrillic': cyrillic,
            'paragraphs': len([p for p in text.split('\n\n') if p.strip()]),
            'code_blocks': text.count('[КОД]')}
