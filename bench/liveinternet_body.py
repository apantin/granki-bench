"""Граница записи и явные служебные роли старого шаблона LiveInternet."""
import re
from datetime import datetime
from urllib.parse import urlsplit


def has(node, token):return token in node.get('class','').split()
def space(text):return ' '.join(text.split())
def compact(text):return ''.join(text.split())


MONTHS={name:i+1 for i,name in enumerate(('января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'))}
COUNTERS=('removed_liveinternet_mood_fields','removed_liveinternet_profile_footers',
          'removed_liveinternet_marquee_footers','removed_liveinternet_image_captions')


def bind(tree,host,url):
    """URL записи, единственный CONBL и один внешний MESS обязаны согласоваться."""
    if host!='liveinternet.ru':return None
    try:target=urlsplit(url)
    except ValueError:return None
    if target.scheme not in {'http','https'} or (target.hostname or '').removeprefix('www.')!='liveinternet.ru':return None
    match=re.fullmatch(r'/users/([^/]+)/post([0-9]+)/?',target.path)
    if not match:return None
    posts=tree.xpath('//*[@id=$key]',key='post'+match[2])
    if len(posts)!=1 or posts[0].tag!='div' or not has(posts[0],'CONBL'):return None
    post=posts[0]
    bodies=[n for n in post.xpath('.//div') if has(n,'MESS')]
    outer=[n for n in bodies if not any(a in bodies for a in n.iterancestors())]
    if len(outer)!=1:return None
    main=outer[0];nested=[n for n in bodies if n is not main]
    # Обычное вложенное тело неизвестного назначения не становится статьёй.
    if nested and (len(nested)!=1 or not has(nested[0],'QUOT_T')
                   or not any(has(n,'QUOT_B') for n in nested[0].xpath('./div'))):return None
    titles=[n for n in post.xpath('.//h1') if has(n,'ZAG') and space(n.text_content())
            and main not in n.iterancestors()]
    title=titles[0] if len(titles)==1 else None
    dates=[n for n in post.xpath('./span') if has(n,'GL_MAR5B')]
    date=None
    if len(dates)==1:
        found=re.fullmatch(r'[А-Яа-яЁё]+, (\d{1,2}) ([А-Яа-яЁё]+) (\d{4}) г\. (\d{2}):(\d{2})',space(dates[0].text or ''))
        if found:
            day,month,year,hour,minute=found.groups()
            try:date=datetime(int(year),MONTHS[month.casefold()],int(day),int(hour),int(minute)).date().isoformat()
            except (KeyError,ValueError):pass
    return dict(main=main,title=title,date=date,owner_path='/users/'+match[1],nested_quotes=len(nested))


def protected(node):
    return any(n.tag in {'blockquote','pre','code','table','figure','figcaption'} for n in [node,*node.iterancestors()])


def image_only(node):
    return (node.tag=='p' and bool(node.xpath('.//img')) and not space(node.text_content())
            and all(n.tag in {'img','a','br','span'} for n in node.iterdescendants()))


def emphasized_only(node):
    emph=node.xpath('./em|./i')
    return (node.tag=='p' and len(emph)==1 and bool(space(emph[0].text_content()))
            and all(n.tag in {'em','i','b','strong','span','br'} for n in node.iterdescendants())
            and compact(node.text_content())==compact(emph[0].text_content()))


def same_paragraph_captions(node):
    if node.tag!='p' or not node.xpath('.//img'):return 0
    allowed={'img','a','br','em','i','span','b','strong'}
    if any(n.tag not in allowed for n in node.iterdescendants()):return 0
    captions=[n for n in node.xpath('.//em|.//i') if not any(a.tag in {'em','i'} for a in n.iterancestors() if a is not node)]
    if not captions or compact(node.text_content())!=''.join(compact(n.text_content()) for n in captions):return 0
    events=[n for n in node.iterdescendants() if n.tag=='img' or n in captions]
    if len(events)!=2*len(captions):return 0
    return len(captions) if all(events[i].tag=='img' and events[i+1] in captions and space(events[i+1].text_content())
                                for i in range(0,len(events),2)) else 0


def terminal(main,node):
    """После компонента допустимы лишь пустые/невидимые элементы, без прозы."""
    while node is not None and node is not main:
        if (node.tail or '').strip():return False
        for sibling in node.itersiblings():
            if (sibling.tail or '').strip():return False
            if sibling.tag in {'script','style','noscript'}:continue
            if space(sibling.text_content()):return False
            if sibling.xpath('.//pre|.//table|.//h1|.//h2|.//p'):return False
        node=node.getparent()
    return node is main


def profile_footer(node,owner_path):
    if node.tag!='center' or any(n.tag not in {'center','font','a','b','strong','i','em','span','img','br'} for n in node.iterdescendants()):return False
    links=node.xpath('.//a[@href]')
    if not links or compact(node.text_content())!=''.join(compact(n.text_content()) for n in links):return False
    profile=False
    for link in links:
        try:target=urlsplit(link.get('href',''))
        except ValueError:return False
        if (target.scheme not in {'','http','https'} or (target.hostname or 'liveinternet.ru') not in {'liveinternet.ru','www.liveinternet.ru'}
                or target.query or target.fragment or target.path.rstrip('/') not in {owner_path,owner_path+'/profile'}):return False
        profile|=target.path.rstrip('/')==owner_path+'/profile'
    return profile


def marquee_footer(node):
    if node.tag!='div' or len(node.xpath('.//marquee'))!=1:return False
    links=node.xpath('./a[@href]');small=node.xpath('./a/marquee/font[@size="1"]')
    if len(links)!=1 or len(small)!=1:return False
    if any(n.tag not in {'a','marquee','font','span','br'} for n in node.iterdescendants()):return False
    return bool(space(small[0].text_content())) and compact(node.text_content())==compact(small[0].text_content())


def repair(bound):
    counts={name:0 for name in COUNTERS}
    if bound is None:return counts
    main=bound['main']
    # Ведущее поле CMS: прямой b, ровно метка и одно em, до обычной прозы.
    leading=not (main.text or '').strip()
    for node in list(main):
        if leading and node.tag=='b' and len(node)==1 and node[0].tag=='em' and len(node[0])==0 and space(node[0].text or '') and space(node.text or '')=='Настроение сейчас -' and not (node[0].tail or '').strip():
            tail=node.tail or ''
            node.drop_tree();counts['removed_liveinternet_mood_fields']+=1
            if tail.strip():leading=False
            continue
        if node.tag not in {'br','nobr','strong','script','style'} and space(node.text_content()):leading=False
        if (node.tail or '').strip():leading=False
    for node in reversed(list(main.xpath('.//center|.//div'))):
        if protected(node) or not terminal(main,node):continue
        if profile_footer(node,bound['owner_path']):
            node.drop_tree();counts['removed_liveinternet_profile_footers']+=1
        elif marquee_footer(node):
            node.drop_tree();counts['removed_liveinternet_marquee_footers']+=1
    used_images=set()
    for node in list(main.xpath('.//p')):
        if node.getparent() is None or main not in node.iterancestors() or protected(node):continue
        previous=node.getprevious()
        captions=same_paragraph_captions(node)
        if captions:
            node.drop_tree();counts['removed_liveinternet_image_captions']+=captions
        elif previous is not None and previous not in used_images and image_only(previous) and emphasized_only(node):
            used_images.add(previous)
            node.drop_tree();counts['removed_liveinternet_image_captions']+=1
    return counts
