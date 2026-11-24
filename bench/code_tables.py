"""Прямоугольные таблицы с явно размеченными блоками кода в ячейках."""
from copy import deepcopy


def code_grid(node):
    """Возвращает текст и число блоков; неоднозначная структура не принимается.

    Исходный DOM не меняется. Маскируются только pre и чистые одноклеточные
    table.code; обычный вложенный табличный макет не становится данными.
    """
    from .html_structure import code_table_blocks,table_grid,SKIP
    if node.tag!='table' or not node.xpath('.//pre'):return None
    if any(n.tag in SKIP for n in node.iterancestors()):return None
    allowed={'table','thead','tbody','tfoot','tr','th','td','caption','div','pre',
             'p','a','span','b','strong','em','i','u','s','small','abbr','br','code','tt','font'}
    for element in list(node.iter())+list(node.iterancestors()):
        if not isinstance(element.tag,str):return None
        if element is node or node in element.iterancestors():
            if element.tag not in allowed:return None
        if (element.get('cite') or 'author' in element.get('itemprop','').split()
                or any(k.lower().startswith('on') for k in element.attrib)
                or any(c.endswith(('__author','__source','__credit')) for c in element.get('class','').split())):return None
        if element.tag in {'blockquote','figure','figcaption','aside','nav','footer','form','button'}:return None
    if {'note','tip','warning','contents','code'}&set(node.get('class','').split()):return None
    clone=deepcopy(node)
    for nested in clone.xpath('.//table'):
        rows=nested.xpath('./tr|./tbody/tr')
        if (len(rows)!=1 or len(rows[0])!=1 or rows[0][0].tag!='td'
                or any(rows[0][0].get(k,'1')!='1' for k in ('rowspan','colspan'))
                or not code_table_blocks(nested) or nested.xpath('.//table')):return None
        nested.tag='div'
        for row in rows:row.tag='div';row[0].tag='div'
        for group in nested.xpath('./tbody'):group.tag='div'
    blocks=clone.xpath('.//pre')
    if not blocks or any(not block.text_content().strip() for block in blocks):return None
    # div допускается только как прозрачная оболочка кода, без своей прозы.
    for wrapper in clone.xpath('.//div'):
        if not wrapper.xpath('.//pre') or ''.join(wrapper.xpath('.//text()[not(ancestor::pre)]')).strip():return None
    for block in blocks:
        block.tag='span';block.attrib.clear();block.text='[КОД]';block[:]=[]
    for wrapper in clone.xpath('.//div'):wrapper.tag='span'
    grid=table_grid(clone)
    return (grid,len(blocks)) if grid is not None else None
