import unittest
from bench.provenance import rsdn_primary_header,rsdn_profile_constraints,rsdn_translation_marker

def page(label='Автор:',value='<a href="/account/info/1">Первый Автор</a>',translation=''):
    return '<html><body><h5><span class="title">'+label+'</span><span class="value">'+value+'</span>'+translation+'</h5><div class="MESS">Текст статьи.</div></body></html>'

class ProvenanceTest(unittest.TestCase):
    def test_translation_without_author_is_a_marker_without_author_admission(self):
        for value in ['Переводчик', '<a href="/account/info/1">Первый</a><br><a href="/account/info/2">Второй</a>']:
            source=page(label='Перевод:',value=value)
            self.assertEqual(rsdn_translation_marker(source,'https://rsdn.org/article'),'explicit-translation')
            self.assertEqual(rsdn_primary_header(source,'https://rsdn.org/article')['translation_status'],'unknown-primary-header')
            self.assertEqual(rsdn_primary_header(source,'https://rsdn.org/article')['authors'],[])
            self.assertEqual(rsdn_profile_constraints(source,'https://rsdn.org/article'),[])

    def test_unknown_source_editor_and_empty_translation_stay_unknown(self):
        for source in [page(label='Источник:'),page(label='Материал предоставил:'),page(label='Редактор:'),
                       page(label='Перевод:',value=' '),page(label='Перевод:').replace('class="value"','class="other"'),
                       page(label='Перевод:').replace('<span class="value">','<br><span class="value">'), '']:
            self.assertEqual(rsdn_translation_marker(source,'https://rsdn.org/article'),'unknown-primary-header')

    def test_translation_only_duplicate_or_active_header_stays_unknown(self):
        source=page(label='Перевод:')
        for content in [source.replace('</h5>','</h5><h5><span class="title">Источник:</span><span class="value">Журнал</span></h5>'),
                        source.replace('</h5>','<span class="title">Перевод:</span><span class="value">Другой</span></h5>'),
                        page(label='Перевод:',value='<script>Имя</script>'),
                        page(label='Перевод:',value='<template>Имя</template>')]:
            self.assertEqual(rsdn_translation_marker(content,'https://rsdn.org/article'),'unknown-primary-header')

    def test_translation_only_nested_quote_and_other_host_are_not_primary(self):
        fragment='<h5><span class="title">Перевод:</span><span class="value">Переводчик</span></h5>'
        for content in ['<body><blockquote>'+fragment+'</blockquote></body>',
                        '<body><article>'+fragment+'</article></body>',
                        '<body><p>Перевод: Переводчик</p></body>']:
            self.assertEqual(rsdn_translation_marker(content,'https://rsdn.org/article'),'unknown-primary-header')
        self.assertEqual(rsdn_translation_marker(page(label='Перевод:'),'https://other.example/article'),'not-applicable')

    def test_ambiguous_author_is_not_bypassed_by_translation_extension(self):
        source=page(translation='<span class="title">Авторы:</span><span class="value">Другой</span><span class="title">Перевод:</span><span class="value">Переводчик</span>')
        self.assertEqual(rsdn_translation_marker(source,'https://rsdn.org/article'),'unknown-primary-header')

    def test_existing_classified_statuses_are_preserved(self):
        for source in [page(),page(translation='<span class="title">Перевод:</span><span class="value">Переводчик</span>'),page(value='Автор<br>Компания')]:
            self.assertEqual(rsdn_translation_marker(source,'https://rsdn.org/article'),rsdn_primary_header(source,'https://rsdn.org/article')['translation_status'])

    def test_profile_aliases_share_constraint_without_replacing_name(self):
        for href in ['/account/info/1','https://rsdn.ru/Users/Profile.aspx?uid=001','//www.rsdn.org/account/info/01']:
            source=page(value='<a href="'+href+'">Другой вариант имени</a>')
            self.assertEqual(rsdn_profile_constraints(source,'https://rsdn.org/article/example'),['rsdn-profile:1'])
            self.assertEqual(rsdn_primary_header(source,'https://rsdn.org/article/example')['authors'],['другой вариант имени'])

    def test_additional_credit_stays_ambiguous_and_still_constrained(self):
        for credit in ['Компания','По материалам другого автора','<a href="/account/info/2">Другой Автор</a>']:
            source=page(value='<a href="/account/info/1">Первый Автор</a><br>'+credit)
            self.assertEqual(rsdn_primary_header(source,'https://rsdn.org/article')['authors'],[])
            expected=['rsdn-profile:1','rsdn-profile:2'] if '/account/info/2' in credit else ['rsdn-profile:1']
            self.assertEqual(rsdn_profile_constraints(source,'https://rsdn.org/article'),expected)

    def test_profile_links_outside_author_field_are_not_constraints(self):
        credit='<br><span class="title">Перевод:</span><span class="value"><a href="/account/info/2">Переводчик</a></span>'
        source=page(value='Первый Автор',translation=credit)
        source=source.replace('</body>','<p><a href="/account/info/1">Чужая ссылка</a></p></body>')
        self.assertEqual(rsdn_profile_constraints(source,'https://rsdn.org/article'),[])
        fragment=page().split('<body>')[1].split('</body>')[0]
        self.assertEqual(rsdn_profile_constraints('<body><blockquote>'+fragment+'</blockquote></body>','https://rsdn.org/article'),[])

    def test_invalid_profile_links_are_not_repaired_or_guessed(self):
        for href in ['https://other.example/account/info/1','https://rsdn.org.other.example/account/info/1',
                     'http:///www.rsdn.ru/Users/Profile.aspx?uid=1','https://user'+'@'+'rsdn.org/account/info/1',
                     'https://rsdn.org:8080/account/info/1','/account/info/0','/account/info/name',
                     '/Users/Profile.aspx?uid=1&amp;uid=2','/Users/Profile.aspx?uid=1&amp;uid=','/Users/Profile.aspx?uid=','javascript:/account/info/1',
                     '/account/info/ 1']:
            with self.subTest(href=href):
                self.assertEqual(rsdn_profile_constraints(page(value='<a href="'+href+'">Автор</a>'),'https://rsdn.org/article'),[])

    def test_multiple_primary_headers_do_not_supply_constraints(self):
        source=page().replace('</h5>','</h5><h5><span class="title">Автор:</span><span class="value">Ещё Автор</span></h5>')
        self.assertEqual(rsdn_profile_constraints(source,'https://rsdn.org/article'),[])

    def test_original_and_translator_are_separate_roles(self):
        credit='<br><span class="title">Перевод:</span><span class="value">Другой Человек</span>'
        result=rsdn_primary_header(page(translation=credit),'https://rsdn.org/article')
        self.assertEqual(result['translation_status'],'explicit-translation')
        self.assertEqual(result['authors'],['первый автор'])
        result=rsdn_primary_header(page(translation=credit.replace('Перевод:','Источник:')),'https://rsdn.org/article')
        self.assertEqual(result['translation_status'],'no-explicit-translation-in-header')

    def test_explicit_coauthors_and_ambiguous_organization(self):
        value='<a href="/account/info/1">Первый Автор</a><br><a href="/account/info/2">Второй Автор</a>'
        result=rsdn_primary_header(page(label='Авторы:',value=value),'https://rsdn.org/article')
        self.assertEqual(result['authors'],['первый автор','второй автор'])
        self.assertEqual(result['author_status'],'explicit-coauthors')
        for value in [value+'Компания',value.replace('<br>',' и '),'<a href="/account/info/1">Первый Автор</a><br>Компания']:
            result=rsdn_primary_header(page(label='Авторы:',value=value),'https://rsdn.org/article')
            self.assertEqual(result['authors'],[])

    def test_body_quote_and_duplicate_header_are_not_primary_proof(self):
        fragment='<h5><span class="title">Автор:</span><span class="value">Кто-то</span></h5>'
        for source in ['<html><body><blockquote>'+fragment+'</blockquote></body></html>',page().replace('</h5>','</h5>'+fragment),page(value='<script>Имя</script>'),'']:
            self.assertEqual(rsdn_primary_header(source,'https://rsdn.org/article')['translation_status'],'unknown-primary-header')
        self.assertEqual(rsdn_primary_header(page(),'https://example.org/article')['author_status'],'not-applicable')
