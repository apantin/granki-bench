import importlib.util
import unittest
from bench.cleaning import html_article_structure_candidate,VERSION


@unittest.skipUnless(importlib.util.find_spec('trafilatura'),'Не установлены зависимости HTML')
class HTMLStructureTest(unittest.TestCase):
    def test_direct_div_keeps_intro_inline_words_and_lists(self):
        source='<html><body><nav>Меню</nav><h1>Синтетический заголовок</h1><div id="post-content-body">Вводное предложение.<br><br><b>Основной текст</b> продолжается.<br><br>Это <i>тот же</i> абзац.<ul><li>Первый пункт</li><li>Второй пункт</li></ul></div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://habr.com/ru/post/1/')
        self.assertEqual(VERSION,'clean-v3')
        self.assertIn('# Синтетический заголовок\n\nВводное предложение.',out.raw)
        self.assertIn('Основной текст продолжается.',out.raw)
        self.assertIn('Это тот же абзац.',out.raw)
        self.assertIn('- Первый пункт\n- Второй пункт',out.raw)
        self.assertNotIn('Меню',out.raw)
        self.assertEqual(meta['extraction_method'],'id:post-content-body')

    def test_semantic_body_title_and_removed_blocks_keep_tails(self):
        source='<html><body><h1 itemprop="headline">Название статьи<script>wrong_title()</script></h1><article itemprop="articleBody"><p>Начало.</p><blockquote>Чужая цитата<pre>foreign_code()</pre></blockquote>Продолжение.<pre>secret_code()</pre>После кода.<figure>Подпись рисунка</figure>Конец.</article></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        for value in ('# Название статьи','Начало.','Продолжение.','После кода.','Конец.','[КОД]'):self.assertIn(value,out.raw)
        for value in ('Чужая цитата','secret_code','foreign_code','wrong_title','Подпись рисунка'):self.assertNotIn(value,out.raw)
        self.assertEqual(out.code_blocks,1)

    def test_liveinternet_title_and_music_widget(self):
        source='<html><body><h1>Логотип</h1><h1 class="ZAG">Заголовок записи</h1><h1 class="ZAG"></h1><div class="MESS"><nobr>В колонках играет - <em>Музыка</em></nobr><p>Авторский текст.</p></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://www.liveinternet.ru/users/example/post1/')
        self.assertEqual(out.raw,'# Заголовок записи\n\nАвторский текст.\n')

    def test_editorial_badge_and_nested_lists(self):
        source='<html><body><h1 itemprop="headline">Основной <span>заголовок <a><span class="content-editorial-tick">Статьи редакции</span></a></span></h1><div itemprop="articleBody"><ul><li>Верхний пункт<ul><li>Вложенный пункт</li></ul></li></ul></div></body></html>'
        out,_=html_article_structure_candidate(source,'https://tjournal.ru/tech/1')
        self.assertIn('# Основной заголовок',out.raw)
        self.assertNotIn('Статьи редакции',out.raw)
        self.assertIn('  - Вложенный пункт',out.raw)
        self.assertIn('  - Вложенный пункт',out.norm)

    def test_platform_body_omits_interface_tags_and_keeps_paragraph_tails(self):
        source='<html><body><h1 itemprop="headline">Заголовок <span class="content-editorial-tick">Статьи редакции</span></h1><div class="content content--full"><div class="l-island-a"><p>Абзац статьи.</p></div><div class="l-island-a"><p><a href="/tag/news">#новости</a> <a href="/tag/test">#пример</a></p></div><div class="content-info">Просмотры 100</div></div><div class="comments">Чужой комментарий</div></body></html>'
        out,_=html_article_structure_candidate(source,'https://tjournal.ru/tech/1')
        self.assertEqual(out.raw,'# Заголовок\n\nАбзац статьи.\n')

    def test_direct_body_preserves_breaks_without_source_indentation(self):
        source='<html><body><div itemprop="articleBody">Начало.<br>\n Продолжение.<hr>\n Последний абзац.<table><tr><td>Табличные данные</td></tr></table>После таблицы.</div></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        self.assertIn('Начало.\nПродолжение.',out.raw)
        self.assertIn('Последний абзац.',out.raw)
        self.assertNotIn('Табличные данные',out.raw)
        self.assertIn('После таблицы.',out.raw)

    def test_direct_dom_keeps_literal_angles_and_formula_paragraph(self):
        source='<html><body><article itemprop="articleBody"><p>Если x &lt;1, меняем подход.</p><h2>Следующий раздел</h2><p>Если x &gt;1, продолжаем.</p><p>Параметр &lt;test-value&gt; сохраняется.</p><p>&gt; Доход = результат / затраты</p><p>Литеральная запись **пример** и &amp;lt;.</p></article></body></html>'
        out,_=html_article_structure_candidate(source,'https://example.org/post')
        for value in ('x <1','## Следующий раздел','x >1','<test-value>','> Доход = результат / затраты','**пример**','&lt;'):
            self.assertIn(value,out.raw)
            self.assertIn(value,out.norm)

    def test_fallback_keeps_literal_angles_without_markdown_reinterpretation(self):
        paragraph='Обычный текст с <strong>выделением</strong>, параметром <code>&lt;test-value&gt;</code> и условием x &lt;1. '
        source='<html><body><div><p>'+paragraph*20+'</p><h2>Раздел источника</h2><p>Теперь x &gt;1.</p><p>&gt; Результат = доход / затраты</p></div></body></html>'
        out,meta=html_article_structure_candidate(source,'https://example.org/post')
        self.assertEqual(meta['extraction_method'],'trafilatura-inline-fallback')
        self.assertIn('<test-value>',out.raw)
        self.assertIn('x <1',out.raw)
        # Полнота отбора заголовков fallback проверяется отдельно; здесь
        # проверяем, что постобработка не съедает текст между <1 и >1.
        self.assertIn('x >1',out.raw)
        self.assertIn('> Результат = доход / затраты',out.raw)
        self.assertNotIn('**выделением**',out.raw)
        self.assertNotIn('`<test-value>`',out.raw)


if __name__=='__main__':unittest.main()
