import json
import unittest
from bench.kontur_author_origin import kontur_author_origin


class KonturAuthorOriginTest(unittest.TestCase):
    url='https://kontur.ru/articles/example'
    def source(self,primary='',body='Основная проза.',extra_head='',preview='Антон Примеров'):
        data=dict(**{'@type':'Article'},headline='Название публикации',author={'@type':'Organization','name':'Компания'})
        return '<html><head><title>Название публикации</title><meta name="twitter:creator" content="@company">'+extra_head+'<script type="application/ld+json">'+json.dumps(data,ensure_ascii=False)+'</script></head><body><div class="content-block_article-announce"><h1>Название публикации</h1>'+primary+'</div><div id="ArticleItem"><p>'+body+'</p></div><article class="tile tile_articlePreview"><span class="byLineBlock-author">'+preview+'</span></article></body></html>'

    def test_preview_fallback_has_no_primary_person_credit(self):
        r=kontur_author_origin(self.source(),self.url)
        self.assertEqual(r['status'],'unbound-preview-credit');self.assertEqual(r['matching_preview_credits'],1);self.assertNotIn('Антон',str(r))

    def test_actual_primary_byline_is_preserved_even_with_same_preview(self):
        r=kontur_author_origin(self.source('<span class="byLineBlock-author">Антон Примеров</span>'),self.url)
        self.assertEqual(r['status'],'primary-name-present')

    def test_name_in_body_holds_ambiguity_without_proving_authorship(self):
        r=kontur_author_origin(self.source(body='Об этом рассказал Антон Примеров.'),self.url)
        self.assertEqual(r['status'],'primary-name-present');self.assertIn('not-proven',r['role'])

    def test_different_head_person_credit_is_not_silently_ignored(self):
        r=kontur_author_origin(self.source(extra_head='<meta name="author" content="Елена Тестовая">'),self.url)
        self.assertNotEqual(r['status'],'unbound-preview-credit')

    def test_head_author_link_requires_review(self):
        r=kontur_author_origin(self.source(extra_head='<link rel="author" href="https://example.org/person">'),self.url)
        self.assertNotEqual(r['status'],'unbound-preview-credit')

    def test_ambiguous_components_or_unmatched_article_are_unknown(self):
        source=self.source()
        for value in [source.replace('</body>','<div id="ArticleItem"></div></body>'),source.replace('<h1>Название публикации</h1>','<h1>Название публикации</h1><h1>Ещё название</h1>'),source.replace('"Organization"','"Person"'),source.replace('"headline": "Название публикации"','"headline": "Другая публикация"')]:
            with self.subTest(value=value):self.assertEqual(kontur_author_origin(value,self.url)['status'],'unresolved')

    def test_other_host_and_empty_source_do_not_establish_author(self):
        self.assertEqual(kontur_author_origin(self.source(),'https://example.org/post')['status'],'not-applicable')
        self.assertEqual(kontur_author_origin('',self.url)['status'],'unresolved')


if __name__=='__main__':unittest.main()
