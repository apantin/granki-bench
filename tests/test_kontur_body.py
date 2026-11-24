import unittest
from bench.cleaning import html_article_kontur_candidate,html_article_publisher_candidate


class KonturBodyTest(unittest.TestCase):
    def source(self,body,lead='<p>Важный лид.</p>',subtitle='',extra=''):
        return '<html><body><div class="content-block_article-announce"><h1>Название</h1>'+subtitle+'<span class="article-announce-autor-block__name">Антон Примеров</span><div class="article-announce__desc">'+lead+'</div></div><div id="ArticleItem"><div class="text">'+body+'</div></div>'+extra+'</body></html>'

    def extract(self,body,**kw):return html_article_kontur_candidate(self.source(body,**kw),'https://kontur.ru/articles/example')

    def test_desc_lead_subtitle_and_text_variant_preserve_order_without_image_credit(self):
        lead='<div class="article-announce__image">Чужая подпись картинки<img alt="Служебный alt"></div><p>Содержательный <b>лид</b>.</p>'
        clean,meta=self.extract('<p>Основная проза.</p>',lead=lead,subtitle='<h2 class="article-announce__title">Подзаголовок</h2>')
        self.assertIn('# Название\n\n## Подзаголовок\n\nСодержательный лид.\n\nОсновная проза.',clean.raw)
        self.assertNotIn('Чужая подпись',clean.raw);self.assertEqual(meta['restored_kontur_leads'],1)
        text='<div class="article-announce__text"><p>Важный лид.</p><section class="content-block"> </section></div>'
        clean,_=self.extract('<p>Основная проза.</p>',lead=text);self.assertEqual(clean.raw.count('Важный лид.'),1)
        clean,meta=self.extract('<p>Важный лид.</p><p>Основная проза.</p>',lead=text)
        self.assertEqual(clean.raw.count('Важный лид.'),1);self.assertEqual(meta['restored_kontur_leads'],0)

    def test_product_variants_keep_outside_tail_and_data_tables(self):
        for role in ['text-block__text','text-block_product__text']:
            body='<p>До.</p><div class="text-block text-block_product clearfix"><div class="'+role+'"><p>Рекламная врезка.</p><a>Действие</a></div></div>После.<p>Остальная проза.</p>'
            clean,meta=self.extract(body);self.assertNotIn('Рекламная врезка',clean.raw);self.assertIn('После.',clean.raw);self.assertEqual(meta['removed_kontur_products'],1)
        clean,meta=self.extract('<div class="text-block_product" data-show-event-name="event-adv-example"><div class="text-block__text"><table><tr><th>Данные</th><th>Единица</th></tr><tr><td>42</td><td>шт.</td></tr></table></div></div>')
        self.assertIn('42',clean.raw);self.assertEqual(meta['removed_kontur_products'],0);self.assertEqual(meta['unresolved_kontur_products'],1)

    def test_workflow_promo_keeps_authored_important_instruction(self):
        ad='<div class="text-block_important"><p>Промо</p><ol><li>Шаг рекламы.</li></ol><p><a href="/extern/features/example">Узнать больше</a></p></div>'
        own='<div class="text-block_important"><h4>Инструкция</h4><ol><li>Авторский шаг.</li></ol><a href="https://example.org/guide">Зарегистрироваться</a></div>'
        clean,meta=self.extract(ad+own);self.assertNotIn('Шаг рекламы',clean.raw);self.assertIn('Авторский шаг.',clean.raw);self.assertEqual(meta['removed_kontur_workflow_promos'],1)

    def test_only_exact_adjacent_copy_of_explicit_product_promo_is_removed(self):
        ad='<div class="text-block_product" data-show-event-name="event-adv-example"><div class="text-block__text"><p>Текст рекламы.</p><a>Узнать больше</a></div></div>'
        clean,meta=self.extract(ad+'<p>Текст рекламы.</p><p>Авторское продолжение.</p>')
        self.assertNotIn('Текст рекламы.',clean.raw);self.assertIn('Авторское продолжение.',clean.raw);self.assertEqual(meta['removed_kontur_duplicate_promos'],1)
        clean,meta=self.extract(ad+'<p>Текст рекламы. Авторская оговорка.</p>')
        self.assertIn('Авторская оговорка.',clean.raw);self.assertEqual(meta['removed_kontur_duplicate_promos'],0)

    def test_buttons_require_standalone_known_route(self):
        button='<a class="btn btn-lg btn-secondary" href="/ca">Подобрать подпись</a>'
        demo='<a href="/kontur-personal/demo?campaign=test">Попробовать бесплатно программу «Пример»</a>'
        clean,meta=self.extract('<p>'+button+'</p><p>'+demo+'</p><p>Проза.</p>')
        self.assertEqual(meta['removed_kontur_buttons'],2);self.assertNotIn('Подобрать',clean.raw)
        clean,meta=self.extract('<p>Условие перед ссылкой: '+button+'</p>');self.assertIn('Условие перед ссылкой',clean.raw);self.assertEqual(meta['removed_kontur_buttons'],0)

    def test_social_related_and_matching_byline_keep_prose_and_coauthors(self):
        related='<p>Читайте также:</p><p><a href="/articles/other">Другая статья</a></p>'
        social='<p><em>Все самое интересное о бизнесе — на нашем канале в </em><a href="https://t.me/konturjournal"><em>Telegram</em></a><em>. Присоединяйтесь!</em></p>'
        clean,meta=self.extract('<p>Проза.</p><p><strong>Антон Примеров</strong>, директор компании</p>'+related+social)
        self.assertNotIn('директор компании',clean.raw);self.assertNotIn('Другая статья',clean.raw);self.assertNotIn('Telegram',clean.raw);self.assertEqual(meta['removed_kontur_bylines'],1)
        second='<p><em>Подпишитесь на наш канал в <a href="https://tele.click/konturjournal">Telegram</a>, чтобы вовремя узнавать о самых важных изменениях для бизнеса.</em></p>'
        clean,meta=self.extract(second);self.assertEqual(meta['removed_kontur_social_ctas'],1)
        for body in ['<p><strong>Антон Примеров</strong>, директор компании, рассказал о новой системе.</p>','<p><em>Антон Примеров и Елена Тестовая, эксперты компании</em></p>','<p>Автор советует <a href="/articles/other">содержательный пример</a>.</p>']:
            clean,meta=self.extract(body);self.assertEqual(meta['removed_kontur_bylines'],0);self.assertEqual(meta['removed_kontur_related'],0)

    def test_layout_credit_stays_with_quotation_and_remains_unresolved(self):
        layout='<table><tr><td><p><br></p></td><td><p><strong>Елена Тестовая,</strong><br>Менеджер организации</p></td></tr></table>'
        quote='<p><em>«Это мнение внешнего специалиста»</em></p>'
        clean,meta=self.extract(layout+quote);self.assertIn('Елена Тестовая,',clean.raw);self.assertIn('мнение внешнего специалиста',clean.raw)
        self.assertEqual(meta['restored_kontur_quote_credits'],1);self.assertEqual(meta['unresolved_kontur_quote_credits'],1)
        clean,meta=self.extract(layout+'<p>Обычная авторская проза.</p>');self.assertEqual(meta['restored_kontur_quote_credits'],0)

    def test_ambiguous_header_does_not_inject_unbound_lead(self):
        for extra in ['<h1>Другой заголовок</h1>','<div class="article-announce__desc">Внешний лид</div>']:
            clean,meta=self.extract('<p>Тело.</p>',extra=extra);self.assertEqual(meta['unresolved_kontur_header'],1);self.assertNotIn('Важный лид.',clean.raw);self.assertNotIn('Внешний лид',clean.raw)

    def test_old_entrypoint_and_other_hosts_keep_content(self):
        source=self.source('<p>Тело.</p><p><strong>Антон Примеров</strong>, директор компании</p>')
        old,meta=html_article_publisher_candidate(source,'https://kontur.ru/articles/example');self.assertIn('директор компании',old.raw);self.assertEqual(meta['clean_version'],'clean-v13-publisher-candidate')
        old,_=html_article_publisher_candidate(source,'https://example.org/article');new,meta=html_article_kontur_candidate(source,'https://example.org/article')
        self.assertEqual(old,new);self.assertEqual(meta['clean_version'],'clean-v14-kontur-candidate')


if __name__=='__main__':unittest.main()
