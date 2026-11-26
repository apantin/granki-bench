"""Кандидат сохранения DOM-структуры при явных границах статьи.

Тексты и ссылки отдельных документов не входят в модуль. Не меняет clean-v3.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from .cleaning import HTML_STRUCTURE_VERSION,HTML_EDITORIAL_VERSION,HTML_CONTENT_VERSION,HTML_ROLES_VERSION,HTML_PRE_TABLE_VERSION,HTML_CALLOUT_VERSION,HTML_CODE_TABLE_VERSION,HTML_BODY_VERSION,HTML_PUBLISHER_VERSION,HTML_KONTUR_VERSION,HTML_NETOLOGY_VERSION,_html_article,extracted_text


def decode(content: bytes | str) -> str:
    if isinstance(content,str):return content
    try:return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        charset=re.search(br'charset\s*=\s*[\"\']?([A-Za-z0-9_-]+)',content[:16384],re.I)
        if charset:return content.decode(charset.group(1).decode('ascii'),errors='replace')
        from charset_normalizer import from_bytes
        decoded=from_bytes(content).best()
        if decoded is None:raise ValueError('Не удалось определить кодировку HTML')
        return str(decoded)


def inline_space(text):return re.sub(r'\s+',' ',text or '')


SKIP={'blockquote','figure','figcaption','table','script','style','nav','footer','aside','form','button','svg','noscript','template'}
BLOCK={'p','div','section','article','header','main','address','dl','dt','dd','table','tr','td','th'}


def code_table_blocks(node):
    """Некоторые старые страницы оформляют блок кода таблицей, не данными."""
    if node.tag!='table' or 'code' not in node.get('class','').split():return []
    blocks=node.xpath('.//pre')
    if blocks and not ''.join(node.xpath('.//text()[not(ancestor::pre)]')).strip():return blocks
    return []


def table_grid(node):
    """Только прямоугольные текстовые ячейки, без угадывания заголовков."""
    rows=node.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
    if len(rows)<2:return None
    if any(n.tag not in {'caption','tr','thead','tbody','tfoot'} for n in node):return None
    if any(n.tag!='tr' for group in node if group.tag in {'thead','tbody','tfoot'} for n in group):return None
    cells=[list(row) for row in rows]
    if len(cells[0])<2 or any(len(row)!=len(cells[0]) for row in cells):return None
    if any(n.tag not in {'td','th'} or any(n.get(k,'1')!='1' for k in ('rowspan','colspan')) for row in cells for n in row):return None
    captions=node.xpath('./caption')
    if len(captions)>1 or captions and node[0] is not captions[0]:return None
    content=[n for row in cells for n in row]+captions
    allowed={'p','a','span','b','strong','em','i','u','s','small','abbr','br'}
    if any(not isinstance(n.tag,str) or n.tag not in allowed for cell in content for n in cell.iterdescendants()):return None
    # Запрещаем потерю текста между строками/ячейками и их перестановку.
    expected=captions+[n for row in cells for n in row]
    if ''.join(node.text_content().split())!=''.join(''.join(n.text_content().split()) for n in expected):return None
    def value(cell):return ' '.join(render(cell).split()).replace('\\','\\\\').replace('|','\\|')
    lines=['| '+' | '.join(value(cell) for cell in row)+' |' for row in cells]
    if all(n.tag=='th' for n in cells[0]):lines.insert(1,'| '+' | '.join('---' for _ in cells[0])+' |')
    if captions:lines.insert(0,value(captions[0]))
    return '\n'.join(lines)


def render(node,depth=0,*,preserve_tables=False,preserve_list_blocks=False,preserve_code_tables=False,preserve_group_headers=False):
    """Хвост child.tail добавляет родитель: удаление блока не съедает продолжение."""
    tag=node.tag
    blocks=code_table_blocks(node)
    if blocks:return '\n\n'+'\n\n'.join('[КОД]' for _ in blocks)+'\n\n'
    if tag=='table' and preserve_tables:
        if preserve_code_tables:
            from .code_tables import code_grid
            result=code_grid(node,allow_group_headers=preserve_group_headers)
            if result is not None:return '\n\n'+result[0]+'\n\n'
        grid=table_grid(node)
        return '\n\n'+grid+'\n\n' if grid is not None else ''
    if not isinstance(tag,str) or tag in SKIP:return ''
    if tag=='pre':return '\n\n[КОД]\n\n'
    if tag=='br':return '\n'
    if tag=='hr':return '\n\n'
    child_depth=depth+1 if tag in {'ul','ol'} else depth
    content=inline_space(node.text) if tag not in {'ul','ol'} or (node.text or '').strip() else ''
    for child in node:
        tail=inline_space(child.tail)
        if tag in {'ul','ol'} and not tail.strip():tail=''
        content+=render(child,child_depth,preserve_tables=preserve_tables,preserve_list_blocks=preserve_list_blocks,preserve_code_tables=preserve_code_tables,preserve_group_headers=preserve_group_headers)+tail
    if tag in {'h1','h2','h3','h4','h5','h6'}:
        value=' '.join(content.split())
        return '\n\n'+'#'*int(tag[1])+' '+value+'\n\n' if value else ''
    if tag=='li':
        content=content.strip()
        if preserve_list_blocks:
            lines=content.splitlines()
            continuation=[' '*max(2*depth,len(re.match(r' *',line).group()))+line.lstrip(' ') if line.strip() else '' for line in lines[1:]]
            content='\n'.join(lines[:1]+continuation)
        return '  '*max(0,depth-1)+'- '+content+'\n'
    if tag in {'ul','ol'}:return '\n\n'+content.strip('\n')+'\n\n'
    if tag in BLOCK:return '\n\n'+content.strip()+'\n\n'
    return content


def code_count(node,*,preserve_code_tables=False,preserve_group_headers=False):
    blocks=code_table_blocks(node)
    if blocks:return len(blocks)
    if node.tag=='table' and preserve_code_tables:
        from .code_tables import code_grid
        result=code_grid(node,allow_group_headers=preserve_group_headers)
        if result is not None:return result[1]
    if not isinstance(node.tag,str) or node.tag in SKIP:return 0
    if node.tag=='pre':return 1
    return sum(code_count(child,preserve_code_tables=preserve_code_tables,preserve_group_headers=preserve_group_headers) for child in node)


def attributed_quote(node):
    if node.get('cite') or node.xpath('.//cite|.//*[@itemprop="author"]'):return True
    return any(n.text_content().strip() and any(c.endswith(('__author','__source','__credit')) for c in n.get('class','').split()) for n in node.iterdescendants() if isinstance(n.tag,str))


def restore_editorial_blocks(main,host):
    callouts=0;quotes=0;unresolved=0
    for node in main.xpath('.//blockquote'):
        parents=[]
        for parent in node.iterancestors():
            if parent is main:break
            parents.append(parent)
        named_teplitsa_quote=(host=='te-st.org' and 'wp-block-tst-tst-quote' in node.get('class','').split()
            and node.xpath('./p[contains(concat(" ",normalize-space(@class)," ")," author-name ") and normalize-space()]'))
        if any(n.tag in SKIP-{'figure'} for n in parents) or attributed_quote(node) or named_teplitsa_quote:continue
        figures=[n for n in parents if n.tag=='figure']
        if any(''.join(n.text_content().split())!=''.join(node.text_content().split()) for n in figures):
            unresolved+=1;continue
        for figure in figures:figure.tag='div'
        if host in {'vc.ru','tjournal.ru'} and 'block-incut' in node.get('class','').split():callouts+=1
        else:quotes+=1
        node.tag='div'
    return dict(preserved_editorial_callouts=callouts,preserved_unattributed_quotes=quotes,
                quote_review_blocks=callouts+quotes+unresolved,unresolved_mixed_figures=unresolved)


def restore_legacy_html_blocks(main,host):
    restored=0;unresolved=0
    if host in {'vc.ru','tjournal.ru'} and 'content--legacy' in main.get('class','').split():
        for figure in main.xpath('./figure'):
            blocks=figure.xpath('./div[contains(concat(" ",normalize-space(@class)," ")," block-html ")]')
            if len(blocks)!=1:continue
            if ''.join(figure.text_content().split())!=''.join(blocks[0].text_content().split()):
                unresolved+=1;continue
            # У старого формата figure оборачивает весь HTML статьи, не иллюстрацию.
            figure.tag='div';restored+=1
    return dict(preserved_legacy_html_blocks=restored,unresolved_legacy_html_figures=unresolved)


def restore_label_tables(main,host):
    """Одномерный список подписей над логотипами, не произвольная таблица данных."""
    restored=0
    if host not in {'selectel.ru','blog.selectel.ru'}:return restored
    for table in main.xpath('./table'):
        rows=table.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
        if len(rows)!=2 or table.xpath('.//table|.//pre|.//blockquote|.//figure|.//figcaption'):continue
        labels=list(rows[0]);pictures=list(rows[1])
        if len(labels)<2 or len(labels)!=len(pictures):continue
        if any(n.tag!='th' or not n.text_content().strip() for n in labels):continue
        if any(n.tag not in {'td','th'} or n.text_content().strip() or not n.xpath('.//img') for n in pictures):continue
        if any(n.get(k,'1')!='1' for n in labels+pictures for k in ('rowspan','colspan')):continue
        if ''.join(table.text_content().split())!=''.join(''.join(n.text_content().split()) for n in labels):continue
        table.tag='ul';table.text=None;table[:]=labels
        for node in labels:node.tag='li';node.tail=None
        restored+=1
    return restored


def content_table_status(main,*,preserve_code_tables=False,preserve_group_headers=False):
    preserved=0;unresolved=0
    for node in main.xpath('.//table'):
        parents=[]
        for parent in node.iterancestors():
            if parent is main:break
            parents.append(parent)
        if any(n.tag in SKIP for n in parents) or code_table_blocks(node):continue
        code=None
        if preserve_code_tables:
            from .code_tables import code_grid
            code=code_grid(node,allow_group_headers=preserve_group_headers)
        if table_grid(node) is None and code is None:unresolved+=1
        else:preserved+=1
    return dict(preserved_data_tables=preserved,unresolved_data_tables=unresolved)


def drop_content_ads(main,host):
    removed=0
    if host not in {'vc.ru','tjournal.ru'}:return removed
    for node in main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," propaganda ")]'):
        footers=node.xpath('./div[contains(concat(" ",normalize-space(@class)," ")," propaganda__footer ")]')
        if len(footers)!=1:continue
        footer=footers[0];links=footer.xpath('./a[contains(concat(" ",normalize-space(@class)," ")," propaganda__link ")]')
        if len(footer)!=2 or len(links)!=2:continue
        expected=[('/business','Купить рекламу'),('/plus','Отключить')]
        if any((urlsplit(a.get('href','')).hostname or host)!=host or
               (urlsplit(a.get('href','')).path,' '.join(a.text_content().split()))!=pair for a,pair in zip(links,expected)):continue
        if ''.join(node.text_content().split())!=''.join(''.join(a.text_content().split()) for a in links):continue
        if any(n.tag not in {'div','a','span'} for n in node.iterdescendants()):continue
        node.drop_tree();removed+=1
    return removed


def drop_editorial_widgets(main,host):
    source_credits=[]
    if host in {'selectel.ru','blog.selectel.ru'}:
        for node in main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," post__preview-author ")]'):
            cards=node.xpath('./a[contains(concat(" ",normalize-space(@class)," ")," author-card ")]')
            if len(node)!=1 or len(cards)!=1:continue
            target=urlsplit(cards[0].get('href',''))
            names=cards[0].xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," author-card__name ") and normalize-space()]')
            if (len(names)==1 and (target.hostname or host) in {'selectel.ru','blog.selectel.ru'}
                    and target.path.startswith('/blog/author/') and ''.join(node.text_content().split())==''.join(cards[0].text_content().split())):node.drop_tree()
    if host=='te-st.org':
        for node in main.xpath('./p[contains(concat(" ",normalize-space(@class)," ")," wp-block-paragraph ")]'):
            links=node.xpath('./a[@href]');value=' '.join(node.text_content().split())
            if len(node)==1 and len(links)==1:
                label=' '.join(links[0].text_content().split()).removesuffix('.')
                target=urlsplit(links[0].get('href',''))
                if label in {'Узнать подробности','Зарегистрироваться'} and value in {label,label+'.'} and target.scheme in {'http','https'} and target.hostname:node.drop_tree()
        for node in main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," testimonial ")]'):
            if any(cite.text_content().strip() for cite in node.xpath('.//cite')):node.drop_tree()
        for node in main.xpath('.//blockquote'):
            links=node.xpath('.//a[@href]')
            label=' '.join(''.join(node.xpath('.//text()[not(ancestor::a)]')).split()).casefold()
            if label in {'еще по теме:','ещё по теме:'} and links and all(
                    (urlsplit(a.get('href','')).hostname or host).removeprefix('www.')==host
                    and re.match(r'^/(?:\d{4}/\d{2}/\d{2}/|reports/[^/]+)',urlsplit(a.get('href','')).path) for a in links):node.drop_tree()
    if host=='journal.tinkoff.ru':
        for node in main.xpath('./div[contains(concat(" ",normalize-space(@class)," ")," article-author ") and @itemprop="author"][.//*[@itemprop="name"]]'):
            if node.xpath('.//a[contains(concat(" ",normalize-space(@class)," ")," article-author__link ")]'):node.drop_tree()
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," button_plashka ")]'):
            links=node.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," panel__button-wrapper ")]//a[contains(concat(" ",normalize-space(@class)," ")," button ")]')
            forms={'/chto-delat-form/':'Задать вопрос','/education-form/':'Рассказать'}
            if any((urlsplit(a.get('href','').strip()).hostname or host)==host
                   and forms.get(urlsplit(a.get('href','').strip()).path)==' '.join(a.text_content().split()) for a in links):node.drop_tree()
    if host=='snob.ru':
        for node in main.xpath('./div[contains(concat(" ",normalize-space(@class)," ")," sharer ")]'):
            headings=node.xpath('./h5')
            if len(headings)==1 and ' '.join(headings[0].text_content().split())=='Поделиться:':node.drop_tree()
    if host=='netology.ru':
        for node in main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," ntlgy-author ")]'):
            paragraphs=node.xpath('./p')
            portraits=node.xpath('./figure[contains(concat(" ",normalize-space(@class)," ")," ntlgy-author-portrait ")][.//img]')
            if (len(paragraphs)==2 and len(portraits)==1 and not node.xpath('.//blockquote|.//pre|.//cite')
                    and paragraphs[0].xpath('./strong[normalize-space()]')
                    and ''.join(node.text_content().split())==''.join(''.join(p.text_content().split()) for p in paragraphs)):node.drop_tree()
        for node in main.xpath('./p'):
            links=node.xpath('./a[@href]')
            residual=' '.join(''.join(node.xpath('.//text()[not(ancestor::a)]')).split())
            if len(node)==1 and len(links)==1 and residual in {'Программа обучения:','Программа обучения: «»','Программа обучения: ""'}:
                target=urlsplit(links[0].get('href'))
                if (target.hostname or host)==host and target.path.startswith('/programs/'):node.drop_tree();continue
            if node.getparent() is not None and pure_related_links(node,host,('Читать ещё:','Читать еще:','Читать ещё: «»','Читать еще: «»','Читать ещё: ""','Читать еще: ""')):node.drop_tree()
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," ntlgy-course--wide ")]'):
            if any((urlsplit(a.get('href','')).hostname or host)==host and urlsplit(a.get('href','')).path.startswith('/programs/')
                   and ' '.join(a.text_content().split())=='Узнать больше' for a in node.xpath('.//a')):node.drop_tree()
        # Колонка конструктора может содержать и всю статью: убираем только
        # чистую навигацию с явной меткой, без другой нелинкованной прозы.
        for node in main.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," stk-grid-col ")]'):
            if node.getparent() is not None and pure_related_links(node,host,('Читать также',)):node.drop_tree()
    if host=='texterra.ru':
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," incut ")]'):
            if pure_related_links(node,host,('Читайте также:',)):node.drop_tree()
        for node in main.xpath('.//span[@id="postId"]'):
            if re.search(r'(?:^|;)\s*display\s*:\s*none\s*(?:!important\s*)?(?:;|$)',node.get('style',''),re.I):node.drop_tree()
    if host=='xakep.ru':
        for node in main.xpath('./div[@id="toc"]'):
            links=node.xpath('.//a[@href]')
            if links and all(a.get('href').startswith('#toc') for a in links) and ' '.join(''.join(node.xpath('.//text()[not(ancestor::a)]')).split())=='Содержание статьи':node.drop_tree()
    if host=='kontur.ru':
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," text-block_test ")]'):
            links=node.xpath('.//a[contains(concat(" ",normalize-space(@class)," ")," btn ") and contains(concat(" ",normalize-space(@rel)," ")," nofollow ")]')
            if any(' '.join(a.text_content().split())=='Узнать больше' for a in links):node.drop_tree()
    if host=='zavtra.ru':
        galleries=main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," photogall ")][.//img]')
        for gallery in galleries:
            previous=gallery.getprevious()
            if previous is not None and previous.tag=='p':
                value=''.join(previous.text_content().split())
                emphasized=''.join(''.join(n.text_content().split()) for n in previous.xpath('./strong'))
                if value==emphasized and re.match(r'^Илл\.',previous.text_content().strip()):previous.drop_tree()
            gallery.drop_tree()
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," zen_inv ")]'):
            if any((urlsplit(a.get('href','')).hostname or '')=='zen.yandex.ru' for a in node.xpath('.//a')):node.drop_tree()
        paragraphs=main.xpath('./p[last()]')
        if paragraphs:
            node=paragraphs[0];strong=node.xpath('./strong');value=' '.join(node.text_content().split())
            links=node.xpath('.//a[@href]')
            terminal_source=(value=='Источник' and len(links)==1 and 'nofollow' in links[0].get('rel','').split()
                and urlsplit(links[0].get('href','')).scheme in {'http','https'} and urlsplit(links[0].get('href','')).hostname
                and urlsplit(links[0].get('href','')).hostname.removeprefix('www.')!=host)
            radio_source=(re.match(r'^Из эфира на\b',value,re.I)
                and any((urlsplit(a.get('href','')).hostname or '').removeprefix('www.')=='radiokp.ru'
                        and urlsplit(a.get('href','')).path.startswith('/podcast/')
                        and 'nofollow' in a.get('rel','').split() for a in links))
            if (node.getnext() is None and len(node)==1 and len(strong)==1
                    and value==' '.join(strong[0].text_content().split()) and (terminal_source or radio_source)):
                source_credits.append(dict(text=value,links=[a.get('href') for a in links]));node.drop_tree()
        paragraphs=main.xpath('./p[last()]')
        if paragraphs:
            node=paragraphs[0];strong=node.xpath('./strong');value=' '.join(node.text_content().split())
            if (node.getnext() is None and len(node)==1 and len(strong)==1
                    and value==' '.join(strong[0].text_content().split()) and value.startswith('На фото:')):node.drop_tree()
    if host=='liveinternet.ru':
        nodes=main.xpath('./p[1]')
        if nodes:
            node=nodes[0];bold=node.xpath('./b')
            if (len(bold)==1 and ''.join(node.text_content().split())==''.join(bold[0].text_content().split())
                    and ' '.join(node.text_content().split()).startswith('Настроение сейчас')):node.drop_tree()
    return source_credits


def pure_related_links(node,host,labels):
    links=node.xpath('.//a[@href]')
    if not links or any((urlsplit(a.get('href','')).hostname or host)!=host or not urlsplit(a.get('href','')).path.startswith('/blog/') for a in links):return False
    residual=' '.join(''.join(node.xpath('.//text()[not(ancestor::a)]')).split()).rstrip(' ?')
    return residual in labels


def choose_editorial_main(tree,host):
    if host=='snob.ru':
        nodes=tree.xpath('//article[@data-article and (contains(concat(" ",normalize-space(@class)," ")," blogEntryBody ") or contains(concat(" ",normalize-space(@class)," ")," entryBody "))]/div[@data-sharer and contains(concat(" ",normalize-space(@class)," ")," content ")]')
        if len(nodes)==1:return nodes[0],'profile:snob-article-text'
    if host=='journal.tinkoff.ru':
        nodes=tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," article-body ")]')
        if len(nodes)==1:return nodes[0],'profile:tinkoff-article-body'
    if host=='xakep.ru':
        nodes=tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," bdaia-post-content ") and contains(concat(" ",normalize-space(@class)," ")," can_read ")][not(.//*[@id="xakepcut"])]')
        if len(nodes)==1:return nodes[0],'profile:xakep-readable-body'
    return None,'trafilatura-inline-fallback'


def choose_main(tree,host):
    if host=='habr.com':
        nodes=tree.xpath('//*[@id="post-content-body"]')
        if len(nodes)==1:return nodes[0],'id:post-content-body'
    if host=='telegra.ph':
        nodes=tree.xpath('//article[@id="_tl_editor"]')
        if len(nodes)==1:return nodes[0],'id:_tl_editor'
    if host=='xakep.ru':
        nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," bdaia-post-content ")]//article[contains(concat(" ",normalize-space(@class)," ")," xmd ")]')
        if len(nodes)==1:return nodes[0],'profile:xakep-xmd'
    nodes=[n for n in tree.xpath('//*[not(self::meta) and contains(concat(" ",normalize-space(@itemprop)," ")," articleBody ")]') if ''.join(n.itertext()).strip()]
    if len(nodes)==1:return nodes[0],'itemprop:articleBody'
    for role in ('entry-content','e-content','article__content','article-content','post-content'):
        nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," '+role+' ")]')
        if len(nodes)==1:return nodes[0],'class:'+role
    if host=='kontur.ru':
        nodes=tree.xpath('//*[@id="ArticleItem"]//*[contains(concat(" ",normalize-space(@class)," ")," text ")]')
        if len(nodes)==1:return nodes[0],'profile:ArticleItem-text'
    if host=='rsdn.org':
        bodies=tree.xpath('//body')
        if len(bodies)==1 and bodies[0].xpath('./h1') and bodies[0].xpath('./h5/span[contains(concat(" ",normalize-space(@class)," ")," title ")]'):
            return bodies[0],'profile:rsdn-article-body'
    if host=='liveinternet.ru':
        nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," MESS ")]')
        if len(nodes)==1:return nodes[0],'class:MESS'
    if host in {'tjournal.ru','vc.ru'}:
        nodes=tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," content--full ")]')
        if len(nodes)==1:return nodes[0],'class:content--full'
    return None,'trafilatura-inline-fallback'


def drop_site_ui(main,host,method,*,strict_rsdn=False):
    if host in {'selectel.ru','blog.selectel.ru'}:
        paragraphs=main.xpath('./p')
        if paragraphs:
            last=paragraphs[-1];previous=last.getprevious();text=last.text_content().casefold()
            if last.getnext() is None and previous is not None and previous.tag=='hr' and 'заполн' in text and 'заявк' in text and any(
                (urlsplit(a.get('href','')).hostname or '')=='startups.selectel.ru' for a in last.xpath('.//a')):last.drop_tree()
    if host=='telegra.ph':
        for node in main.xpath('./address'):node.drop_tree()
    if host=='texterra.ru':
        for node in main.xpath('.//p[contains(concat(" ",normalize-space(@class)," ")," text_under_video ")]'):node.drop_tree()
    if host=='snob.ru':
        for node in main.xpath('.//p[.//img]'):
            text=''.join(node.text_content().split())
            emphasized=''.join(''.join(n.text_content().split()) for n in node.xpath('.//em[not(ancestor::em)]'))
            if re.search(r'\bФото\s*:',node.text_content()) and text==emphasized:node.drop_tree()
        for node in main.xpath('.//p[.//a]'):
            links=node.xpath('.//a')
            if all(a.text_content().strip() in {'Начало','Продолжение'} for a in links) and ''.join(node.text_content().split())==''.join(''.join(a.text_content().split()) for a in links):node.drop_tree()
    if host=='kontur.ru':
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," text-block_product ") and starts-with(@data-show-event-name,"event-adv-")]'):
            node.drop_tree()
    if host=='journal.tinkoff.ru':
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," inline-level ")][.//form and .//input[@type="email"]]'
                               '|.//*[contains(concat(" ",normalize-space(@class)," ")," mobile-table ")]'):
            if node.getparent() is not None:node.drop_tree()
    if host=='netology.ru':
        for node in main.xpath('.//p[count(*)=1 and em]'):
            links=node.xpath('.//a')
            if ' '.join(node.text_content().split()).startswith('Мнение автора') and any(
                'условия публикации' in ' '.join(a.text_content().casefold().split()) and ((urlsplit(a.get('href','')).hostname or '')=='netology.ru' or (urlsplit(a.get('href','')).hostname or '').endswith('.netology.ru')) for a in links):node.drop_tree()
    if method=='profile:rsdn-article-body':
        for node in list(main):
            if node.tag=='p':break
            if node.tag in {'h5','h6'} and node.xpath('.//span[contains(concat(" ",normalize-space(@class)," ")," title ")]'):node.drop_tree()
        for node in main.xpath('./div[@align="right"][.//hr and .//a[contains(@href,"/mag/")]]'):node.drop_tree()
        if not strict_rsdn:
            for node in main.xpath('.//i[contains(@style,"x-small")]'):
                if re.match(r'^Рисунок\s+\d+\.',node.text_content().strip(),re.I):node.drop_tree()
    if method=='class:content--full':
        for node in main.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," content-info ")]'):node.drop_tree()
        paragraphs=main.xpath('.//p')
        if paragraphs:
            last=paragraphs[-1];links=last.xpath('./a')
            if links and len(links)==len(last) and not (last.text or '').strip() and all(
                a.text_content().strip().startswith('#') and '/tag/' in a.get('href','') and not (a.tail or '').strip() for a in links):last.drop_tree()
    if host=='liveinternet.ru':
        for node in main.xpath('./nobr'):
            if ' '.join(node.text_content().split()).startswith('В колонках играет'):node.drop_tree()


def supplementary_blocks(tree,main,host):
    nodes=[]
    if host=='journal.tinkoff.ru':
        nodes=tree.xpath('//h3[contains(concat(" ",normalize-space(@class)," ")," article-header__subtitle ")]')
    elif host=='kontur.ru':
        nodes=tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," article-announce__text ")]')
    # Не добавляем неоднозначные блоки либо уже включённое содержимое.
    if len(nodes)!=1 or main is nodes[0] or main in nodes[0].iterancestors():return ''
    return render(nodes[0]).strip()


def choose_title(tree,main,host):
    def nonempty(nodes):return [n for n in nodes if ''.join(n.itertext()).strip()]
    nodes=nonempty(tree.xpath('//h1[contains(concat(" ",normalize-space(@itemprop)," ")," headline ")]'))
    if len(nodes)==1:return nodes[0]
    if host=='liveinternet.ru':
        nodes=nonempty(tree.xpath('//h1[contains(concat(" ",normalize-space(@class)," ")," ZAG ")]'))
        if len(nodes)==1:return nodes[0]
    if main is not None:
        nodes=nonempty(main.xpath('.//h1'))
        if len(nodes)==1:return nodes[0]
    nodes=nonempty(tree.xpath('//h1'))
    return nodes[0] if len(nodes)==1 else None


def extract_candidate(content: bytes | str,url: str,*,preserve_editorial=False,preserve_content=False,preserve_roles=False,preserve_pre_tables=False,preserve_callouts=False,preserve_code_tables=False,preserve_body_roles=False,preserve_publisher_roles=False,preserve_kontur_roles=False,preserve_netology_roles=False):
    from lxml import html
    if preserve_netology_roles:preserve_kontur_roles=True
    if preserve_kontur_roles:preserve_publisher_roles=True
    if preserve_publisher_roles:preserve_body_roles=True
    if preserve_body_roles:preserve_code_tables=True
    if preserve_code_tables:preserve_callouts=True
    if preserve_callouts:preserve_pre_tables=True
    if preserve_pre_tables:preserve_roles=True
    if preserve_roles:preserve_content=True
    if preserve_content:preserve_editorial=True
    source=decode(content)
    fallback,meta=_html_article(source,url,flatten_inline=True,preserve_extracted=True)
    tree=html.fromstring(source);host=(urlsplit(url).hostname or '').removeprefix('www.')
    for comment in tree.xpath('//comment()'):
        if comment.getparent() is not None:comment.drop_tree()
    # Интерфейсная отметка редакции, а не часть заголовка.
    if host in {'tjournal.ru','vc.ru'}:
        for node in tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," content-editorial-tick ")]'):node.drop_tree()
    main,method=choose_main(tree,host)
    if preserve_editorial and main is None:main,method=choose_editorial_main(tree,host)
    quote_meta={}
    kontur_prefix=None
    if preserve_netology_roles:
        from .netology_body import repair
        quote_meta.update(repair(main,host))
    if preserve_kontur_roles:
        from .kontur_body import repair
        counts,kontur_prefix=repair(tree,main,host)
        quote_meta.update(counts)
    if preserve_publisher_roles:
        from .publisher_roles import repair
        quote_meta.update(repair(main,host))
    if main is not None:drop_site_ui(main,host,method,strict_rsdn=preserve_roles)
    if preserve_body_roles:
        from .habr_body import repair
        quote_meta.update(repair(main,host))
    if preserve_roles and main is not None and host=='rsdn.org' and method=='profile:rsdn-article-body':
        from .rsdn_roles import repair
        quote_meta.update(repair(main,extended=True) if preserve_callouts else repair(main))
    if preserve_editorial:
        # Отсутствие маркера не доказывает полноту. Наличие — отдельный отказ
        # источника, который нельзя исправить обработкой доступного отрывка.
        quote_meta['source_incomplete_markers']=['xakep-access-cut'] if host=='xakep.ru' and tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," bdaia-post-content ")]//*[@id="xakepcut" and contains(concat(" ",normalize-space(@class)," ")," xakepcut ")]') else []
        quote_meta['source_credits']=drop_editorial_widgets(main,host) if main is not None else None
        quote_meta.update(restore_legacy_html_blocks(main,host) if main is not None else dict(preserved_legacy_html_blocks=None,unresolved_legacy_html_figures=None))
        restored=restore_label_tables(main,host) if main is not None else 0
        if restored:quote_meta['preserved_label_tables']=restored
        quote_meta.update(restore_editorial_blocks(main,host) if main is not None else dict(preserved_editorial_callouts=None,preserved_unattributed_quotes=None,quote_review_blocks=None,unresolved_mixed_figures=None))
    if preserve_pre_tables:
        from .pre_tables import restore
        quote_meta.update(restore(main) if main is not None else dict(preserved_pre_tables=None,unresolved_pre_tables=None))
    if preserve_content:
        quote_meta['removed_ad_widgets']=drop_content_ads(main,host) if main is not None else None
        quote_meta.update(content_table_status(main,preserve_code_tables=preserve_code_tables,preserve_group_headers=preserve_body_roles) if main is not None else dict(preserved_data_tables=None,unresolved_data_tables=None))
    title=choose_title(tree,main,host)
    if preserve_netology_roles:
        from .netology_body import primary_title
        bound_title=primary_title(main,host)
        quote_meta['restored_netology_primary_title']=int(bound_title is not None and bound_title is not title)
        if bound_title is not None:title=bound_title
    title_text=render(title).strip().removeprefix('# ') if title is not None else ''
    if main is None:
        clean=fallback
        # Общий fallback остаётся явным: заголовок добавляется только из единственного h1.
        if title_text and not any(line.lstrip('# ').strip()==title_text for line in clean.raw.splitlines()):
            clean=extracted_text('# '+title_text+'\n\n'+clean.raw,code_blocks=fallback.code_blocks)
    else:
        list_blocks=preserve_callouts and method=='profile:rsdn-article-body'
        text=render(main,preserve_tables=preserve_content,preserve_list_blocks=list_blocks,preserve_code_tables=preserve_code_tables,preserve_group_headers=preserve_body_roles).strip()
        prefix=kontur_prefix if kontur_prefix is not None else supplementary_blocks(tree,main,host)
        if preserve_editorial and method=='profile:snob-article-text':
            leads=main.getparent().xpath('./hgroup/h3[contains(concat(" ",normalize-space(@class)," ")," lead ")]')
            if len(leads)==1:prefix=render(leads[0]).strip()
        if prefix:text=prefix+'\n\n'+text
        text='\n'.join(line.rstrip() if (list_blocks and line.startswith('  ')) or re.match(r'^ *- ',line) else line.strip() for line in text.splitlines())
        if title_text and main is not title and main not in title.iterancestors():
            text='# '+title_text+'\n\n'+text
        clean=extracted_text(text,code_blocks=code_count(main,preserve_code_tables=preserve_code_tables,preserve_group_headers=preserve_body_roles))
    version=HTML_NETOLOGY_VERSION if preserve_netology_roles else HTML_KONTUR_VERSION if preserve_kontur_roles else HTML_PUBLISHER_VERSION if preserve_publisher_roles else HTML_BODY_VERSION if preserve_body_roles else HTML_CODE_TABLE_VERSION if preserve_code_tables else HTML_CALLOUT_VERSION if preserve_callouts else HTML_PRE_TABLE_VERSION if preserve_pre_tables else HTML_ROLES_VERSION if preserve_roles else HTML_CONTENT_VERSION if preserve_content else HTML_EDITORIAL_VERSION if preserve_editorial else HTML_STRUCTURE_VERSION
    return clean,meta|quote_meta|dict(clean_version=version,extraction_method=method,
                           title_source='DOM-h1' if title_text else 'not-found',quality_review='pending')
