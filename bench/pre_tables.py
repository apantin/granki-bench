"""Явные текстовые таблицы в pre; без классификации программного кода по словам."""
import re

SEPARATOR=re.compile(r'\s*-{2,}(?:[ \t]+-{2,})+\s*')


def table_like(value):
    return any(SEPARATOR.fullmatch(line) for line in value.expandtabs().splitlines())


def parse(value):
    """Колонки задаёт полная строка подчёркивания под непустым заголовком.

    Все межколоночные промежутки должны оставаться пробельными в каждой
    строке. Последняя колонка сохраняет весь остаток, включая длинный текст.
    """
    lines=value.expandtabs().splitlines()
    while lines and not lines[0].strip():lines.pop(0)
    while lines and not lines[-1].strip():lines.pop()
    if (len(lines)<3 or any(not line.strip() for line in lines) or not SEPARATOR.fullmatch(lines[1])
            or any(SEPARATOR.fullmatch(line) for line in lines[2:])):return None
    spans=[m.span() for m in re.finditer(r'-{2,}',lines[1])]
    result=[]
    for line in [lines[0],*lines[2:]]:
        if line[:spans[0][0]].strip() or any(line[end:spans[i+1][0]].strip() for i,(_,end) in enumerate(spans[:-1])):return None
        cells=[line[start:end].strip() for start,end in spans[:-1]]+[line[spans[-1][0]:].strip()]
        if not any(cells) or not result and not all(cells):return None
        result.append(cells)
    return result


def restore(main):
    """Возвращает роли до подсчёта кода и таблиц; сложные случаи удерживаются."""
    from lxml import html
    from .html_structure import SKIP,code_table_blocks
    preserved=0;unresolved=0
    if main.tag in SKIP|{'pre'}:return dict(preserved_pre_tables=0,unresolved_pre_tables=0)
    for node in list(main.xpath('.//pre')):
        ancestors=[]
        for parent in node.iterancestors():
            if parent is main:break
            ancestors.append(parent)
        if any(n.tag in (SKIP-{'table'})|{'pre'} for n in ancestors):continue
        value=node.text_content()
        if not table_like(value):continue
        grid=parse(value);tables=[n for n in ancestors if n.tag=='table']
        if (grid is None or len(node) or tables and (len(tables)!=1 or code_table_blocks(tables[0])!=[node])):
            unresolved+=1;continue
        target=tables[0] if tables else node
        table=html.Element('table')
        for i,cells in enumerate(grid):
            row=html.Element('tr')
            for value in cells:
                cell=html.Element('th' if i==0 else 'td');cell.text=value;row.append(cell)
            table.append(row)
        table.tail=target.tail;target.getparent().replace(target,table);preserved+=1
    return dict(preserved_pre_tables=preserved,unresolved_pre_tables=unresolved)
