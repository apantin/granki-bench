import unittest
from bench.pre_tables import parse,table_like
from bench.cleaning import html_article_pre_tables_candidate,html_article_roles_candidate,HTML_PRE_TABLE_VERSION


class PreTablesTest(unittest.TestCase):
    TABLE='Name     Version  Meaning\n-------  -------  -------\nAlpha    2.3      First release with a long description\n-        4.5      Missing name'

    def page(self,body):return '<html><body><h1>Пример</h1><article itemprop="articleBody"><p>Начало.</p>'+body+'<p>Продолжение.</p></article></body></html>'

    def test_header_alignment_long_last_cell_and_missing_value_preserved(self):
        self.assertEqual(parse(self.TABLE),[['Name','Version','Meaning'],['Alpha','2.3','First release with a long description'],['-','4.5','Missing name']])
        self.assertEqual(parse('Key  Value\n---  -----\nA    one\nB'),[['Key','Value'],['A','one'],['B','']])
        self.assertEqual(parse('\n\tKey  Value\n\t---  -----\n\tA    one\n'),[['Key','Value'],['A','one']])

    def test_programs_comments_single_separator_and_crossed_columns_not_guessed(self):
        for value in ['var x = 1;\nreturn x;', '// Key  Value\n// ---  -----\n// A    one',
                      'Title\n-----\nvalue', 'Key  Value\n---  -----\nABCD one',
                      'Title\nKey  Value\n---  -----\nA    one', 'Key  Value\n---  -----\n\nA    one',
                      'Key  Value\n---  -----\nA    one\n---  -----']:
            with self.subTest(value=value):self.assertIsNone(parse(value))
        self.assertTrue(table_like('Title\nKey  Value\n---  -----\nA    one'))
        self.assertFalse(table_like('// Key  Value\n// ---  -----\n// A    one'))

    def test_code_wrapper_becomes_data_with_tails_and_adjusted_code_count(self):
        source=self.page('<table class="code"><tr><td><pre>'+self.TABLE+'</pre></td></tr></table>Хвост.<pre>command()</pre>После кода.')
        new,meta=html_article_pre_tables_candidate(source,'https://example.org/post')
        old,_=html_article_roles_candidate(source,'https://example.org/post')
        self.assertIn('| Name | Version | Meaning |\n| --- | --- | --- |',new.raw)
        self.assertIn('| Alpha | 2.3 | First release with a long description |',new.raw)
        self.assertIn('| - | 4.5 | Missing name |',new.raw)
        for text in ['Хвост.','После кода.','Продолжение.']:self.assertIn(text,new.raw)
        self.assertEqual(new.code_blocks,new.raw.count('[КОД]'));self.assertEqual(new.code_blocks,1)
        self.assertEqual(old.code_blocks,2);self.assertNotIn('First release',old.raw)
        self.assertEqual((meta['preserved_pre_tables'],meta['unresolved_pre_tables']),(1,0))
        self.assertEqual((meta['preserved_data_tables'],meta['unresolved_data_tables']),(1,0))
        self.assertEqual(meta['clean_version'],HTML_PRE_TABLE_VERSION)

    def test_literal_characters_are_data_not_html_or_new_columns(self):
        source=self.page('<pre>Key   Value\n----  -----\na|b   &lt;x&gt;\\path\nв     слово</pre>')
        out,_=html_article_pre_tables_candidate(source,'https://example.org/post')
        self.assertIn('| a\\|b | <x>\\\\path |',out.raw);self.assertIn('| в | слово |',out.raw)

    def test_nested_tables_highlighted_or_mixed_pre_stay_unresolved(self):
        for body in ['<table><tr><td><pre>'+self.TABLE+'</pre></td></tr></table>',
                     '<table class="code"><tr><td><pre>'+self.TABLE+'</pre><pre>command()</pre></td></tr></table>',
                     '<pre>'+self.TABLE.replace('Alpha','<b>Alpha</b>')+'</pre>']:
            with self.subTest(body=body):
                _,meta=html_article_pre_tables_candidate(self.page(body),'https://example.org/post')
                self.assertEqual((meta['preserved_pre_tables'],meta['unresolved_pre_tables']),(0,1))

    def test_excluded_quote_does_not_reappear_as_data(self):
        source=self.page('<blockquote cite="https://example.org/source"><pre>'+self.TABLE+'</pre></blockquote>Хвост цитаты.')
        out,meta=html_article_pre_tables_candidate(source,'https://example.org/post')
        self.assertNotIn('First release',out.raw);self.assertIn('Хвост цитаты.',out.raw)
        self.assertEqual((meta['preserved_pre_tables'],meta['unresolved_pre_tables']),(0,0))

    def test_data_inside_an_opaque_code_or_main_table_is_not_claimed_restored(self):
        from lxml import html
        from bench.pre_tables import restore
        for tag in ['pre','table']:
            main=html.Element(tag);node=html.Element('pre');node.text=self.TABLE;main.append(node)
            with self.subTest(tag=tag):
                self.assertEqual(restore(main),dict(preserved_pre_tables=0,unresolved_pre_tables=0))
                self.assertEqual(node.tag,'pre')
        main=html.Element('div');outer=html.Element('pre');inner=html.Element('pre');inner.text=self.TABLE;outer.append(inner);main.append(outer)
        self.assertEqual(restore(main)['preserved_pre_tables'],0)


if __name__=='__main__':unittest.main()
