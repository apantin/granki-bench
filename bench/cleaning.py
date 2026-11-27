"""Единая очистка корпуса, генераций и входного текста; две версии типографики."""
from __future__ import annotations
import html
import re
import unicodedata
from dataclasses import dataclass

VERSION = 'clean-v3'
HTML_INLINE_VERSION = 'clean-v4-inline-candidate'
HTML_STRUCTURE_VERSION = 'clean-v5-structure-candidate'
HTML_EDITORIAL_VERSION = 'clean-v6-editorial-candidate'
HTML_CONTENT_VERSION = 'clean-v7-content-candidate'
HTML_ROLES_VERSION = 'clean-v8-roles-candidate'
HTML_PRE_TABLE_VERSION = 'clean-v9-pre-tables-candidate'
HTML_CALLOUT_VERSION = 'clean-v10-callouts-candidate'
HTML_CODE_TABLE_VERSION = 'clean-v11-code-tables-candidate'
HTML_BODY_VERSION = 'clean-v12-body-candidate'
HTML_PUBLISHER_VERSION = 'clean-v13-publisher-candidate'
HTML_KONTUR_VERSION = 'clean-v14-kontur-candidate'
HTML_NETOLOGY_VERSION = 'clean-v15-netology-candidate'
HTML_LIVEINTERNET_VERSION = 'clean-v16-liveinternet-candidate'
HTML_SEMANTIC_BLOCKS_VERSION = 'clean-v17-semantic-blocks-candidate'
HTML_PUBLICATION_BODY_VERSION = 'clean-v18-publication-body-candidate'
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


def extracted_text(text: str, *, code_blocks: int = 0) -> CleanText:
    """Нормализация уже извлечённого текста без повторного разбора разметки.

    DOM/извлекатель уже обработал HTML и блоковые цитаты. Литеральные
    <параметры>, знаки сравнения и ведущий > здесь являются текстом.
    """
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text).strip() + '\n'
    norm = '\n'.join(re.match(r' *', line).group() + typography(line.lstrip(' '))
                     for line in text.split('\n'))
    return CleanText(text, norm, code_blocks)


def html_article(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Локальное извлечение HTML; библиотека не выполняет сетевых запросов."""
    return _html_article(content, url, flatten_inline=False)


def html_article_code_tables_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат: сохраняет таблицы с явными блоками кода в ячейках."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_code_tables=True)


def html_article_body_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Кандидат формул/секций code-таблиц и явных ролей тела; старые версии прежние."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_body_roles=True)


def html_article_publisher_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат издательских ролей; прежние версии не меняются."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_publisher_roles=True)


def html_article_kontur_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Кандидат лидов/издательских ролей Контура; старые версии сохраняются."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_kontur_roles=True)


def html_article_netology_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат явных ролей Нетологии; прежние версии не меняет."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_netology_roles=True)


def html_article_liveinternet_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Кандидат границ/служебных ролей LiveInternet; прежние версии сохраняются."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_liveinternet_roles=True)


def html_article_semantic_blocks_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Кандидат ремонта текстовых таблиц и pre-прозы; v3–v16 неизменны."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_semantic_blocks=True)


def html_article_publication_body_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Первичная шапка/тело, явные служебные вставки и мягкие переносы norm."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_publication_body=True)


def html_article_inline_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат: сохраняет порядок inline-текста, не меняет clean-v3."""
    clean, meta = _html_article(content, url, flatten_inline=True)
    return clean, meta | {'clean_version': HTML_INLINE_VERSION}


def html_article_structure_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный DOM-кандидат: не включён в clean-v3 и рецепты нормы."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url)


def html_article_editorial_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат: сохраняет явные редакционные врезки, не меняет v3/v5."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_editorial=True)


def html_article_content_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат таблиц/служебных блоков; не меняет v3–v6 и норму."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_content=True)


def html_article_roles_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат DOM-ролей; прежние v3–v7 и норма не меняются."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_roles=True)


def html_article_pre_tables_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Отдельный кандидат явных таблиц в pre; не меняет прежние версии."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_pre_tables=True)


def html_article_callouts_candidate(content: bytes | str, url: str = '') -> tuple[CleanText, dict]:
    """Кандидат расширенных DOM-врезок и подписей; v3–v9 не меняет."""
    from .html_structure import extract_candidate
    return extract_candidate(content, url, preserve_callouts=True)


def rsdn_author_header_candidate(tree) -> str | None:
    """Кандидат авторства: границы полей вместо склеенного text_content.

    Не включён в clean-v3/v4 и не меняет прежние рецепты корпуса.
    При неоднозначном или незавершённом заголовке возвращает None.
    Возвращает поле страницы, не каноническую личность: организация
    или соавторство внутри значения требуют отдельной проверки.
    """
    labels = [node for node in tree.xpath('//span[contains(concat(" ",normalize-space(@class)," ")," title ")]')
              if ' '.join(''.join(node.itertext()).split()).casefold() in {'автор:', 'авторы:'}]
    if len(labels) != 1:
        return None
    value = labels[0].getnext()
    if value is None or value.tag != 'span' or 'value' not in value.get('class', '').split():
        return None
    # Разрыв может отделять организацию либо другого соавтора. Не угадываем.
    if value.xpath('.//br|.//script|.//style'):
        return None
    name = ' '.join(' '.join(value.itertext()).split())
    if not name or len(name) > 200:
        return None
    return name


def _html_article(content: bytes | str, url: str, *, flatten_inline: bool,
                  preserve_extracted: bool = False) -> tuple[CleanText, dict]:
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
    if preserve_extracted:
        # Сначала убираем чужие блоки, затем считаем только оставшийся код.
        for node in tree.xpath('//blockquote|//script|//style|//nav|//footer|//figcaption|//figure'):
            if node.getparent() is not None:node.drop_tree()
        for node in tree.xpath('//pre'):
            count += 1;node.tag = 'p';node.clear(keep_tail=True);node.text = '[КОД]'
        # Форматирование удаляется до извлечения, не regex по готовому тексту.
        # Ссылки остаются: их плотность нужна общему извлекателю.
        for node in tree.xpath('//b|//strong|//em|//i|//u|//font|//code|//tt|//kbd|//samp'):
            if node.getparent() is not None:node.drop_tag()
    else:
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
    clean = extracted_text(extracted) if preserve_extracted else markdown(extracted)
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
