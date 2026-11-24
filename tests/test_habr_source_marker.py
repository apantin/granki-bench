import unittest
from bench.habr_provenance import habr_source_marker
from bench.provenance import habr_translation_marker


class HabrSourceMarkerTest(unittest.TestCase):
    URL='https://habr.com/ru/post/example/'
    LABEL='<ul class="post__marks inline-list"><li class="inline-list__item_post-type"><span class="post__type-label" title="Перевод">Перевод</span></li></ul>'

    def page(self,body='<p>Авторский разбор.</p>',label=''):
        return '<article class="post post_full"><div class="post__wrapper"><h1>Тестовая публикация</h1>'+label+'<div id="post-content-body">'+body+'</div></div></article>'

    def status(self,source):return habr_source_marker(source,self.URL)['status']

    def test_primary_legacy_label_and_old_marker_independence(self):
        source=self.page(label=self.LABEL)
        self.assertEqual(habr_source_marker(source,self.URL),dict(status='explicit-translation',role='legacy-header'))
        self.assertEqual(habr_translation_marker(source,self.URL),'unknown-primary-header')
        extra=self.LABEL.replace('</ul>','<li class="inline-list__item_post-type"><span class="post__type-label" title="Обучающий материал">Tutorial</span></li></ul>')
        self.assertEqual(self.status(self.page(label=extra)),'explicit-translation')

    def test_legacy_label_in_body_or_elsewhere_is_ignored(self):
        for source in [self.page(body=self.LABEL),self.page()+self.page(label=self.LABEL).replace('post-content-body','other-body'),self.page()+'<aside>'+self.LABEL+'</aside>']:
            self.assertEqual(self.status(source),'no-explicit-source-marker')

    def test_conflicting_duplicate_and_active_legacy_headers_are_unknown(self):
        for label in [self.LABEL*2,self.LABEL.replace('>Перевод<','>Оригинал<'),self.LABEL+'<script>run()</script>',self.LABEL.replace(' title="Перевод"','')]:
            with self.subTest(label=label):self.assertEqual(self.status(self.page(label=label)),'unknown-primary-article')

    def test_explicit_opening_declaration_with_inline_link(self):
        body='<p>Предлагаю вашему вниманию перевод интересной <a href="https://example.org/original">статьи</a> о тестовом формате.</p><p>Материал.</p>'
        result=habr_source_marker(self.page(body),self.URL)
        self.assertEqual((result['status'],result['role']),('explicit-translation','opening-declaration'))
        self.assertGreater(result['evidence_span'][1],0)

    def test_translated_topic_later_paragraph_and_quoted_examples_are_not_declarations(self):
        variants=['<p>Перевод терминов в интерфейсе.</p>','<p>Авторский текст.</p><p>Предлагаю перевод статьи о формате.</p>',
                  '<blockquote>Предлагаю перевод полезной статьи.</blockquote>','<pre>Предлагаю перевод полезной статьи.</pre>',
                  '<p><q>Предлагаю перевод полезной статьи.</q> — пример фразы.</p>',
                  '<article><p>Предлагаю перевод полезной статьи.</p></article>',
                  '<h2>Предлагаю перевод полезной статьи.</h2><p>Разбор заголовка.</p>']
        for body in variants:
            with self.subTest(body=body):self.assertEqual(self.status(self.page(body)),'no-explicit-source-marker')

    def test_mixed_commentary_is_not_declared_wholly_translated(self):
        for body in ['<p>Предлагаю перевод интересной статьи с моими комментариями.</p>',
                     '<p>Сделаю обзор-перевод: курсивом выдержки, обычным шрифтом мои комментарии.</p>']:
            self.assertNotEqual(self.status(self.page(body)),'explicit-translation')

    def test_closing_repost_declaration_requires_original_address_and_cannot_be_quoted(self):
        trailer='<p>P.S. Оригинал тут <a href="https://example.org/original">статья</a>, не могу опубликовать топик-ссылку.</p>'
        result=habr_source_marker(self.page('<p>Основной текст.</p>'+trailer),self.URL)
        self.assertEqual((result['status'],result['role']),('explicit-reprint','closing-repost-declaration'))
        printed=trailer.replace('<a href="https://example.org/original">статья</a>','https://example.org/original')
        self.assertEqual(self.status(self.page(printed)),'explicit-reprint')
        self.assertEqual(self.status(self.page('<p>Пример <a href="http://[">битой ссылки</a>.</p>'+trailer)),'explicit-reprint')
        for value in [trailer.replace('href="https://example.org/original"','href="javascript:run()"'),'<blockquote>'+trailer+'</blockquote>','<pre>'+trailer+'</pre>',trailer+'<p>Затем собственный разбор продолжается.</p>']:
            self.assertEqual(self.status(self.page(value)),'no-explicit-source-marker')

    def test_original_link_alone_and_different_host_are_not_repost_proof(self):
        source=self.page('<p>Источник: <a href="https://example.org/paper">оригинал исследования</a>.</p>')
        self.assertEqual(self.status(source),'no-explicit-source-marker')
        self.assertEqual(habr_source_marker(source,'https://example.org/post')['status'],'not-applicable')

    def test_duplicate_body_and_unrecognized_article_are_unknown(self):
        for source in [self.page()+self.page(),self.page().replace('post post_full','unknown'),'']:
            self.assertEqual(self.status(source),'unknown-primary-article')

    def test_modern_header_remains_recognized(self):
        source='<article class="tm-article-presenter__content"><div class="tm-article-presenter__header"><div class="tm-article-presenter__snippet"><h1>Тестовая статья</h1><div class="tm-article-snippet__labels"><div class="tm-article-snippet__label tm-article-snippet__label_variant-translation">Перевод</div></div></div></div><div id="post-content-body">Проза.</div></article>'
        self.assertEqual(habr_source_marker(source,self.URL),dict(status='explicit-translation',role='modern-header'))


if __name__=='__main__':unittest.main()
