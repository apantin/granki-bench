"""Явные роли конструктора и старых подписей Нетологии; без частных данных."""
import re
from urllib.parse import urlsplit


def has(node,token):return token in node.get('class','').split()
def space(text):return ' '.join(text.split())
def compact(text):return ''.join(text.split())


def local(link,prefix):
    try:target=urlsplit(link.get('href',''))
    except ValueError:return False
    return (target.scheme in {'','http','https'} and (target.hostname or 'netology.ru') in {'netology.ru','www.netology.ru'}
            and target.path.startswith(prefix))


def protected(node):
    return any(n.tag in {'blockquote','pre','code'} for n in [node,*node.iterancestors()])


def primary_title(main,host):
    if host!='netology.ru' or main is None or not has(main,'entry-content'):return None
    articles=list(main.iterancestors('article'))
    if not articles:return None
    article=articles[0]
    titles=[n for n in article.xpath('.//h1') if has(n,'entry-title') and space(n.text_content())
            and next(n.iterancestors('article'),None) is article]
    return titles[0] if len(titles)==1 else None


def pure_author(node):
    if node.get('data-container-name') not in {'Автор (десктоп)','Автор (мобильный)'}:return False
    paragraphs=node.xpath('./p')
    portraits=[n for n in node.xpath('./figure') if has(n,'ntlgy-author-portrait') and n.xpath('.//img')]
    if (len(paragraphs) not in {1,2} or len(portraits)!=1 or len(node)!=len(paragraphs)+1
            or node.xpath('.//blockquote|.//pre|.//code|.//table')
            or not all(space(p.text_content()) for p in paragraphs)
            or not all(n.tag in {'strong','b','em','i','a','span','font','br'} for p in paragraphs for n in p.iterdescendants())):return False
    if len(paragraphs)==2:
        role=space(paragraphs[1].text_content())
        if (not re.match(r'^(?:главный редактор|редактор|автор|руководитель|директор|(?:клиентский|креативный|операционный|генеральный|коммерческий|исполнительный) директор|контент[- ]маркетолог|маркетолог|основатель|эксперт|дизайнер|предприниматель|CEO|CMO|CPO)\b',role,re.I)
                or re.search(r'[.!?]\s+\S|\b(?:говорит|рассказал[аи]?|объяснил[аи]?|пишет|рекомендует|советует|написал[аи]?)\b',role,re.I)):return False
    return compact(node.text_content())==''.join(compact(p.text_content()) for p in paragraphs)


