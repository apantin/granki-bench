import unittest
from lxml import html
from bench.candidates.publication_context import header_lead, publisher_context
from bench.publication_body import bind


class PublicationContextTests(unittest.TestCase):
    def test_tinkoff_header_bound_to_same_article(self):
        tree = html.fromstring('<article><header class="article-header"><h1>Заголовок</h1><h3 class="article-header__subtitle">Вводка</h3></header><div id="body"><p>Текст</p></div></article>')
        main, = tree.xpath('//*[@id="body"]'); title, = tree.xpath('//h1')
        self.assertEqual(header_lead(tree, main, title, 'journal.tinkoff.ru').text_content(), 'Вводка')
        self.assertIsNone(header_lead(tree, main, title, 'example.org'))

    def test_tinkoff_does_not_take_sidebar_or_other_article(self):
        for lead in ['<aside><h3 class="article-header__subtitle">Чужая вводка</h3></aside>', '<h3 class="article-header__subtitle">Первая</h3><h3 class="article-header__subtitle">Вторая</h3>']:
            with self.subTest(lead=lead):
                tree = html.fromstring('<article><header class="article-header"><h1>Заголовок</h1>' + lead + '</header><div id="body">Текст</div></article>')
                self.assertIsNone(header_lead(tree, tree.xpath('//*[@id="body"]')[0], tree.xpath('//h1')[0], 'journal.tinkoff.ru'))
        for body in ['</article><article><div id="body">Другое тело</div>', '<article><div id="body">Вложенная статья</div></article>']:
            with self.subTest(body=body):
                tree = html.fromstring('<div><article><header class="article-header"><h1>Заголовок</h1><h3 class="article-header__subtitle">Вводка</h3></header>' + body + '</article></div>')
                self.assertIsNone(header_lead(tree, tree.xpath('//*[@id="body"]')[0], tree.xpath('//h1')[0], 'journal.tinkoff.ru'))

    def test_kontur_header_and_article_are_unique(self):
        original = '<div><div class="content-block_article-announce"><h1>Заголовок</h1><div class="article-announce__text"><p>Вводка</p></div></div><div id="ArticleItem"><div id="body">Текст</div></div>{extra}</div>'
        for extra, accepted in [('', True), ('<div id="ArticleItem">Другое</div>', False), ('<h1>Ещё заголовок</h1>', False), ('<div class="content-block_article-announce">Другая шапка</div>', False)]:
            with self.subTest(extra=extra):
                tree = html.fromstring(original.format(extra=extra)); lead = header_lead(tree, tree.xpath('//*[@id="body"]')[0], tree.xpath('//h1')[0], 'kontur.ru')
                self.assertEqual(lead is not None, accepted)

    def test_kontur_lead_outside_header_is_not_source(self):
        tree = html.fromstring('<div><div class="content-block_article-announce"><h1>Заголовок</h1></div><aside class="article-announce__text">Сосед</aside><div id="ArticleItem">Текст</div></div>')
        self.assertIsNone(header_lead(tree, tree.xpath('//*[@id="ArticleItem"]')[0], tree.xpath('//h1')[0], 'kontur.ru'))

    def test_explicit_advertorial_requires_bound_primary_article(self):
        template = '<div id="warp"><div class="bdaia-post-style7-head"><header class="bdaia-post-header"><h1 class="post-title entry-title">Заголовок</h1></header></div><div id="content"><article id="post-123" class="hentry post-123 {role}"><div class="bdaia-post-content">Текст</div></article></div>{extra}</div>'
        for role, extra, expected in [('category-advert', '', ['category-advert']), ('', '<aside class="category-advert">Реклама</aside>', []), ('category-review', '', [])]:
            with self.subTest(role=role, extra=extra):
                tree = html.fromstring(template.format(role=role, extra=extra)); publication = bind(tree, 'xakep.ru')
                self.assertIsNotNone(publication)
                context = publisher_context(tree, publication['main'], publication['title'], 'xakep.ru')
                self.assertEqual(context, dict(publisher_domain='xakep.ru', primary_publication_markers=expected))
                self.assertEqual(publisher_context(tree, publication['main'], None, 'xakep.ru')['primary_publication_markers'], [])


if __name__ == '__main__':
    unittest.main()
