"""Смысл формул/границы кода и контроли против удаления собственной прозы."""
import unittest

from bench.candidates.technical_markup import extract, VERSION
from bench.candidates.publication_cleanup import extract as previous
from test_publication_body import xakep


def listing(lines=('echo one', 'echo two')):
    return '<code class="highlight shell"><div class="wrapper">' + ''.join(
        f'<div class="l l{i}"><span class="token">{line}</span></div>'
        for i, line in enumerate(lines, 1)) + '</div></code>'


class TechnicalMarkupTest(unittest.TestCase):
    def convert(self, body):
        return extract(xakep(body), 'https://xakep.ru/post')

    def test_exponents_indices_and_adjacent_text_keep_their_relationship(self):
        clean, meta = self.convert('<p>Шанс 0,2<sup>3</sup> = 8 × 10<sup>−3</sup>.'
                                   ' Вещество H<sub>2</sub>O и x<sup>n+1</sup>.</p>')
        self.assertIn('0,2^(3) = 8 × 10^(−3).', clean.raw)
        self.assertIn('H_(2)O и x^(n+1).', clean.raw)
        self.assertIn('0,2^(3)', clean.norm)
        self.assertEqual(meta['preserved_superscripts'], 3)
        self.assertEqual(meta['preserved_subscripts'], 1)
        self.assertEqual(meta['unresolved_super_subscript_nodes'], 0)

    def test_formula_in_a_data_table_is_not_lost_or_reordered(self):
        clean, meta = self.convert('<table><tr><th>Вещество</th><th>Площадь</th></tr>'
                                   '<tr><td>H<sub>2</sub>O</td><td>м<sup>2</sup></td></tr></table>')
        self.assertIn('| H_(2)O | м^(2) |', clean.raw)
        self.assertEqual(meta['unresolved_data_tables'], 0)

    def test_linked_nested_empty_and_multiline_scripts_require_review(self):
        for fragment in ['<sup><a href="#note">1</a></sup>', '<sup><span>2</span></sup>',
                         '<sup></sup>', '<sub>a\nb</sub>']:
            with self.subTest(fragment=fragment):
                body = '<p>Начало' + fragment + ' конец.</p>'
                clean, meta = self.convert(body)
                old, _ = previous(xakep(body), 'https://xakep.ru/post')
                self.assertEqual(clean, old)
                self.assertEqual(meta['unresolved_super_subscript_nodes'], 1)

    def test_typed_listing_is_one_placeholder_with_surrounding_prose(self):
        clean, meta = self.convert('<p>Начало.</p>' + listing() + 'Продолжение.<p>Конец.</p>')
        self.assertIn('Начало.', clean.raw)
        self.assertIn('Продолжение.', clean.raw)
        self.assertIn('Конец.', clean.raw)
        self.assertNotIn('echo', clean.raw)
        self.assertEqual(clean.raw.count('[КОД]'), 1)
        self.assertEqual(clean.code_blocks, 1)
        self.assertEqual(meta['masked_highlighted_code'], 1)

    def test_one_line_empty_middle_line_and_wbr_remain_code(self):
        for lines in [('echo one',), ('echo one', '', 'echo two'), ('<span>echo</span><wbr> one',)]:
            with self.subTest(lines=lines):
                clean, meta = self.convert(listing(lines))
                self.assertEqual(clean.code_blocks, 1)
                self.assertEqual(meta['masked_highlighted_code'], 1)

    def test_inline_code_and_untyped_commands_in_prose_are_preserved(self):
        body = '<p>Вызови <code>print(x)</code> после проверки.</p><ul><li>Пояснение: echo one</li></ul>'
        clean, meta = self.convert(body)
        old, _ = previous(xakep(body), 'https://xakep.ru/post')
        self.assertEqual(clean, old)
        self.assertEqual(meta['masked_highlighted_code'], 0)

    def test_unknown_block_shapes_preserve_text_and_report_the_problem(self):
        variants = [listing().replace('class="wrapper"', 'class="other"'),
                    listing().replace('class="l l2"', 'class="l l9"'),
                    listing().replace('</code>', '<p>Своя проза.</p></code>'),
                    listing().replace('<span class="token">echo one</span>', '<a href="/">echo one</a>'),
                    '<code>echo one\necho two</code>']
        for fragment in variants:
            with self.subTest(fragment=fragment):
                clean, meta = self.convert(fragment)
                self.assertIn('echo', clean.raw)
                self.assertEqual(meta['masked_highlighted_code'], 0)
                self.assertEqual(meta['unresolved_highlighted_code'], 1)

    def test_existing_pre_quotes_and_sidebars_are_not_double_processed(self):
        body = '<pre><code>' + listing() + '</code></pre>'
        body += '<blockquote>' + listing() + '<sup>2</sup></blockquote>'
        body += '<aside>' + listing() + '<sub>2</sub></aside><p>Своя проза.</p>'
        clean, meta = self.convert(body)
        self.assertEqual(clean.code_blocks, 1)
        self.assertEqual(meta['masked_highlighted_code'], 0)
        self.assertEqual(meta['preserved_superscripts'] + meta['preserved_subscripts'], 0)
        self.assertIn('Своя проза.', clean.raw)

    def test_marked_inline_context_never_erases_its_own_sentence(self):
        clean, meta = self.convert('<p>Пояснение ' + listing() + ' продолжение.</p>')
        self.assertIn('Пояснение', clean.raw)
        self.assertIn('продолжение.', clean.raw)
        self.assertEqual(meta['masked_highlighted_code'], 0)

    def test_general_explicit_article_body_and_unbound_fallback(self):
        clean, meta = extract('<div itemprop="articleBody"><p>x<sup>2</sup></p>' + listing() + '</div>',
                              'https://example.org/post')
        self.assertIn('x^(2)', clean.raw)
        self.assertEqual(clean.code_blocks, 1)
        self.assertEqual(meta['clean_version'], VERSION)
        source = '<html><body><p>Пример x<sup>2</sup> без явного тела.</p></body></html>'
        old, _ = previous(source, 'https://example.org/post')
        unchanged, meta = extract(source, 'https://example.org/post')
        self.assertEqual(unchanged, old)
        self.assertEqual(meta['technical_markup_scope'], 'trafilatura-inline-fallback')
        self.assertEqual(meta['unresolved_technical_markup_scope'], 1)


if __name__ == '__main__':
    unittest.main()
