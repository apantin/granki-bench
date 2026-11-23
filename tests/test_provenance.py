import unittest
from bench.provenance import rsdn_primary_header

def page(label='Автор:',value='<a href="/account/info/1">Первый Автор</a>',translation=''):
    return '<html><body><h5><span class="title">'+label+'</span><span class="value">'+value+'</span>'+translation+'</h5><div class="MESS">Текст статьи.</div></body></html>'

class ProvenanceTest(unittest.TestCase):
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
