import unittest
from bench.cleaning import html_article_netology_candidate,html_article_kontur_candidate


class NetologyBodyTest(unittest.TestCase):
    def source(self,body):return '<html><body><article><h1 class="entry-title">Название публикации</h1><div class="entry-content">'+body+'</div></article></body></html>'

    def extract(self,body,url='https://netology.ru/blog/example'):
        return html_article_netology_candidate(self.source(body),url)

    def column(self,body,width='2'):return '<div class="stk-grid-col" data-col-width="'+width+'">'+body+'</div>'

    def test_bound_primary_title_preserves_all_internal_levels(self):
        body='<h1>Первый раздел</h1><p>Проза.</p><h1>Второй раздел</h1><h2>Подраздел</h2>'
        clean,meta=self.extract(body)
        self.assertTrue(clean.raw.startswith('# Название публикации\n\n# Первый раздел'))
        self.assertIn('# Второй раздел\n\n## Подраздел',clean.raw)
        self.assertEqual(meta['restored_netology_primary_title'],1)
        old,_=html_article_kontur_candidate(self.source(body),'https://netology.ru/blog/example')
        self.assertNotIn('# Название публикации',old.raw)

    def test_primary_title_is_scoped_to_same_article_and_unique(self):
        source=self.source('<h1>Раздел один</h1><h1>Раздел два</h1>')
        source=source.replace('</body>','<article><h1 class="entry-title">Чужая публикация</h1></article></body>')
        clean,_=html_article_netology_candidate(source,'https://netology.ru/blog/example')
        self.assertTrue(clean.raw.startswith('# Название публикации'));self.assertNotIn('Чужая публикация',clean.raw)
        duplicate=source.replace('<h1 class="entry-title">Название публикации</h1>','<h1 class="entry-title">Первое название</h1><h1 class="entry-title">Второе название</h1>')
        clean,meta=html_article_netology_candidate(duplicate,'https://netology.ru/blog/example')
        self.assertNotIn('Первое название',clean.raw);self.assertEqual(meta['restored_netology_primary_title'],0)

    def test_explicit_one_and_two_paragraph_author_panels_preserve_tail(self):
        for paragraphs in ['<p><strong>Анна Примерова</strong></p>','<p>Анна Примерова</p><p>Главный редактор</p>','<p><font><span>Анна Примерова</span></font></p><p>Клиентский директор компании</p>']:
            panel='<div class="ntlgy-author" data-container-name="Автор (десктоп)"><figure class="ntlgy-author-portrait"><img></figure>'+paragraphs+'</div>'
            clean,meta=self.extract('<p>Начало.</p>'+panel+'Продолжение.')
            self.assertNotIn('Анна Примерова',clean.raw);self.assertIn('Продолжение.',clean.raw);self.assertEqual(meta['removed_netology_bylines'],1)
            mixed=panel.replace('</div>','<p>Авторская оговорка.</p></div>')
            clean,meta=self.extract(mixed);self.assertIn('Авторская оговорка.',clean.raw);self.assertEqual(meta['removed_netology_bylines'],0)
        mixed='<div class="ntlgy-author" data-container-name="Автор (десктоп)"><figure class="ntlgy-author-portrait"><img></figure><p><strong>Анна Примерова</strong></p><p>Редактор. Авторская оговорка.</p></div>'
        clean,meta=self.extract(mixed);self.assertIn('Авторская оговорка.',clean.raw);self.assertEqual(meta['unresolved_netology_bylines'],1)

    def test_publisher_cta_requires_exact_whole_template_and_owned_routes(self):
        cta='<p>Мнение автора и редакции может не совпадать. Хотите написать колонку для Нетологии? Читайте наши <a href="/blog/terms">условия публикации</a>. Чтобы быть в курсе всех новостей и читать новые статьи, присоединяйтесь к <a href="https://t.me/netology_ru">Телеграм-каналу Нетологии</a>.</p>'
        clean,meta=self.extract(cta+'После блока.');self.assertNotIn('Хотите написать',clean.raw);self.assertIn('После блока.',clean.raw);self.assertEqual(meta['removed_netology_publisher_ctas'],1)
        for variant in [cta.replace('</p>',' Авторская оговорка.</p>'),cta.replace('/blog/terms','https://other.example/blog/terms')]:
            clean,meta=self.extract(variant);self.assertIn('Хотите написать',clean.raw);self.assertEqual(meta['removed_netology_publisher_ctas'],0)

    def test_standalone_course_link_keeps_personal_story_and_external_links(self):
        ad='<p>Обучение в онлайн-университете: курс «<a href="/programs/example">Курс примера</a>»</p>'
        clean,meta=self.extract(ad+'Продолжение.');self.assertNotIn('Курс примера',clean.raw);self.assertIn('Продолжение.',clean.raw);self.assertEqual(meta['removed_netology_courses'],1)
        for variant in [ad.replace('</p>',' помог мне разобраться в работе.</p>'),ad.replace('/programs/example','https://other.example/programs/example'),'<p>Я записался на курс «<a href="/programs/example">Курс примера</a>».</p>']:
            clean,meta=self.extract(variant);self.assertIn('Курс примера',clean.raw);self.assertEqual(meta['removed_netology_courses'],0)

    def test_linkless_builder_button_removes_only_complete_promo_fields(self):
        ad='<div class="ntlgy-course--wide"><div><p>курс</p><h3>Название курса</h3><div class="ntlgy-btn" data-container-name="Кнопка"><p><strong>Узнать больше</strong></p></div></div><div><ul><li>Преимущество курса.</li></ul></div></div>'
        clean,meta=self.extract(ad+'Авторское продолжение.');self.assertNotIn('Преимущество курса',clean.raw);self.assertIn('Авторское продолжение.',clean.raw);self.assertEqual(meta['removed_netology_courses'],1)
        linked=ad.replace('<div class="ntlgy-btn" data-container-name="Кнопка">','<a class="ntlgy-btn" data-container-name="Кнопка" href="/programs/example">').replace('</strong></p></div>','</strong></p></a>')
        clean,meta=self.extract(linked);self.assertNotIn('Преимущество курса',clean.raw);self.assertEqual(meta['removed_netology_courses'],1)
        clean,meta=self.extract(linked.replace('<p>курс</p>','<p>Профессия</p>'))
        self.assertNotIn('Преимущество курса',clean.raw);self.assertEqual(meta['removed_netology_courses'],1)
        clean,meta=self.extract(linked.replace('/programs/example','https://other.example/programs/example'))
        self.assertIn('Преимущество курса',clean.raw);self.assertEqual(meta['unresolved_netology_courses'],1)
        for variant in [ad.replace('</ul>','</ul><p>Самостоятельная авторская оговорка.</p>'),ad.replace('ntlgy-btn','another-button'),ad.replace('<strong>Узнать больше</strong>','<a href="/programs/example">Узнать больше</a>').replace('</ul>','</ul><p>Самостоятельная авторская оговорка.</p>')]:
            clean,meta=self.extract(variant);self.assertIn('Преимущество курса',clean.raw);self.assertEqual(meta['removed_netology_courses'],0)

    def test_related_figcaption_and_separate_link_cards_are_removed_with_label(self):
        for content in ['<figure><img><figcaption><a href="/blog/other">Другая статья</a></figcaption></figure>','<figure><img></figure><p><a href="/blog/other">Другая статья</a></p>']:
            card=self.column('<p><strong>ЧИТАТЬ ТАКЖЕ</strong></p>'+content)
            clean,meta=self.extract('<p>Проза.</p>'+card+'Продолжение.')
            self.assertNotIn('Другая статья',clean.raw);self.assertNotIn('ЧИТАТЬ ТАКЖЕ',clean.raw);self.assertIn('Продолжение.',clean.raw);self.assertEqual(meta['removed_netology_navigation'],1)

    def test_mixed_sidebar_and_main_editorial_digest_are_not_navigation(self):
        mixed=self.column('<p>ЧИТАТЬ ТАКЖЕ</p><p><a href="/blog/other">Ссылка</a></p><p>Авторская оговорка.</p>')
        digest='<h2><a href="/blog/one">Первая статья</a></h2><p>Первый редакционный анонс.</p><h2><a href="/blog/two">Вторая статья</a></h2><p>Второй редакционный анонс.</p>'
        clean,meta=self.extract(mixed+digest)
        for s in ['Авторская оговорка.','Первый редакционный анонс.','Второй редакционный анонс.']:self.assertIn(s,clean.raw)
        self.assertEqual(meta['removed_netology_navigation'],0)

    def test_narrow_course_card_requires_marker_and_owned_link_only(self):
        card=self.column('<p>курс</p><p><a href="/programs/example">Название курса</a></p>')
        clean,meta=self.extract(card);self.assertNotIn('Название курса',clean.raw);self.assertEqual(meta['removed_netology_courses'],1)
        for variant in [card.replace('/programs/example','https://other.example/programs/example'),card.replace('</a></p>','</a> Авторское объяснение.</p>')]:
            clean,meta=self.extract(variant);self.assertIn('Название курса',clean.raw);self.assertEqual(meta['removed_netology_courses'],0)

    def test_legacy_image_caption_does_not_drop_mixed_prose_or_adjacent_italic(self):
        caption='<p><a href="image.jpg"><img></a><br><em>Подпись иллюстрации.</em></p>'
        clean,meta=self.extract(caption+'Хвост.');self.assertNotIn('Подпись иллюстрации',clean.raw);self.assertIn('Хвост.',clean.raw);self.assertEqual(meta['removed_netology_image_captions'],1)
        for variant in [caption.replace('<br>',' Авторское объяснение. '),'<p><img></p><p><em>Отдельная авторская мысль.</em></p>','<p><em>Отдельная авторская мысль.</em><img></p>']:
            clean,meta=self.extract(variant);self.assertEqual(meta['removed_netology_image_captions'],0)
            self.assertTrue('Авторское объяснение.' in clean.raw or 'Отдельная авторская мысль.' in clean.raw)

    def test_speaker_quote_is_retained_with_explicit_review_count(self):
        speech='<div class="ntlgy-quote--basic" data-container-name="Цитата без фона"><p>Анна Примерова, эксперт:</p><p>«Речь приглашённого эксперта».</p></div>'
        clean,meta=self.extract(speech+'<p>Авторская проза.</p>')
        self.assertIn('Речь приглашённого эксперта',clean.raw);self.assertEqual(meta['retained_netology_speaker_blocks'],1)
        self.assertEqual(meta['quality_review'],'pending')

    def test_old_versions_and_other_hosts_are_not_modified(self):
        body='<p>Обучение в онлайн-университете: курс «<a href="/programs/example">Курс примера</a>»</p>'
        source=self.source(body);old,meta=html_article_kontur_candidate(source,'https://netology.ru/blog/example')
        self.assertIn('Курс примера',old.raw);self.assertEqual(meta['clean_version'],'clean-v14-kontur-candidate')
        for url in ['https://example.org/post','https://kontur.ru/articles/example','https://habr.com/ru/articles/example']:
            old,_=html_article_kontur_candidate(source,url);new,meta=html_article_netology_candidate(source,url)
            self.assertEqual(old,new);self.assertEqual(meta['clean_version'],'clean-v15-netology-candidate');self.assertEqual(meta['removed_netology_courses'],0)


if __name__=='__main__':unittest.main()
