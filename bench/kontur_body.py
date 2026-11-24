"""Явные издательские роли Контура, без данных отдельных публикаций."""
from copy import deepcopy
import re
from urllib.parse import urlsplit
from .habr_body import terminal


def has(node,token):return token in node.get('class','').split()
def space(value):return ' '.join(value.split())
def compact(value):return ''.join(value.split())

def address(value):
    try:return urlsplit(value)
    except ValueError:return None


def local(link,prefix):
    target=address(link.get('href',''))
    return bool(target and target.scheme in {'','http','https'} and (target.hostname or 'kontur.ru') in {'kontur.ru','www.kontur.ru'} and target.path.startswith(prefix))


def pure_links(node):
    links=node.xpath('.//a[@href]')
    return bool(links and all(local(a,'/articles/') for a in links)
                and compact(node.text_content())==''.join(compact(a.text_content()) for a in links)
                and all(n.tag in {'p','ul','li','a','span','em','strong','b','br'} for n in node.iter()))


def header_prefix(tree,main,counts):
    from .html_structure import render
    headers=[n for n in tree.xpath('//div') if has(n,'content-block_article-announce')]
    bodies=tree.xpath('//*[@id="ArticleItem"]');titles=tree.xpath('//h1')
    if (len(headers)!=1 or len(bodies)!=1 or len(titles)!=1 or headers[0] not in titles[0].iterancestors()
            or main is None or main is not bodies[0] and bodies[0] not in main.iterancestors()
            or headers[0] is bodies[0] or headers[0] in bodies[0].iterancestors() or bodies[0] in headers[0].iterancestors()):
        counts['unresolved_kontur_header']+=1;return '',None
    header=headers[0];descs=[n for n in tree.iter() if isinstance(n.tag,str) and has(n,'article-announce__desc')]
    subtitles=[n for n in header.xpath('.//h2') if has(n,'article-announce__title')]
    if len(descs)!=1 or header not in descs[0].iterancestors() or len(subtitles)>1:
        counts['unresolved_kontur_header']+=1;return '',header
    parts=[]
    if subtitles and compact(subtitles[0].text_content())!=compact(titles[0].text_content()):
        parts.append(render(subtitles[0]).strip());counts['restored_kontur_subtitles']+=1
    lead=deepcopy(descs[0])
    for node in list(lead.iterdescendants()):
        if node.getparent() is not None and (has(node,'article-announce__image') or node.tag in {'script','style','img','figure'}):node.drop_tree()
    if any(n.tag not in {'div','section','p','span','a','em','strong','b','i','u','br','sup','sub','small','s'} for n in lead.iter()):
        counts['unresolved_kontur_header']+=1;return '\n\n'.join(parts),header
    text=render(lead).strip()
    if text and not compact(render(main)).startswith(compact(text)):
        parts.append(text);counts['restored_kontur_leads']+=1
    return '\n\n'.join(parts),header


