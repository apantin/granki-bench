"""Кандидат сохранения DOM-структуры при явных границах статьи.

Тексты и ссылки отдельных документов не входят в модуль. Не меняет clean-v3.
"""
from __future__ import annotations
import re
from urllib.parse import urlsplit
from .cleaning import HTML_STRUCTURE_VERSION,HTML_EDITORIAL_VERSION,_html_article,extracted_text


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


def render(node,depth=0):
    """Хвост child.tail добавляет родитель: удаление блока не съедает продолжение."""
    tag=node.tag
    blocks=code_table_blocks(node)
    if blocks:return '\n\n'+'\n\n'.join('[КОД]' for _ in blocks)+'\n\n'
    if not isinstance(tag,str) or tag in SKIP:return ''
    if tag=='pre':return '\n\n[КОД]\n\n'
    if tag=='br':return '\n'
    if tag=='hr':return '\n\n'
    child_depth=depth+1 if tag in {'ul','ol'} else depth
    content=inline_space(node.text) if tag not in {'ul','ol'} or (node.text or '').strip() else ''
    for child in node:
        tail=inline_space(child.tail)
        if tag in {'ul','ol'} and not tail.strip():tail=''
        content+=render(child,child_depth)+tail
    if tag in {'h1','h2','h3','h4','h5','h6'}:
        value=' '.join(content.split())
        return '\n\n'+'#'*int(tag[1])+' '+value+'\n\n' if value else ''
    if tag=='li':
        content=content.strip()
        return '  '*max(0,depth-1)+'- '+content+'\n'
    if tag in {'ul','ol'}:return '\n\n'+content.strip('\n')+'\n\n'
    if tag in BLOCK:return '\n\n'+content.strip()+'\n\n'
    return content


def code_count(node):
    blocks=code_table_blocks(node)
    if blocks:return len(blocks)
    if not isinstance(node.tag,str) or node.tag in SKIP:return 0
    if node.tag=='pre':return 1
    return sum(code_count(child) for child in node)


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
        if any(n.tag in SKIP-{'figure'} for n in parents) or attributed_quote(node):continue
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


def drop_editorial_widgets(main,host):
    source_credits=[]
    if host=='te-st.org':
        for node in main.xpath('.//blockquote'):
            links=node.xpath('.//a[@href]')
            label=' '.join(''.join(node.xpath('.//text()[not(ancestor::a)]')).split()).casefold()
            if label in {'еще по теме:','ещё по теме:'} and links and all(
                    (urlsplit(a.get('href','')).hostname or host).removeprefix('www.')==host
                    and re.match(r'^/\d{4}/\d{2}/\d{2}/',urlsplit(a.get('href','')).path) for a in links):node.drop_tree()
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
            if (node.getnext() is None and len(node)==1 and len(strong)==1
                    and value==' '.join(strong[0].text_content().split()) and re.match(r'^Из эфира на\b',value,re.I)
                    and any((urlsplit(a.get('href','')).hostname or '').removeprefix('www.')=='radiokp.ru'
                            and urlsplit(a.get('href','')).path.startswith('/podcast/')
                            and 'nofollow' in a.get('rel','').split() for a in links)):
                source_credits.append(dict(text=value,links=[a.get('href') for a in links]));node.drop_tree()
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


def drop_site_ui(main,host,method):
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


def extract_candidate(content: bytes | str,url: str,*,preserve_editorial=False):
    from lxml import html
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
    if main is not None:drop_site_ui(main,host,method)
    quote_meta={}
    if preserve_editorial:
        # Отсутствие маркера не доказывает полноту. Наличие — отдельный отказ
        # источника, который нельзя исправить обработкой доступного отрывка.
        quote_meta['source_incomplete_markers']=['xakep-access-cut'] if host=='xakep.ru' and tree.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," bdaia-post-content ")]//*[@id="xakepcut" and contains(concat(" ",normalize-space(@class)," ")," xakepcut ")]') else []
        quote_meta['source_credits']=drop_editorial_widgets(main,host) if main is not None else None
        quote_meta.update(restore_legacy_html_blocks(main,host) if main is not None else dict(preserved_legacy_html_blocks=None,unresolved_legacy_html_figures=None))
        quote_meta.update(restore_editorial_blocks(main,host) if main is not None else dict(preserved_editorial_callouts=None,preserved_unattributed_quotes=None,quote_review_blocks=None,unresolved_mixed_figures=None))
    title=choose_title(tree,main,host)
    title_text=render(title).strip().removeprefix('# ') if title is not None else ''
    if main is None:
        clean=fallback
        # Общий fallback остаётся явным: заголовок добавляется только из единственного h1.
        if title_text and not any(line.lstrip('# ').strip()==title_text for line in clean.raw.splitlines()):
            clean=extracted_text('# '+title_text+'\n\n'+clean.raw,code_blocks=fallback.code_blocks)
    else:
        text=render(main).strip()
        prefix=supplementary_blocks(tree,main,host)
        if preserve_editorial and method=='profile:snob-article-text':
            leads=main.getparent().xpath('./hgroup/h3[contains(concat(" ",normalize-space(@class)," ")," lead ")]')
            if len(leads)==1:prefix=render(leads[0]).strip()
        if prefix:text=prefix+'\n\n'+text
        text='\n'.join(line.rstrip() if re.match(r'^ *- ',line) else line.strip() for line in text.splitlines())
        if title_text and main is not title and main not in title.iterancestors():
            text='# '+title_text+'\n\n'+text
        clean=extracted_text(text,code_blocks=code_count(main))
    return clean,meta|quote_meta|dict(clean_version=HTML_EDITORIAL_VERSION if preserve_editorial else HTML_STRUCTURE_VERSION,extraction_method=method,
                           title_source='DOM-h1' if title_text else 'not-found',quality_review='pending')
