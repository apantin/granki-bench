import unittest
from bench.cleaning import html_article_liveinternet_candidate,html_article_netology_candidate


class LiveInternetBodyTest(unittest.TestCase):
    url='https://www.liveinternet.ru/users/example/post42/'

    def source(self,body,*,date='Пятница, 20 Ноября 2015 г. 21:40',title='Название записи'):
        return ('<html><head><title>Сервис дневников</title></head><body>'
                '<aside>Создан: 01.01.2001 <p>Боковая колонка.</p></aside>'
                '<div class="CONBL" id="post42"><h1 class="ZAG">'+title+'</h1>'
                '<span class="GL_TXTSM GL_MAR5B">'+date+'<a>+ в цитатник</a></span>'
                '<div class="GL_MAR10T GL_MAR10B MESS">'+body+'</div></div>'
                '<div class="COMR"><p>Чужой комментарий.</p></div></body></html>')

    def extract(self,body,**kw):return html_article_liveinternet_candidate(self.source(body,**kw),self.url)

    def test_post_metadata_replaces_service_title_and_profile_date(self):
        clean,meta=self.extract('<p>Основной текст.</p>')
        self.assertEqual(clean.raw,'# Название записи\n\nОсновной текст.\n')
        self.assertEqual((meta['title'],meta['date']),('Название записи','2015-11-20'))
        self.assertEqual(meta['metadata_title_source'],'DOM-post-title')
        self.assertEqual(meta['date_source'],'DOM-post-date')
        self.assertEqual(meta['bound_liveinternet_posts'],1)
        self.assertNotIn('Боковая колонка',clean.raw);self.assertNotIn('Чужой комментарий',clean.raw)

    def test_invalid_or_ambiguous_post_date_does_not_restore_profile_date(self):
        for date in ['Пятница, 31 Февраля 2015 г. 21:40','Пятница, 20 Неизвестного 2015 г. 21:40','Пятница, 20 Ноября 2015 г. 25:40','2015-11-20']:
            with self.subTest(date=date):
                _,meta=self.extract('<p>Текст.</p>',date=date)
                self.assertIsNone(meta['date']);self.assertEqual(meta['date_source'],'not-found-or-ambiguous')
        source=self.source('<p>Текст.</p>').replace('<span class="GL_TXTSM GL_MAR5B">','<span class="GL_MAR5B">иная дата</span><span class="GL_TXTSM GL_MAR5B">')
        _,meta=html_article_liveinternet_candidate(source,self.url);self.assertIsNone(meta['date'])

    def test_ambiguous_title_does_not_use_unrelated_global_heading(self):
        source=self.source('<p>Текст.</p>').replace('<h1 class="ZAG">','<h1 class="ZAG">Другой заголовок</h1><h1 class="ZAG">')
        clean,meta=html_article_liveinternet_candidate(source,self.url)
        self.assertIsNone(meta['title']);self.assertNotIn('Другой заголовок',clean.raw)
        self.assertEqual(meta['metadata_title_source'],'not-found-or-ambiguous')

    def test_post_id_class_and_url_must_agree(self):
        source=self.source('<p>Основной текст.</p>')
        for changed,url in [(source,self.url.replace('post42','post43')),(source.replace('CONBL','OTHER'),self.url),(source.replace('id="post42"','id="post41"'),self.url),(source.replace('</body>','<div id="post42" class="CONBL"></div></body>'),self.url)]:
            with self.subTest(url=url,source=changed):
                _,meta=html_article_liveinternet_candidate(changed,url)
                self.assertEqual(meta['bound_liveinternet_posts'],0);self.assertEqual(meta['unresolved_liveinternet_posts'],1)

    def test_target_post_is_separate_from_neighbour_posts(self):
        source=self.source('<p>Искомый текст.</p>').replace('</body>','<div class="CONBL" id="post43"><h1 class="ZAG">Сосед</h1><div class="MESS"><p>Соседний текст.</p></div></div></body>')
        clean,meta=html_article_liveinternet_candidate(source,self.url)
        self.assertIn('Искомый текст',clean.raw);self.assertNotIn('Соседний текст',clean.raw)
        self.assertEqual(meta['title'],'Название записи');self.assertEqual(meta['date'],'2015-11-20')

    def test_known_nested_repost_restores_body_and_reports_foreign_origin(self):
        source=self.source('<div class="MESS QUOT_T"><div class="QUOT_B"><b>Цитата сообщения Пример</b><blockquote>Вступление.</blockquote><h1>Подзаголовок</h1><p>Основная часть.</p></div></div>')
        clean,meta=html_article_liveinternet_candidate(source,self.url)
        self.assertIn('Вступление.',clean.raw);self.assertIn('# Подзаголовок',clean.raw)
        self.assertIn('Основная часть.',clean.raw);self.assertNotIn('Боковая колонка',clean.raw)
        self.assertEqual(meta['retained_liveinternet_quoted_posts'],1)
        self.assertEqual(meta['extraction_method'],'profile:liveinternet-post')
        self.assertGreater(meta['quote_review_blocks'],0);self.assertEqual(meta['quality_review'],'pending')

    def test_unknown_or_multiple_nested_bodies_remain_unresolved(self):
        for body in ['<div class="MESS">Неизвестное тело.</div>', '<div class="MESS QUOT_T"><div class="QUOT_B">Первое.</div></div><div class="MESS QUOT_T"><div class="QUOT_B">Второе.</div></div>']:
            _,meta=self.extract(body)
            self.assertEqual(meta['bound_liveinternet_posts'],0);self.assertEqual(meta['unresolved_liveinternet_posts'],1)

    def test_leading_mood_field_preserves_following_prose(self):
        clean,meta=self.extract('<strong>Внутренний титул</strong><br><b>Настроение сейчас - <em>Спокойное</em></b>Продолжение.<br><p>Основная проза.</p>')
        self.assertNotIn('Настроение сейчас',clean.raw);self.assertIn('Продолжение.',clean.raw)
        self.assertIn('Основная проза.',clean.raw);self.assertEqual(meta['removed_liveinternet_mood_fields'],1)

    def test_mood_phrase_in_prose_or_after_prose_is_preserved(self):
        forms=['<p>Настроение сейчас - <em>это часть рассказа</em></p>','<p>Вступление.</p><b>Настроение сейчас - <em>часть рассказа</em></b>', '<b>Настроение сейчас - <em>хорошее</em> и это важно автору.</b>', '<b>Настроение сейчас - <em><a href="https://example.org">Содержательная ссылка</a></em></b>']
        for body in forms:
            clean,meta=self.extract(body);self.assertIn('Настроение сейчас',clean.raw)
            self.assertEqual(meta['removed_liveinternet_mood_fields'],0)
        body='<b>Настроение сейчас - <em>Поле CMS</em></b>Авторская проза.<b>Настроение сейчас - <em>фраза автора</em></b>'
        clean,meta=self.extract(body);self.assertIn('фраза автора',clean.raw);self.assertEqual(meta['removed_liveinternet_mood_fields'],1)

    def test_terminal_own_profile_footer_only(self):
        footer='<center><font><a href="/users/example/"><img></a><a href="/users/example/profile/"><b>Мой дневник</b></a></font></center>'
        clean,meta=self.extract('<p>Проза.</p>'+footer)
        self.assertNotIn('Мой дневник',clean.raw);self.assertEqual(meta['removed_liveinternet_profile_footers'],1)
        clean,meta=self.extract('<center>Заключительная авторская проза.<br>'+footer+'</center>')
        self.assertIn('Заключительная авторская проза.',clean.raw);self.assertNotIn('Мой дневник',clean.raw)
        self.assertEqual(meta['removed_liveinternet_profile_footers'],1)
        for changed in [footer+'Продолжение.',footer.replace('/users/example/profile/','/users/other/profile/'),footer.replace('<font>','<font>Содержательная оговорка. '),footer.replace('/profile/','/profile/?mode=article')]:
            clean,meta=self.extract('<p>Проза.</p>'+changed)
            self.assertIn('Мой дневник',clean.raw);self.assertEqual(meta['removed_liveinternet_profile_footers'],0)

    def test_tiny_terminal_marquee_link_and_mixed_component(self):
        footer='<div><a href="https://example.org"><marquee><font size="1">Ссылка виджета</font></marquee></a></div>'
        clean,meta=self.extract('<p>Проза.</p>'+footer)
        self.assertNotIn('Ссылка виджета',clean.raw);self.assertEqual(meta['removed_liveinternet_marquee_footers'],1)
        for changed in [footer+'Продолжение.',footer.replace('</div>','Дополнительная проза.</div>'),footer.replace('size="1"','size="3"')]:
            clean,meta=self.extract(changed);self.assertIn('Ссылка виджета',clean.raw)
            self.assertEqual(meta['removed_liveinternet_marquee_footers'],0)

    def test_separate_caption_requires_immediate_pure_image(self):
        image='<p><a><img></a></p>';caption='<p><em>Подпись.</em></p>'
        clean,meta=self.extract(image+caption+'Хвост.')
        self.assertNotIn('Подпись.',clean.raw);self.assertIn('Хвост.',clean.raw)
        self.assertEqual(meta['removed_liveinternet_image_captions'],1)
        for body in [caption,image+'<hr>'+caption,'<p>Проза<img></p>'+caption,image+'<p><em>Подпись.</em> Авторская оговорка.</p>','<blockquote>'+image+caption+'</blockquote>']:
            clean,meta=self.extract(body);self.assertIn('Подпись.',clean.raw)
            self.assertEqual(meta['removed_liveinternet_image_captions'],0)
        clean,meta=self.extract(image+caption+'<p><em>Следующее выделение.</em></p>')
        self.assertIn('Следующее выделение.',clean.raw);self.assertEqual(meta['removed_liveinternet_image_captions'],1)

    def test_same_paragraph_single_and_multiple_captions(self):
        for body,count in [('<p><img><br><em>Подпись1</em></p>',1),('<p><img><br><em>Подпись1</em><br><img><em>Подпись2</em></p>',2)]:
            clean,meta=self.extract(body+'Хвост.')
            self.assertNotIn('Подпись1',clean.raw);self.assertIn('Хвост.',clean.raw)
            self.assertEqual(meta['removed_liveinternet_image_captions'],count)
        for body in ['<p><img><em>Подпись1</em> Авторская проза.</p>','<p><em>Подпись1</em><img></p>','<p><img><img><em>Подпись1</em></p>']:
            clean,meta=self.extract(body);self.assertIn('Подпись1',clean.raw)
            self.assertEqual(meta['removed_liveinternet_image_captions'],0)

    def test_other_hosts_and_v15_keep_previous_behavior(self):
        body='<b>Настроение сейчас - <em>Поле CMS</em></b><p>Основной текст.</p>'
        source=self.source(body)
        old,meta=html_article_netology_candidate(source,self.url)
        self.assertIn('Настроение сейчас',old.raw);self.assertEqual(meta['clean_version'],'clean-v15-netology-candidate')
        for url in ['https://example.org/story','https://liveinternet.ru.example.org/users/example/post42/']:
            old,_=html_article_netology_candidate(source,url);new,meta=html_article_liveinternet_candidate(source,url)
            self.assertEqual(old,new);self.assertEqual(meta['bound_liveinternet_posts'],0)
            self.assertEqual(meta['clean_version'],'clean-v16-liveinternet-candidate')


if __name__=='__main__':unittest.main()
