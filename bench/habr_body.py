"""Явные роли Habr: формулы, код и ограниченные служебные окончания."""
import json
import re
from urllib.parse import urlsplit


def address(value):
    try:
        parsed=urlsplit(value)
        return parsed if parsed.scheme in {'http','https'} and parsed.hostname else None
    except ValueError:return None


def safe(node):
    return all(isinstance(n.tag,str) and n.tag not in {'script','style','template','noscript','iframe'}
               and not n.get('cite') and 'author' not in n.get('itemprop','').split()
               and not any(k.casefold().startswith('on') for k in n.attrib) for n in node.iter())


def empty(node):
    return node.tag in {'br','div','span','p'} and not len(node) and not (node.text or '').strip() and not (node.tail or '').strip()


def terminal(node,main):
    while node is not main:
        if (node.tail or '').strip() or any(not empty(n) for n in node.itersiblings()):return False
        node=node.getparent()
        if node is None:return False
    return True


def repair(main,host):
    counts=dict(preserved_formula_alts=0,unresolved_formula_images=0,masked_standalone_code=0,
                masked_json_spoilers=0,removed_code_labels=0,removed_embedded_tweets=0,
                removed_social_ctas=0,removed_book_ctas=0,removed_terminal_source_credits=0)
    if host!='habr.com':return counts
    if main is None:return {k:None for k in counts}
    # Не интерпретируем произвольный alt или MathML как авторскую формулу.
    for node in main.xpath('.//math'):
        images=node.xpath('./img');image=images[0] if len(images)==1 else None
        parsed=address(image.get('src','')) if image is not None else None
        if (image is None or len(node)!=1 or len(image) or not safe(node) or not parsed
                or parsed.hostname!='habrastorage.org' or not parsed.path.startswith('/getpro/habr/formulas/')
                or not parsed.path.endswith('.svg') or image.get('data-tex') not in {'inline','display'}
                or not image.get('alt','').strip() or node.text_content().strip()
                or image.get('data-src',image.get('src'))!=image.get('src')
                or any(n.tag in {'pre','code','blockquote','figure','aside','nav','footer','table'} for n in node.iterancestors() if n is not main)):
            counts['unresolved_formula_images']+=1;continue
        node.tag='span';node.text=image.get('alt');node[:]=[];node.attrib.clear()
        counts['preserved_formula_alts']+=1
    for node in list(main.xpath('.//blockquote[contains(concat(" ",normalize-space(@class)," ")," twitter-tweet ")]')):
        links=node.xpath('./a');paragraphs=node.xpath('./p')
        if not safe(node) or len(links)!=1 or len(paragraphs)!=1 or len(node)!=2:continue
        link=address(links[0].get('href',''))
        if (link and link.hostname in {'twitter.com','www.twitter.com','x.com','www.x.com'}
                and re.fullmatch(r'/[A-Za-z0-9_]+/status/[0-9]+/?',link.path)
                and paragraphs[0].text_content().strip() and (paragraphs[0].tail or '').strip()):
            node.drop_tree();counts['removed_embedded_tweets']+=1
    for node in main.xpath('.//code[not(ancestor::pre)]'):
        before,after=node.getprevious(),node.getnext()
        if (node.getparent() is main and before is not None and after is not None
                and before.tag==after.tag=='br' and not (before.tail or '').strip()
                and not (node.tail or '').strip() and node.text_content().strip() and safe(node)
                and all(n.tag in {'span','br'} for n in node.iterdescendants())):
            node.tag='pre';counts['masked_standalone_code']+=1
    for node in main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," spoiler ")]'):
        title=node.xpath('./b[contains(concat(" ",normalize-space(@class)," ")," spoiler_title ")]')
        body=node.xpath('./div[contains(concat(" ",normalize-space(@class)," ")," spoiler_text ")]')
        if (len(title)!=1 or len(body)!=1 or len(node)!=2 or not safe(node)
                or not re.fullmatch(r'(?:Пример\s+)?JSON',' '.join(title[0].text_content().split()),re.I)
                or any(n.tag not in {'br','span'} for n in body[0].iterdescendants())
                or (node.text or '').strip() or (title[0].tail or '').strip() or (body[0].tail or '').strip()
                or any(n.tag in {'pre','blockquote','figure','aside','nav','footer','table'} for n in node.iterancestors() if n is not main)):continue
        raw=body[0].text_content().replace('«','"').replace('»','"')
        try:parsed=json.loads(raw)
        except (ValueError,RecursionError):continue
        if not isinstance(parsed,(dict,list)):continue
        title[0].drop_tree();body[0].tag='pre'
        counts['masked_json_spoilers']+=1;counts['removed_code_labels']+=1
    for node in list(main.xpath('.//p')):
        if not terminal(node,main) or not safe(node):continue
        links=node.xpath('.//a');parsed=[address(a.get('href','')) for a in links]
        text=' '.join(node.text_content().split())
        # Отдельное полностью курсивное послесловие, только социальные профили.
        if (links and all(p and p.hostname in {'t.me','twitter.com','www.twitter.com','x.com','www.x.com'}
                          and re.fullmatch(r'/[A-Za-z0-9_]+/?',p.path) and not p.query and not p.fragment for p in parsed)
                and all(n.tag in {'em','a'} for n in node.iterdescendants())
                and ''.join(text.split())==''.join(''.join(n.text_content().split()) for n in node.xpath('.//em[not(ancestor::em)]'))
                and re.match(r'^P\.?S\.?(?:\s|:)',text,re.I) and re.search(r'\b(?:буду\s+)?рад(?:а)?\s+новым\s+подписчикам\b',text,re.I)):
            node.drop_tree();counts['removed_social_ctas']+=1
    for label in list(main.xpath('.//u|.//strong|.//b')):
        if ' '.join(label.text_content().split())!='Важно!' or len(label):continue
        link_wrapper=label.getnext();parent=label.getparent()
        before=label.getprevious()
        if (link_wrapper is None or link_wrapper.tag not in {'b','strong'} or parent.tag!='div'
                or before is None or before.tag!='br' or (before.tail or '').strip()
                or any(n.tag in {'pre','code','blockquote','figure','aside','nav','footer','table'} for n in label.iterancestors() if n is not main)):continue
        links=link_wrapper.xpath('./a');suffix=list(label.itersiblings())
        if (len(links)!=1 or len(link_wrapper)!=1 or (link_wrapper.text or '').strip()
                or (links[0].tail or '').strip() or len(suffix)<3
                or any(n.tag!='br' or not empty(n) for n in suffix[1:3])):continue
        parsed=address(links[0].get('href',''))
        if (parsed and parsed.hostname=='t.me' and safe(label) and safe(link_wrapper)
                and re.fullmatch(r'Все обновления\b[^.!?]*\bтелеграм[- ]канал\w*\s*',(label.tail or '').strip(),re.I)
                and re.fullmatch(r'\.\s*Подписывайтесь\b[^.!?]*[.!?]?\s*',(link_wrapper.tail or '').strip(),re.I)):
            for node in [label,link_wrapper]:node.tail=None;node.drop_tree()
            counts['removed_social_ctas']+=1
    for node in list(main.xpath('.//i|.//em')):
        links=node.xpath('./a');before=node.getprevious()
        if (len(links)==1 and len(node)==1 and not (node.text or '').strip() and not (links[0].tail or '').strip()
                and before is not None and before.tag=='br' and terminal(node,main) and safe(node)
                and address(links[0].get('href','')) and re.fullmatch(
                    r'\s*С полной версией книги (?:вы )?можете ознакомиться(?:,)? (?:перейдя )?по ссылке:\s*',before.tail or '',re.I)):
            before.tail=None;node.drop_tree();counts['removed_book_ctas']+=1
    for node in list(main.xpath('.//a')):
        if (node.getparent() is not None and node.getparent().tag in {'div','p'}
                and ' '.join(node.text_content().split()).casefold()=='источник' and address(node.get('href',''))
                and terminal(node,main) and safe(node)):
            before=node.getprevious()
            if before is not None and before.tag=='br' and not (before.tail or '').strip():
                node.drop_tree();counts['removed_terminal_source_credits']+=1
    return counts
