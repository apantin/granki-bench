import unittest
from unittest.mock import patch
from bench.cleaning import CleanText
from bench.liveinternet_provenance import liveinternet_source_marker
from bench.liveinternet_series_provenance import liveinternet_series_source_marker


class LiveInternetSeriesProvenanceTest(unittest.TestCase):
    url='https://www.liveinternet.ru/users/example/post42/'
    raw='Текст цитируемого поста.'

    def quote(self):
        return ('<div class="MESS QUOT_T"><div class="QUOT_B">'
                '<b>Цитата сообщения <a href="/users/other/profile">Другой</a></b>'
                '<a href="/users/other/post40/">Прочитать целиком</a>'
                '<a href="/journal_post.php?fjid=2&amp;fpid=40&amp;action=q_add">В цитатник</a>'
                '<p>'+self.raw+'</p></div></div>')

    def footer(self):
        return ('<blockquote>\n<b>Серия сообщений "<a href="/users/example/rubric/7/">Название серии</a>":</b><br>'
                'Часть 1 - <a href="https://www.liveinternet.ru/users/example/post41">Первый пост</a><br>'
                'Часть 2 - Название  поста<br>'
                '...<br>Часть 9 - <a href="/users/example/post49/">Другой пост</a><br>\n</blockquote>')

    def page(self,main,comments=''):
        return ('<html><body><div id="post42" class="CONBL"><h1 class="ZAG">Название поста</h1>'
                '<span class="GL_MAR5B"><a href="/journal_post.php?fjid=1&amp;fpid=42&amp;action=q_add">Цитировать</a></span>'
                '<div class="MESS">'+main+'</div></div>'+comments+'</body></html>')

    def classify(self,footer=None,prefix='',suffix='',quote=None):
        content=self.page(prefix+(self.quote() if quote is None else quote)+(self.footer() if footer is None else footer)+suffix)
        return liveinternet_series_source_marker(content,self.url,extracted_raw=self.raw)

    def test_whole_quote_plus_exact_series_navigation(self):
        value=self.classify()
        self.assertEqual(value['status'],'explicit-reprint')
        self.assertIn('known-series-navigation-only',value['role'])
        self.assertEqual(set(value),{'status','role'})
        self.assertEqual(liveinternet_source_marker(self.page(self.quote()+self.footer()),self.url,extracted_raw=self.raw),
                         dict(status='unresolved',role='mixed-primary-and-quoted-post'))

    def test_own_intro_conclusion_and_footer_tail_stay_mixed(self):
        for prefix,suffix in [('<p>Моя позиция.</p>',''),('','Мой вывод.'),('','<p>Мой вывод.</p>')]:
            with self.subTest(prefix=prefix,suffix=suffix):
                self.assertEqual(self.classify(prefix=prefix,suffix=suffix)['status'],'unresolved')
        self.assertEqual(self.classify(footer=self.footer().replace('</blockquote>','Мой вывод.</blockquote>'))['status'],'unresolved')

    def test_prose_added_to_a_link_or_heading_is_not_navigation(self):
        for footer in [self.footer().replace('Первый пост</a>','Первый пост</a> Я не согласен.'),
                       self.footer().replace('Серия сообщений "','Мои замечания. Серия сообщений "'),
                       self.footer().replace('</b>',' Мои замечания.</b>'),
                       self.footer().replace('Часть 1 -','Мои замечания. Часть 1 -'),
                       self.footer().replace('<a href="/users/example/post49/">','<em>Мои замечания.</em><a href="/users/example/post49/">')]:
            with self.subTest(footer=footer):self.assertEqual(self.classify(footer=footer)['status'],'unresolved')

    def test_current_title_requires_literal_nfc_and_whitespace_only_match(self):
        for title in ['Название другого поста','название поста','Название поста!','Название поста. Мой вывод.']:
            with self.subTest(title=title):self.assertEqual(self.classify(footer=self.footer().replace('Название  поста',title))['status'],'unresolved')
        footer=self.footer().replace('Название  поста','Е\u0308жик')
        page=self.page(self.quote()+footer).replace('<h1 class="ZAG">Название поста</h1>','<h1 class="ZAG">Ёжик</h1>')
        self.assertEqual(liveinternet_series_source_marker(page,self.url,extracted_raw=self.raw)['status'],'explicit-reprint')

    def test_all_links_must_be_same_owner_known_paths_without_extra_data(self):
        for old,new in [('/rubric/7/','/post7/'),('/users/example/rubric/','/users/other/rubric/'),
                        ('/post41','/profile'),('/post41','/post41?comment=1'),('/post41','/post41#x'),
                        ('https://www.liveinternet.ru','https://foreign.example'),
                        ('https://www.liveinternet.ru','https://user@www.liveinternet.ru'),
                        ('/users/example/post49/','/users/other/post49/'),
                        ('/post49/','/post0/'),('/post49/','/post42/'),('/post49/','/post41/')]:
            with self.subTest(old=old,new=new):self.assertEqual(self.classify(footer=self.footer().replace(old,new))['status'],'unresolved')

    def test_part_numbers_are_increasing_and_current_occurs_once(self):
        for footer in [self.footer().replace('Часть 9 -','Часть 1 -'),self.footer().replace('Часть 1 -','Часть 3 -'),
                       self.footer().replace('Часть 2 - Название  поста<br>',''),
                       self.footer().replace('...<br>','Часть 3 - Название поста<br>'),
                       self.footer().replace('Часть 2 -','Часть 0 -'),self.footer().replace('Часть 2 -','Часть 02 -')]:
            with self.subTest(footer=footer):self.assertEqual(self.classify(footer=footer)['status'],'unresolved')

    def test_ellipsis_is_one_internal_line_and_not_free_prose(self):
        for footer in [self.footer().replace('...<br>','...<br>...<br>'),
                       self.footer().replace('...<br>','Мой вывод<br>'),
                       self.footer().replace('...<br>','').replace('</b><br>','</b><br>...<br>'),
                       self.footer().replace('...<br>','').replace('</blockquote>','...<br></blockquote>')]:
            with self.subTest(footer=footer):self.assertEqual(self.classify(footer=footer)['status'],'unresolved')

    def test_nested_extra_and_invisible_elements_inside_footer_are_not_supported(self):
        for footer in [self.footer().replace('Первый пост','<span>Первый пост</span>'),
                       self.footer().replace('<blockquote>','<blockquote class="own">'),
                       self.footer().replace('<br>','<br class="x">',1),
                       self.footer().replace('</blockquote>','<script>own()</script></blockquote>'),
                       self.footer().replace('</blockquote>','<textarea>Моя проза.</textarea></blockquote>'),
                       self.footer().replace('href="/users/example/post49/"','href="/users/example/post49/" title="Моя проза"')]:
            with self.subTest(footer=footer):self.assertEqual(self.classify(footer=footer)['status'],'unresolved')

    def test_footer_before_quote_nested_footer_or_two_footers_are_not_supported(self):
        self.assertEqual(self.classify(footer='',prefix=self.footer())['status'],'unresolved')
        self.assertEqual(self.classify(footer='<section>'+self.footer()+'</section>')['status'],'unresolved')
        self.assertEqual(self.classify(footer=self.footer()+self.footer())['status'],'unresolved')
        self.assertEqual(self.classify(quote='<section>'+self.quote()+'</section>')['status'],'unresolved')

    def test_numeric_identity_and_credit_guards_are_still_required(self):
        for quote in [self.quote().replace('fjid=2','fjid=1'),self.quote().replace('fjid=2','unknown=2'),
                      self.quote().replace('fpid=40','fpid=99'),self.quote().replace('fjid=2','fjid=0'),
                      self.quote().replace('fjid=2','fjid=2&amp;fjid=3'),
                      self.quote().replace('/users/other/profile','/users/different/profile'),
                      self.quote().replace('/users/other/profile','/users/example/profile'),
                      self.quote().replace('Прочитать целиком','Читать')]:
            with self.subTest(quote=quote):self.assertEqual(self.classify(quote=quote)['status'],'unresolved')

    def test_existing_positive_and_other_host_results_are_exactly_preserved(self):
        for main in [self.quote(),'<p>Авторская проза.</p>','']:
            for url in [self.url,'https://foreign.example/post42/']:
                content=self.page(main)
                self.assertEqual(liveinternet_series_source_marker(content,url,extracted_raw=self.raw),
                                 liveinternet_source_marker(content,url,extracted_raw=self.raw))

    def test_comment_only_status_is_preserved_with_series_footer(self):
        raw='Только комментарий.'
        content=self.page(self.quote()+self.footer(),'<div class="COMR">'+raw+'</div>')
        result=liveinternet_series_source_marker(content,self.url,extracted_raw=raw)
        self.assertEqual(result,liveinternet_source_marker(content,self.url,extracted_raw=raw))
        self.assertEqual(result['status'],'extracted-comment')

    def test_no_second_extraction_and_invisible_siblings_are_preserved(self):
        content=self.page('<!-- CMS -->'+self.quote()+'<script>tracking()</script><p> </p>'+self.footer())
        with patch('bench.cleaning.html_article',return_value=(CleanText(self.raw,self.raw),{})) as extract:
            self.assertEqual(liveinternet_series_source_marker(content,self.url)['status'],'explicit-reprint')
            extract.assert_called_once_with(content,self.url)
        with patch('bench.cleaning.html_article') as extract:
            self.assertEqual(liveinternet_series_source_marker(content,self.url,extracted_raw=self.raw)['status'],'explicit-reprint')
            extract.assert_not_called()


if __name__=='__main__':unittest.main()
