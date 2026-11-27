"""Узкий opt-in ремонт текстовых таблиц и обычных предложений в pre."""
from copy import deepcopy
import re
from lxml import html

INLINE={'p','a','span','b','strong','em','i','u','s','small','abbr','br'}


def text(node):return ' '.join(node.text_content().split())


def span(cell,name):
    value=cell.get(name,'1')
    if not value.isascii() or not value.isdecimal():return None
    try:result=int(value)
    except ValueError:return None
    return result if result>0 else None


def rows(node):return node.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')


def text_order(node,cells):
    captions=node.xpath('./caption')
    return ''.join(node.text_content().split())==''.join(''.join(c.text_content().split()) for c in captions+cells)


def repair_loose_rows(node):
    """Только явные ведущие th и tr-разделители; ширина не подбирается."""
    children=list(node);captions=node.xpath('./caption')
    if captions:
        if len(captions)!=1 or children[0] is not captions[0]:return False
        children=children[1:]
    headers=[]
    while children and children[0].tag=='th':headers.append(children.pop(0))
    width=len(headers)
    if width<2 or any(span(c,k)!=1 for c in headers for k in ('rowspan','colspan')):return False
    output=[];cells=list(headers)
    while children:
        row=children.pop(0)
        if row.tag!='tr':return False
        data=list(row)
        if not data:
            while children and children[0].tag=='td':data.append(children.pop(0))
        if len(data)!=width or any(c.tag!='td' or any(span(c,k)!=1 for k in ('rowspan','colspan')) for c in data):return False
        cells.extend(data);output.append((row,data))
    if not output or not text_order(node,cells):return False
    header=html.Element('tr')
    for c in headers:header.append(c)
    new_rows=[header]
    for row,data in output:
        row[:]=data;new_rows.append(row)
    node[:]=captions+new_rows
    return True


def flatten_group_header(node):
    """Два явно связанных уровня: rowspan=2 слева, colspan-группы сверху."""
    if any(c.tag not in {'caption','tr','thead','tbody','tfoot'} for c in node):return False
    if any(c.tag!='tr' for g in node if g.tag in {'thead','tbody','tfoot'} for c in g):return False
    data_rows=rows(node)
    if len(data_rows)<3:return False
    top=list(data_rows[0]);bottom=list(data_rows[1]);data=[list(r) for r in data_rows[2:]]
    if len(top)<2 or any(c.tag not in {'td','th'} for r in [top,bottom,*data] for c in r):return False
    if span(top[0],'rowspan')!=2 or span(top[0],'colspan')!=1:return False
    groups=top[1:];width=len(data[0])
    spans=[span(c,'colspan') for c in groups]
    if any(v is None for v in spans) or sum(spans)!=width-1 or len(bottom)!=width-1:return False
    if any(span(c,'rowspan')!=1 for c in groups) or any(span(c,k)!=1 for c in bottom for k in ('rowspan','colspan')):return False
    if any(len(r)!=width or any(span(c,k)!=1 for c in r for k in ('rowspan','colspan')) for r in data):return False
    if any(not text(c) or any(n.tag not in INLINE for n in c.iterdescendants()) for c in top+bottom):return False
    if not text_order(node,[c for r in [top,bottom,*data] for c in r]):return False
    labels=[text(top[0])];position=0
    for group,size in zip(groups,spans):
        for _ in range(size):labels.append(text(group)+' / '+text(bottom[position]));position+=1
    header=html.Element('tr')
    for label in labels:
        cell=html.Element('th');cell.text=label;header.append(cell)
    node[:]=node.xpath('./caption')+[header]+data_rows[2:]
    return True


def repaired_table(node):
    from .html_structure import table_grid
    if node.tag!='table' or node.xpath('.//table|.//pre'):return None
    clone=deepcopy(node)
    for n in clone.xpath('.//nobr'):n.tag='span'
    if table_grid(clone) is None:
        repair_loose_rows(clone)
    if table_grid(clone) is None:
        flatten_group_header(clone)
    return clone if table_grid(clone) is not None else None


def prose_pre(node):
    """Кандидат обычного русского предложения,а не доказательство авторства."""
    if len(node) or any('code' in c.lower() or 'highlight' in c.lower() or 'syntax' in c.lower() or c.lower().startswith(('lang-','language-')) for c in node.get('class','').split()):return False
    if any(k in node.attrib for k in ('lang','data-language','data-lang')):return False
    value=node.text.strip() if node.text else ''
    if not re.fullmatch(r'[А-ЯЁ][А-Яа-яЁёA-Za-z0-9 \t\u00a0\u202f.,!?—–-]*[.!?]',value):return False
    return len(re.findall(r'\b[А-Яа-яЁё]{2,}\b',value))>=2 and bool(re.search(r'\s',value))


def repair(main):
    from .html_structure import SKIP,table_grid
    counts=dict(repaired_text_tables=0,preserved_prose_pre=0,prose_pre_review_required=0)
    if main is None:return {k:None for k in counts}
    def visible(node):
        for parent in node.iterancestors():
            if parent is main:return True
            if parent.tag in SKIP|{'pre','code'}:return False
            if any('code' in c.lower() or 'highlight' in c.lower() or 'syntax' in c.lower() for c in parent.get('class','').split()):return False
        return False
    for table in list(main.xpath('.//table')):
        if not visible(table) or table_grid(table) is not None:continue
        fixed=repaired_table(table)
        if fixed is not None:table.getparent().replace(table,fixed);counts['repaired_text_tables']+=1
    for node in main.xpath('.//pre'):
        if visible(node) and prose_pre(node):
            node.tag='p';counts['preserved_prose_pre']+=1;counts['prose_pre_review_required']+=1
    return counts
