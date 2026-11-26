"""Opt-in происхождение старой записи LiveInternet; без переатрибуции авторов."""
import re
import unicodedata
from urllib.parse import urlsplit,parse_qs
from .html_structure import decode
from .liveinternet_body import bind,has


_HIDDEN={'script','style','template','noscript','textarea','svg'}
_BLOCK={'p','div','section','article','header','footer','aside','nav','blockquote',
        'pre','br','hr','h1','h2','h3','h4','h5','h6','li','ul','ol','table','tr','td','th'}


def visible(node):
    if not isinstance(node.tag,str) or node.tag in _HIDDEN:return ''
    text=(node.text or '')+''.join(visible(child)+(child.tail or '') for child in node)
    return ' '+text+' ' if node.tag in _BLOCK else text


def key(text):
    tokens=re.findall(r'\w+',unicodedata.normalize('NFC',text).casefold())
    return '\0'+'\0'.join(tokens)+'\0' if tokens else ''


def account(value,kind):
    try:target=urlsplit(value)
    except ValueError:return None
    if (target.scheme not in {'','http','https'} or (target.hostname or 'liveinternet.ru').removeprefix('www.')!='liveinternet.ru'
            or target.query or target.fragment):return None
    pattern=r'/users/([^/]+)/'+(r'profile/?' if kind=='profile' else r'post([0-9]+)/?')
    match=re.fullmatch(pattern,target.path)
    return match[1].casefold() if match else None


def publisher_id(links,number):
    identities=set()
    for link in links:
        try:target=urlsplit(link.get('href',''))
        except ValueError:continue
        if (target.scheme not in {'','http','https'} or (target.hostname or 'liveinternet.ru').removeprefix('www.')!='liveinternet.ru'
                or target.path!='/journal_post.php' or target.fragment):continue
        query=parse_qs(target.query)
        if query.get('action')!=['q_add'] or query.get('fpid')!=[number] or len(query.get('fjid',[]))!=1:continue
        identity=query['fjid'][0]
        if re.fullmatch('[0-9]+',identity) and int(identity)>0:identities.add(str(int(identity)))
    return next(iter(identities)) if len(identities)==1 else None


def original_post(value):
    try:target=urlsplit(value)
    except ValueError:return None
    if (target.scheme not in {'','http','https'} or (target.hostname or 'liveinternet.ru').removeprefix('www.')!='liveinternet.ru'
            or target.query or target.fragment):return None
    match=re.fullmatch(r'/(users|community)/([^/]+)/post([0-9]+)/?',target.path)
    return (match[1],match[2].casefold(),match[3]) if match else None


