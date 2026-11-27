"""Синтетические положительные/отрицательные контроли издательских ролей."""
import unittest

from bench.candidates.publication_cleanup import extract, VERSION
from bench.cleaning import html_article_publication_body_candidate as previous
from test_publication_body import xakep, zavtra, issue, photo


def series(extra=''):
    return ('<div class="panel default"><div class="empty-ad"></div><ul>'
            '<li><a href="/2020/01/01/first/">Другой материал</a></li>'
            '<li><strong>Основной заголовок</strong></li>'
            '<li><a href="/2020/01/02/second/">Ещё материал</a></li>'
            '</ul><p></p>' + extra + '</div>')


class PublicationCleanupTest(unittest.TestCase):
    def test_whole_lead_can_overlap_start_or_middle_without_losing_body(self):
        for body in ['<p>Первая фраза. Продолжение.</p>',
                     '<p>Вступление.</p><p>В целом первая фраза. Продолжение.</p>']:
            with self.subTest(body=body):
                source = zavtra(body, 'Первая фраза')
                old, _ = previous(source, 'https://zavtra.ru/blogs/example')
                clean, meta = extract(source, 'https://zavtra.ru/blogs/example')
                self.assertEqual(old.raw.casefold().count('первая фраза'), 2)
                self.assertEqual(clean.raw.casefold().count('первая фраза'), 1)
                self.assertIn('Продолжение.', clean.raw)
                self.assertEqual(meta['deduplicated_overlapping_leads'], 1)

    def test_distinct_information_word_boundaries_and_ellipsis_are_preserved(self):
        for lead, body in [('Первая фраза 2', '<p>Первая фраза 3.</p>'),
                           ('Новая статья', '<p>Сверхновая статья.</p>'),
                           ('Первая фраза', '<p>Первая</p><p>фраза.</p>'),
                           ('Первая фраза...', '<p>Первая фраза без пропуска.</p>'),
                           ('Свой анонс', '<blockquote><p>Свой анонс.</p></blockquote>')]:
            with self.subTest(lead=lead, body=body):
                clean, meta = extract(zavtra(body, lead), 'https://zavtra.ru/blogs/example')
                self.assertIn(lead, clean.raw)
                self.assertEqual(meta['deduplicated_overlapping_leads'], 0)

    def test_final_period_and_inline_markup_do_not_duplicate_a_whole_lead(self):
        clean, meta = extract(zavtra('<p>Начало. Полный анонс. Конец.</p>',
                                    '<strong>Полный анонс.</strong>'), 'https://zavtra.ru/blogs/example')
        self.assertEqual(clean.raw.count('Полный анонс'), 1)
        self.assertIn('Начало.', clean.raw)
        self.assertIn('Конец.', clean.raw)
        self.assertEqual(meta['bound_primary_publications'], 1)

    def test_series_has_current_title_and_only_local_article_links(self):
        clean, meta = extract(xakep('<p>Начало.</p>' + series() + 'Продолжение.'), 'https://xakep.ru/post')
        self.assertNotIn('Другой материал', clean.raw)
        self.assertIn('Продолжение.', clean.raw)
        self.assertEqual(meta['removed_publisher_series_panels'], 1)
        self.assertEqual(meta['unresolved_publisher_series_panels'], 0)

    def test_author_recommendations_and_unknown_panel_are_not_erased(self):
        for panel in [series('<p>Собственное пояснение.</p>'),
                      series().replace('Основной заголовок', 'Другая тема'),
                      series().replace('/2020/01/01/first/', 'https://elsewhere.test/2020/01/01/first/'),
                      series().replace('/2020/01/01/first/', '/2020/01/01/first/?mode=other'),
                      series().replace('/2020/01/01/first/', 'http://[broken/article')]:
            with self.subTest(panel=panel):
                clean, meta = extract(xakep(panel), 'https://xakep.ru/post')
                self.assertIn('Другой материал', clean.raw)
                self.assertEqual(meta['removed_publisher_series_panels'], 0)
                self.assertEqual(meta['unresolved_publisher_series_panels'], 1)
        own_list = '<p>Рекомендую прочесть:</p><ul><li><a href="/2020/01/01/first/">Другой материал</a></li></ul>'
        clean, _ = extract(xakep(own_list), 'https://xakep.ru/post')
        self.assertIn('Рекомендую прочесть:', clean.raw)
        self.assertIn('Другой материал', clean.raw)

    def test_current_series_title_can_be_shortened_at_a_word_boundary(self):
        source = xakep(series()).replace('<h1 class="post-title entry-title">Основной заголовок</h1>',
                                        '<h1 class="post-title entry-title">Основной заголовок, продолжение</h1>')
        _, meta = extract(source, 'https://xakep.ru/post')
        self.assertEqual(meta['removed_publisher_series_panels'], 1)

    def test_own_link_free_callout_is_not_unknown_publisher_navigation(self):
        panel = '<div class="panel default"><h4>Достоинства решения</h4><ul><li>Собственный довод.</li><li>Ещё довод.</li></ul></div>'
        clean, meta = extract(xakep(panel), 'https://xakep.ru/post')
        self.assertIn('Собственный довод.', clean.raw)
        self.assertIn('Ещё довод.', clean.raw)
        self.assertEqual(meta['removed_publisher_series_panels'], 0)
        self.assertEqual(meta['unresolved_publisher_series_panels'], 0)

    def test_alternative_issue_label_requires_all_other_widget_guards(self):
        for extra, expected in [('', 1), ('<p>Авторская проза.</p>', 0)]:
            widget = issue(extra).replace('Другие статьи в выпуске:', 'Рекомендуем почитать:')
            clean, meta = extract(xakep(widget + '<p>Конец.</p>'), 'https://xakep.ru/post')
            self.assertEqual(meta['removed_extra_issue_widgets'], expected)
            self.assertIn('Конец.', clean.raw)
            if not expected:
                self.assertIn('Авторская проза.', clean.raw)
                self.assertEqual(meta['unresolved_issue_widgets'], 1)

    def test_image_link_caption_is_removed_but_mixed_prose_and_other_links_remain(self):
        link = '<a href="/wp-content/uploads/example.jpg">Подпись изображения</a>'
        clean, meta = extract(xakep('<p>' + link + '</p>Продолжение.'), 'https://xakep.ru/post')
        self.assertNotIn('Подпись изображения', clean.raw)
        self.assertIn('Продолжение.', clean.raw)
        self.assertEqual(meta['removed_link_image_captions'], 1)
        for body in ['<p>Собственная фраза ' + link + '</p>',
                     '<p>' + link.replace('example.jpg', 'example.pdf') + '</p>',
                     '<p>' + link.replace('/wp-content', 'https://elsewhere.test/wp-content') + '</p>',
                     '<p>' + link.replace('example.jpg', 'example.jpg?download=1') + '</p>']:
            with self.subTest(body=body):
                clean, meta = extract(xakep(body), 'https://xakep.ru/post')
                self.assertIn('Подпись изображения', clean.raw)
                self.assertEqual(meta['removed_link_image_captions'], 0)

    def test_terminal_credit_requires_image_full_name_emphasis_and_no_own_followup(self):
        credit = '<p><strong>Рис. Ивана Петрова</strong></p>'
        picture = '<p><img src="/image.jpg"></p>'
        clean, meta = extract(zavtra(picture + '<p>Авторский конец.</p>' + credit), 'https://zavtra.ru/blogs/example')
        self.assertNotIn('Рис. Ивана Петрова', clean.raw)
        self.assertIn('Авторский конец.', clean.raw)
        self.assertEqual(meta['removed_terminal_illustration_credits'], 1)
        for body in [credit, picture + credit + '<p>Своя последующая проза.</p>',
                     picture + credit.replace('<strong>', '').replace('</strong>', ''),
                     picture + credit.replace('Ивана Петрова', 'это моя тема')]:
            with self.subTest(body=body):
                clean, meta = extract(zavtra(body), 'https://zavtra.ru/blogs/example')
                self.assertIn('Рис.', clean.raw)
                self.assertEqual(meta['removed_terminal_illustration_credits'], 0)

    def test_empty_editor_decoration_can_be_removed_without_losing_tail(self):
        marker = 'двойной клик - редактировать изображение'
        source = zavtra(photo(marker).replace('<p class="pgzeditchange">', '<p class="pgzeditchange"><em> </em>'))
        clean, meta = extract(source, 'https://zavtra.ru/blogs/example')
        self.assertNotIn(marker, clean.raw)
        self.assertIn('Хвост редактора.', clean.raw)
        self.assertEqual(meta['removed_extended_cms_placeholders'], 1)
        # Стандартная прежняя структура по-прежнему обрабатывается самим v18.
        _, meta = extract(zavtra(photo(marker)), 'https://zavtra.ru/blogs/example')
        self.assertEqual(meta['removed_extended_cms_placeholders'], 0)
        self.assertEqual(meta['removed_cms_image_placeholders'], 1)

    def test_editor_id_and_marker_do_not_remove_real_caption_or_unknown_structure(self):
        marker = 'двойной клик - редактировать изображение'
        for body in [photo('Содержательная подпись.'), photo(marker, image=''), '<p>' + marker + '</p>']:
            with self.subTest(body=body):
                clean, meta = extract(zavtra(body), 'https://zavtra.ru/blogs/example')
                self.assertEqual(meta['removed_extended_cms_placeholders'], 0)
                self.assertTrue(marker in clean.raw or 'Содержательная подпись.' in clean.raw)

    def test_unbound_or_other_host_does_not_apply_publisher_rules(self):
        source = xakep(series())
        clean, meta = extract(source, 'https://example.test/post')
        old, _ = previous(source, 'https://example.test/post')
        self.assertEqual(clean, old)
        self.assertIn('Другой материал', clean.raw)
        self.assertEqual(meta['removed_publisher_series_panels'], 0)

    def test_old_candidate_and_own_quotes_code_soft_hyphens_remain_unchanged(self):
        source = zavtra('<p>Своя реплика: «Продолжай». Мяг\u00adкий перенос.</p><pre>print(1)</pre>')
        before = previous(source, 'https://zavtra.ru/blogs/example')
        clean, meta = extract(source, 'https://zavtra.ru/blogs/example')
        self.assertEqual(previous(source, 'https://zavtra.ru/blogs/example'), before)
        self.assertEqual(clean, before[0])
        self.assertEqual(meta['clean_version'], VERSION)
        self.assertIn('«Продолжай»', clean.raw)
        self.assertIn('Мяг\u00adкий', clean.raw)
        self.assertIn('Мягкий', clean.norm)
        self.assertEqual(clean.code_blocks, 1)


if __name__ == '__main__':
    unittest.main()
