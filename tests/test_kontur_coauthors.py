import unittest
from bench.kontur_author_origin import kontur_coauthors


class KonturCoauthorsTest(unittest.TestCase):
    url='https://kontur.ru/articles/example'
    credit='Ирина Проверова и Михаил Тестов, эксперты системы интернет-отчетности Контур.Экстерн'

    def page(self,body=None,name='Ирина Проверова'):
        body=body if body is not None else '<p><em>'+self.credit+'</em></p>'
        return '<html><body><div class="content-block_article-announce"><h1>Пример</h1><span class="article-announce-autor-block__name">'+name+'</span></div><div id="ArticleItem"><div class="lp-styles"><div class="lp-forms"><div class="text js-mediator-article">'+body+'</div></div></div></div></body></html>'

    def test_standalone_joint_credit_binds_each_name_to_existing_primary(self):
        for name in ['Ирина Проверова','Михаил Тестов']:
            with self.subTest(name=name):
                value=kontur_coauthors(self.page(name=name),self.url)
                self.assertEqual(value['status'],'explicit-coauthors')
                self.assertEqual(value['authors'],['ирина проверова','михаил тестов'])
                self.assertIn('quotas-only',value['role'])

    def test_unbound_other_names_and_duplicate_credits_are_unresolved(self):
        for source in [self.page(name='Елена Примерова'),self.page(('<p><em>'+self.credit+'</em></p>')*2),
                       self.page().replace('Михаил Тестов','Ирина Проверова'),
                       self.page().replace('</body>','<div id="ArticleItem"></div></body>'),
                       self.page().replace('</h1>','</h1><h1>Другой заголовок</h1>')]:
            with self.subTest(source=source):
                value=kontur_coauthors(source,self.url)
                self.assertEqual(value['status'],'unresolved');self.assertEqual(value['authors'],[])

    def test_quote_table_advertisement_and_mixed_paragraph_do_not_establish_authors(self):
        credit='<p><em>'+self.credit+'</em></p>'
        for body in ['<blockquote>'+credit+'</blockquote>','<table><tr><td>'+credit+'</td></tr></table>',
                     '<div class="important">'+credit+'</div>','<div class="product">'+credit+'</div>',
                     '<p>Эксперты говорят: <em>'+self.credit+'</em></p>',
                     '<p><em><a href="https://example.org/person">'+self.credit+'</a></em></p>']:
            with self.subTest(body=body):
                value=kontur_coauthors(self.page(body),self.url)
                self.assertEqual(value['status'],'unresolved');self.assertEqual(value['authors'],[])

    def test_other_roles_mentions_preview_and_three_people_are_not_a_supported_credit(self):
        for body in ['<p>Об этом рассказали '+self.credit+'.</p>',
                     '<p><em>'+self.credit.replace('эксперты системы интернет-отчетности Контур.Экстерн','герои интервью')+'</em></p>',
                     '<p><em>'+self.credit.replace(' и Михаил Тестов',', Елена Примерова и Михаил Тестов')+'</em></p>',
                     '<p>Обычная проза.</p>']:
            with self.subTest(body=body):
                value=kontur_coauthors(self.page(body),self.url)
                self.assertEqual(value['status'],'no-explicit-coauthors');self.assertEqual(value['authors'],[])
        source=self.page('<p>Проза.</p>').replace('</body>','<article class="tile_articlePreview"><p><em>'+self.credit+'</em></p></article></body>')
        self.assertEqual(kontur_coauthors(source,self.url)['authors'],[])

    def test_missing_primary_and_other_host_do_not_prove_coauthors(self):
        self.assertEqual(kontur_coauthors('',self.url)['status'],'unresolved')
        self.assertEqual(kontur_coauthors(self.page(),'https://example.org/post')['status'],'not-applicable')
        source=self.page().replace('article-announce-autor-block__name','other-name')
        self.assertEqual(kontur_coauthors(source,self.url)['status'],'unresolved')


if __name__=='__main__':unittest.main()
