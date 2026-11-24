import importlib.util
import unittest
from bench.cleaning import html_article_callouts_candidate,html_article_pre_tables_candidate,HTML_CALLOUT_VERSION,VERSION


@unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости HTML')
class RSDNCalloutsTest(unittest.TestCase):
    URL='https://rsdn.org/article/example.xml'

    def page(self,body):
        return '<html><body><h1>Учебная статья</h1><h5><span class="title">Автор:</span><span class="value">Синтетический Автор</span></h5>'+body+'</body></html>'

    def extract(self,body):return html_article_callouts_candidate(self.page(body),self.URL)

    def callout(self,role='note',content='Пояснение автора.',label=False):
        header='<strong>'+{'note':'ПРИМЕЧАНИЕ','tip':'СОВЕТ','warning':'ПРЕДУПРЕЖДЕНИЕ'}[role]+'</strong><br>' if label else ''
        return '<table class="'+role+'"><tr><td>'+header+content+'</td></tr></table>'

    def test_labelled_and_unlabelled_callouts_inside_lists_preserve_order_and_code(self):
        for role in ('note','tip','warning'):
            for label in (True,False):
                with self.subTest(role=role,label=label):
                    note=self.callout(role,'<p>Пояснение автора.</p><ul><li>Условие.</li></ul><pre>sample()</pre>',label)
                    out,meta=self.extract('<p>Начало.</p><ul><li>Пункт.'+note+'Хвост пункта.</li></ul><p>Конец.</p>')
                    positions=[out.raw.index(s) for s in ('Начало.','Пункт.','Пояснение автора.','Условие.','[КОД]','Хвост пункта.','Конец.')]
                    self.assertEqual(positions,sorted(positions));self.assertNotIn('sample()',out.raw)
                    self.assertIn('\n\n  Пояснение автора.\n',out.raw)
                    self.assertIn('\n\n  Пояснение автора.\n',out.norm)
                    self.assertIn('\n\n  Хвост пункта.',out.raw)
                    self.assertEqual(out.code_blocks,1);self.assertEqual(meta['unresolved_rsdn_callouts'],0)
                    self.assertEqual(meta['restored_rsdn_'+{'note':'notes','tip':'tips','warning':'warnings'}[role]],1)
                    old,_=html_article_pre_tables_candidate(self.page('<p>Начало.</p><ul><li>'+note+'</li></ul>'),self.URL)
                    self.assertNotIn('Пояснение автора.',old.raw)

    def test_direct_text_in_cell_is_not_dropped_without_paragraph_tag(self):
        out,meta=self.extract('<p>Введение.</p>'+self.callout('warning','Требуется отдельная настройка.<br>Она выполняется заранее.'))
        self.assertIn('Требуется отдельная настройка.\nОна выполняется заранее.',out.raw)
        self.assertEqual(meta['restored_rsdn_warnings'],1)

    def test_list_continuations_remain_inside_their_item_without_new_bullets(self):
        out,_=self.extract('<p>Введение.</p><ul><li>Первый.<p>Его пояснение.</p><ul><li>Вложенный.<p>Деталь.</p></li></ul>Хвост первого.</li><li>Второй.</li></ul>')
        for text in ('- Первый.','  Его пояснение.','  - Вложенный.','    Деталь.','  Хвост первого.','- Второй.'):
            self.assertIn(text,out.raw)
        self.assertNotIn('- Его пояснение.',out.raw)

    def test_source_indentation_does_not_become_a_list_continuation(self):
        out,_=self.extract('<p>Начало.<br>\n     Продолжение.</p><p>\n   Отдельный абзац.</p>\n<a href="example.zip">Материалы</a>')
        self.assertIn('Начало.\nПродолжение.',out.raw)
        self.assertIn('\n\nОтдельный абзац.',out.raw)
        self.assertNotIn('\n Продолжение.',out.raw)
        self.assertNotIn('\n Материалы',out.raw)

    def test_structured_foreign_credits_and_active_content_are_not_restored(self):
        template=self.callout(content='<p>Неизвестное авторство.</p>')
        variants=[template.replace('class="note"','class="note" cite="https://example.org/source"'),
                  template.replace('<p>','<p itemprop="author">'),
                  template.replace('<p>','<p class="quote__source">'),
                  template.replace('</td>','<cite>Источник</cite></td>'),
                  template.replace('<p>','<p onclick="action()">'),
                  template.replace('</td>','<script>action()</script></td>')]
        for note in variants:
            with self.subTest(note=note):
                out,meta=self.extract('<p>Начало.</p>'+note+'Хвост.<p>Конец.</p>')
                self.assertNotIn('Неизвестное авторство.',out.raw)
                self.assertIn('Хвост.',out.raw);self.assertIn('Конец.',out.raw)
                self.assertEqual(meta['unresolved_rsdn_notes'],1)

    def test_multicell_spans_nested_tables_and_stray_text_remain_unresolved(self):
        note=self.callout(content='Неоднозначное содержимое.')
        variants=[note.replace('</td>','</td><td>Вторая ячейка.'),
                  note.replace('<td>','<td colspan="2">'),
                  note.replace('<td>','<td rowspan="2">'),
                  note.replace('</td>','<table><tr><td>Вложенные данные</td></tr></table></td>'),
                  note.replace('<tr>','Внешний текст<tr>'),
                  note.replace('class="note"','class="note tip"')]
        for variant in variants:
            with self.subTest(variant=variant):
                _,meta=self.extract('<p>Начало.</p>'+variant)
                self.assertEqual(meta['restored_rsdn_notes'],0)
                self.assertGreater(meta['unresolved_rsdn_callouts'],0)

    def test_callout_inside_foreign_or_opaque_parent_is_not_restored(self):
        for before,after in [('<blockquote cite="https://example.org/source">','</blockquote>'),
                             ('<figure>','</figure>'),('<table><tr><td>','</td></tr></table>'),
                             ('<div cite="https://example.org/source">','</div>'),
                             ('<div class="quote__credit">','</div>')]:
            with self.subTest(before=before):
                out,meta=self.extract('<p>Авторская проза.</p>'+before+self.callout(content='Чужая вставка.')+after)
                self.assertNotIn('Чужая вставка.',out.raw);self.assertEqual(meta['restored_rsdn_notes'],0)

    def test_normal_data_table_and_unmarked_program_like_prose_keep_their_roles(self):
        body='<p>Строка print(value) — часть объяснения.</p><table><tr><th>Ключ</th><th>Значение</th></tr><tr><td>А</td><td>10</td></tr></table>'
        out,meta=self.extract(body)
        self.assertIn('print(value)',out.raw);self.assertIn('| А | 10 |',out.raw)
        self.assertEqual(out.code_blocks,0);self.assertEqual(meta['preserved_data_tables'],1)

    def test_unnumbered_picture_caption_and_standalone_number_are_removed(self):
        body='<p>Начало.</p><p><img src="example.png"><br><i style="font-size:x-small">Вид окна</i></p>Хвост.<p><img src="other.png"></p><p>Рисунок 9.</p>Продолжение.'
        out,meta=self.extract(body)
        self.assertNotIn('Вид окна',out.raw);self.assertNotIn('Рисунок 9.',out.raw)
        self.assertIn('Хвост.',out.raw);self.assertIn('Продолжение.',out.raw)
        self.assertEqual(meta['removed_rsdn_captions'],2)

    def test_mixed_picture_paragraph_and_plain_reference_are_preserved(self):
        body='<p><img src="example.png">Авторское пояснение <i style="font-size:x-small">Рисунок 3. Важная часть</i> продолжается.</p><p>Рисунок 4.</p><p><i style="font-size:x-small">Отдельное пояснение без снимка.</i></p>'
        out,meta=self.extract(body)
        for text in ('Авторское пояснение','Рисунок 3. Важная часть','продолжается.','Рисунок 4.','Отдельное пояснение без снимка.'):
            self.assertIn(text,out.raw)
        self.assertEqual(meta['removed_rsdn_captions'],0);self.assertEqual(meta['unresolved_rsdn_caption_blocks'],1)

    def test_table_caption_needs_small_pure_font_and_adjacent_real_table(self):
        table='<table><tr><th>Имя</th><th>Число</th></tr><tr><td>А</td><td>17</td></tr></table>'
        caption='<font style="font-size:x-small;margin-left:1em"><i>Таблица 2. Учебные значения</i></font>'
        out,meta=self.extract('<p>Текст.</p>'+table+caption+'Хвост таблицы.')
        self.assertNotIn('Таблица 2.',out.raw);self.assertIn('| А | 17 |',out.raw);self.assertIn('Хвост таблицы.',out.raw)
        self.assertEqual(meta['removed_rsdn_captions'],1)
        for body in [caption,table+'<p>Пояснение.</p>'+caption,
                     table+caption.replace('<i>','Авторская мысль <i>'),table+caption.replace('font-size:x-small','font-size:large')]:
            with self.subTest(body=body):
                out,meta=self.extract(body);self.assertIn('Таблица 2.',out.raw);self.assertEqual(meta['removed_rsdn_captions'],0)

    def toggle(self):
        return '<a href="#" onclick="return ToggleCode(\'code1\');"><img id="imgcode1" src="icon.png">Открыть листинг</a>'

    def target(self):
        return '<div id="code1"><table class="code"><tr><td><pre>sample()</pre></td></tr></table></div>'

    def test_code_toggle_label_removed_without_losing_code_or_author_resource_link(self):
        out,meta=self.extract('<p>Текст.</p>'+self.toggle()+self.target()+'После кода.<a href="example.zip" class="link-file">Материалы примера</a>')
        self.assertNotIn('Открыть листинг',out.raw);self.assertIn('[КОД]',out.raw)
        self.assertIn('После кода.',out.raw);self.assertIn('Материалы примера',out.raw)
        self.assertEqual(out.code_blocks,1);self.assertEqual(meta['removed_rsdn_code_toggles'],1)

    def test_ambiguous_code_toggle_is_preserved_and_reported(self):
        link=self.toggle();target=self.target()
        variants=[link,link+target+target,link.replace('imgcode1','wrong')+target,
                  link.replace('href="#"','href="example.zip"')+target,
                  link.replace("ToggleCode('code1');","ToggleCode('code1'); other();")+target,
                  '<p>Авторское пояснение '+link+'</p>'+target,
                  link+target.replace('</div>','Авторское пояснение.</div>'),
                  link+target.replace('<table class="code">','<table>')]
        for body in variants:
            with self.subTest(body=body):
                out,meta=self.extract('<p>Текст.</p>'+body)
                self.assertIn('Открыть листинг',out.raw);self.assertEqual(meta['removed_rsdn_code_toggles'],0)
                self.assertEqual(meta['unresolved_rsdn_code_toggles'],1)

    def test_single_item_toc_needs_exact_heading_and_precedes_body_prose(self):
        toc='<div style="margin-left:2em"><a href="#one"><b>Раздел</b></a></div>'
        body='<p>Введение.</p><h2 id="one">Раздел</h2><p>Конец.</p>'
        out,meta=self.extract(toc+body)
        self.assertEqual(meta['removed_rsdn_toc'],1);self.assertEqual(out.raw.count('Раздел'),1)
        old,old_meta=html_article_pre_tables_candidate(self.page(toc+body),self.URL)
        self.assertEqual(old_meta['removed_rsdn_toc'],0);self.assertEqual(old.raw.count('Раздел'),2)
        for variant in [toc.replace('#one','#absent'),toc.replace('<b>Раздел','<b>Другое'),
                        toc.replace('</div>','Авторская мысль.</div>'),'<p>До ссылки.</p>'+toc]:
            with self.subTest(variant=variant):
                _,meta=self.extract(variant+body);self.assertEqual(meta['removed_rsdn_toc'],0)

    def test_other_profiles_keep_v9_text_and_default_version_is_v3(self):
        for source,url in [(self.page('<p>Текст.</p>'+self.callout()),'https://example.org/article'),
                           ('<body><article itemprop="articleBody"><p>Текст.</p>'+self.callout()+'</article></body>',self.URL)]:
            old,_=html_article_pre_tables_candidate(source,url);new,meta=html_article_callouts_candidate(source,url)
            self.assertEqual(old,new);self.assertNotIn('restored_rsdn_notes',meta)
            self.assertEqual(meta['clean_version'],HTML_CALLOUT_VERSION)
        self.assertEqual(VERSION,'clean-v3')


if __name__=='__main__':unittest.main()
