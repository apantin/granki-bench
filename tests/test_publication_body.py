import unittest
from lxml import html

from bench.cleaning import (html_article_publication_body_candidate as convert,
                            html_article_semantic_blocks_candidate as previous, words)
from bench.publication_body import bind, issue_widget


def xakep(body, head=None):
    head = head or '<div class="bdaia-post-style7-head"><header class="bdaia-post-header"><h1 class="post-title entry-title">Основной заголовок</h1></header></div>'
    return '<html><body><div id="warp">' + head + '<div id="content"><article id="post-7" class="hentry post-7"><div class="bdaia-post-content">' + body + '</div></article></div></div></body></html>'


def zavtra(body, lead='Подзаголовок'):
    return '<html><body><div id="content_blogs"><div class="contentblock"><div id="article__header"><div class="header__title"><h1>Основной заголовок</h1></div><div class="header__anonse">' + lead + '</div></div><div class="article__content">' + body + '</div></div></div></body></html>'


def issue(extra='', link='/issues/xa/7'):
    return '<div id="current_issue_box"><small>Другие статьи в выпуске:</small><a class="cover" href="' + link + '"><img></a><a href="' + link + '"><h3>Другой выпуск</h3></a><ul><li><a href="/about">Подписка</a></li></ul>' + extra + '</div>'


def photo(caption, image='<img>'):
    return '<div class="onephoto" contenteditable="false" data-pg="image-role">' + image + '<div class="onepzedit"><p class="pgzeditchange"><span type-bloc="onep">' + caption + '</span></p>Хвост редактора.</div></div>'


