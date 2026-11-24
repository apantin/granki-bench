import json
import unittest
from bench.cleaning import html_article_body_candidate,html_article_publisher_candidate


class PublisherRolesTest(unittest.TestCase):
    def extract(self,body,url='https://journal.tinkoff.ru/example/'):
        return html_article_publisher_candidate('<html><body><h1>Тестовая статья</h1><div itemprop="articleBody">'+body+'</div></body></html>',url)

    def widget(self,types):
        data=dict(levels=[dict(type='1-slot',flows=[dict(type='cards',items=[dict(type=t) for t in types])])])
        return '<div data-component-name="levels" data-component-data=\''+json.dumps(data)+'\'>Маркетинговый блок</div>'

    def test_bylines_keep_tails_and_own_prose(self):
        body='<p>Начало.</p><div class="article-author"><div class="article-author__name">Редактор</div><div class="article-author__position">роль</div><a class="article-author__link">Профиль</a></div>Продолжение.<div class="ugc-author-block"><div class="ugc-author-block__name"><b>Участник</b><br>подпись</div></div><div class="highlight"><p>Важная авторская оговорка.</p></div>'
        clean,meta=self.extract(body)
        for text in ['Начало.','Продолжение.','Важная авторская оговорка.']:self.assertIn(text,clean.raw)
        for text in ['Редактор','Участник','Профиль']:self.assertNotIn(text,clean.raw)
        self.assertEqual(meta['removed_publisher_bylines'],2)
        clean,meta=self.extract('<div class="article-author"><div class="article-author__name">Автор</div><p>Необычная содержательная проза.</p></div>')
        self.assertIn('Необычная содержательная проза.',clean.raw);self.assertEqual(meta['removed_publisher_bylines'],0)

    def test_only_homogeneous_known_widgets_are_removed(self):
        clean,meta=self.extract('<p>До.</p>'+self.widget(['promo-banner','subscription'])+'После.')
        self.assertNotIn('Маркетинговый блок',clean.raw);self.assertIn('После.',clean.raw);self.assertEqual(meta['removed_publisher_widgets'],1)
        for body in [self.widget(['promo-banner','article']),'<div data-component-name="levels" data-component-data="broken">Содержимое неизвестно</div>',self.widget([])]:
            with self.subTest(body=body):
                clean,meta=self.extract(body);self.assertEqual(meta['removed_publisher_widgets'],0);self.assertEqual(meta['unresolved_publisher_widgets'],1)

    def test_subscription_tile_keeps_outside_prose(self):
        tile='<div class="tile"><div class="tile__content"><h3 class="tile__title">Рассылка<div class="tile__description">Описание подписки</div>'+self.widget(['subscription'])+'</h3></div>EXTRA</div>'
        clean,meta=self.extract(tile.replace('EXTRA',''));self.assertNotIn('Рассылка',clean.raw);self.assertNotIn('Описание подписки',clean.raw)
        clean,meta=self.extract(tile.replace('EXTRA','<p>Отдельная авторская проза.</p>'));self.assertIn('Отдельная авторская проза.',clean.raw)

    def test_notice_requires_full_text_and_same_site_link(self):
        notice='Этот текст написан <a href="/community/">в Сообществе</a>, в нем сохранены авторский стиль и орфография.'
        clean,meta=self.extract('<div class="incut">'+notice+'</div><p>Основная проза.</p>');self.assertNotIn('Этот текст',clean.raw);self.assertIn('Основная проза.',clean.raw);self.assertEqual(meta['removed_publisher_notices'],1)
        for text in [notice+' Новая авторская мысль.',notice.replace('/community/','https://example.org/community/')]:
            clean,meta=self.extract('<div class="incut">'+text+'</div>');self.assertIn('Этот текст',clean.raw);self.assertEqual(meta['removed_publisher_notices'],0)

    def test_tile_heading_and_description_are_separate(self):
        clean,meta=self.extract('<div class="tile"><h3 class="tile__title">Совет<div class="tile__description">Объяснение совета.</div><a class="tile__button">Подробности</a></h3></div>')
        self.assertIn('### Совет\n\nОбъяснение совета.',clean.raw);self.assertNotIn('Подробности',clean.raw);self.assertEqual(meta['separated_publisher_tile_descriptions'],1)
        clean,meta=self.extract('<p><a>Авторская рекомендация</a></p>');self.assertIn('Авторская рекомендация',clean.raw)

    def test_only_single_plain_explanatory_aside_is_restored(self):
        aside='<aside class="aside"><div class="aside__text"><p></p><p>Авторское уточнение.</p></div></aside>'
        clean,meta=self.extract(aside);self.assertIn('Авторское уточнение.',clean.raw);self.assertEqual(meta['restored_publisher_asides'],1)
        for body in [aside.replace('class="aside"','class="aside aside--article"'),aside.replace('Авторское уточнение.','<a href="/related/">Связанная статья</a>'),aside.replace('<p></p>','<p>Вторая заметка.</p>')]:
            clean,meta=self.extract(body);self.assertEqual(meta['restored_publisher_asides'],0)

    def test_details_requires_exact_button_and_adjacent_content(self):
        label='<p class="details highlight js-unfolder"><button role="button" class="details__button js-unfolder-button"><u class="details__pseudolink">Расчёт результата</u></button></p>'
        content='<div class="details-content"><p>Развёрнутое объяснение.</p></div>'
        clean,meta=self.extract(label+content);self.assertIn('### Расчёт результата',clean.raw);self.assertIn('Развёрнутое объяснение.',clean.raw);self.assertEqual(meta['restored_publisher_details_labels'],1)
        clean,meta=self.extract(label+'<p>Другой контекст.</p>');self.assertEqual(meta['restored_publisher_details_labels'],0)

    def test_service_subtitle_keeps_content_subtitle_and_old_version(self):
        for text,expected in [('Вопрос читательницы Т—Ж',1),('Пошаговая инструкция',0)]:
            source='<html><body><article><h1>Заголовок</h1><h3 class="article-header__subtitle">'+text+'</h3><div itemprop="articleBody"><p>Проза.</p></div></article></body></html>'
            new,meta=html_article_publisher_candidate(source,'https://journal.tinkoff.ru/example/')
            old,_=html_article_body_candidate(source,'https://journal.tinkoff.ru/example/')
            self.assertIn(text,old.raw);self.assertEqual(text in new.raw,not bool(expected));self.assertEqual(meta['removed_publisher_service_subtitles'],expected)

    def test_other_host_and_previous_entrypoint_preserve_behavior(self):
        body='<div class="article-author"><div class="article-author__name">Подпись</div></div><p>Проза.</p>'
        source='<html><body><h1>Заголовок</h1><div itemprop="articleBody">'+body+'</div></body></html>'
        old,_=html_article_body_candidate(source,'https://example.org/article/');new,meta=html_article_publisher_candidate(source,'https://example.org/article/')
        self.assertEqual(old,new);self.assertEqual(meta['clean_version'],'clean-v13-publisher-candidate')
        old,_=html_article_body_candidate(source,'https://journal.tinkoff.ru/example/');self.assertIn('Подпись',old.raw)


if __name__=='__main__':unittest.main()
