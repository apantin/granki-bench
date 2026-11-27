import unittest
from lxml import html
from bench.cleaning import html_article_liveinternet_candidate,html_article_semantic_blocks_candidate
from bench.html_structure import table_grid
from bench.semantic_blocks import repaired_table


def page(body):return '<html><body><h1>Разбор устройства</h1><article itemprop="articleBody">'+body+'</article></body></html>'


def convert(body):return html_article_semantic_blocks_candidate(page(body),'https://example.org/post')


class SemanticTablesTest(unittest.TestCase):
    def test_nowrap_is_transparent_and_original_tree_is_unchanged(self):
        node=html.fromstring('<table><tr><th>Метод</th><th>Путь</th></tr><tr><td>GET</td><td><nobr>/items/{id}</nobr></td></tr></table>')
        before=html.tostring(node);fixed=repaired_table(node)
        self.assertIsNotNone(fixed);self.assertIn('| GET | /items/{id} |',table_grid(fixed));self.assertEqual(html.tostring(node),before)

    def test_bare_headers_and_explicit_empty_row_markers_keep_cell_binding(self):
        clean,meta=convert('<table><th>Параметр</th><th>Первый</th><th>Второй</th><tr></tr><td>Память</td><td>64</td><td>96</td><tr></tr><td>Потоки</td><td>8</td><td>12</td></table>')
        self.assertIn('| Параметр | Первый | Второй |',clean.raw)
        self.assertIn('| Память | 64 | 96 |',clean.raw);self.assertIn('| Потоки | 8 | 12 |',clean.raw)
        self.assertEqual(meta['unresolved_data_tables'],0);self.assertEqual(meta['repaired_text_tables'],1)

    def test_bare_headers_also_keep_complete_following_rows(self):
        clean,_=convert('<table><th>Тест</th><th>Время</th><tr><td>Первый</td><td>21</td></tr><tr><td>Второй</td><td>34</td></tr></table>')
        self.assertIn('| Первый | 21 |',clean.raw);self.assertIn('| Второй | 34 |',clean.raw)

    def test_grouped_header_expands_only_explicit_column_relationships(self):
        table='<table><tbody><tr><td rowspan="2">Команда</td><td colspan="2">Группа А</td><td colspan="2">Группа Б</td></tr><tr><td>Один</td><td>Пять</td><td>Один</td><td>Пять</td></tr><tr><td>Добавить</td><td>11</td><td>12</td><td>21</td><td>22</td></tr></tbody></table>'
        clean,meta=convert(table)
        self.assertIn('| Команда | Группа А / Один | Группа А / Пять | Группа Б / Один | Группа Б / Пять |',clean.raw)
        self.assertIn('| Добавить | 11 | 12 | 21 | 22 |',clean.raw);self.assertEqual(meta['unresolved_data_tables'],0)

    def test_missing_boundary_ragged_row_or_unbound_text_is_not_guessed(self):
        for value in [
            '<table><td>Один</td><td>Два</td><td>Три</td><td>Четыре</td></table>',
            '<table><th>А</th><th>Б</th><tr></tr><td>1</td></table>',
            '<table>Не потеряй эту прозу<th>А</th><th>Б</th><tr><td>1</td><td>2</td></tr></table>',
            '<table><th>А</th><th>Б</th><tr><td>1</td><td><img src="x.png" alt="Значение"></td></tr></table>']:
            with self.subTest(value=value):
                clean,meta=convert(value);self.assertEqual(meta['unresolved_data_tables'],1);self.assertEqual(meta['repaired_text_tables'],0)

    def test_data_spans_or_incomplete_two_level_headers_stay_unresolved(self):
        values=[
            '<table><tr><td rowspan="2">Тест</td><td colspan="2">А</td></tr><tr><td>1</td></tr><tr><td>x</td><td>2</td><td>3</td></tr></table>',
            '<table><tr><td rowspan="3">Тест</td><td colspan="2">А</td></tr><tr><td>1</td><td>2</td></tr><tr><td>x</td><td>2</td><td>3</td></tr></table>',
            '<table><tr><td rowspan="2">Тест</td><td colspan="2">А</td></tr><tr><td>1</td><td>2</td></tr><tr><td>x</td><td colspan="2">3</td></tr></table>']
        for value in values:
            with self.subTest(value=value):
                _,meta=convert(value);self.assertEqual(meta['unresolved_data_tables'],1)


class ProsePreTest(unittest.TestCase):
    def test_plain_sentence_restores_referent_and_keeps_real_command_masked(self):
        clean,meta=convert('<pre>Закройте доступ к административному разделу.</pre><p>В этом разделе создайте файл настроек.</p><pre>chmod 600 config</pre>')
        self.assertIn('Закройте доступ к административному разделу.',clean.raw)
        self.assertLess(clean.raw.index('Закройте'),clean.raw.index('В этом разделе'))
        self.assertEqual(clean.code_blocks,1);self.assertEqual(clean.raw.count('[КОД]'),1)
        self.assertEqual(meta['preserved_prose_pre'],1);self.assertEqual(meta['prose_pre_review_required'],1)

    def test_code_syntax_and_explicit_code_roles_are_never_prose_promotions(self):
        samples=['<pre>Число = 42</pre>','<pre>print("Важное сообщение.")</pre>','<pre># Важное сообщение.</pre>',
                 '<pre class="language-python">Важное сообщение.</pre>','<pre><code>Важное сообщение.</code></pre>',
                 '<div class="highlight"><pre>Важное сообщение.</pre></div>']
        for value in samples:
            with self.subTest(value=value):
                clean,meta=convert(value);self.assertEqual(clean.code_blocks,1);self.assertEqual(meta['preserved_prose_pre'],0)

    def test_code_role_on_an_outer_wrapper_also_blocks_promotion(self):
        for wrapper in ['class="language-python"','data-language="python"','data-lang="console"','lang="python"']:
            with self.subTest(wrapper=wrapper):
                clean,meta=convert('<div '+wrapper+'><pre>Важное сообщение.</pre></div>')
                self.assertEqual(clean.code_blocks,1);self.assertEqual(meta['preserved_prose_pre'],0)

    def test_quoted_foreign_pre_is_not_restored_as_own_prose(self):
        clean,meta=convert('<blockquote cite="https://example.org/source"><pre>Чужое авторское предложение.</pre></blockquote><p>Свой вывод.</p>')
        self.assertNotIn('Чужое авторское',clean.raw);self.assertEqual(meta['preserved_prose_pre'],0)

    def test_v16_remains_exactly_on_its_old_contract(self):
        value=page('<pre>Закройте доступ к административному разделу.</pre><table><th>А</th><th>Б</th><tr><td>1</td><td>2</td></tr></table>')
        old,meta=html_article_liveinternet_candidate(value,'https://example.org/post')
        self.assertEqual(old.code_blocks,1);self.assertNotIn('Закройте',old.raw);self.assertNotIn('| 1 | 2 |',old.raw)
        self.assertEqual(meta['clean_version'],'clean-v16-liveinternet-candidate');self.assertNotIn('preserved_prose_pre',meta)
        current,new_meta=html_article_semantic_blocks_candidate(value,'https://example.org/post')
        self.assertEqual(new_meta['clean_version'],'clean-v17-semantic-blocks-candidate');self.assertEqual(current.code_blocks,0)


if __name__=='__main__':unittest.main()
