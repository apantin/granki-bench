import unittest
from unittest.mock import patch
from bench.cleaning import CleanText
from bench.liveinternet_provenance import liveinternet_source_marker


class LiveInternetProvenanceTest(unittest.TestCase):
    url='https://www.liveinternet.ru/users/example/post42/'

    def page(self,main,comments='',extra=''):
        return ('<html><body><div id="post42" class="CONBL"><h1 class="ZAG">Название</h1>'
                '<span class="GL_MAR5B"><a href="/journal_post.php?fjid=1&amp;fpid=42&amp;action=q_add">+ в цитатник</a></span>'
                '<div class="MESS">'+main+'</div></div>'+comments+extra+'</body></html>')

    def quote(self,account='other',prefix='',suffix='',credit=None,original=None):
        credit=credit if credit is not None else '<b>Цитата сообщения <a href="https://www.liveinternet.ru/users/'+account+'/profile">Пример имени</a></b>'
        original=original if original is not None else '<a href="https://www.liveinternet.ru/users/'+account+'/post41/">Прочитать целиком</a>'
        uid='1' if account.casefold()=='example' else '2'
        toolbar='<a href="/journal_post.php?fjid='+uid+'&amp;fpid=41&amp;action=q_add">В свой цитатник</a>'
        return prefix+'<div class="MESS QUOT_T"><div class="QUOT_B">'+credit+original+toolbar+'<p>Текст процитированной записи.</p></div></div>'+suffix

    def classify(self,main,raw='Текст процитированной записи.',comments='',**kw):
        return liveinternet_source_marker(self.page(main,comments),self.url,extracted_raw=raw,**kw)

    def test_complete_other_account_quote_has_both_credit_and_original(self):
        value=self.classify(self.quote())
        self.assertEqual(value,dict(status='explicit-reprint',role='whole-quoted-post-of-other-publisher-id'))
        self.assertNotIn('authors',value);self.assertNotIn('url',value)
        value=self.classify(self.quote(prefix='<script>tracking()</script>'))
        self.assertEqual(value['status'],'explicit-reprint')

    def test_self_quote_is_separate_and_not_proved_original(self):
        value=self.classify(self.quote('example'))
        self.assertEqual(value['status'],'self-quoted-post');self.assertIn('not-proven',value['role'])
        self.assertEqual(self.classify(self.quote('EXAMPLE'))['status'],'self-quoted-post')

    def test_alias_paths_require_agreeing_numeric_publisher_evidence(self):
        own_alias=self.quote('other').replace('fjid=2','fjid=1')
        self.assertEqual(self.classify(own_alias)['status'],'self-quoted-post')
        for source in [self.quote().replace('fjid=2','unrelated=2'),self.quote().replace('fpid=41','fpid=99'),
                       self.quote().replace('fjid=2','fjid=0'),self.quote().replace('fjid=2','fjid=2&amp;fjid=3')]:
            self.assertEqual(self.classify(source)['status'],'unresolved')
        conflict=self.quote('example').replace('fjid=1','fjid=2')
        self.assertEqual(self.classify(conflict)['status'],'unresolved')

    def test_community_publisher_is_separate_from_credited_person(self):
        source=self.quote(original='<a href="/community/example_group/post41/">Прочитать целиком</a>')
        self.assertEqual(self.classify(source)['status'],'explicit-reprint')
        own_credit=self.quote('example',original='<a href="/community/example_group/post41/">Прочитать целиком</a>').replace('fjid=1','fjid=2')
        self.assertEqual(self.classify(own_credit)['status'],'unresolved')
        numeric_alias=self.quote(original='<a href="/users/2/post41/">Прочитать целиком</a>')
        self.assertEqual(self.classify(numeric_alias)['status'],'explicit-reprint')

    def test_own_intro_or_conclusion_prevents_whole_reprint_label(self):
        for source in [self.quote(prefix='<p>Авторская оговорка.</p>'),self.quote(suffix='Собственный вывод.')]:
            value=self.classify(source)
            self.assertEqual(value['status'],'unresolved');self.assertEqual(value['role'],'mixed-primary-and-quoted-post')

    def test_missing_mixed_duplicate_and_foreign_credit_stay_unresolved(self):
        for source in [self.quote(credit=''),self.quote(original=''),self.quote(credit='<b>Цитата сообщения <a href="https://example.org/person">Автор</a></b>'),
                       self.quote(credit='<b>Цитата сообщения <a href="/users/other/profile">Автор</a> со своими замечаниями</b>'),
                       self.quote(original='<a href="/users/different/post41/">Прочитать целиком</a>'),
                       self.quote(original='<a href="/users/other/post41/">Прочитать целиком</a><a href="/users/other/post40/">Прочитать целиком</a>')]:
            with self.subTest(source=source):self.assertEqual(self.classify(source)['status'],'unresolved')

    def test_primary_and_comment_identity_is_not_a_comment_only_extraction(self):
        raw='Основной авторский текст.';comment='<div class="COMR"><p>'+raw+'</p></div>'
        value=self.classify('<p>'+raw+'</p>',raw,comment)
        self.assertEqual(value['status'],'no-explicit-source-marker');self.assertIn('not-proven',value['role'])

    def test_entire_extracted_sequence_in_comment_only_is_positive(self):
        raw='Первое предложение. Второе предложение.'
        comment='<div class="COMR"><b>Комментатор</b><p>Первое предложение.</p><p>Второе предложение.</p></div>'
        value=self.classify('<p>Собственный короткий пост.</p>',raw,comment)
        self.assertEqual(value['status'],'extracted-comment');self.assertEqual(value['matching_comments'],1)

    def test_whitespace_punctuation_case_and_nfc_do_not_change_source_location(self):
        raw='Ёжик смотрит: "два слова". Конец.'
        comment='<div class="COMR"><p>Е\u0308ЖИК смотрит — «два слова»...</p><p>Конец!</p></div>'
        self.assertEqual(self.classify('<p>Иная проза.</p>',raw,comment)['status'],'extracted-comment')

    def test_partial_match_substring_and_words_out_of_order_are_not_positive(self):
        raw='Важный факт и точный вывод.'
        for text in ['Важный факт.','Важный факт и точный выводный.','точный вывод и Важный факт']:
            value=self.classify('<p>Иная проза.</p>',raw,'<div class="COMR">'+text+'</div>')
            self.assertEqual(value['status'],'unresolved')

    def test_inline_word_fragments_and_block_boundaries_stay_primary(self):
        raw='Автомобиль и велосипед Новая строка'
        main='<p>Авто<b>мобиль</b> и велосипед</p><p>Новая строка</p>'
        value=self.classify(main,raw,'<div class="COMR">'+raw+'</div>')
        self.assertEqual(value['status'],'no-explicit-source-marker')
        value=self.classify('<p>Основная проза.</p>','Название Основная проза.')
        self.assertEqual(value['status'],'no-explicit-source-marker')

    def test_hidden_form_script_and_ordinary_div_do_not_count_as_comment(self):
        for comment in ['<div class="COMR"><script>Искомый текст</script></div>','<div class="COMR"><textarea>Искомый текст</textarea></div>','<div class="OTHER">Искомый текст</div>']:
            self.assertEqual(self.classify('<p>Иная проза.</p>','Искомый текст',comment)['status'],'unresolved')
        value=self.classify('<div class="COMR">Искомый текст</div>','Искомый текст')
        self.assertEqual(value['status'],'no-explicit-source-marker')

    def test_placeholder_needs_review_and_unknown_template_does_not_guess(self):
        self.assertEqual(self.classify('<p>Текст.</p>','Текст [КОД]','<div class="COMR">Текст [КОД]</div>')['status'],'unresolved')
        source=self.page('<p>Основной текст.</p>','<div class="COMR">Текст комментария.</div>').replace('id="post42"','id="post43"')
        self.assertEqual(liveinternet_source_marker(source,self.url,extracted_raw='Текст комментария.')['status'],'unresolved')
        self.assertEqual(self.classify('<div class="MESS">Неизвестное вложение.</div>')['status'],'unresolved')
        for source in ['',b'\x00','<html></html>']:
            self.assertEqual(liveinternet_source_marker(source,self.url)['status'],'unresolved')
        self.assertEqual(liveinternet_source_marker('', 'https://[')['status'],'unresolved')

    def test_old_extractor_is_used_when_result_not_supplied_and_not_for_other_host(self):
        source=self.page('<p>Основной текст.</p>','<div class="COMR">Чужая проза.</div>')
        with patch('bench.cleaning.html_article',return_value=(CleanText('Чужая проза.','Чужая проза.'),{})) as extract:
            self.assertEqual(liveinternet_source_marker(source,self.url)['status'],'extracted-comment')
            self.assertEqual(extract.call_count,1)
            self.assertEqual(liveinternet_source_marker(source,'https://example.org/post')['status'],'not-applicable')
            self.assertEqual(extract.call_count,1)

    def test_comment_only_error_is_not_masked_by_self_quoted_post(self):
        value=self.classify(self.quote('example'),'Комментарий вместо поста.','<div class="COMR">Комментарий вместо поста.</div>')
        self.assertEqual(value['status'],'extracted-comment')


if __name__=='__main__':unittest.main()
