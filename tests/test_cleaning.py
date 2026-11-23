import unittest
import importlib.util
from bench.cleaning import markdown, typography, words


class CleaningTest(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('lxml'),'Не установлены зависимости HTML')
    def test_rsdn_candidate_uses_field_boundaries(self):
        from lxml import html
        from bench.cleaning import rsdn_author_header_candidate
        source='<html><body><h5><span class="title">Автор: </span><span class="value"><a>Иван Примеров</a></span><br><span class="title">Источник: </span><span class="value">Журнал</span></h5></body></html>'
        self.assertEqual(rsdn_author_header_candidate(html.fromstring(source)),'Иван Примеров')
        source='<html><body><h5><span class="title">Авторы: </span><span class="value"><b>Анна Примерова, Борис Тестов</b></span><span class="title">Опубликовано: </span><span class="value">2007</span></h5></body></html>'
        self.assertEqual(rsdn_author_header_candidate(html.fromstring(source)),'Анна Примерова, Борис Тестов')

    @unittest.skipUnless(importlib.util.find_spec('lxml'),'Не установлены зависимости HTML')
    def test_rsdn_candidate_refuses_missing_or_ambiguous_boundaries(self):
        from lxml import html
        from bench.cleaning import rsdn_author_header_candidate
        for source in ('<body><p>Автор: Автор Без Завершения</p></body>',
                       '<body><span class="title">Автор: </span><span class="value">Анна Примерова<br>Организация</span></body>',
                       '<body><span class="title">Автор: </span><span class="value">Анна Примерова</span><span class="title">Автор: </span><span class="value">Борис Тестов</span></body>'):
            self.assertIsNone(rsdn_author_header_candidate(html.fromstring(source)))

    @unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости сбора данных')
    def test_inline_candidate_preserves_words_order_and_blocks(self):
        from bench.cleaning import html_article_inline_candidate,HTML_INLINE_VERSION,VERSION
        intro='На встрече выступят <strong>Анна</strong>, <em><a href="https://example.org/boris">Борис</a></em> и <span>Вера</span>. '
        body='Специалисты обсудят методы проверки русского текста и разберут примеры из практики. '*20
        source='<html><body><article><h2>Встреча <span>специалистов</span></h2><p>'+intro+body+'</p><ul><li>Первый <strong>пункт</strong> списка.</li><li>Второй пункт.</li></ul></article></body></html>'
        result,meta=html_article_inline_candidate(source)
        self.assertEqual(VERSION,'clean-v3')
        self.assertEqual(meta['clean_version'],HTML_INLINE_VERSION)
        self.assertIn('На встрече выступят Анна, Борис и Вера.',result.raw)
        self.assertIn('## Встреча специалистов',result.raw)
        self.assertIn('- Первый пункт списка.',result.raw)
        self.assertNotIn('https://example.org',result.raw)

    @unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости сбора данных')
    def test_inline_candidate_keeps_removal_policy(self):
        from bench.cleaning import html_article_inline_candidate
        source='<html><body><article><p>'+('Проверяем порядок слов в основном тексте. '*30)+'</p><blockquote>Чужая цитата</blockquote><figure><figcaption>Подпись картинки</figcaption></figure><pre>secret_code()</pre></article></body></html>'
        result,_=html_article_inline_candidate(source)
        self.assertNotIn('Чужая цитата',result.raw)
        self.assertNotIn('Подпись картинки',result.raw)
        self.assertNotIn('secret_code',result.raw)
        self.assertIn('[КОД]',result.raw)
    @unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости сбора данных')
    def test_utf8_with_late_charset(self):
        from bench.cleaning import html_article
        body='Русский текст сохраняется без искажения кодировки. '*30
        source=('<html><head>'+(' '*6000)+'<meta charset="utf-8"></head><body><article><p>'+body+'</p></article></body></html>').encode()
        result,_=html_article(source)
        self.assertIn('Русский текст',result.norm)
        self.assertNotIn('Р\u0093',result.norm)

    @unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости сбора данных')
    def test_comment_inside_heading(self):
        from bench.cleaning import html_article
        source='<html><body><article><h1>Заголовок<!-- маркер --><span> текста</span></h1><p>'+('Русское предложение для проверки извлечения. '*30)+'</p></article></body></html>'
        result,_=html_article(source)
        self.assertIn('Заголовок текста',result.norm)
        result,_=html_article('<!-- внешний комментарий -->'+source)
        self.assertIn('Русское предложение',result.norm)

    def test_structure_and_raw_typography(self):
        source = '# Заголовок\n\n"Текст" - это **пример**. Ёж.\n\n* Один\n* Два\n\n> Чужая цитата\n\n```python\nx=1\n```\n'
        out = markdown(source)
        self.assertIn('"Текст" -', out.raw)
        self.assertIn('«Текст» —', out.norm)
        self.assertIn('Ёж', out.norm)
        self.assertIn('# Заголовок', out.raw)
        self.assertIn('- Один', out.raw)
        self.assertIn('- Один', out.norm)
        self.assertNotIn('Чужая', out.raw)
        self.assertNotIn('x=1', out.raw)
        self.assertIn('[КОД]', out.raw)
        self.assertEqual(out.code_blocks, 1)

    def test_idempotent_and_no_word_hyphen_rewrite(self):
        source = 'Из-за этого — «пример».\n\n- Список\n'
        out = markdown(source)
        self.assertEqual(markdown(out.norm).norm, out.norm)
        self.assertIn('Из-за', out.norm)
        self.assertEqual(len(words('Из-за 12,5 слов')), 3)


if __name__ == '__main__':
    unittest.main()
