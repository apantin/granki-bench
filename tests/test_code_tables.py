import importlib.util
import unittest
from bench.code_tables import code_grid
from bench.cleaning import html_article_callouts_candidate,html_article_code_tables_candidate,HTML_CODE_TABLE_VERSION,VERSION
try:
    from lxml import html
except ImportError:
    html=None


@unittest.skipIf(html is None,'Не установлены зависимости HTML')
class CodeGridTest(unittest.TestCase):
    def table(self,cell='<pre>run()</pre>'):
        return '<table><tr><th>Вариант А</th><th>Вариант Б</th></tr><tr><td>'+cell+'</td><td>Обычное пояснение.</td></tr></table>'

    def wrapper(self):
        return '<div id="sample"><table class="code"><tbody><tr><td><pre><span class="keyword">call</span>()</pre></td></tr></tbody></table></div>'

    def test_cell_order_prose_and_count_with_explicit_pre_and_pure_code_wrapper(self):
        node=html.fromstring(self.table('<p>До кода.</p>'+self.wrapper()+'<p>После кода.</p><pre>next()</pre>'))
        before=html.tostring(node)
        self.assertEqual(code_grid(node),('| Вариант А | Вариант Б |\n| --- | --- |\n| До кода. [КОД] После кода. [КОД] | Обычное пояснение. |',2))
        self.assertEqual(html.tostring(node),before)

    def test_code_punctuation_is_masked_but_prose_pipes_are_escaped(self):
        value=code_grid(html.fromstring(self.table('Проза | продолжение <pre>x &lt; y | z</pre>')))
        self.assertEqual(value[1],1);self.assertIn('Проза \\| продолжение [КОД]',value[0]);self.assertNotIn('x &lt;',value[0])

    def test_literal_marker_is_not_counted_as_an_additional_code_block(self):
        value=code_grid(html.fromstring(self.table('Литерал [КОД] <pre>run()</pre>')))
        self.assertEqual(value[1],1);self.assertEqual(value[0].count('[КОД]'),2)

    def test_layout_tables_spans_empty_blocks_and_stray_text_are_rejected(self):
        table=self.table();wrapper=self.wrapper()
        variants=[table.replace('<td>','<td colspan="2">',1),table.replace('<td>','<td rowspan="2">',1),
                  table.replace('<tr><td>','Между строками<tr><td>'),
                  table.replace('<pre>run()</pre>','<pre> </pre>'),
                  self.table('<div>Проза внутри оболочки.<pre>run()</pre></div>'),
                  self.table(wrapper.replace('class="code"','class="layout"')),
                  self.table(wrapper.replace('</td>','Проза внутри code-таблицы.</td>')),
                  self.table(wrapper.replace('</td>','</td><td>')),
                  self.table(wrapper.replace('<td>','<td colspan="2">'))]
        for source in variants:
            with self.subTest(source=source):self.assertIsNone(code_grid(html.fromstring(source)))

    def test_foreign_credits_active_content_and_opaque_ancestors_are_rejected(self):
        source=self.table()
        variants=[source.replace('<table>','<table cite="https://example.org/quote">',1),
                  source.replace('<td>','<td itemprop="author">',1),
                  source.replace('<td>','<td itemprop="name author">',1),
                  source.replace('<td>','<td class="quote__credit">',1),
                  source.replace('<td>','<td onclick="run()">',1),
                  source.replace('</td>','<script>run()</script></td>'),
                  source.replace('</td>','<blockquote>Чужая проза.</blockquote></td>')]
        for source in variants:
            with self.subTest(source=source):self.assertIsNone(code_grid(html.fromstring(source)))
        for tag,attrs in [('blockquote',''),('figure',''),('table',''),('template',''),('div','cite="https://example.org/quote"')]:
            root=html.fromstring('<'+tag+' '+attrs+'>'+self.table()+'</'+tag+'>')
            table=root.xpath('.//table')[-1]
            with self.subTest(tag=tag,attrs=attrs):self.assertIsNone(code_grid(table))


@unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости HTML')
class CodeTableExtractionTest(unittest.TestCase):
    table=CodeGridTest.table
    wrapper=CodeGridTest.wrapper
    def extract(self,body):
        source='<article itemprop="articleBody"><h1>Учебный текст</h1><p>Введение.</p>'+body+'Хвост таблицы.<p>Заключение.</p></article>'
        return html_article_code_tables_candidate(source,'https://example.org/article'),html_article_callouts_candidate(source,'https://example.org/article')

    def test_new_candidate_preserves_table_and_old_candidate_stays_unchanged(self):
        (new,meta),(old,old_meta)=self.extract(self.table(self.wrapper()))
        self.assertIn('| Вариант А | Вариант Б |',new.raw);self.assertIn('| [КОД] | Обычное пояснение. |',new.raw)
        self.assertEqual(new.code_blocks,1);self.assertEqual(meta['preserved_data_tables'],1);self.assertEqual(meta['unresolved_data_tables'],0)
        self.assertNotIn('Вариант А',old.raw);self.assertEqual(old.code_blocks,0);self.assertEqual(old_meta['unresolved_data_tables'],1)
        self.assertEqual(meta['clean_version'],HTML_CODE_TABLE_VERSION);self.assertEqual(VERSION,'clean-v3')
        self.assertIn('Хвост таблицы.',new.raw);self.assertIn('Заключение.',new.raw)

    def test_rejected_or_foreign_tables_do_not_inflate_code_count(self):
        for body in [self.table().replace('<td>','<td colspan="2">',1),'<blockquote cite="https://example.org/quote">'+self.table()+'</blockquote>',
                     '<table><tr><td>'+self.table()+'</td></tr></table>']:
            with self.subTest(body=body):
                (new,_),_=self.extract(body)
                self.assertEqual(new.code_blocks,0);self.assertNotIn('[КОД]',new.raw);self.assertIn('Хвост таблицы.',new.raw)


if __name__=='__main__':unittest.main()