def pure_sidebar(node):
    if (node.get('data-col-width')!='2' or not has(node,'stk-grid-col')
            or node.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6|.//ul|.//ol|.//table|.//pre|.//code|.//blockquote')):return None
    links=node.xpath('.//a[@href]')
    outside=compact(''.join(node.xpath('.//text()[not(ancestor::a)]'))).casefold()
    if links and re.fullmatch(r'(?:читатьтакже[:.]?)+',outside) and all(local(a,'/blog/') for a in links):return 'navigation'
    if links and outside=='курс' and all(local(a,'/programs/') for a in links):return 'courses'
    return None


def wide_course(node):
    if not has(node,'ntlgy-course--wide') or node.xpath('.//blockquote|.//pre|.//code|.//table'):return False
    headings=node.xpath('.//h1|.//h2|.//h3|.//h4|.//h5|.//h6')
    buttons=[n for n in node.xpath('.//div|.//a') if has(n,'ntlgy-btn') and n.get('data-container-name')=='Кнопка']
    labels=[p for p in node.xpath('.//p') if space(p.text_content()).casefold() in {'курс','профессия'}]
    if len(headings)!=1 or headings[0].tag not in {'h3','h4'} or len(buttons)!=1 or len(labels)!=1:return False
    button=buttons[0];links=([button] if button.tag=='a' and button.get('href') else [])+button.xpath('.//a[@href]')
    if space(button.text_content())!='Узнать больше' or any(not local(a,'/programs/') for a in links):return False
    items=node.xpath('.//li')
    if not items:return False
    # Вне явных полей рекламной карточки не должно быть авторской прозы.
    fields=[labels[0],headings[0],button,*items]
    known={n for field in fields for n in field.iter()}
    return all(not (n.text or '').strip() or n in known for n in node.iter()) and all(
        not (n.tail or '').strip() or n.getparent() is not None and n.getparent() in known
        for n in node.iterdescendants())


def publisher_cta(node):
    if node.tag!='p' or any(n.tag not in {'a','em','i','strong','b','span','br'} for n in node.iterdescendants()):return False
    links=node.xpath('.//a[@href]')
    if not links or not any(local(a,'/blog/terms') and space(a.text_content()).casefold()=='условия публикации' for a in links):return False
    start='Хотите написать колонку для {}? Читайте наши условия публикации.'
    suffix=' Чтобы быть в курсе всех новостей и читать новые статьи, присоединяйтесь к Телеграм-каналу Нетологии.'
    templates={compact(prefix+start.format(name)+tail) for prefix in ['', 'Мнение автора и редакции может не совпадать. ']
               for name in ['Нетологии','«Нетологии»','"Нетологии"'] for tail in ['',suffix]}
    if compact(node.text_content()) not in templates:return False
    for a in links:
        try:target=urlsplit(a.get('href',''))
        except ValueError:return False
        if not (local(a,'/blog/terms') and target.path.rstrip('/')=='/blog/terms'
                or target.scheme in {'http','https'} and target.hostname=='t.me' and target.path.rstrip('/')=='/netology_ru'):return False
    return True


def standalone_course(node):
    if node.tag!='p' or any(n.tag not in {'a','strong','b','span','em','i'} for n in node.iterdescendants()):return False
    links=node.xpath('.//a[@href]')
    if len(links)!=1 or not local(links[0],'/programs/'):return False
    outside=compact(''.join(node.xpath('.//text()[not(ancestor::a)]')))
    return outside in {'Обучениевонлайн-университете:курс«»','Обучениевонлайн-университете:курс""'}


def image_caption(node):
    captions=node.xpath('./em|./i')
    if node.tag!='p' or len(captions)!=1 or len(node.xpath('.//img'))!=1 or not space(captions[0].text_content()):return False
    if any(n.tag not in {'em','i','img','a','br','span','strong','b'} for n in node.iterdescendants()):return False
    order=list(node.iter())
    if order.index(node.xpath('.//img')[0])>order.index(captions[0]):return False
    return compact(node.text_content())==compact(captions[0].text_content())


def repair(main,host):
    counts={k:0 for k in ['removed_netology_bylines','unresolved_netology_bylines','removed_netology_courses','unresolved_netology_courses','removed_netology_navigation',
                          'removed_netology_publisher_ctas','removed_netology_image_captions','retained_netology_speaker_blocks']}
    if host!='netology.ru' or main is None or not has(main,'entry-content'):return counts
    for node in list(main.xpath('.//div')):
        if node.getparent() is None or main not in node.iterancestors() or protected(node):continue
        if has(node,'ntlgy-author'):
            if pure_author(node):node.drop_tree();counts['removed_netology_bylines']+=1
            else:
                # Прежний фильтр удаляет любые два p с портретом/strong.
                # В v15 неизвестный или смешанный блок удерживается целиком.
                node.set('class',' '.join('ntlgy-author-unresolved' if c=='ntlgy-author' else c for c in node.get('class','').split()))
                counts['unresolved_netology_bylines']+=1
        elif has(node,'ntlgy-course--wide'):
            if wide_course(node):node.drop_tree();counts['removed_netology_courses']+=1
            else:
                node.set('class',' '.join('ntlgy-course-unresolved' if c=='ntlgy-course--wide' else c for c in node.get('class','').split()))
                counts['unresolved_netology_courses']+=1
    # Сначала вложенная карточка, затем содержащая её колонка. Смешанная
    # колонка с другой прозой не удовлетворяет pure_sidebar.
    for node in reversed(list(main.xpath('.//div'))):
        if node.getparent() is None or main not in node.iterancestors() or protected(node):continue
        kind=pure_sidebar(node)
        if kind:node.drop_tree();counts['removed_netology_'+kind]+=1
    for node in list(main.xpath('.//p')):
        if node.getparent() is None or main not in node.iterancestors() or protected(node):continue
        if publisher_cta(node):node.drop_tree();counts['removed_netology_publisher_ctas']+=1
        elif standalone_course(node):node.drop_tree();counts['removed_netology_courses']+=1
        elif image_caption(node):node.drop_tree();counts['removed_netology_image_captions']+=1
    counts['retained_netology_speaker_blocks']=sum(
        has(n,'ntlgy-speaker--narrow') or has(n,'ntlgy-quote--basic') for n in main.xpath('.//div'))
    return counts
