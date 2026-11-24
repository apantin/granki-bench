"""Расширенные роли старого шаблона RSDN, только для кандидата v10.

Структурное восстановление не доказывает авторство неподписанной врезки
и не классифицирует содержимое pre или обычных p как программный код.
"""
import re
from .rsdn_roles import text


def within_body(node,main):
    """Врезка в списке допустима; внутри чужой/непрозрачной структуры — нет."""
    for parent in node.iterancestors():
        if parent is main:return True
        if (parent.tag not in {'div','section','article','ul','ol','li'} or parent.get('cite')
                or parent.get('itemprop')=='author' or any(c.endswith(('__author','__source','__credit'))
                for c in parent.get('class','').split())):return False
    return False


def repair_callouts(main):
    counts={f'{state}_rsdn_{role}':0 for state in ('restored','unresolved') for role in ('notes','tips','warnings')}
    allowed={'tbody','tr','td','strong','br','p','a','span','em','i','b','code','pre','ul','ol','li','u','small'}
    for node in main.xpath('.//table'):
        roles=set(node.get('class','').split())&{'note','tip','warning'}
        if not roles:continue
        role=next(iter(roles));plural={'note':'notes','tip':'tips','warning':'warnings'}[role]
        rows=node.xpath('./tr|./tbody/tr');cells=rows[0].xpath('./td') if len(rows)==1 else []
        credited=any(n.get('cite') or n.get('itemprop')=='author' or
                     any(c.endswith(('__author','__source','__credit')) for c in n.get('class','').split())
                     for n in node.iter())
        if (len(roles)!=1 or not within_body(node,main) or len(cells)!=1 or len(rows[0])!=1
                or any(n.tag not in allowed for n in node.iterdescendants())
                or any(n.get(k,'1')!='1' for k in ('rowspan','colspan') for n in cells)
                or any(k.lower().startswith('on') for n in node.iter() for k in n.attrib)
                or credited or ''.join(node.text_content().split())!=''.join(cells[0].text_content().split())):
            for r in roles:counts['unresolved_rsdn_'+{'note':'notes','tip':'tips','warning':'warnings'}[r]]+=1
            continue
        for n in [node,*node.xpath('./tbody'),rows[0],cells[0]]:n.tag='div'
        counts['restored_rsdn_'+plural]+=1
    counts['unresolved_rsdn_callouts']=sum(v for k,v in counts.items() if k.startswith('unresolved_'))
    return counts


def small(node):
    return bool(re.search(r'(?:^|;)\s*font-size\s*:\s*x-small\s*(?:;|$)',node.get('style',''),re.I))


def picture_only(node):
    return (node is not None and node.tag=='p' and len(node.xpath('./img'))==1
            and all(n.tag in {'img','br','i'} for n in node) and not text(node))


def drop_captions(main):
    from .html_structure import table_grid,code_table_blocks
    removed=0;unresolved=0;toggles=0;unresolved_toggles=0
    for p in main.xpath('./p[./img]'):
        italics=p.xpath('./i')
        if len(italics)!=1 or not small(italics[0]) or not text(italics[0]):continue
        label=italics[0]
        if (len(p.xpath('./img'))==1 and all(n.tag in {'img','br','i'} for n in p)
                and not (p.text or '').strip() and all(not (n.tail or '').strip() for n in p)):
            label.drop_tree();removed+=1
        else:unresolved+=1
    for node in list(main):
        previous=node.getprevious()
        if (node.tag=='p' and not len(node) and re.fullmatch(r'Рис(?:унок|\.)\s*\d+\.?',text(node),re.I)
                and picture_only(previous)):
            node.drop_tree();removed+=1
        elif (node.tag=='font' and small(node) and len(node)==1 and node[0].tag=='i'
                and not len(node[0]) and text(node)==text(node[0])
                and re.fullmatch(r'Таблица\s*\d+\..+',text(node),re.I)
                and previous is not None and previous.tag=='table' and table_grid(previous) is not None):
            node.drop_tree();removed+=1
    for link in main.xpath('.//a[contains(@onclick,"ToggleCode")]'):
        call=re.fullmatch(r"\s*return\s+ToggleCode\(\s*(['\"])([A-Za-z_][A-Za-z0-9_-]*)\1\s*\);?\s*",link.get('onclick',''))
        targets=main.xpath('./div[@id=$key]',key=call[2]) if call else []
        images=link.xpath('./img');parent=link.getparent()
        standalone=parent is main or (parent.tag=='p' and len(parent)==1 and not (parent.text or '').strip() and not (link.tail or '').strip())
        if (call and standalone and link.get('href')=='#' and len(link)==len(images)==1
                and images[0].get('id')=='img'+call[2] and len(targets)==1
                and len(targets[0])==1 and code_table_blocks(targets[0][0])
                and text(targets[0])==text(targets[0][0])):
            link.drop_tree();toggles+=1
        else:unresolved_toggles+=1
    return dict(removed_rsdn_captions=removed,unresolved_rsdn_caption_blocks=unresolved,
                removed_rsdn_code_toggles=toggles,unresolved_rsdn_code_toggles=unresolved_toggles)
