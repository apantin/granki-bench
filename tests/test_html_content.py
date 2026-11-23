import importlib.util
import unittest
from bench.cleaning import (HTML_CONTENT_VERSION,html_article_content_candidate,
                            html_article_editorial_candidate,html_article_structure_candidate)


@unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости HTML')
class HTMLContentTest(unittest.TestCase):
    @staticmethod
    def page(body):
        return '<html><body><h1>Пример</h1><article itemprop="articleBody"><p>Начало.</p>'+body+'<p>Продолжение.</p></article></body></html>'

    def test_grid_keeps_cells_headers_empty_values_and_literal_pipes(self):
        source=self.page('<table><caption>Сравнение</caption><thead><tr><th><p>Имя</p></th><th>Условия</th></tr></thead><tbody><tr><td>Альфа</td><td>один<br>два | три</td></tr><tr><td>Бета</td><td></td></tr></tbody></table>Хвост таблицы.')
        out,meta=html_article_content_candidate(source,'https://example.org/post')
        self.assertIn('Сравнение\n| Имя | Условия |\n| --- | --- |\n| Альфа | один два \\| три |\n| Бета |  |',out.raw)
        self.assertIn('Хвост таблицы.',out.raw)
        self.assertIn('Продолжение.',out.raw)
        self.assertEqual(meta['clean_version'],HTML_CONTENT_VERSION)
        self.assertEqual((meta['preserved_data_tables'],meta['unresolved_data_tables']),(1,0))
        for extract in (html_article_structure_candidate,html_article_editorial_candidate):
            old,old_meta=extract(source,'https://example.org/post')
            self.assertNotIn('Альфа',old.raw)
            self.assertNotIn('preserved_data_tables',old_meta)

    def test_data_rows_do_not_invent_a_header_from_bold_text(self):
        source=self.page('<table><tr><td><strong>Номер</strong></td><td><span>Количество</span></td></tr><tr><td>7</td><td>12.5</td></tr></table>')
        out,meta=html_article_content_candidate(source,'https://example.org/post')
        self.assertIn('| Номер | Количество |\n| 7 | 12.5 |',out.raw)
        self.assertNotIn('---',out.raw)
        self.assertEqual(meta['preserved_data_tables'],1)

    def test_unsupported_tables_are_explicit_and_code_tables_stay_code(self):
        cases={
            'rowspan':'<tr><td rowspan="2">Сложное</td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'colspan':'<tr><td colspan="2">Сложное</td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'unequal':'<tr><td>А</td><td>Б</td></tr><tr><td>В</td></tr>',
            'nested':'<tr><td><table><tr><td>Вложенное</td></tr></table></td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'image':'<tr><td><img src="logo.png">А</td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'quote':'<tr><td><blockquote>Чужое</blockquote></td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'code':'<tr><td><pre>command()</pre></td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'superscript':'<tr><td>2<sup>3</sup></td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'outside-cells':'Важное пояснение<tr><td>А</td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
            'unsupported-element':'<tr><td><input value="12">А</td><td>Б</td></tr><tr><td>В</td><td>Г</td></tr>',
        }
        for name,body in cases.items():
            with self.subTest(name=name):
                source=self.page('<table>'+body+'</table>')
                out,meta=html_article_content_candidate(source,'https://example.org/post')
                self.assertEqual((meta['preserved_data_tables'],meta['unresolved_data_tables']),(0,1))
                self.assertIn('Продолжение.',out.raw)
        out,meta=html_article_content_candidate(self.page('<table class="code"><tr><td><pre>command()</pre></td></tr></table>'),'https://example.org/post')
        self.assertEqual(out.code_blocks,1)
        self.assertIn('[КОД]',out.raw)
        self.assertEqual((meta['preserved_data_tables'],meta['unresolved_data_tables']),(0,0))

    def test_ad_requires_domain_role_two_local_actions_and_no_extra_content(self):
        widget='<div class="propaganda propaganda--with-footer"><div class="propaganda__footer"><a class="propaganda__link" href="/business">Купить рекламу</a><a class="propaganda__link" href="/plus">Отключить</a></div></div>'
        source=self.page(widget+'Хвост виджета.')
        out,meta=html_article_content_candidate(source,'https://vc.ru/marketing/1')
        self.assertNotIn('Купить рекламу',out.raw)
        self.assertEqual(meta['removed_ad_widgets'],1)
        self.assertIn('Хвост виджета.',out.raw)
        for extract in (html_article_structure_candidate,html_article_editorial_candidate):
            old,_=extract(source,'https://vc.ru/marketing/1')
            self.assertIn('Купить рекламу',old.raw)
        cases=[('https://example.org/post',widget),
               ('https://vc.ru/marketing/1',widget.replace('/business','https://other.example/business')),
               ('https://vc.ru/marketing/1',widget.replace('propaganda--with-footer','author-note').replace('class="propaganda ','class="')),
               ('https://vc.ru/marketing/1',widget.replace('<div class="propaganda__footer">','<p>Авторский совет.</p><div class="propaganda__footer">')),
               ('https://vc.ru/marketing/1',widget.replace('Купить рекламу','Как устроена реклама'))]
        for url,body in cases:
            with self.subTest(url=url,body=body):
                out,meta=html_article_content_candidate(self.page(body),url)
                self.assertEqual(meta['removed_ad_widgets'],0)
                self.assertIn('Отключить',out.raw)


if __name__=='__main__':unittest.main()