class PublicationBodyTest(unittest.TestCase):
    def test_full_xakep_body_and_primary_header_instead_of_inner_heading(self):
        source = xakep('<p>Введение.</p><article class="xmd"><h1>Внутренний раздел</h1><p>Середина.</p></article><p>Конец.</p>')
        clean, meta = convert(source, 'https://xakep.ru/example')
        self.assertTrue(clean.raw.startswith('# Основной заголовок\n\n'))
        self.assertLess(clean.raw.index('Введение'), clean.raw.index('Середина'))
        self.assertLess(clean.raw.index('Середина'), clean.raw.index('Конец'))
        self.assertIn('# Внутренний раздел', clean.raw)
        self.assertEqual(meta['extraction_method'], 'profile:xakep-primary-publication')
        self.assertEqual(meta['bound_primary_publications'], 1)

    def test_unrelated_host_does_not_bind_site_specific_header(self):
        _, meta = convert(xakep('<p>Своё содержание.</p>'), 'https://example.org/post')
        self.assertEqual(meta['bound_primary_publications'], 0)
        self.assertEqual(meta['unresolved_primary_publications'], 0)

    def test_ambiguous_or_unrelated_primary_roles_never_bind(self):
        source = xakep('<p>Содержание.</p>')
        values = [source.replace('id="content"', 'id="other"'),
                  source.replace('class="hentry post-7"', 'class="hentry post-8"'),
                  source.replace('</body>', '<article class="hentry"></article></body>'),
                  source.replace('<p>Содержание.</p>', '<article class="other"><p>Содержание.</p></article>'),
                  source.replace('</header>', '<h1 class="post-title entry-title">Другой</h1></header>')]
        for value in values:
            with self.subTest(value=value):
                self.assertIsNone(bind(html.fromstring(value), 'xakep.ru'))
                _, meta = convert(value, 'https://xakep.ru/example')
                self.assertEqual(meta['unresolved_primary_publications'], 1)

    def test_access_cut_marker_still_prevents_source_completeness(self):
        _, meta = convert(xakep('<p>Начало.</p><div id="xakepcut" class="xakepcut">Продолжение закрыто</div>'), 'https://xakep.ru/example')
        self.assertEqual(meta['source_incomplete_markers'], ['xakep-access-cut'])

    def test_typed_issue_widget_removed_and_surrounding_text_kept(self):
        clean, meta = convert(xakep('<p>Начало.</p>' + issue() + 'Продолжение.'), 'https://xakep.ru/example')
        self.assertNotIn('Другой выпуск', clean.raw)
        self.assertNotIn('Подписка', clean.raw)
        self.assertIn('Продолжение.', clean.raw)
        self.assertEqual(meta['removed_issue_widgets'], 1)
        self.assertEqual(meta['unresolved_issue_widgets'], 0)

    def test_widget_id_cannot_remove_author_prose_or_an_unknown_route(self):
        for widget in [issue('<p>Собственное пояснение.</p>'), issue(link='/article/other'), issue(link='https://elsewhere.org/issues/xa/7')]:
            with self.subTest(widget=widget):
                clean, meta = convert(xakep(widget), 'https://xakep.ru/example')
                self.assertIn('Другой выпуск', clean.raw)
                self.assertEqual(meta['removed_issue_widgets'], 0)
                self.assertEqual(meta['unresolved_issue_widgets'], 1)

    def test_malformed_widget_link_remains_unresolved(self):
        for link in ['http://[broken/issues/xa/7', 'https://xakep.ru:invalid/issues/xa/7']:
            self.assertFalse(issue_widget(html.fromstring(issue(link=link)), 'xakep.ru'))

    def test_zavtra_own_lead_restored_before_body(self):
        clean, meta = convert(zavtra('<p>Первый абзац.</p>'), 'https://zavtra.ru/blogs/example')
        self.assertIn('# Основной заголовок\n\nПодзаголовок\n\nПервый абзац.', clean.raw)
        self.assertEqual(meta['restored_primary_leads'], 1)

    def test_only_full_first_block_duplicate_is_removed(self):
        clean, meta = convert(zavtra('<p>ПОДЗАГОЛОВОК</p><p>Продолжение.</p>'), 'https://zavtra.ru/blogs/example')
        self.assertEqual(clean.raw.casefold().count('подзаголовок'), 1)
        self.assertEqual(meta['deduplicated_primary_leads'], 1)
        for lead in ['Подзаголовок другой', 'Под заголовок']:
            clean, meta = convert(zavtra('<p>Подзаголовок</p>', lead), 'https://zavtra.ru/blogs/example')
            self.assertIn(lead, clean.raw)
            self.assertEqual(meta['deduplicated_primary_leads'], 0)

    def test_zavtra_unbound_header_cannot_supply_another_articles_lead(self):
        source = zavtra('<p>Тело.</p>').replace('id="article__header"', 'id="another_header"')
        clean, meta = convert(source, 'https://zavtra.ru/blogs/example')
        self.assertEqual(meta['unresolved_primary_publications'], 1)
        self.assertNotIn('Подзаголовок', clean.raw)

    def test_cms_placeholder_requires_exact_photo_editor_structure(self):
        marker = 'двойной клик - редактировать изображение'
        clean, meta = convert(zavtra('<p>Введение.</p>' + photo(marker) + '<p>Конец.</p>'), 'https://zavtra.ru/blogs/example')
        self.assertNotIn(marker, clean.raw)
        self.assertIn('Хвост редактора.', clean.raw)
        self.assertIn('Конец.', clean.raw)
        self.assertEqual(meta['removed_cms_image_placeholders'], 1)
        for body in ['<p>' + marker + '</p>', photo('Подпись автора.'), photo(marker, image='')]:
            clean, meta = convert(zavtra(body), 'https://zavtra.ru/blogs/example')
            self.assertEqual(meta['removed_cms_image_placeholders'], 0)
            self.assertTrue(marker in clean.raw or 'Подпись автора.' in clean.raw)

    def test_quotes_and_explicit_code_keep_existing_roles(self):
        clean, meta = convert(zavtra('<p>Автор вообразил ответ: «Продолжай».</p><pre class="language-python">print(1)</pre>'), 'https://zavtra.ru/blogs/example')
        self.assertIn('«Продолжай»', clean.raw)
        self.assertEqual(clean.code_blocks, 1)
        self.assertIn('[КОД]', clean.raw)

    def test_soft_hyphens_only_in_norm_and_true_hyphens_are_kept(self):
        source = zavtra('<p>Луч\u00adший научно-технический текст.</p>')
        clean, meta = convert(source, 'https://zavtra.ru/blogs/example')
        self.assertIn('Луч\u00adший', clean.raw)
        self.assertIn('Лучший научно-технический', clean.norm)
        self.assertIn('Лучший', words(clean.norm))
        self.assertEqual(meta['normalized_soft_hyphens'], 1)
        old, old_meta = previous(source, 'https://zavtra.ru/blogs/example')
        self.assertIn('Луч\u00adший', old.norm)
        self.assertEqual(old_meta['clean_version'], 'clean-v17-semantic-blocks-candidate')
        self.assertNotIn('normalized_soft_hyphens', old_meta)
        self.assertEqual(meta['clean_version'], 'clean-v18-publication-body-candidate')


if __name__ == '__main__':
    unittest.main()
