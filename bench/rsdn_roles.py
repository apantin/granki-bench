"""Узкие DOM-роли старого шаблона RSDN; только для кандидата v8."""
import re
from urllib.parse import unquote,urlsplit


def text(node):return ' '.join(' '.join(node.itertext()).split())


def local_link(href):
    try:
        link=urlsplit(href)
        if link.scheme not in {'','http','https'} or link.username or link.password:return None
        if link.hostname and link.hostname.removeprefix('www.') not in {'rsdn.org','rsdn.ru'}:return None
        return link
    except ValueError:return None


def toolbar(node):
    if node.tag!='table' or node.get('width')!='100%' or node.get('border')!='0':return False
    links=[local_link(a.get('href','')) for a in node.xpath('.//a')]
    if not links or any(link is None for link in links):return False
    if not any(link.query=='print' and not link.path for link in links):return False
    if not any(link.path.casefold()=='/forum/ratelist.aspx' for link in links):return False
    return bool(re.fullmatch(r'Сообщений\s*\d+\s*Оценка\s*-?\d+(?:\s*\[\s*\+\s*\d+\s*/\s*-\s*\d+\s*\])?\s*Оценить',text(node),re.I))


def toc(node,targets,*,min_links=2):
    if node.tag!='div' or not re.search(r'(?:^|;)\s*margin-left\s*:\s*2em\s*(?:;|$)',node.get('style',''),re.I):return False
    if any(n.tag not in {'div','a','b','strong','span','br'} for n in node.iterdescendants()):return False
    links=node.xpath('.//a[@href]')
    if len(links)<min_links or ''.join(node.xpath('.//text()[not(ancestor::a)]')).strip():return False
    return all(a.get('href','').startswith('#') and targets.get(unquote(a.get('href')[1:]))==text(a) for a in links)


def legal_footer(node):
    if node.tag!='div' or node.get('align','').casefold()!='right':return False
    if any(n.tag not in {'font','i','hr','copyright'} for n in node.iterdescendants()):return False
    if len(node.xpath('.//hr'))!=1 or len(node.xpath('./font/i'))!=1:return False
    value=node.xpath('./font/i')[0]
    if text(node)!=text(value):return False
    copyrights=value.xpath('./copyright')
    if len(copyrights)==1 and text(value)==text(copyrights[0]):return True
    font=value.getparent()
    return bool(re.search(r'font-size\s*:\s*9pt\b',font.get('style',''),re.I)
                and re.fullmatch(r'Любой из материалов,.*владельцев авторских прав\.',text(value),re.I))


def repair(main,*,extended=False):
    """Неоднозначные врезки остаются таблицами и явно требуют проверки."""
    counts=dict(restored_rsdn_notes=0,unresolved_rsdn_notes=0,removed_rsdn_toolbar_tables=0,
                removed_rsdn_toc=0,removed_rsdn_captions=0,removed_rsdn_legal_footers=0,removed_rsdn_contact_lines=0)
    headings=main.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6');targets={}
    for heading in headings:
        for key in [heading.get('id'),*heading.xpath('.//a/@name'),*heading.xpath('.//a/@id')]:
            if key:targets[key]=text(heading)
    children=list(main);first_heading=next((i for i,n in enumerate(children) if n.tag=='h1'),-1)
    for i,node in enumerate(children):
        edge=i<first_heading or all(n.tag in {'script','style','noscript','template'} or not text(n) for n in children[i+1:])
        if edge and toolbar(node):node.drop_tree();counts['removed_rsdn_toolbar_tables']+=1
    for node in list(main):
        if node.tag=='p':break
        if toc(node,targets,min_links=1 if extended else 2):node.drop_tree();counts['removed_rsdn_toc']+=1
    if extended:
        from .rsdn_callouts import repair_callouts,drop_captions
        counts.update(repair_callouts(main))
        counts.update(drop_captions(main))
    for node in main.xpath('./p[.//img]/i'):
        if extended:break
        if (re.search(r'font-size\s*:\s*x-small\b',node.get('style',''),re.I)
                and re.fullmatch(r'Рис(?:унок|\.)\s*\d+(?:\..*)?',text(node),re.I)):
            node.drop_tree();counts['removed_rsdn_captions']+=1
    for node in main.xpath('./table[contains(concat(" ",normalize-space(@class)," ")," note ")]'):
        if extended:break
        rows=node.xpath('./tr|./tbody/tr');cells=rows[0].xpath('./td') if len(rows)==1 else []
        allowed={'tbody','tr','td','strong','br','p','a','span','em','i','b','code','pre','ul','ol','li'}
        if (len(cells)!=1 or len(rows[0])!=1 or any(n.tag not in allowed for n in node.iterdescendants())
                or any(n.get('rowspan','1')!='1' or n.get('colspan','1')!='1' for n in cells)
                or not cells[0].xpath('./strong') or text(cells[0].xpath('./strong')[0]).casefold()!='примечание'
                or node.get('cite') or node.get('itemprop')=='author' or node.xpath('.//*[@cite or @itemprop="author"]')
                or any(c.endswith(('__author','__source','__credit')) for n in node.iterdescendants() for c in n.get('class','').split())):
            counts['unresolved_rsdn_notes']+=1;continue
        # Не превращаем многоклеточную таблицу данных во врезку.
        for n in [node,*node.xpath('./tbody'),rows[0],cells[0]]:n.tag='div'
        counts['restored_rsdn_notes']+=1
    visible=[n for n in main if n.tag not in {'script','style','noscript','template'} and text(n)]
    if visible and legal_footer(visible[-1]):
        node=visible[-1];previous=node.getprevious()
        if previous is not None and previous.tag=='p' and all(n.tag=='a' for n in previous):
            contact=re.fullmatch(r'(?P<series>\[Продолжение следует\.\.\.\]\s*)?Домашняя страничка:\s*https?://\S+',text(previous),re.I)
            if contact:
                if contact.group('series'):previous[:]=[];previous.text=contact.group('series').rstrip()
                else:previous.drop_tree()
                counts['removed_rsdn_contact_lines']+=1
        node.drop_tree();counts['removed_rsdn_legal_footers']+=1
    return counts
