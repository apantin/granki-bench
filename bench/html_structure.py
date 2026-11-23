"""Кандидат сохранения DOM-структуры при явных границах статьи.

Тексты и ссылки отдельных документов не входят в модуль. Не меняет clean-v3.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from .cleaning import CleanText,HTML_STRUCTURE_VERSION,html_article_inline_candidate,markdown,typography


def decode(content: bytes | str) -> str:
    if isinstance(content,str):return content
    try:return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        charset=re.search(br'charset\s*=\s*[\"\']?([A-Za-z0-9_-]+)',content[:16384],re.I)
        if charset:return content.decode(charset.group(1).decode('ascii'),errors='replace')
        from charset_normalizer import from_bytes
        decoded=from_bytes(content).best()
        if decoded is None:raise ValueError('Не удалось определить кодировку HTML')
        return str(decoded)


def inline_space(text):return re.sub(r'\s+',' ',text or '')


SKIP={'blockquote','figure','figcaption','table','script','style','nav','footer','aside','form','button','svg','noscript','template'}
BLOCK={'p','div','section','article','header','main','address','dl','dt','dd','table','tr','td','th'}


def render(node,depth=0):
    """Хвост child.tail добавляет родитель: удаление блока не съедает продолжение."""
    tag=node.tag
    if not isinstance(tag,str) or tag in SKIP:return ''
    if tag=='pre':return '\n\n[КОД]\n\n'
    if tag=='br':return '\n'
    if tag=='hr':return '\n\n'
    child_depth=depth+1 if tag in {'ul','ol'} else depth
    content=inline_space(node.text) if tag not in {'ul','ol'} or (node.text or '').strip() else ''
    for child in node:
        tail=inline_space(child.tail)
        if tag in {'ul','ol'} and not tail.strip():tail=''
        content+=render(child,child_depth)+tail
    if tag in {'h1','h2','h3','h4','h5','h6'}:
        value=' '.join(content.split())
        return '\n\n'+'#'*int(tag[1])+' '+value+'\n\n' if value else ''
    if tag=='li':
        content=content.strip()
        return '  '*max(0,depth-1)+'- '+content+'\n'
    if tag in {'ul','ol'}:return '\n\n'+content.strip('\n')+'\n\n'
    if tag in BLOCK:return '\n\n'+content.strip()+'\n\n'
    return content


def code_count(node):
    if not isinstance(node.tag,str) or node.tag in SKIP:return 0
    if node.tag=='pre':return 1
    return sum(code_count(child) for child in node)


def choose_main(tree,host):
    if host=='habr.com':
        nodes=tree.xpath('//*[@id="post-content-body"]')
        if len(nodes)==1:return nodes[0],'id:post-content-body'
    nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@itemprop)," ")," articleBody ")]')
    if len(nodes)==1:return nodes[0],'itemprop:articleBody'
    if host=='liveinternet.ru':
        nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," MESS ")]')
        if len(nodes)==1:return nodes[0],'class:MESS'
    if host in {'tjournal.ru','vc.ru'}:
        nodes=tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," content--full ")]')
        if len(nodes)==1:return nodes[0],'class:content--full'
    return None,'trafilatura-inline-fallback'


def choose_title(tree,main,host):
    def nonempty(nodes):return [n for n in nodes if ''.join(n.itertext()).strip()]
    nodes=nonempty(tree.xpath('//h1[contains(concat(" ",normalize-space(@itemprop)," ")," headline ")]'))
    if len(nodes)==1:return nodes[0]
    if host=='liveinternet.ru':
        nodes=nonempty(tree.xpath('//h1[contains(concat(" ",normalize-space(@class)," ")," ZAG ")]'))
        if len(nodes)==1:return nodes[0]
    if main is not None:
        nodes=nonempty(main.xpath('.//h1'))
        if len(nodes)==1:return nodes[0]
    nodes=nonempty(tree.xpath('//h1'))
    return nodes[0] if len(nodes)==1 else None


def extract_candidate(content: bytes | str,url: str):
    from lxml import html
    source=decode(content)
    fallback,meta=html_article_inline_candidate(source,url)
    tree=html.fromstring(source);host=(urlsplit(url).hostname or '').removeprefix('www.')
    for comment in tree.xpath('//comment()'):
        if comment.getparent() is not None:comment.drop_tree()
    # Интерфейсная отметка редакции, а не часть заголовка.
    if host in {'tjournal.ru','vc.ru'}:
        for node in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," content-editorial-tick ")]'):node.drop_tree()
    main,method=choose_main(tree,host)
    if main is not None and method=='class:content--full':
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," content-info ")]'):node.drop_tree()
        # Конечный навигационный блок тегов: все слова — ссылки на /tag/.
        paragraphs=main.xpath('.//p')
        if paragraphs:
            last=paragraphs[-1];links=last.xpath('./a')
            if links and len(links)==len(last) and not (last.text or '').strip() and all(
                a.text_content().strip().startswith('#') and '/tag/' in a.get('href','') and not (a.tail or '').strip() for a in links):last.drop_tree()
    if main is not None and host=='liveinternet.ru':
        for node in main.xpath('./nobr'):
            if ' '.join(node.text_content().split()).startswith('В колонках играет'):node.drop_tree()
    title=choose_title(tree,main,host)
    title_text=render(title).strip().removeprefix('# ') if title is not None else ''
    if main is None:
        clean=fallback
        # Общий fallback остаётся явным: заголовок добавляется только из единственного h1.
        if title_text and not any(line.lstrip('# ').strip()==title_text for line in clean.raw.splitlines()):
            clean=markdown('# '+title_text+'\n\n'+clean.raw)
            clean=CleanText(clean.raw,clean.norm,fallback.code_blocks)
    else:
        text=render(main).strip()
        text='\n'.join(line.rstrip() if re.match(r'^ *- ',line) else line.strip() for line in text.splitlines())
        if title_text and main is not title and main not in title.iterancestors():
            text='# '+title_text+'\n\n'+text
        clean=markdown(text)
        # Нормализация типографики не уничтожает отступ вложенного списка.
        norm='\n'.join(re.match(r' *',line).group()+typography(line.lstrip(' ')) for line in clean.raw.split('\n'))
        clean=CleanText(clean.raw,norm,code_count(main))
    return clean,meta|dict(clean_version=HTML_STRUCTURE_VERSION,extraction_method=method,
                           title_source='DOM-h1' if title_text else 'not-found',quality_review='pending')