def repair(tree,main,host):
    counts={k:0 for k in ['restored_kontur_leads','restored_kontur_subtitles','removed_kontur_products','removed_kontur_buttons',
            'removed_kontur_workflow_promos','removed_kontur_social_ctas','removed_kontur_related','removed_kontur_bylines',
            'removed_kontur_duplicate_promos','restored_kontur_quote_credits','unresolved_kontur_header','unresolved_kontur_products','unresolved_kontur_quote_credits']}
    if host!='kontur.ru':return counts,None
    prefix,header=header_prefix(tree,main,counts)
    if main is None:return counts,prefix
    for node in list(main.xpath('.//div')):
        if node.getparent() is None or main not in node.iterancestors():continue
        if has(node,'text-block_product'):
            texts=[n for n in node if has(n,'text-block__text') or has(n,'text-block_product__text')]
            if len(texts)==1 and not node.xpath('.//pre|.//code|.//table|.//blockquote'):
                descriptions=texts[0].xpath('./p');following=node.getnext()
                if (node.get('data-show-event-name','').startswith('event-adv-') and len(descriptions)==1
                        and following is not None and following.tag=='p' and space(following.text_content())
                        and compact(following.text_content())==compact(descriptions[0].text_content())
                        and all(n.tag in {'span','strong','b','em','i','br'} for n in following.iterdescendants())):
                    following.drop_tree();counts['removed_kontur_duplicate_promos']+=1
                node.drop_tree();counts['removed_kontur_products']+=1
            else:
                # Иначе последующий прежний UI-filter всё равно удалит блок.
                # В v14 неизвестная форма удерживается вместе с её данными.
                node.attrib.pop('data-show-event-name',None);counts['unresolved_kontur_products']+=1
        elif has(node,'text-block_important'):
            links=node.xpath('.//a[@href]')
            if (len(links)==1 and local(links[0],'/extern/features/') and space(links[0].text_content())=='Узнать больше'
                    and node.xpath('./ol') and not node.xpath('.//pre|.//code|.//table|.//blockquote|.//h1|.//h2|.//h3|.//h4')):
                node.drop_tree();counts['removed_kontur_workflow_promos']+=1
    for node in list(main.xpath('./p')):
        links=node.xpath('.//a[@href]');text=space(node.text_content())
        if len(links)==1 and compact(text)==compact(links[0].text_content()):
            link=links[0];target=address(link.get('href',''))
            if ((local(link,'/ca') and target.path.rstrip('/')=='/ca' and has(link,'btn') and has(link,'btn-secondary'))
                    or local(link,'/kontur-personal/demo') and text.startswith('Попробовать бесплатно программу')):
                node.drop_tree();counts['removed_kontur_buttons']+=1;continue
        if (len(links)==1 and (target:=address(links[0].get('href',''))) and target.hostname in {'t.me','tele.click'} and target.path=='/konturjournal'
                and text in {'Все самое интересное о бизнесе — на нашем канале в Telegram. Присоединяйтесь!',
                             'Подпишитесь на наш канал в Telegram, чтобы вовремя узнавать о самых важных изменениях для бизнеса.'}):
            node.drop_tree();counts['removed_kontur_social_ctas']+=1
    for node in list(main):
        if node.getparent() is None:continue
        links=node.xpath('.//a[@href]');text=space(node.text_content())
        outside=space(''.join(node.xpath('.//text()[not(ancestor::a)]')))
        if node.tag=='p' and links and outside=='Читайте также:' and all(local(a,'/articles/') for a in links):
            node.drop_tree();counts['removed_kontur_related']+=1;continue
        if text not in {'Читайте также','Читайте также:'} or node.tag not in {'p','h2','h3'}:continue
        following=[]
        for n in node.itersiblings():
            if not pure_links(n):break
            following.append(n)
        if following and terminal(following[-1],main):
            for n in following:n.drop_tree()
            node.drop_tree();counts['removed_kontur_related']+=1
    names=[] if header is None else [space(n.text_content()) for n in header.iter() if isinstance(n.tag,str) and has(n,'article-announce-autor-block__name')]
    if len(names)==1 and names[0]:
        name=names[0]
        for node in list(main.xpath('./p')):
            text=space(node.text_content());first=node[0] if len(node) else None
            suffix=text[len(name)+1:].lstrip() if text.startswith(name+',') else ''
            if (suffix and re.match(r'(?:главный редактор|редактор|директор|руководитель|основатель|контент[- ]маркетолог|эксперт|налоговый юрист)\b',suffix,re.I)
                    and not re.search(r'\b(?:говорит|рассказал[аи]?|объяснил[аи]?|отметил[аи]?|сообщил[аи]?|считает|пояснил[аи]?|пишет|рекомендует)\b',suffix,re.I)
                    and first is not None and first.tag in {'strong','b','em','i'} and not (node.text or '').strip()
                    and (space(first.text_content()).rstrip(',')==name or compact(first.text_content())==compact(text))
                    and all(n.tag in {'strong','b','em','i','a','span','br'} for n in node.iterdescendants()) and terminal(node,main)):
                node.drop_tree();counts['removed_kontur_bylines']+=1
    # Подпись в layout-таблице и следующая цитата связаны. Сохраняем связь,
    # но это не допуск внешнего голоса в одноголосный корпус.
    for table in list(main.xpath('./table')):
        next_node=table.getnext();cells=table.xpath('./tr/td|./tbody/tr/td');nonempty=[n for n in cells if space(n.text_content())]
        if (len(table.xpath('./tr|./tbody/tr'))!=1 or len(cells)>2 or len(nonempty)!=1 or table.xpath('.//table|.//th|.//pre|.//code|.//img|.//a|.//blockquote')
                or next_node is None or next_node.tag!='p' or len(next_node)!=1 or next_node[0].tag not in {'em','i'}):continue
        cell=nonempty[0];paragraphs=cell.xpath('./p');names=cell.xpath('./p/strong|./p/b')
        if (len(paragraphs)!=1 or len(names)!=1 or not space(names[0].text_content()).endswith(',')
                or compact(cell.text_content())!=compact(paragraphs[0].text_content())
                or not re.fullmatch(r'[А-ЯЁ][а-яё]+(?:[- ][А-ЯЁ][а-яё]+){1,2},',space(names[0].text_content()))
                or not space(next_node.text_content()).startswith(('«','“','"'))):continue
        from lxml import html
        restored=html.Element('div');restored.append(deepcopy(paragraphs[0]));restored.tail=table.tail;table.getparent().replace(table,restored)
        counts['restored_kontur_quote_credits']+=1;counts['unresolved_kontur_quote_credits']+=1
    return counts,prefix
