import importlib.util
import unittest
from bench.cleaning import html_article_structure_candidate,html_article_editorial_candidate,VERSION


@unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости HTML')
class HTMLStructureTest(unittest.TestCase):
    def test_direct_div_keeps_intro_inline_words_and_lists(self):
        source='<html><body><nav>Меню</nav><h1>Синтетический заголовок</h1><div id="post-content-body">Вводное предложение.<br><br><b>Основной текст</b> продолжается.<br><br>Это <i>тот же</i> абзац.<ul><li>Первый пункт</li><li>Второй пункт</li></ul></div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://habr.com/ru/post/1/')
        self.assertEqual(VERSION,'clean-v3')
        self.assertIn('# Синтетический заголовок\n\nВводное предложение.',out.raw)
        self.assertIn('Основной текст продолжается.',out.raw)
        self.assertIn('Это тот же абзац.',out.raw)
        self.assertIn('- Первый пункт\n- Второй пункт',out.raw)
        self.assertNotIn('Меню',out.raw)
        self.assertEqual(meta['extraction_method'],'id:post-content-body')

    def test_semantic_body_title_and_removed_blocks_keep_tails(self):
        source='<html><body><h1 itemprop="headline">Название статьи<script>wrong_title()</script></h1><article itemprop="articleBody"><p>Начало.</p><blockquote>Чужая цитата<pre>foreign_code()</pre></blockquote>Продолжение.<pre>secret_code()</pre>После кода.<figure>Подпись рисунка</figure>Конец.</article></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        for value in ('# Название статьи','Начало.','Продолжение.','После кода.','Конец.','[КОД]'):self.assertIn(value,out.raw)
        for value in ('Чужая цитата','secret_code','foreign_code','wrong_title','Подпись рисунка'):self.assertNotIn(value,out.raw)
        self.assertEqual(out.code_blocks,1)

    def test_liveinternet_title_and_music_widget(self):
        source='<html><body><h1>Логотип</h1><h1 class="ZAG">Заголовок записи</h1><h1 class="ZAG"></h1><div class="MESS"><nobr>В колонках играет - <em>Музыка</em></nobr><p>Авторский текст.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://www.liveinternet.ru/users/example/post1/')
        self.assertEqual(out.raw,'# Заголовок записи\n\nАвторский текст.\n')

    def test_editorial_badge_and_nested_lists(self):
        source='<html><body><h1 itemprop="headline">Основной <span>заголовок <a><span class="content-editorial-tick">Статьи редакции</span></a></span></h1><div itemprop="articleBody"><ul><li>Верхний пункт<ul><li>Вложенный пункт</li></ul></li></ul></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://tjournal.ru/tech/1')
        self.assertIn('# Основной заголовок',out.raw)
        self.assertNotIn('Статьи редакции',out.raw)
        self.assertIn('  - Вложенный пункт',out.raw)
        self.assertIn('  - Вложенный пункт',out.norm)

    def test_platform_body_omits_interface_tags_and_keeps_paragraph_tails(self):
        source='<html><body><h1 itemprop="headline">Заголовок <span class="content-editorial-tick">Статьи редакции</span></h1><div class="content content--full"><div class="l-island-a"><p>Абзац статьи.</p></div><div class="l-island-a"><p><a href="/tag/news">#новости</a> <a href="/tag/test">#пример</a></p></div><div class="content-info">Просмотры 100</div></div><div class="comments">Чужой комментарий</div></body></html>'
        out,_=html_article_structure_candidate(source,'https://tjournal.ru/tech/1')
        self.assertEqual(out.raw,'# Заголовок\n\nАбзац статьи.\n')

    def test_direct_body_preserves_breaks_without_source_indentation(self):
        source='<html><body><div itemprop="articleBody">Начало.<br>\n Продолжение.<hr>\n Последний абзац.<table><tr><td>Табличные данные</td></tr></table>После таблицы.</div></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        self.assertIn('Начало.\nПродолжение.',out.raw)
        self.assertIn('Последний абзац.',out.raw)
        self.assertNotIn('Табличные данные',out.raw)
        self.assertIn('После таблицы.',out.raw)

    def test_direct_dom_keeps_literal_angles_and_formula_paragraph(self):
        source='<html><body><article itemprop="articleBody"><p>Если x &lt;1, меняем подход.</p><h2>Следующий раздел</h2><p>Если x &gt;1, продолжаем.</p><p>Параметр &lt;test-value&gt; сохраняется.</p><p>&gt; Доход = результат / затраты</p><p>Литеральная запись **пример** и &amp;lt;.</p></article></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        for value in ('x <1','## Следующий раздел','x >1','<test-value>','> Доход = результат / затраты','**пример**','&lt;'):
            self.assertIn(value,out.raw)
            self.assertIn(value,out.norm)

    def test_fallback_keeps_literal_angles_without_markdown_reinterpretation(self):
        paragraph='Обычный текст с <strong>выделением</strong>, параметром <code>&lt;test-value&gt;</code> и условием x &lt;1. '
        source='<html><body><div><p>'+paragraph*20+'</p><h2>Раздел источника</h2><p>Теперь x &gt;1.</p><p>&gt; Результат = доход / затраты</p></div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://example.org/post')
        self.assertEqual(meta['extraction_method'],'trafilatura-inline-fallback')
        self.assertIn('<test-value>',out.raw)
        self.assertIn('x <1',out.raw)
        # Полнота отбора заголовков fallback проверяется отдельно; здесь
        # проверяем, что постобработка не съедает текст между <1 и >1.
        self.assertIn('x >1',out.raw)
        self.assertIn('> Результат = доход / затраты',out.raw)
        self.assertNotIn('**выделением**',out.raw)
        self.assertNotIn('`<test-value>`',out.raw)

    def test_standard_entry_body_keeps_deleted_author_text_and_current_tail(self):
        source='<html><body><h1>Запись</h1><article class="entry-content"><p>Начало.</p>Автор говорит, что <del>отменённая фраза</del> текущая фраза.<ul><li>Первый</li><li>Второй</li></ul></article><div>Чужая рекомендация.</div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://example.org/post')
        self.assertEqual(meta['extraction_method'],'class:entry-content')
        self.assertIn('Автор говорит, что отменённая фраза текущая фраза.',out.raw)
        self.assertNotIn('Чужая рекомендация',out.raw)
        self.assertIn('- Первый\n- Второй',out.raw)

    def test_tinkoff_subtitle_and_responsive_table_and_form(self):
        source='<html><body><header><h1>Заголовок</h1><h3 class="article-header__subtitle">Подзаголовок</h3></header><div itemprop="articleBody"><p>Основной текст.</p><div class="inline-level"><p>Подписка на новости</p><form><input type="email"></form></div><h3 class="table-heading">Табличный заголовок</h3><table><tr><td>Данные desktop</td></tr></table><div class="mobile-table">Данные mobile</div><p>Концовка.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://journal.tinkoff.ru/example/')
        for value in ('# Заголовок','### Подзаголовок','Основной текст.','### Табличный заголовок','Концовка.'):self.assertIn(value,out.raw)
        for value in ('Подписка','Данные'):self.assertNotIn(value,out.raw)

    def test_kontur_lead_outside_body_and_sidebar_text(self):
        source='<html><body><h1>Заголовок</h1><div class="article-announce__text"><p>Вводный абзац.</p></div><div id="ArticleItem"><div class="lp-forms"><div class="text"><h2>Раздел</h2><p>Основной текст.</p><div class="text-block text-block_product" data-show-event-name="event-adv-example"><p>Рекламная вставка.</p></div>Продолжение после рекламы.<div class="text-block_product"><p>Авторское описание продукта.</p></div></div></div></div><aside><div class="text">Боковая колонка.</div></aside></body></html>'
        out,_=html_article_structure_candidate(source,'https://kontur.ru/articles/1')
        self.assertIn('Вводный абзац.\n\n## Раздел',out.raw)
        self.assertNotIn('Боковая колонка',out.raw)
        self.assertNotIn('Рекламная вставка',out.raw)
        self.assertIn('Продолжение после рекламы.',out.raw)
        self.assertIn('Авторское описание продукта.',out.raw)

    def test_rsdn_article_body_keeps_sections_and_omits_service_header(self):
        source='<html><body><table><tr><td>Рейтинг</td></tr></table><h1>Техническая статья</h1><h5><span class="title">Автор:</span><span>Иван Примеров</span></h5><h6><span class="title">Опубликовано:</span>2007</h6><table><tr><td>Оглавление</td></tr></table><p>Введение.</p><ul><li>Первый</li><li>Второй</li></ul><h2>Раздел</h2><p>Параметр &lt;test-value&gt;.</p><p><i style="font-size:x-small;">Рисунок 1.</i></p><div align="right"><hr><a href="/mag/">О журнале</a></div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://rsdn.org/article/example.xml')
        self.assertEqual(meta['extraction_method'],'profile:rsdn-article-body')
        for value in ('# Техническая статья','Введение.','- Первый\n- Второй','## Раздел','<test-value>'):self.assertIn(value,out.raw)
        for value in ('Рейтинг','Автор:','Опубликовано','Оглавление','Рисунок 1.','О журнале'):self.assertNotIn(value,out.raw)

    def test_telegraph_editor_excludes_duplicate_header_byline_and_comments(self):
        source='<html><body><header><h1>Название</h1></header><article id="_tl_editor" class="tl_article_content"><h1>Название</h1><address>Подпись автора</address><p>Начало статьи.</p><h2>Раздел</h2><p>Продолжение.</p></article><section><p>Добавить комментарий</p></section></body></html>'
        out,meta=html_article_structure_candidate(source,'https://telegra.ph/example')
        self.assertEqual(meta['extraction_method'],'id:_tl_editor')
        self.assertEqual(out.raw.count('# Название'),1)
        self.assertIn('Начало статьи.\n\n## Раздел',out.raw)
        self.assertNotIn('Подпись автора',out.raw);self.assertNotIn('Добавить комментарий',out.raw)

    def test_xakep_nested_article_omits_toc_and_preserves_literal_parameters(self):
        source='<html><body><h1>Устройство</h1><article>Рекомендованная статья</article><div class="bdaia-post-content can_read"><div>Содержание статьи</div><article class="xmd coding"><p>Вводный абзац.</p><p>Передатчик 1 &lt;&lt; TXEN0; следующая фраза.</p><p>Библиотека &lt;eeprom.h&gt; и продолжение.</p></article></div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://xakep.ru/example')
        self.assertEqual(meta['extraction_method'],'profile:xakep-xmd')
        for value in ('# Устройство','Вводный абзац.','1 << TXEN0; следующая фраза.','<eeprom.h> и продолжение.'):self.assertIn(value,out.raw)
        for value in ('Рекомендованная','Содержание статьи'):self.assertNotIn(value,out.raw)

    def test_texterra_image_caption_keeps_the_following_paragraph(self):
        source='<html><body><div class="article-content"><p>Начало.</p><div><img><p class="text_under_video">Подпись изображения</p>Хвост блока.</div><p>Концовка.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://texterra.ru/example')
        self.assertNotIn('Подпись изображения',out.raw)
        for value in ('Начало.','Хвост блока.','Концовка.'):self.assertIn(value,out.raw)

    def test_snob_photo_caption_and_part_navigation_are_not_author_body(self):
        source='<html><body><div class="post-content"><p><strong><a>Начало</a></strong> <strong><a>Продолжение</a></strong></p><p><strong><img><em>Место съёмки. Фото: архив</em></strong></p><p>Авторский текст <em>с выделением.</em></p><p><img>В обычном абзаце Фото: это часть рассуждения.</p><p><em>Фото: авторская фраза без изображения.</em></p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://snob.ru/example')
        for value in ('Начало Продолжение','Место съёмки.'):self.assertNotIn(value,out.raw)
        for value in ('Авторский текст с выделением.','В обычном абзаце Фото: это часть рассуждения.','Фото: авторская фраза без изображения.'):self.assertIn(value,out.raw)

    def test_pure_code_table_keeps_marker_count_and_following_text(self):
        source='<html><body><div itemprop="articleBody"><p>Перед примером.</p><table class="code"><tr><td><pre><b>код</b> &lt;параметр&gt;</pre></td></tr></table>Продолжение после примера.<table class="code"><tr><td><pre>первый</pre></td><td><pre>второй</pre></td></tr></table></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        self.assertEqual(out.raw.count('[КОД]'),3);self.assertEqual(out.code_blocks,3)
        self.assertIn('Перед примером.',out.raw);self.assertIn('Продолжение после примера.',out.raw)
        self.assertNotIn('<параметр>',out.raw)

    def test_data_table_with_code_cell_and_quoted_code_table_still_omitted(self):
        source='<html><body><div itemprop="articleBody"><p>Основной текст.</p><table class="code"><tr><th>Данные таблицы</th><td><pre>код в данных</pre></td></tr></table><blockquote><table class="code"><tr><td><pre>чужой код</pre></td></tr></table></blockquote><p>Концовка.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        self.assertEqual(out.code_blocks,0);self.assertNotIn('[КОД]',out.raw)
        for value in ('Данные таблицы','код в данных','чужой код'):self.assertNotIn(value,out.raw)
        self.assertIn('Концовка.',out.raw)

    def test_selectel_standalone_application_footer_preserves_author_content(self):
        source='<html><body><div itemprop="articleBody"><p>Основной текст и <a href="https://startups.selectel.ru">описание сервиса</a>.</p><p>Концовка статьи.</p><hr><p>Чтобы участвовать, заполните заявку на сайте <a href="https://startups.selectel.ru">сервиса</a>.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://blog.selectel.ru/example')
        self.assertIn('Основной текст и описание сервиса.',out.raw);self.assertIn('Концовка статьи.',out.raw)
        self.assertNotIn('заполните заявку',out.raw)
        source='<html><body><div itemprop="articleBody"><p>Основной текст.</p><hr><p>История <a href="https://startups.selectel.ru">сервиса</a> завершает рассказ.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://selectel.ru/example')
        self.assertIn('История сервиса завершает рассказ.',out.raw)

    def test_editorial_candidate_restores_plain_callout_and_keeps_v5_unchanged(self):
        source='<html><body><h1>Статья</h1><div class="content--full"><p>Начало.</p><figure><div><blockquote class="block-incut"><div><p>Авторская врезка.</p></div></blockquote></div></figure>Продолжение.<blockquote class="block-quote"><p>Неатрибутированная цитата.</p></blockquote></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://vc.ru/example')
        out,meta=html_article_editorial_candidate(source,'https://vc.ru/example')
        self.assertNotIn('Авторская врезка.',old.raw)
        self.assertIn('Авторская врезка.',out.raw);self.assertIn('Продолжение.',out.raw)
        self.assertIn('Неатрибутированная цитата.',out.raw)
        self.assertEqual(meta['preserved_editorial_callouts'],1);self.assertEqual(meta['preserved_unattributed_quotes'],1)
        self.assertEqual(meta['quote_review_blocks'],2)
        self.assertEqual(meta['clean_version'],'clean-v6-editorial-candidate');self.assertEqual(VERSION,'clean-v3')

    def test_editorial_candidate_does_not_restore_attributed_or_mixed_figure(self):
        source='<html><body><div class="content--full"><p>Основной текст.</p><figure><blockquote class="block-incut" cite="https://example.org/source"><p>Чужая цитата.</p></blockquote></figure><figure><blockquote class="block-incut"><p>Неоднозначная врезка.</p></blockquote><p>Внешняя подпись.</p></figure><blockquote class="block-incut"><div class="block-incut__author">Другой автор</div><p>Подписанная цитата.</p></blockquote></div></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://tjournal.ru/example')
        for value in ('Чужая цитата.','Неоднозначная врезка.','Внешняя подпись.','Подписанная цитата.'):self.assertNotIn(value,out.raw)
        self.assertEqual(meta['preserved_editorial_callouts'],0);self.assertEqual(meta['quote_review_blocks'],1)
        self.assertEqual(meta['unresolved_mixed_figures'],1)

    def test_editorial_callout_code_is_counted_but_nested_foreign_quote_is_not(self):
        source='<html><body><div class="content--full"><blockquote class="block-incut"><p>Авторский текст.</p><pre>свой код</pre><blockquote cite="https://example.org/source"><blockquote class="block-incut"><pre>чужой код</pre><p>Чужие слова.</p></blockquote></blockquote></blockquote></div></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://vc.ru/example')
        self.assertIn('Авторский текст.',out.raw);self.assertNotIn('Чужие слова.',out.raw)
        self.assertEqual(out.code_blocks,1);self.assertEqual(out.raw.count('[КОД]'),1)
        self.assertEqual(meta['preserved_editorial_callouts'],1)

    def test_editorial_widget_filter_keeps_ordinary_author_block(self):
        source='<html><body><div itemprop="articleBody"><p>Основной текст.</p><div class="text-block_test"><p>Рекламное приглашение.</p><a class="btn btn-primary" rel="nofollow noopener">Узнать больше</a></div>Продолжение после рекламы.<div class="text-block_test"><p>Авторский пример.</p><a>Обычная ссылка</a></div></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://kontur.ru/example')
        out,_=html_article_editorial_candidate(source,'https://kontur.ru/example')
        self.assertIn('Рекламное приглашение.',old.raw);self.assertNotIn('Рекламное приглашение.',out.raw)
        for value in ('Основной текст.','Продолжение после рекламы.','Авторский пример.','Обычная ссылка'):self.assertIn(value,out.raw)

    def test_legacy_html_figure_keeps_entire_article_and_excludes_media(self):
        source='<html><body><h1>Статья</h1><div class="content content--full content--legacy"><figure><div class="content-image">Подпись картинки</div></figure><figure><div class="block-html">Вводная фраза.<br><br><h2>Раздел</h2><p>Полный основной текст.</p><pre>Код</pre></div></figure></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://vc.ru/example')
        out,meta=html_article_editorial_candidate(source,'https://vc.ru/example')
        self.assertNotIn('Основной текст',old.raw)
        for value in ('# Статья','Вводная фраза.','## Раздел','Полный основной текст.','[КОД]'):self.assertIn(value,out.raw)
        self.assertNotIn('Подпись картинки',out.raw);self.assertEqual(out.code_blocks,1)
        self.assertEqual(meta['preserved_legacy_html_blocks'],1)

    def test_legacy_html_requires_known_role_and_no_external_caption(self):
        for classes in ('content--full','content--full content--legacy'):
            source='<html><body><div class="'+classes+'"><figure><div class="block-html"><p>Неоднозначный блок.</p></div><figcaption>Другой автор</figcaption></figure></div></body></html>'
            out,meta=html_article_editorial_candidate(source,'https://vc.ru/example')
            self.assertNotIn('Неоднозначный блок.',out.raw)
            self.assertEqual(meta['preserved_legacy_html_blocks'],0)
            self.assertEqual(meta['unresolved_legacy_html_figures'],int('content--legacy' in classes))

    def test_legacy_html_and_editorial_quote_rules_compose(self):
        source='<html><body><div class="content--full content--legacy"><figure><div class="block-html"><p>Основной текст.</p><blockquote><p>Авторская врезка.</p></blockquote><blockquote cite="https://example.org/source"><p>Чужая цитата.</p></blockquote></div></figure></div></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://vc.ru/example')
        self.assertIn('Авторская врезка.',out.raw);self.assertNotIn('Чужая цитата.',out.raw)
        self.assertEqual(meta['preserved_legacy_html_blocks'],1)
        self.assertEqual(meta['preserved_unattributed_quotes'],1);self.assertEqual(meta['unresolved_mixed_figures'],0)

    def test_zavtra_gallery_caption_and_channel_widget_removed_with_tails(self):
        source='<html><body><div class="article__content"><p>Авторский текст.</p><p><strong>Илл. Автор изображения.</strong></p><div class="photogall"><img><p>двойной клик - редактировать галерею</p></div>Продолжение.<div class="zen_inv"><b>Подписывайтесь на <a href="https://zen.yandex.ru/example">наш канал</a>!</b></div>Концовка.</div></body></html>'
        old,_=html_article_structure_candidate(source,'https://zavtra.ru/example')
        out,_=html_article_editorial_candidate(source,'https://zavtra.ru/example')
        self.assertIn('редактировать галерею',old.raw)
        for value in ('Илл. Автор','редактировать галерею','Подписывайтесь'):self.assertNotIn(value,out.raw)
        for value in ('Авторский текст.','Продолжение.','Концовка.'):self.assertIn(value,out.raw)

    def test_zavtra_author_caption_word_without_gallery_or_widget_stays(self):
        source='<html><body><div class="article__content"><p><strong>Илл. — обозначение в авторском примере.</strong></p><p>Обсудим <a href="https://zen.yandex.ru/example">канал</a>.</p><div class="photogall"><p>Авторское описание без изображения.</p></div></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://zavtra.ru/example')
        for value in ('Илл. — обозначение','Обсудим канал.','Авторское описание без изображения.'):self.assertIn(value,out.raw)

    def test_liveinternet_generated_first_mood_field_is_not_author_body(self):
        source='<html><body><h1 class="ZAG">Запись</h1><div class="MESS"><p><b>Настроение сейчас - <em>СПОКОЙНО</em></b></p><p>Авторский абзац.</p></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://liveinternet.ru/example')
        out,_=html_article_editorial_candidate(source,'https://liveinternet.ru/example')
        self.assertIn('Настроение сейчас',old.raw);self.assertNotIn('Настроение сейчас',out.raw)
        self.assertIn('Авторский абзац.',out.raw)

    def test_liveinternet_author_sentence_about_mood_stays(self):
        source='<html><body><div class="MESS"><p>Настроение сейчас — часть рассказа.</p><p><b>Настроение сейчас — авторская цитата ниже текста.</b></p></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://liveinternet.ru/example')
        self.assertIn('часть рассказа.',out.raw);self.assertIn('авторская цитата ниже текста.',out.raw)

    def test_tinkoff_class_body_restores_subtitle_without_footer(self):
        source='<html><body><h1>Тема</h1><h3 class="article-header__subtitle">Вводный подзаголовок</h3><div class="article-body"><p>Первый абзац.</p><h2>Раздел</h2><p>Последний абзац.</p></div><footer class="article-body">Поделиться</footer></body></html>'
        _,old=html_article_structure_candidate(source,'https://journal.tinkoff.ru/example/')
        out,meta=html_article_editorial_candidate(source,'https://journal.tinkoff.ru/example/')
        self.assertEqual(old['extraction_method'],'trafilatura-inline-fallback')
        self.assertEqual(meta['extraction_method'],'profile:tinkoff-article-body')
        self.assertEqual(out.raw,'# Тема\n\n### Вводный подзаголовок\n\nПервый абзац.\n\n## Раздел\n\nПоследний абзац.\n')
        ambiguous=source.replace('</footer>','</footer><div class="article-body">Другое тело</div>')
        _,meta=html_article_editorial_candidate(ambiguous,'https://journal.tinkoff.ru/example/')
        self.assertEqual(meta['extraction_method'],'trafilatura-inline-fallback')

    def test_tinkoff_question_widget_removed_but_author_question_stays(self):
        source='<html><body><div itemprop="articleBody"><p>Чтобы задать вопрос, изучим <a href="/chto-delat-form/">форму</a>.</p><div class="panel button_plashka"><p>Приглашение читателей.</p><div class="panel__button-wrapper"><a class="button" href="/chto-delat-form/">Задать вопрос</a></div></div>Продолжение.<div class="button_plashka"><p>Авторский пример.</p><a href="/chto-delat-form/">Задать вопрос</a></div></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://journal.tinkoff.ru/example/')
        out,_=html_article_editorial_candidate(source,'https://journal.tinkoff.ru/example/')
        self.assertIn('Приглашение читателей.',old.raw);self.assertNotIn('Приглашение читателей.',out.raw)
        for value in ('Чтобы задать вопрос, изучим форму.','Продолжение.','Авторский пример.'):self.assertIn(value,out.raw)

    def test_netology_builder_keeps_article_but_drops_course_and_pure_navigation(self):
        source='<html><body><div class="entry-content"><div class="stk-post"><div class="stk-grid-col"><h2>Авторский раздел</h2><p>Автор объясняет <a href="/blog/source">источник</a>.</p><div class="ntlgy-course--wide"><p>Реклама курса.</p><a href="/programs/example">Узнать больше</a></div>Продолжение после рекламы.<div class="stk-grid-col"><p><b>Читать также</b></p><figure><img></figure><p><a href="/blog/related">Другая статья</a> ?<br></p></div></div><div class="ntlgy-course--wide"><p>Авторский рассказ о курсе без кнопки.</p></div></div></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://netology.ru/blog/example')
        out,_=html_article_editorial_candidate(source,'https://netology.ru/blog/example')
        self.assertIn('Реклама курса.',old.raw)
        for value in ('Реклама курса.','Читать также','Другая статья'):self.assertNotIn(value,out.raw)
        for value in ('## Авторский раздел','Автор объясняет источник.','Продолжение после рекламы.','Авторский рассказ о курсе без кнопки.'):self.assertIn(value,out.raw)

    def test_related_label_with_author_prose_or_external_link_stays(self):
        body='<div class="{role}"><p>{label} <a href="/blog/link">ссылка</a>, которую стоит обсудить.</p></div><div class="{role}"><p>{label} <a href="https://elsewhere.example/blog/link">внешний источник</a></p></div>'
        for host,role,label in [('netology.ru','stk-grid-col','Читать также'),('texterra.ru','incut','Читайте также:')]:
            source='<html><body><article itemprop="articleBody">'+body.format(role=role,label=label)+'</article></body></html>'
            out,_=html_article_editorial_candidate(source,'https://'+host+'/example')
            self.assertIn('которую стоит обсудить.',out.raw);self.assertIn('внешний источник',out.raw)

    def test_texterra_related_widgets_and_hidden_id_leave_authored_incuts(self):
        source='<html><body><article itemprop="articleBody"><div class="incut">Авторская мысль.</div><div class="incut"><p>Читайте также: <a href="/blog/related">Соседняя статья</a></p></div>После ссылки.<span id="postId" style="color:red; DISPLAY: none !important;">service-slug</span><span id="postId">Видимый авторский идентификатор.</span><span style="display:none">Другой скрытый элемент.</span></article></body></html>'
        old,_=html_article_structure_candidate(source,'https://texterra.ru/example')
        out,_=html_article_editorial_candidate(source,'https://texterra.ru/example')
        self.assertIn('service-slug',old.raw)
        for value in ('Соседняя статья','service-slug'):self.assertNotIn(value,out.raw)
        for value in ('Авторская мысль.','После ссылки.','Видимый авторский идентификатор.','Другой скрытый элемент.'):self.assertIn(value,out.raw)

    def test_xakep_readable_body_preserves_main_sections_references_and_code(self):
        source='<html><body><h1>Статья</h1><div class="bdaia-post-content can_read"><div id="toc">Содержание статьи<a href="#toc01">Раздел</a></div><p>Вводный абзац.</p><div class="toch" id="toc01"></div><h2>Раздел</h2><p>Основной текст.</p><pre>код</pre><div class="panel www"><a href="https://elsewhere.example">Источник</a></div></div><aside>Посторонняя рекомендация</aside></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://xakep.ru/example')
        self.assertEqual(meta['extraction_method'],'profile:xakep-readable-body')
        self.assertEqual(meta['source_incomplete_markers'],[])
        self.assertEqual(out.raw,'# Статья\n\nВводный абзац.\n\n## Раздел\n\nОсновной текст.\n\n[КОД]\n\nИсточник\n')
        self.assertEqual(out.code_blocks,1)
        # Идентификатор toc сам по себе не повод удалять авторский текст.
        source=source.replace('Содержание статьи<a href="#toc01">Раздел</a>','Авторское обсуждение <a href="#toc01">раздела</a>.')
        out,_=html_article_editorial_candidate(source,'https://xakep.ru/example')
        self.assertIn('Авторское обсуждение раздела.',out.raw)

    def test_xakep_cut_is_flagged_without_claiming_complete_article(self):
        for readable in ('',' can_read'):
            source='<html><body><div class="bdaia-post-content'+readable+'"><p>Доступный отрывок.</p><div id="xakepcut" class="xakepcut default"><h3>Продолжение доступно только участникам</h3></div></div></body></html>'
            _,meta=html_article_editorial_candidate(source,'https://xakep.ru/example')
            self.assertEqual(meta['source_incomplete_markers'],['xakep-access-cut'])
            self.assertEqual(meta['extraction_method'],'trafilatura-inline-fallback')
            _,old=html_article_structure_candidate(source,'https://xakep.ru/example')
            self.assertNotIn('source_incomplete_markers',old)
        _,meta=html_article_editorial_candidate(source,'https://example.org/post')
        self.assertEqual(meta['source_incomplete_markers'],[])


    def test_snob_explicit_inner_body_keeps_lead_lists_and_excludes_outer_interface(self):
        for role in ('entryBody','stuff blogEntryBody'):
            source='<html><body><article class="'+role+'" data-article><div class="columnistsHeader"><h2>Наши колумнисты</h2></div><hgroup><h1>Статья</h1><h3 class="lead">Вводный подзаголовок.</h3></hgroup><div class="main"><dl class="media image"><dt>Подпись иллюстрации</dt></dl></div><div class="content body" data-sharer><div class="sharer"><h5>Поделиться:</h5><a href="#">В сеть</a></div>Начало.<p>Основной абзац.</p><ul><li>Первый пункт</li><li>Второй пункт</li></ul><div class="sharer"><p>Авторский разбор обмена.</p></div></div><ul class="entryFeatures"><li>Забрать себе</li></ul></article></body></html>'
            _,old=html_article_structure_candidate(source,'https://snob.ru/example')
            out,meta=html_article_editorial_candidate(source,'https://snob.ru/example')
            self.assertEqual(old['extraction_method'],'trafilatura-inline-fallback')
            self.assertEqual(meta['extraction_method'],'profile:snob-article-text')
            self.assertEqual(out.raw,'# Статья\n\n### Вводный подзаголовок.\n\nНачало.\n\nОсновной абзац.\n\n- Первый пункт\n- Второй пункт\n\nАвторский разбор обмена.\n')

    def test_snob_missing_role_or_ambiguous_inner_body_is_not_silently_selected(self):
        from bench.html_structure import choose_editorial_main
        from lxml import html
        bodies=('<article class="entryBody"><div class="content" data-sharer>Текст</div></article>',
                '<article class="unknown" data-article><div class="content" data-sharer>Текст</div></article>',
                '<article class="entryBody" data-article><div class="content" data-sharer>Первый</div><div class="content" data-sharer>Второй</div></article>')
        for body in bodies:
            main,method=choose_editorial_main(html.fromstring('<html><body>'+body+'</body></html>'),'snob.ru')
            self.assertIsNone(main);self.assertEqual(method,'trafilatura-inline-fallback')

    def test_tinkoff_direct_signature_is_removed_without_removing_nested_author_context(self):
        signature='<div class="article-author" itemprop="author"><div itemprop="name">Автор подписи</div><a class="article-author__link" href="/user1/">Профиль автора</a></div>'
        source='<html><body><div itemprop="articleBody">'+signature+'Текст после подписи.<section>'+signature.replace('Автор подписи','Герой авторского примера')+'</section><div class="article-author"><p>Авторский рассказ.</p></div></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://journal.tinkoff.ru/example')
        self.assertNotIn('Автор подписи',out.raw)
        for value in ('Текст после подписи.','Герой авторского примера','Авторский рассказ.'):self.assertIn(value,out.raw)

    def test_tinkoff_story_form_cta_requires_known_form_label_and_widget_role(self):
        def panel(href,label,wrapper=True):
            return '<div class="button_plashka"><p>Текст виджета '+label+'.</p><div class="'+('panel__button-wrapper' if wrapper else 'author-example')+'"><a class="button" href="'+href+'">'+label+'</a></div></div>'
        source='<html><body><div itemprop="articleBody">'+panel('/education-form/ ','Рассказать')+'Продолжение.'+panel('/education-form/','Описание')+panel('https://elsewhere.example/education-form/','Рассказать')+panel('/education-form/','Рассказать',False)+'</div></body></html>'
        old,_=html_article_structure_candidate(source,'https://journal.tinkoff.ru/example')
        out,_=html_article_editorial_candidate(source,'https://journal.tinkoff.ru/example')
        self.assertEqual(old.raw.count('Текст виджета Рассказать.'),3)
        self.assertEqual(out.raw.count('Текст виджета Рассказать.'),2)
        self.assertIn('Текст виджета Описание.',out.raw);self.assertIn('Продолжение.',out.raw)


    def test_teplitsa_related_navigation_is_removed_before_restoring_editorial_quotes(self):
        source='<html><body><div class="entry-content"><p>Основная проза.</p><blockquote><p>Еще по теме: <a href="https://te-st.org/2020/02/03/synthetic/">Соседняя статья</a></p></blockquote>Продолжение.<blockquote><p>Ещё по теме: <a href="/2019/04/05/example/">Другая статья</a></p></blockquote><blockquote><p>Авторская врезка.</p><pre>пример кода</pre></blockquote></div></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://te-st.org/2021/01/02/post/')
        for value in ('Соседняя статья','Другая статья','по теме:'):self.assertNotIn(value,out.raw)
        for value in ('Основная проза.','Продолжение.','Авторская врезка.','[КОД]'):self.assertIn(value,out.raw)
        self.assertEqual(meta['quote_review_blocks'],1);self.assertEqual(out.code_blocks,1)

    def test_teplitsa_related_words_with_authored_prose_or_external_link_are_preserved(self):
        source='<html><body><article itemprop="articleBody"><blockquote><p>Еще по теме: <a href="/2020/01/02/example/">Источник</a> поясняет авторскую мысль.</p></blockquote><blockquote><p>Еще по теме: <a href="https://example.org/2020/01/02/other/">Внешняя ссылка</a></p></blockquote></article></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://te-st.org/2021/01/02/post/')
        self.assertIn('Источник поясняет авторскую мысль.',out.raw);self.assertIn('Внешняя ссылка',out.raw)
        self.assertEqual(meta['quote_review_blocks'],2)

    def test_radio_credit_leaves_prose_and_preserves_provenance_in_metadata(self):
        source='<html><body><div class="article__content"><p>Авторская проза.</p><p><strong>Из эфира на <a href="https://radiokp.ru/podcast/synthetic/" rel="nofollow noopener">радио «Пример»</a></strong></p>Послесловие.</div></body></html>'
        old,old_meta=html_article_structure_candidate(source,'https://zavtra.ru/example')
        out,meta=html_article_editorial_candidate(source,'https://zavtra.ru/example')
        self.assertIn('Из эфира',old.raw);self.assertNotIn('source_credits',old_meta)
        self.assertNotIn('Из эфира',out.raw);self.assertIn('Авторская проза.',out.raw);self.assertIn('Послесловие.',out.raw)
        self.assertEqual(meta['source_credits'],[dict(text='Из эфира на радио «Пример»',links=['https://radiokp.ru/podcast/synthetic/'])])

    def test_radio_credit_words_outside_known_terminal_role_remain_author_text(self):
        variants=[
            '<p><strong>Из эфира на <a href="https://radiokp.ru/podcast/synthetic/" rel="nofollow">радио</a></strong></p><p>Следующий авторский абзац.</p>',
            '<p>Из эфира на <a href="https://radiokp.ru/podcast/synthetic/" rel="nofollow">радио</a> взят авторский пример.</p>',
            '<p><strong>Из эфира на <a href="https://example.org/podcast/synthetic/" rel="nofollow">другом сайте</a></strong></p>',
            '<p><strong>Из эфира на <a href="https://radiokp.ru/podcast/synthetic/">радио без роли ссылки</a></strong></p>',
        ]
        for body in variants:
            out,meta=html_article_editorial_candidate('<html><body><div class="article__content">'+body+'</div></body></html>','https://zavtra.ru/example')
            self.assertIn('Из эфира',out.raw);self.assertEqual(meta['source_credits'],[])

    def test_source_credit_status_is_unknown_without_explicit_body(self):
        _,meta=html_article_editorial_candidate('<html><body><p>Обычный текст. '*20+'</p></body></html>','https://example.org/post')
        self.assertIsNone(meta['source_credits'])





    def test_testimonial_with_cite_removed_before_quote_restore_and_code_count(self):
        source='<html><body><div class="entry-content"><p>Начало.</p><div class="box testimonial"><blockquote><p>Чужой отзыв.</p></blockquote><pre>foreign_code()</pre><cite><span>Автор отзыва</span></cite></div>Продолжение.<div class="testimonial"><img><p><cite>Подпись изображения</cite></p></div>Конец.<blockquote><p>Авторская формула.</p></blockquote><pre>own_code()</pre></div></body></html>'
        old,_=html_article_structure_candidate(source,'https://te-st.org/example')
        out,meta=html_article_editorial_candidate(source,'https://te-st.org/example')
        self.assertIn('Автор отзыва',old.raw);self.assertIn('Подпись изображения',old.raw)
        for value in ('Начало.','Продолжение.','Конец.','Авторская формула.'):
            self.assertIn(value,out.raw)
        for value in ('Чужой отзыв','Автор отзыва','Подпись изображения','foreign_code'):
            self.assertNotIn(value,out.raw)
        self.assertEqual(out.code_blocks,1);self.assertEqual(meta['preserved_unattributed_quotes'],1)

    def test_testimonial_requires_known_host_div_role_and_nonempty_cite(self):
        blocks=['<div class="testimonial"><p>Авторский пример.</p></div>',
                '<div class="testimonial"><p>Авторский пример.</p><cite> </cite></div>',
                '<div class="testimonial-other"><p>Авторский пример.</p><cite>Подпись</cite></div>',
                '<section class="testimonial"><p>Авторский пример.</p><cite>Подпись</cite></section>']
        for block in blocks:
            out,_=html_article_editorial_candidate('<html><body><div class="entry-content">'+block+'</div></body></html>','https://te-st.org/example')
            self.assertIn('Авторский пример.',out.raw)
        source='<html><body><div class="entry-content"><div class="testimonial"><p>Авторский пример.</p><cite>Подпись</cite></div></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://example.org/example')
        self.assertIn('Авторский пример.',out.raw)

    def test_zavtra_last_strong_photo_caption_removed_with_tail_only_in_v6(self):
        source='<html><body><div class="article__content"><p>Авторская проза.</p><p><strong>На фото: <i>подпись иллюстрации</i>.</strong></p>Продолжение.</div></body></html>'
        old,_=html_article_structure_candidate(source,'https://zavtra.ru/example')
        out,_=html_article_editorial_candidate(source,'https://zavtra.ru/example')
        self.assertIn('На фото:',old.raw);self.assertNotIn('На фото:',out.raw)
        self.assertIn('Авторская проза.',out.raw);self.assertIn('Продолжение.',out.raw)

    def test_photo_caption_requires_terminal_wholly_strong_paragraph_and_known_host(self):
        blocks=['<p><strong>На фото: автор рассуждает.</strong></p><p>Ещё проза.</p>',
                '<p>На фото: автор рассуждает.</p>',
                '<p>Введение. <strong>На фото: автор рассуждает.</strong></p>',
                '<p><strong>На фото: автор рассуждает.</strong><span>Продолжение.</span></p>',
                '<div><p><strong>На фото: автор рассуждает.</strong></p></div>']
        for block in blocks:
            out,_=html_article_editorial_candidate('<html><body><div class="article__content">'+block+'</div></body></html>','https://zavtra.ru/example')
            self.assertIn('На фото:',out.raw)
        source='<html><body><div class="article__content"><p><strong>На фото: автор рассуждает.</strong></p></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://example.org/example')
        self.assertIn('На фото:',out.raw)

    def test_named_teplitsa_quote_is_not_restored_as_author_callout(self):
        source='<html><body><div class="entry-content"><blockquote class="wp-block-tst-tst-quote"><p class="quote-content">Чужой отзыв.</p><p class="author-name">Автор отзыва</p><p class="author-about">Участник</p><pre>foreign_code()</pre></blockquote>Продолжение.<blockquote><p>Авторская врезка.</p></blockquote><pre>own_code()</pre></div></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://te-st.org/example')
        for value in ('Чужой отзыв.','Автор отзыва','Участник'):self.assertNotIn(value,out.raw)
        self.assertIn('Продолжение.',out.raw);self.assertIn('Авторская врезка.',out.raw)
        self.assertEqual(meta['quote_review_blocks'],1);self.assertEqual(out.code_blocks,1)

    def test_named_quote_requires_known_host_role_and_nonempty_direct_attribution(self):
        variants=[('<blockquote class="wp-block-tst-tst-quote"><p>Авторский текст.</p><p class="author-name"> </p></blockquote>','te-st.org'),
                  ('<blockquote><p>Авторский текст.</p><p class="author-name">Автор</p></blockquote>','te-st.org'),
                  ('<blockquote class="wp-block-tst-tst-quote"><p>Авторский текст.</p><p class="author-name">Автор</p></blockquote>','example.org')]
        for block,host in variants:
            out,_=html_article_editorial_candidate('<html><body><div class="entry-content">'+block+'</div></body></html>','https://'+host+'/example')
            self.assertIn('Авторский текст.',out.raw)

    def test_teplitsa_pure_cta_paragraphs_leave_descriptions_and_tails(self):
        source='<html><body><div class="entry-content"><h2>Возможность</h2><p>Описание события.</p><p class="wp-block-paragraph"><a href="https://example.org/event">Узнать подробности</a>.</p>Продолжение.<p class="wp-block-paragraph"><a href="https://example.org/form">Зарегистрироваться.</a></p>Конец.</div></body></html>'
        old,_=html_article_structure_candidate(source,'https://te-st.org/example')
        out,_=html_article_editorial_candidate(source,'https://te-st.org/example')
        self.assertIn('Узнать подробности',old.raw)
        self.assertNotIn('Узнать подробности',out.raw);self.assertNotIn('Зарегистрироваться',out.raw)
        for value in ('## Возможность','Описание события.','Продолжение.','Конец.'):self.assertIn(value,out.raw)

    def test_cta_words_need_pure_direct_paragraph_known_role_and_web_link(self):
        variants=['<p class="wp-block-paragraph">Можно <a href="https://example.org/">Узнать подробности</a>.</p>',
                  '<p><a href="https://example.org/">Узнать подробности</a>.</p>',
                  '<p class="wp-block-paragraph"><a href="https://example.org/">Узнать подробности</a><span>Важно</span></p>',
                  '<blockquote><p class="wp-block-paragraph"><a href="https://example.org/">Узнать подробности</a>.</p></blockquote>',
                  '<p class="wp-block-paragraph"><a href="#details">Узнать подробности</a>.</p>']
        for block in variants:
            out,_=html_article_editorial_candidate('<html><body><div class="entry-content">'+block+'</div></body></html>','https://te-st.org/example')
            self.assertIn('Узнать подробности',out.raw)
        source='<html><body><div class="entry-content"><p class="wp-block-paragraph"><a href="https://example.org/">Узнать подробности</a>.</p></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://example.org/example');self.assertIn('Узнать подробности',out.raw)

    def test_report_related_navigation_requires_pure_label_and_internal_report(self):
        source='<html><body><div class="entry-content"><blockquote><p>Еще по теме: <a href="https://te-st.org/reports/synthetic/">Соседний отчёт</a></p></blockquote>Продолжение.<blockquote><p>Еще по теме: <a href="/reports/source/">Авторский источник</a> поясняет мысль.</p></blockquote><blockquote><p>Еще по теме: <a href="https://example.org/reports/external/">Внешний отчёт</a></p></blockquote><blockquote><p>Еще по теме: <a href="/reports/">Архив отчётов</a></p></blockquote></div></body></html>'
        out,meta=html_article_editorial_candidate(source,'https://te-st.org/example')
        self.assertNotIn('Соседний отчёт',out.raw)
        for value in ('Продолжение.','Авторский источник поясняет мысль.','Внешний отчёт','Архив отчётов'):self.assertIn(value,out.raw)
        self.assertEqual(meta['quote_review_blocks'],3)

    def test_terminal_source_link_credit_keeps_metadata_and_following_tail(self):
        source='<html><body><div class="article__content"><p>Авторская проза.</p><p><strong><a href="https://example.org/original" rel="nofollow">Источник</a></strong></p>Продолжение.</div></body></html>'
        old,_=html_article_structure_candidate(source,'https://zavtra.ru/example')
        out,meta=html_article_editorial_candidate(source,'https://zavtra.ru/example')
        self.assertIn('Источник',old.raw);self.assertNotIn('Источник',out.raw)
        self.assertIn('Авторская проза.',out.raw);self.assertIn('Продолжение.',out.raw)
        self.assertEqual(meta['source_credits'],[dict(text='Источник',links=['https://example.org/original'])])

    def test_source_link_words_outside_exact_terminal_role_are_preserved(self):
        variants=['<p><strong><a href="https://example.org/" rel="nofollow">Источник</a></strong></p><p>Дальше проза.</p>',
                  '<p>Источник <a href="https://example.org/" rel="nofollow">поясняет мысль</a>.</p>',
                  '<p><strong><a href="https://example.org/">Источник</a></strong></p>',
                  '<p><strong><a href="/article/" rel="nofollow">Источник</a></strong></p>',
                  '<p><strong><a href="https://zavtra.ru/another/" rel="nofollow">Источник</a></strong></p>',
                  '<p><strong><a href="https://example.org/" rel="nofollow">Источник</a> авторской мысли</strong></p>']
        for block in variants:
            out,meta=html_article_editorial_candidate('<html><body><div class="article__content">'+block+'</div></body></html>','https://zavtra.ru/example')
            self.assertIn('Источник',out.raw);self.assertEqual(meta['source_credits'],[])


    def test_selectel_primary_author_card_is_removed_only_in_editorial_mode(self):
        card='<div class="post__preview-author"><a class="author-card" href="/blog/author/example/"><div class="author-card__name">Автор примера</div><div class="author-card__position">Редактор</div></a></div>'
        source='<html><body><div itemprop="articleBody"><p>Вступление.</p>'+card+'Продолжение.<p>Вывод.</p></div></body></html>'
        out,_=html_article_editorial_candidate(source,'https://selectel.ru/blog/example/')
        for value in ('Вступление.','Продолжение.','Вывод.'):self.assertIn(value,out.raw)
        self.assertNotIn('Автор примера',out.raw);self.assertNotIn('Редактор',out.raw)
        old,_=html_article_structure_candidate(source,'https://selectel.ru/blog/example/')
        self.assertIn('Автор примера',old.raw)
        for variant in (card.replace('</a></div>','</a><p>Содержательная оговорка.</p></div>'),card.replace('/blog/author/example/','https://elsewhere.example/blog/author/example/'),card.replace('author-card__name','example-name')):
            with self.subTest(variant=variant):
                out,_=html_article_editorial_candidate('<div itemprop="articleBody">'+variant+'</div>','https://selectel.ru/blog/example/')
                self.assertIn('Автор примера',out.raw)

    def test_netology_author_panel_keeps_mixed_content_and_other_domains(self):
        panel='<div class="ntlgy-author"><figure class="ntlgy-author-portrait"><img src="portrait.jpg"></figure><p><strong>Автор примера</strong></p><p>Редактор</p></div>'
        out,_=html_article_editorial_candidate('<div class="entry-content"><p>Начало.</p>'+panel+'Продолжение.</div>','https://netology.ru/blog/example')
        self.assertNotIn('Автор примера',out.raw);self.assertIn('Продолжение.',out.raw)
        for variant,url in ((panel.replace('</div>','<p>Авторское объяснение.</p></div>'),'https://netology.ru/blog/example'),(panel,'https://example.org/post'),(panel.replace('ntlgy-author-portrait','example-portrait'),'https://netology.ru/blog/example')):
            out,_=html_article_editorial_candidate('<div class="entry-content">'+variant+'</div>',url)
            self.assertIn('Автор примера',out.raw)

    def test_netology_course_and_related_links_keep_explanations_and_quoted_examples(self):
        course='<p>Программа обучения: «<a href="/programs/example">Курс примера</a>»</p>'
        related='<p>Читать ещё: «<a href="/blog/another">Другая статья</a>»</p>'
        source='<div class="entry-content"><p>Основной текст.</p>'+course+related+'<p>Концовка.</p></div>'
        out,_=html_article_editorial_candidate(source,'https://netology.ru/blog/example')
        self.assertNotIn('Курс примера',out.raw);self.assertNotIn('Другая статья',out.raw)
        self.assertIn('Концовка.',out.raw)
        variants=(course.replace('</p>',' доступна при выполнении условий.</p>'),course.replace('/programs/example','https://elsewhere.example/programs/example'),'<blockquote>'+course+'</blockquote>')
        for variant in variants:
            out,_=html_article_editorial_candidate('<div class="entry-content">'+variant+'</div>','https://netology.ru/blog/example')
            self.assertIn('Курс примера',out.raw)

    def test_selectel_logo_labels_are_preserved_as_a_list_without_changing_v5(self):
        table='<table><tbody><tr><th>Студия Альфа</th><th>Команда <a>Бета</a></th></tr><tr><th><img src="a.png"></th><th><noscript><img src="b.png"></noscript><img src="b.png"></th></tr></tbody></table>'
        source='<div itemprop="articleBody"><p>Наши клиенты.</p>'+table+'После списка.</div>'
        out,meta=html_article_editorial_candidate(source,'https://selectel.ru/blog/example')
        self.assertIn('- Студия Альфа\n- Команда Бета',out.raw);self.assertIn('После списка.',out.raw)
        self.assertEqual(meta['preserved_label_tables'],1)
        old,_=html_article_structure_candidate(source,'https://selectel.ru/blog/example')
        self.assertNotIn('Студия Альфа',old.raw)
        for variant,url in ((table.replace('<img src="a.png">','10 единиц'),'https://selectel.ru/blog/example'),(table.replace('<th>Студия','<th colspan="2">Студия'),'https://selectel.ru/blog/example'),(table.replace('</tbody>','<tr><td>Другие данные</td></tr></tbody>'),'https://selectel.ru/blog/example'),(table,'https://example.org/post')):
            out,meta=html_article_editorial_candidate('<div itemprop="articleBody">'+variant+'</div>',url)
            self.assertNotIn('Студия Альфа',out.raw);self.assertNotIn('preserved_label_tables',meta)


if __name__=='__main__':unittest.main()
