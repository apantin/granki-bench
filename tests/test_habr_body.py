"""Все строки/адреса в примерах синтетические; копий статей здесь нет."""
import unittest
from lxml import html
from bench.cleaning import html_article_body_candidate,html_article_code_tables_candidate,HTML_BODY_VERSION,VERSION
from bench.code_tables import code_grid
from bench.habr_body import repair


class GroupedCodeTableTest(unittest.TestCase):
    def table(self):
        return '<table><tr><th colspan="2">Первый вариант</th></tr><tr><td><pre>run()</pre></td><td>Пояснение <pre>other()</pre></td></tr><tr><th colspan="2">Второй вариант</th></tr><tr><td><pre>next()</pre></td><td>Текст | значение</td></tr></table>'

    def test_sections_preserve_order_cells_and_real_code_count(self):
        node=html.fromstring(self.table());before=html.tostring(node)
        self.assertIsNone(code_grid(node))
        self.assertEqual(code_grid(node,allow_group_headers=True),('Первый вариант\n| [КОД] | Пояснение [КОД] |\n\nВторой вариант\n| [КОД] | Текст \\| значение |',3))
        self.assertEqual(html.tostring(node),before)

    def test_no_arbitrary_merged_cells_layout_empty_sections_or_lost_text(self):
        source=self.table()
        variants=[source.replace('<td>','<td colspan="2">',1),source.replace('<td>','<td rowspan="2">',1),
                  source.replace('colspan="2">Второй','colspan="3">Второй'),source.replace('Первый вариант',''),
                  source.replace('<tr><td>','Лишняя проза<tr><td>',1),source.replace('</td>','</td>Хвост',1),
                  source.replace('Первый вариант','<pre>header()</pre>'),
                  source.replace('colspan="2"','colspan="٢"'),source.replace('colspan="2"','colspan="'+'9'*5000+'"'),
                  source.replace('<table>','<table onclick="run()">'),source.replace('<td>','<td itemprop="author">',1),
                  source.replace('</table>','<tr><th colspan="2">Пустая секция</th></tr></table>')]
        for value in variants:
            with self.subTest(value=value):self.assertIsNone(code_grid(html.fromstring(value),allow_group_headers=True))