def quoted_origin(bound,url):
    if not bound['nested_quotes']:return None
    main=bound['main'];nested=[n for n in main.xpath('.//div') if has(n,'MESS') and has(n,'QUOT_T')]
    if len(nested)!=1:return dict(status='unresolved',role='ambiguous-quoted-post')
    quote=nested[0]
    if key(visible(main))!=key(visible(quote)):
        return dict(status='unresolved',role='mixed-primary-and-quoted-post')
    bars=[n for n in quote.xpath('./div') if has(n,'QUOT_B')]
    if len(bars)!=1:return dict(status='unresolved',role='ambiguous-quote-body')
    credits=[n for n in bars[0].xpath('./b') if ' '.join(visible(n).split()).startswith('Цитата сообщения')]
    if len(credits)!=1:return dict(status='unresolved',role='missing-or-ambiguous-quote-credit')
    credit=credits[0];links=credit.xpath('.//a[@href]')
    if (len(links)!=1 or not ' '.join(visible(links[0]).split())
            or ' '.join(''.join(credit.xpath('.//text()[not(ancestor::a)]')).split())!='Цитата сообщения'):
        return dict(status='unresolved',role='mixed-quote-credit')
    author=account(links[0].get('href',''),'profile')
    originals=[n for n in bars[0].xpath('.//a[@href]') if ' '.join(visible(n).split())=='Прочитать целиком']
    reference=original_post(originals[0].get('href','')) if len(originals)==1 else None
    if author is None or reference is None:
        return dict(status='unresolved',role='quote-profile-and-original-disagree')
    owner=bound['owner_path'].split('/')[-1].casefold()
    number=re.fullmatch(r'/users/[^/]+/post([0-9]+)/?',urlsplit(url).path)[1]
    post=next(n for n in main.iterancestors() if n.get('id')=='post'+number and has(n,'CONBL'))
    header_links=[a for n in post.xpath('./span') if has(n,'GL_MAR5B') for a in n.xpath('.//a[@href]')]
    owner_id=publisher_id(header_links,number)
    original_kind,original_account,original_number=reference
    quoted_id=publisher_id(bars[0].xpath('.//a[@href]'),original_number)
    # Кредит автора сообщества не является именем самого сообщества. Для двух
    # разных пользовательских путей нужен хотя бы один согласованный numeric ID.
    if original_kind=='users' and original_account!=author and not (
            quoted_id is not None and any(a.isdecimal() and str(int(a))==quoted_id for a in [author,original_account])):
        return dict(status='unresolved',role='quote-profile-and-original-disagree')
    if owner_id is not None and quoted_id is not None:
        if owner_id==quoted_id:return dict(status='self-quoted-post',role='same-publisher-id; authorship-not-proven')
        if author==owner:return dict(status='unresolved',role='account-path-and-publisher-ids-conflict')
        return dict(status='explicit-reprint',role='whole-quoted-post-of-other-publisher-id')
    if author==owner and original_kind=='users' and original_account==owner:
        return dict(status='self-quoted-post',role='same-account-path; authorship-not-proven')
    return dict(status='unresolved',role='different-paths-without-proven-publisher-ids')


def liveinternet_source_marker(content:bytes|str,url:str,*,extracted_raw:str|None=None)->dict:
    """Полная цитируемая запись либо весь извлечённый текст только в комментарии.

    Нет метки — не доказательство оригинальности. Тексты/имена не возвращаются.
    extracted_raw — ровно сырой результат прежнего html_article, не новый v16.
    """
    try:host=(urlsplit(url).hostname or '').removeprefix('www.')
    except ValueError:return dict(status='unresolved',role='invalid-url')
    if host!='liveinternet.ru':return dict(status='not-applicable',role='other-host')
    source=decode(content)
    if not source.strip():return dict(status='unresolved',role='empty-source')
    from lxml import html
    try:tree=html.fromstring(source)
    except (ValueError,html.etree.ParserError):return dict(status='unresolved',role='unparseable-source')
    for node in tree.xpath('//comment()'):
        if node.getparent() is not None:node.drop_tree()
    bound=bind(tree,host,url)
    if bound is None:return dict(status='unresolved',role='ambiguous-primary-components')
    quoted=quoted_origin(bound,url)
    if quoted is not None and quoted['status']=='explicit-reprint':return quoted
    if extracted_raw is None:
        from .cleaning import html_article
        extracted_raw=html_article(content,url)[0].raw
    if not isinstance(extracted_raw,str) or not key(extracted_raw):return dict(status='unresolved',role='empty-extracted-body')
    if '[КОД]' in extracted_raw:return dict(status='unresolved',role='code-placeholder-needs-review')
    extracted=key(extracted_raw);main=bound['main']
    title=visible(bound['title']) if bound['title'] is not None else ''
    if extracted in key(title+' '+visible(main)):
        return quoted or dict(status='no-explicit-source-marker',role='extracted-body-within-primary-post; authorship-not-proven')
    comments=[n for n in tree.xpath('//div') if has(n,'COMR') and n is not main and main not in n.iterancestors()]
    matches=sum(extracted in key(visible(n)) for n in comments)
    if matches:return dict(status='extracted-comment',role='whole-extracted-token-sequence-in-comment-only',matching_comments=matches)
    return quoted or dict(status='unresolved',role='extracted-body-not-bound-to-primary-or-comment')
