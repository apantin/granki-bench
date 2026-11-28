"""Проверяемые издательские факты для полной проекции первоисточника."""
from ..publication_body import bind, has, unique


def header_lead(tree, main, title, host):
    """Дополнительная вводка только из шапки той же публикации."""
    if main is None or title is None or unique(tree.xpath('//h1')) is not title:
        return None
    if host == 'journal.tinkoff.ru':
        header = title.getparent()
        if (header is None or header.tag != 'header' or not has(header, 'article-header')
                or header.getparent() is None or header.getparent().tag != 'article'
                or next((n for n in main.iterancestors() if n.tag == 'article'), None) is not header.getparent()):
            return None
        lead = unique([n for n in header.xpath('./h3') if has(n, 'article-header__subtitle')])
    elif host == 'kontur.ru':
        header = unique([n for n in tree.xpath('//div') if has(n, 'content-block_article-announce')])
        article = unique(tree.xpath('//*[@id="ArticleItem"]'))
        if (header is None or article is None or header not in title.iterancestors()
                or main is not article and article not in main.iterancestors()
                or header is article or header in article.iterancestors()
                or article in header.iterancestors()):
            return None
        lead = unique([n for n in header.iterdescendants() if has(n, 'article-announce__text')])
    else:
        return None
    if lead is None or not lead.text_content().strip() or lead is main or main in lead.iterancestors():
        return None
    return lead


def publisher_context(tree, main, title, host):
    """Домен и явная роль статьи; отсутствие маркера не доказывает качество."""
    markers = []
    if host == 'xakep.ru':
        publication = bind(tree, host)
        if publication is not None and main is publication['main'] and title is publication['title']:
            post = unique([n for n in main.iterancestors() if n.tag == 'article' and has(n, 'hentry')])
            if post is not None and has(post, 'category-advert'):
                markers.append('category-advert')
    return dict(publisher_domain=host, primary_publication_markers=markers)