class HabrBodyTest(unittest.TestCase):
    def source(self,body):return '<html><body><h1>Учебная статья</h1><div id="post-content-body">'+body+'</div></body></html>'

    def extract(self,body,host='habr.com'):
        return html_article_body_candidate(self.source(body),'https://'+host+'/example/')

    def formula(self,alt='$x_1 = y^2$'):
        return '<math><img src="https://habrastorage.org/getpro/habr/formulas/example.svg" data-tex="display" alt="'+alt+'"></math>'

    def test_literal_formula_alt_and_surrounding_prose_survive_without_second_markup_parse(self):
        value,meta=self.extract('<p>До '+self.formula('$x &lt; y$')+' после.</p><p>'+self.formula()+'</p>')
        self.assertIn('До $x < y$ после.',value.raw);self.assertIn('$x_1 = y^2$',value.raw)
        self.assertEqual(meta['preserved_formula_alts'],2);self.assertEqual(meta['unresolved_formula_images'],0)
        self.assertEqual(value.code_blocks,0);self.assertEqual(meta['clean_version'],HTML_BODY_VERSION);self.assertEqual(VERSION,'clean-v3')

    def test_unrecognized_formula_boundaries_are_flagged_and_ordinary_image_alt_is_not_prose(self):
        source=self.formula()
        variants=[source.replace('habrastorage.org','example.org'),source.replace('data-tex="display"',''),
                  source.replace('alt="$x_1 = y^2$"','alt=""'),source.replace('<math>','<math>Проза '),
                  source.replace('<img ','<img onload="run()" '),source.replace('</math>','<img alt="другая"></math>'),
                  '<blockquote>'+source+'</blockquote>']
        for value in variants:
            with self.subTest(value=value):
                clean,meta=self.extract(value);self.assertEqual(meta['preserved_formula_alts'],0);self.assertEqual(meta['unresolved_formula_images'],1)
        clean,meta=self.extract('<img alt="Подпись иллюстрации" src="https://example.org/a.svg">')
        self.assertNotIn('Подпись иллюстрации',clean.raw);self.assertEqual(meta['unresolved_formula_images'],0)

    def test_embedded_tweet_requires_its_widget_role_and_direct_status_credit(self):
        tweet='<blockquote class="twitter-tweet"><p>Синтетическая цитата.</p>— Автор <a href="https://twitter.com/example/status/123">Дата</a></blockquote>'
        clean,meta=self.extract('<p>До.</p>'+tweet+'Хвост.<p>После.</p>')
        self.assertNotIn('Синтетическая цитата',clean.raw);self.assertIn('Хвост.',clean.raw);self.assertIn('После.',clean.raw)
        self.assertEqual(meta['removed_embedded_tweets'],1)
        for value in [tweet.replace('twitter-tweet','own-note'),tweet.replace('/status/123','/profile'),tweet.replace('twitter.com','example.org'),tweet.replace('</blockquote>','<p>Продолжение автора.</p></blockquote>')]:
            with self.subTest(value=value):
                clean,meta=self.extract(value);self.assertEqual(meta['removed_embedded_tweets'],0);self.assertIn('Синтетическая цитата',clean.raw)

    def test_only_isolated_direct_code_lines_are_masked(self):
        clean,meta=self.extract('До.<br>\n<code>run()</code><br>После.<p>Переменная <code>value</code> важна.</p>')
        self.assertEqual(meta['masked_standalone_code'],1);self.assertEqual(clean.code_blocks,1)
        self.assertNotIn('run()',clean.raw);self.assertIn('Переменная value важна.',clean.raw);self.assertIn('После.',clean.raw)
        multiline,meta=self.extract('<br><code>first();<br>second();</code><br>Пояснение.')
        self.assertEqual(meta['masked_standalone_code'],1);self.assertEqual(multiline.code_blocks,1)
        self.assertNotIn('second()',multiline.raw);self.assertIn('Пояснение.',multiline.raw)
        for value in ['До.<br>Описание <code>value</code><br>После.','<p><code>value</code> — переменная.</p>','<br><code>value</code> — пояснение.<br>']:
            with self.subTest(value=value):self.assertEqual(self.extract(value)[1]['masked_standalone_code'],0)

    def json_spoiler(self,label='Пример JSON',value='[{«value»: 2}]'):
        return '<div class="spoiler"><b class="spoiler_title">'+label+'</b><div class="spoiler_text">'+value+'</div></div>'

    def test_explicit_json_spoiler_and_valid_json_mask_as_one_block(self):
        clean,meta=self.extract('<p>До.</p>'+self.json_spoiler()+'После.')
        self.assertEqual(clean.code_blocks,1);self.assertEqual(meta['masked_json_spoilers'],1);self.assertEqual(meta['removed_code_labels'],1)
        self.assertNotIn('Пример JSON',clean.raw);self.assertNotIn('value',clean.raw);self.assertIn('После.',clean.raw)
        for value in [self.json_spoiler('Авторский пример'),self.json_spoiler(value='Это обычная проза.'),self.json_spoiler(value='[{«value»: 2}] Продолжение.'),self.json_spoiler().replace('</b>','</b>Проза между блоками.')]:
            with self.subTest(value=value):self.assertEqual(self.extract(value)[1]['masked_json_spoilers'],0)

    def test_grouped_table_integrates_with_renderer_metadata_and_count(self):
        clean,meta=self.extract(GroupedCodeTableTest().table()+'Хвост.')
        self.assertIn('Первый вариант',clean.raw);self.assertIn('Текст \\| значение',clean.raw);self.assertIn('Хвост.',clean.raw)
        self.assertEqual(clean.code_blocks,3);self.assertEqual(meta['preserved_data_tables'],1);self.assertEqual(meta['unresolved_data_tables'],0)
        old,old_meta=html_article_code_tables_candidate(self.source(GroupedCodeTableTest().table()),'https://habr.com/example/')
        self.assertNotIn('Первый вариант',old.raw);self.assertEqual(old.code_blocks,0);self.assertEqual(old_meta['unresolved_data_tables'],1)

    def social(self):return '<p><em>P.S. Мой канал </em><a href="https://t.me/example"><em>Учебный</em></a><em>. Рад новым подписчикам.</em></p>'

    def test_terminal_social_postscript_requires_emphasis_social_links_and_subscription(self):
        clean,meta=self.extract('<p>Итог автора.</p>'+self.social())
        self.assertIn('Итог автора.',clean.raw);self.assertNotIn('подписчикам',clean.raw);self.assertEqual(meta['removed_social_ctas'],1)
        for value in [self.social()+'<p>Содержательное продолжение.</p>',self.social().replace('t.me','example.org'),self.social().replace('<em>','<span>').replace('</em>','</span>'),self.social().replace('Рад новым подписчикам.','Обсуждаю работу с подписчиками.'),self.social().replace('/example','/example/123')]:
            with self.subTest(value=value):self.assertEqual(self.extract(value)[1]['removed_social_ctas'],0)

    def bare_social(self):return '<u>Важно!</u> Все обновления доступны в телеграм-канале <b><a href="https://t.me/example">Учебный</a></b>. Подписывайтесь, чтобы получать заметки :)<br>\n<br>\n'

    def test_bare_social_ending_removes_only_the_confirmed_suffix(self):
        clean,meta=self.extract('Основная мысль.<br><br>'+self.bare_social())
        self.assertIn('Основная мысль.',clean.raw);self.assertNotIn('Важно!',clean.raw);self.assertEqual(meta['removed_social_ctas'],1)
        continued,meta=self.extract('Проза.<br><br>'+self.bare_social()+'<div>Библиография и продолжение.</div>')
        self.assertEqual(meta['removed_social_ctas'],1);self.assertIn('Библиография и продолжение.',continued.raw)
        variants=[self.bare_social().replace('Все обновления','Практические рекомендации'),self.bare_social().replace('Подписывайтесь','Обсудим пример'),self.bare_social().replace('t.me','example.org'),'<blockquote><br>'+self.bare_social()+'</blockquote>']
        for value in ['Проза.<br><br>'+v for v in variants]:
            with self.subTest(value=value):self.assertEqual(self.extract(value)[1]['removed_social_ctas'],0)

    def test_book_invitation_and_source_credit_need_exact_terminal_roles(self):
        book='<br>С полной версией книги вы можете ознакомиться перейдя по ссылке: <i><a href="https://example.org/book">Учебная книга</a></i>'
        clean,meta=self.extract('Авторская проза.'+book)
        self.assertIn('Авторская проза.',clean.raw);self.assertNotIn('Учебная книга',clean.raw);self.assertEqual(meta['removed_book_ctas'],1)
        self.assertEqual(self.extract(book+'<p>Продолжение.</p>')[1]['removed_book_ctas'],0)
        self.assertEqual(self.extract(book.replace('С полной версией книги вы можете ознакомиться перейдя по ссылке:','В книге рассматривается материал:'))[1]['removed_book_ctas'],0)
        clean,meta=self.extract('Проза.<br><br><a href="https://example.org/source">источник</a>')
        self.assertNotIn('источник',clean.raw);self.assertEqual(meta['removed_terminal_source_credits'],1)
        self.assertEqual(self.extract('<a href="https://example.org/source">источник</a><p>Проза.</p>')[1]['removed_terminal_source_credits'],0)

    def test_other_domains_own_callouts_and_input_dom_are_preserved(self):
        root=html.fromstring('<div>'+self.formula()+self.social()+'</div>');before=html.tostring(root)
        self.assertTrue(all(v==0 for v in repair(root,'example.org').values()));self.assertEqual(html.tostring(root),before)
        clean,meta=self.extract('<blockquote><p>Собственная врезка.</p></blockquote><p>Проза.</p>')
        self.assertIn('Собственная врезка.',clean.raw);self.assertEqual(meta['preserved_unattributed_quotes'],1)


if __name__=='__main__':unittest.main()
