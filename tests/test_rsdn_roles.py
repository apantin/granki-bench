import importlib.util
import unittest
from bench.cleaning import html_article_content_candidate,html_article_roles_candidate,HTML_ROLES_VERSION


@unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости HTML')
class RSDNRolesTest(unittest.TestCase):
    URL='https://rsdn.org/article/example.xml'

    def page(self,body):
        return '<html><body><h1>Пример статьи</h1><h5><span class="title">Автор:</span><span class="value">Синтетический Автор</span></h5>'+body+'</body></html>'

    def extract(self,body):return html_article_roles_candidate(self.page(body),self.URL)

    def legal(self,body='<copyright>Copyright учебного примера.</copyright>'):
        return '<div align="right"><font style="font-family:arial;font-size:9pt"><i><hr>'+body+'</i></font></div>'

    def toolbar(self,extra=''):
        return '<table width="100%" border="0"><tr><td><a href="?print">'+extra+'</a><a href="/forum/example/1">Сообщений 1</a><a href="/Forum/RateList.aspx?mid=1">Оценка 3 [+1/-0]</a> Оценить</td></tr></table>'

    def test_note_restored_with_paragraphs_but_data_and_code_keep_roles(self):
        body='<p>Начало.</p><table class="note"><tr><td><strong>ПРИМЕЧАНИЕ</strong><br><p>Условие автора.</p><p>Второе условие.</p></td></tr></table>Хвост.<table><tr><td>А</td><td>Б</td></tr><tr><td>1</td><td>2</td></tr></table><table class="code"><tr><td><pre>command()</pre></td></tr></table>'
        out,meta=self.extract(body)
        self.assertIn('Условие автора.\n\nВторое условие.',out.raw);self.assertIn('Хвост.',out.raw)
        self.assertIn('| А | Б |\n| 1 | 2 |',out.raw)
        self.assertEqual(out.code_blocks,out.raw.count('[КОД]'));self.assertEqual(out.code_blocks,1)
        self.assertEqual((meta['restored_rsdn_notes'],meta['unresolved_rsdn_notes']),(1,0))
        self.assertEqual((meta['preserved_data_tables'],meta['unresolved_data_tables']),(1,0))
        self.assertEqual(meta['clean_version'],HTML_ROLES_VERSION)
        old,_=html_article_content_candidate(self.page(body),self.URL)
        self.assertNotIn('Условие автора.',old.raw)

    def test_ambiguous_note_is_reported_without_wholesale_table_permission(self):
        for note in ['<table class="note" cite="https://example.org/source"><tr><td><strong>ПРИМЕЧАНИЕ</strong><p>Условие.</p></td></tr></table>',
                     '<table class="note"><tr><td><strong>ПРИМЕЧАНИЕ</strong><p>Условие.</p></td><td>Вторая ячейка.</td></tr></table>',
                     '<table class="note"><tr><td><p>Неизвестная роль.</p></td></tr></table>']:
            with self.subTest(note=note):
                out,meta=self.extract('<p>Начало.</p>'+note+'<p>Продолжение.</p>')
                self.assertEqual((meta['restored_rsdn_notes'],meta['unresolved_rsdn_notes']),(0,1))
                self.assertIn('Продолжение.',out.raw)

    def test_only_edge_toolbar_is_removed_and_not_counted_as_data(self):
        source=self.page('<p>Текст.</p>');source=source.replace('<h1>',self.toolbar()+'<h1>')
        source=source.replace('</body>',self.toolbar()+'</body>')
        out,meta=html_article_roles_candidate(source,self.URL)
        self.assertEqual(meta['removed_rsdn_toolbar_tables'],2)
        self.assertEqual(meta['unresolved_data_tables'],0);self.assertNotIn('Сообщений',out.raw)
        split_rating=source.replace('[+1/-0]','[ <span>+1</span> / <span>-0</span> ]')
        out,meta=html_article_roles_candidate(split_rating,self.URL)
        self.assertEqual(meta['removed_rsdn_toolbar_tables'],2);self.assertEqual(meta['unresolved_data_tables'],0)
        from lxml import html
        from bench.rsdn_roles import repair
        tree=html.fromstring(self.page('<p>Текст.</p>'+self.toolbar('Авторское пояснение.')))
        main=tree.xpath('//body')[0];meta=repair(main)
        self.assertEqual(meta['removed_rsdn_toolbar_tables'],0)
        self.assertIn('Авторское пояснение.',main.text_content())

    def test_toc_requires_only_local_links_matching_real_headings(self):
        toc='<div style="margin-left:2em"><a href="#one"><b>Один</b></a><br><div style="margin-left:2em"></div><a href="#two">Два</a></div>'
        content='<p>Введение.</p><h2>Один<a name="one"></a></h2><p>Первое.</p><h2 id="two">Два</h2><p>Второе.</p>'
        out,meta=self.extract(toc+content)
        self.assertEqual(meta['removed_rsdn_toc'],1);self.assertEqual(out.raw.count('Один'),1)
        for variant in [toc.replace('#two','#absent'),toc.replace('Два</a>','Другой текст</a>'),toc.replace('<br>','<br>Авторский комментарий.')]:
            with self.subTest(variant=variant):
                _,meta=self.extract(variant+content);self.assertEqual(meta['removed_rsdn_toc'],0)
        _,meta=self.extract('<p>До оглавления.</p>'+toc+content);self.assertEqual(meta['removed_rsdn_toc'],0)

    def test_caption_needs_picture_and_small_italic_role_not_an_inline_reference(self):
        body='<p>Ссылка на <i style="font-size:x-small">Рисунок 1. Авторское объяснение</i> важна.</p><p><img src="example.png"><br><i style="font-size:x-small">Рис.2</i></p>Хвост.'
        out,meta=self.extract(body)
        self.assertIn('Рисунок 1. Авторское объяснение',out.raw);self.assertNotIn('Рис.2',out.raw)
        self.assertIn('Хвост.',out.raw);self.assertEqual(meta['removed_rsdn_captions'],1)

    def test_rights_and_trailing_contact_removed_without_losing_series_marker(self):
        body='<p>Текст.</p><p>[Продолжение следует...] Домашняя страничка: https://example.org</p>'+self.legal()
        out,meta=self.extract(body)
        self.assertIn('[Продолжение следует...]',out.raw);self.assertNotIn('Домашняя страничка',out.raw);self.assertNotIn('Copyright',out.raw)
        self.assertEqual((meta['removed_rsdn_legal_footers'],meta['removed_rsdn_contact_lines']),(1,1))
        out,meta=self.extract('<p>Текст.</p>'+self.legal('Любой из материалов, условия учебного примера принадлежат владельцев авторских прав.'))
        self.assertEqual(meta['removed_rsdn_legal_footers'],1)
        old,_=html_article_content_candidate(self.page(body),self.URL);self.assertIn('Copyright',old.raw)

    def test_legal_words_alone_or_mixed_footer_do_not_remove_author_prose(self):
        for body in ['<p>Текст про Copyright и права.</p><div align="right"><p>Авторское объяснение.</p></div>',
                     '<p>Текст.</p>'+self.legal('<p>Авторское объяснение.</p><copyright>Copyright примера.</copyright>'),
                     self.legal()+'<p>Авторское объяснение после цитирования footer.</p>']:
            with self.subTest(body=body):
                out,meta=self.extract(body);self.assertIn('Авторское объяснение',out.raw);self.assertEqual(meta['removed_rsdn_legal_footers'],0)
        out,meta=self.extract('<p>Домашняя страничка: https://example.org</p>')
        self.assertIn('Домашняя страничка:',out.raw);self.assertEqual(meta['removed_rsdn_contact_lines'],0)

    def test_other_domain_or_semantic_article_keeps_v7_bytes(self):
        for source,url in [(self.page('<p>Текст.</p>'+self.legal()),'https://example.org/article'),
                           ('<body><h1>Пример</h1><article itemprop="articleBody"><p>Текст.</p>'+self.legal()+'</article></body>',self.URL)]:
            old,_=html_article_content_candidate(source,url);new,meta=html_article_roles_candidate(source,url)
            self.assertEqual(old,new);self.assertNotIn('restored_rsdn_notes',meta)


if __name__=='__main__':unittest.main()
