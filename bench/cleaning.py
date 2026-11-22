"""Единая очистка корпуса, генераций и входного текста; две версии типографики."""
from __future__ import annotations
import html
import re
import unicodedata
from dataclasses import dataclass

VERSION = 'clean-v1'
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
    text = re.sub(r'(?<=\s)[–-](?=\s)', '—', text)
    text = re.sub(r'^[–-] ', '— ', text, flags=re.M)
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
    from lxml import html as lhtml
    from trafilatura import extract
    from trafilatura.metadata import extract_metadata
    tree = lhtml.fromstring(content)
    metadata = extract_metadata(tree, default_url=url)
    count = 0
    for node in tree.xpath('//blockquote|//pre|//script|//style|//nav|//footer|//figcaption|//figure'):
        if node.tag == 'pre':
            count += 1
            node.tag = 'p'
            node.clear()
            node.text = '[КОД]'
        else:
            node.drop_tree()
    extracted = extract(tree, url=url or None, output_format='markdown', include_comments=False,
                        include_tables=False, include_links=False, include_images=False,
                        include_formatting=True, favor_precision=True) or ''
    clean = markdown(extracted)
    meta = {key: getattr(metadata, key, None) for key in ('title', 'author', 'date', 'sitename')}
    return CleanText(clean.raw, clean.norm, count + clean.code_blocks), meta


def text_features(text: str) -> dict:
    tokens = words(text)
    letters = re.findall(r'[A-Za-zА-Яа-яЁё]', text)
    cyrillic = len(re.findall(r'[А-Яа-яЁё]', text)) / max(1, len(letters))
    return {'words': len(tokens), 'cyrillic': cyrillic,
            'paragraphs': len([p for p in text.split('\n\n') if p.strip()]),
            'code_blocks': text.count('[КОД]')}
