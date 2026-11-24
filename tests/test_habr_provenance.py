import importlib.util
import unittest
from bench.provenance import habr_translation_marker


@unittest.skipUnless(importlib.util.find_spec('lxml'),'Не установлены зависимости HTML')
class HabrTranslationTest(unittest.TestCase):
    URL='https://habr.com/ru/post/example/'

    def label(self):return '<div class="tm-article-snippet__labels"><div class="tm-article-snippet__label tm-article-snippet__label_variant-translation"><span>Перевод</span></div></div>'

    def page(self,label=None,body='Исходная проза.'):
        return '<article class="tm-article-presenter__content"><div class="tm-article-presenter__header"><div class="tm-article-presenter__snippet"><h1>Тестовая статья</h1>'+(self.label() if label is None else label)+'</div></div><div id="post-content-body">'+body+'</div></article>'

    def test_primary_translation_marker_with_whitespace_and_extra_classes(self):
        source=self.page().replace('>Перевод<','>\n Перевод \n<').replace('tm-article-presenter__content"','tm-article-presenter__content extra"')
        self.assertEqual(habr_translation_marker(source,self.URL),'explicit-translation')

    def test_absence_is_not_claimed_original(self):
        self.assertEqual(habr_translation_marker(self.page(label=''),self.URL),'no-explicit-translation-in-header')
        self.assertEqual(habr_translation_marker(self.page(label='<div class="tm-article-snippet__labels"></div>'),self.URL),'no-explicit-translation-in-header')

    def test_markers_in_body_recommendation_and_other_article_are_ignored(self):
        variants=[self.page(label='',body=self.label()),self.page(label='')+self.page().replace('post-content-body','other-body'),
                  self.page(label='')+'<aside>'+self.label()+'</aside>']
        for source in variants:
            with self.subTest(source=source):self.assertEqual(habr_translation_marker(source,self.URL),'no-explicit-translation-in-header')

    def test_duplicate_body_header_or_label_is_unknown(self):
        source=self.page()
        for value in [source+source,source.replace('</article>','<div id="post-content-body">Ещё</div></article>'),
                      source.replace('<h1>','<h1>Ещё</h1><h1>'),self.page(label=self.label()*2),
                      self.page(label=self.label().replace('</span></div>','</span></div><div class="tm-article-snippet__label tm-article-snippet__label_variant-translation">Перевод</div>'))]:
            with self.subTest(value=value):self.assertEqual(habr_translation_marker(value,self.URL),'unknown-primary-header')

    def test_wrong_text_or_unrecognized_shapes_stay_unknown(self):
        for value in [self.page().replace('Перевод','Оригинал'),self.page().replace('tm-article-presenter__content','post post_full'),
                      '<article><h1>Перевод</h1><p>Текст.</p></article>','']:
            with self.subTest(value=value):self.assertEqual(habr_translation_marker(value,self.URL),'unknown-primary-header')

    def test_active_header_and_missing_title_are_unknown(self):
        for value in [self.page().replace('</h1>','</h1><script>run()</script>'),self.page().replace('<h1>Тестовая статья</h1>','')]:
            with self.subTest(value=value):self.assertEqual(habr_translation_marker(value,self.URL),'unknown-primary-header')

    def test_other_host_never_uses_habr_roles(self):
        for url in ['https://example.org/post','https://habr.com.example.org/post']:
            self.assertEqual(habr_translation_marker(self.page(),url),'not-applicable')


if __name__=='__main__':unittest.main()
