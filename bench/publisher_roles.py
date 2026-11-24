"""Подтверждённые издательские компоненты, без текстов отдельных публикаций."""
import json
from urllib.parse import urlsplit


def has(node,token):return token in node.get('class','').split()


def compact(text):return ''.join(text.split())


def byline(node,kind):
    roles={'article-author__name','article-author__position','article-author__link'} if kind=='article-author' else {'ugc-author-block__name'}
    roots=[n for n in node.iterdescendants() if isinstance(n.tag,str) and roles.intersection(n.get('class','').split())]
    roots=[n for n in roots if not any(a in roots for a in n.iterancestors())]
    names=[n for n in node.iterdescendants() if has(n,kind+'__name') and n.text_content().strip()]
    return (len(names)==1 and compact(node.text_content())==''.join(compact(n.text_content()) for n in roots)
            and not node.xpath('.//pre|.//blockquote|.//table|.//form'))


def widget_types(node):
    try:data=json.loads(node.get('data-component-data',''))
    except (ValueError,RecursionError):return None
    if not isinstance(data,dict) or not isinstance(data.get('levels'),list) or not data['levels']:return None
    types=[]
    for level in data['levels']:
        if not isinstance(level,dict) or level.get('type')!='1-slot' or not isinstance(level.get('flows'),list) or not level['flows']:return None
        for flow in level['flows']:
            if not isinstance(flow,dict) or flow.get('type')!='cards' or not isinstance(flow.get('items'),list) or not flow['items']:return None
            if flow.get('totalItemsCount',len(flow['items']))!=len(flow['items']):return None
            for item in flow['items']:
                if not isinstance(item,dict) or item.get('type') not in {'promo-banner','subscription'}:return None
                types.append(item['type'])
    return types


NOTICES={
    'Этот текст написан в Сообществе, в нем сохранены авторский стиль и орфография.',
    'Этот текст написал читатель в Сообществе Т—Ж. Бережно отредактировано и оформлено по стандартам редакции.',
    'Это истории читателей из Сообщества Т—Ж. Редакция задала наводящие вопросы, бережно отредактировала и оформила текст по стандартам журнала.',
}


def notice(node,host):
    text=' '.join(node.text_content().split());links=node.xpath('.//a')
    if text not in NOTICES or len(links)!=1:return False
    try:target=urlsplit(links[0].get('href',''))
    except ValueError:return False
    return (target.scheme in {'','http','https'} and (target.hostname or host)==host
            and target.path=='/community/' and not target.query and not target.fragment)


def repair(main,host):
    counts=dict(removed_publisher_bylines=0,removed_publisher_widgets=0,removed_publisher_notices=0,
                removed_publisher_service_subtitles=0,removed_publisher_tile_actions=0,separated_publisher_tile_descriptions=0,
                restored_publisher_asides=0,restored_publisher_details_labels=0,unresolved_publisher_widgets=0)
    if host!='journal.tinkoff.ru':return counts
    if main is None:return {k:None for k in counts}
    # Сначала типизированные компоненты: старый email-filter удаляет лишь
    # внутреннюю форму, после чего внешний заголовок подписной tile уже не опознать.
    for node in list(main.xpath('.//*[@data-component-name="levels"]')):
        if node.getparent() is None:continue
        types=widget_types(node)
        if not types:counts['unresolved_publisher_widgets']+=1;continue
        target=node
        if set(types)=={'subscription'}:
            tiles=[a for a in node.iterancestors() if has(a,'tile')]
            if tiles:
                tile=tiles[0];titles=tile.xpath('.//h3[contains(concat(" ",normalize-space(@class)," ")," tile__title ")]')
                if (len(titles)==1 and compact(tile.text_content())==compact(titles[0].text_content())
                        and len(tile.xpath('.//*[@data-component-name="levels"]'))==1):target=tile
        target.drop_tree();counts['removed_publisher_widgets']+=1
    for kind in ['article-author','ugc-author-block']:
        for node in list(main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," '+kind+' ")]')):
            if node.getparent() is not None and byline(node,kind):node.drop_tree();counts['removed_publisher_bylines']+=1
    articles=[n for n in main.iterancestors() if n.tag=='article']
    if articles:
        subtitles=articles[0].xpath('.//h3[contains(concat(" ",normalize-space(@class)," ")," article-header__subtitle ")]')
        if len(subtitles)==1 and ' '.join(subtitles[0].text_content().split()) in {'Вопрос читательницы Т—Ж','Вопрос читателя Т—Ж'}:
            subtitles[0].drop_tree();counts['removed_publisher_service_subtitles']+=1
    for node in list(main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," incut ")]'
                                '|.//div[contains(concat(" ",normalize-space(@class)," ")," panel__inner ")]')):
        if node.getparent() is not None and notice(node,host):node.drop_tree();counts['removed_publisher_notices']+=1
    for node in list(main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," tile__button ")]')):
        if any(has(a,'tile') for a in node.iterancestors()) and node.tag in {'a','button'}:node.drop_tree();counts['removed_publisher_tile_actions']+=1
    for title in main.xpath('.//h3[contains(concat(" ",normalize-space(@class)," ")," tile__title ")]'):
        descriptions=[n for n in title if has(n,'tile__description')]
        if len(descriptions)!=1 or descriptions[0] is not title[-1] or (descriptions[0].tail or '').strip():continue
        description=descriptions[0];title.remove(description);title.addnext(description)
        counts['separated_publisher_tile_descriptions']+=1
    for node in main.xpath('.//aside'):
        if set(node.get('class','').split())!={'aside'} or node.xpath('.//a|.//img|.//pre|.//blockquote|.//table|.//form'):continue
        bodies=node.xpath('./div[contains(concat(" ",normalize-space(@class)," ")," aside__text ")]')
        if len(bodies)!=1 or len(node)!=1 or (node.text or '').strip() or (bodies[0].tail or '').strip():continue
        body=bodies[0]
        if ((body.text or '').strip() or not len(body) or any(n.tag!='p' or (n.tail or '').strip() for n in body)
                or sum(bool(n.text_content().strip()) for n in body)!=1
                or any(n.tag not in {'p','span','b','strong','em','i','u','br'} for n in body.iterdescendants())):continue
        node.tag='div';counts['restored_publisher_asides']+=1
    for node in main.xpath('.//p[contains(concat(" ",normalize-space(@class)," ")," js-unfolder ")]'):
        following=node.getnext();buttons=node.xpath('./button')
        if (not {'details','highlight','js-unfolder'}<=set(node.get('class','').split()) or len(node)!=1 or len(buttons)!=1
                or (node.text or '').strip() or (buttons[0].tail or '').strip() or following is None or not has(following,'details-content')):continue
        button=buttons[0];labels=button.xpath('./u[contains(concat(" ",normalize-space(@class)," ")," details__pseudolink ")]')
        if (button.get('role')!='button' or not {'details__button','js-unfolder-button'}<=set(button.get('class','').split())
                or len(button)!=1 or len(labels)!=1 or len(labels[0]) or not labels[0].text_content().strip()
                or (button.text or '').strip() or (labels[0].tail or '').strip()):continue
        label=labels[0].text_content();node[:]=[];node.tag='h3';node.text=label;node.attrib.clear()
        counts['restored_publisher_details_labels']+=1
    return counts
