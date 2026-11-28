"""Служебная роль не должна вырезать соседнюю или похожую авторскую прозу."""
import unittest

from bench.candidates.editorial_roles import extract, VERSION
from bench.candidates.technical_markup import extract as previous
from test_publication_body import zavtra


def page(body, main='<section itemprop="articleBody">{}</section>', author='Иван Петров'):
    return ('<html><head><meta name="author" content="' + author + '"></head><body>'
            '<h1>Основная статья</h1>' + main.format(body) + '</body></html>')


def related(extra='', href='/blog/another.html'):
    return ('<div class="incut read"><p>Статьи по теме:</p><ul>'
            '<li><a href="' + href + '">Соседняя статья</a></li>'
            '<li><a href="/blog/second.html">Вторая статья</a></li></ul>' + extra + '</div>')


def habr(body):
    return page(body, '<div id="post-content-body" class="post__text">{}</div>')


def prefix(current='/ru/post/1/'):
    return ('Посты серии:<br><a href="/ru/post/2/">Вторая часть</a><br>'
            '<a href="' + current + '">Первая часть</a><br><br>')


def kontur(body, author='Иван Петров'):
    return page(body, '<div id="ArticleItem"><div class="text">{}</div></div>', author)


def netology(body, author='Иван Петров'):
    return page(body, '<article><div class="entry-content">{}</div></article>', author)


class EditorialRolesTest(unittest.TestCase):
    def test_related_widgets_removed_but_own_recommendation_and_tail_preserved(self):
        body = ('<p>Начало.</p>' + related() + 'Содержательный хвост.'
                '<div class="readblogmore"><a href="/blog/third.html">Третья статья</a></div>'
                '<p>Рекомендую книгу:</p><ul><li><a href="/blog/book.html">Мой выбор</a> — с пояснением.</li></ul>')
        clean, meta = extract(page(body), 'https://texterra.ru/blog/main.html')
        self.assertNotIn('Соседняя статья', clean.raw)
        self.assertNotIn('Третья статья', clean.raw)
        self.assertIn('Содержательный хвост.', clean.raw)
        self.assertIn('Мой выбор', clean.raw)
        self.assertEqual(meta['removed_related_widgets'], 2)

    def test_related_role_does_not_erase_mixed_content_or_external_links(self):
        for widget in [related('<p>Собственное пояснение.</p>'),
                       related(href='https://elsewhere.test/blog/another.html'),
                       related(href='/blog/another.html?mode=other'),
                       related().replace('Статьи по теме:', 'Мои доводы:'),
                       '<div class="readblogmore">Мой довод <a href="/blog/another.html">Соседняя статья</a></div>']:
            with self.subTest(widget=widget):
                clean, meta = extract(page(widget), 'https://texterra.ru/blog/main.html')
                self.assertIn('Соседняя статья', clean.raw)
                self.assertEqual(meta['unresolved_related_widgets'], 1)

    def test_habr_prefix_keeps_all_first_paragraph_and_following_structure(self):
        source = habr(prefix() + 'Начало собственной прозы.<br><h2>Разбор</h2><p>Конец.</p>')
        old, _ = previous(source, 'https://habr.com/ru/post/1/')
        clean, meta = extract(source, 'https://habr.com/ru/post/1/')
        self.assertIn('Посты серии:', old.raw)
        self.assertNotIn('Посты серии:', clean.raw)
        self.assertNotIn('Вторая часть', clean.raw)
        self.assertIn('Начало собственной прозы.', clean.raw)
        self.assertIn('Разбор', clean.raw)
        self.assertIn('Конец.', clean.raw)
        self.assertEqual(meta['removed_series_links'], 2)

    def test_habr_prefix_without_tail_keeps_following_paragraph(self):
        clean, _ = extract(habr(prefix() + '<p>Не потерять абзац.</p>'), 'https://habr.com/ru/post/1/')
        self.assertIn('Не потерять абзац.', clean.raw)
        self.assertNotIn('Вторая часть', clean.raw)

    def test_habr_requires_own_post_link_and_unmixed_prefix(self):
        for body in [prefix('/ru/post/3/') + 'Своя проза.',
                     prefix('https://elsewhere.test/ru/post/1/') + 'Своя проза.',
                     prefix().replace('>Вторая часть</a>', '>Вторая часть</a> Своя мысль.') + 'Своя проза.']:
            with self.subTest(body=body):
                clean, meta = extract(habr(body), 'https://habr.com/ru/post/1/')
                self.assertIn('Вторая часть', clean.raw)
                self.assertIn('Своя проза.', clean.raw)
                self.assertEqual(meta['unresolved_series_prefixes'], 1)
        clean, _ = extract(habr('Свой рассказ о серии.<br>' + prefix()), 'https://habr.com/ru/post/1/')
        self.assertIn('Посты серии:', clean.raw)

    def test_terminal_publication_credit_is_separate_from_own_reference(self):
        credit = '<p><strong><a href="https://publisher.test/article">Публикация: Издание</a></strong></p>'
        source = zavtra('<p>Конец моей статьи.</p>' + credit + '<div class="zen_inv">Подписка</div>')
        clean, meta = extract(source, 'https://zavtra.ru/blogs/example')
        self.assertNotIn('Публикация: Издание', clean.raw)
        self.assertIn('Конец моей статьи.', clean.raw)
        self.assertEqual(meta['removed_publication_credits'], 1)
        for body in [credit + '<p>Авторское продолжение.</p>',
                     credit.replace('<strong>', '<strong>Мой комментарий: '),
                     '<p>Публикация: мой собственный довод.</p>']:
            with self.subTest(body=body):
                clean, meta = extract(zavtra(body), 'https://zavtra.ru/blogs/example')
                self.assertIn('Публикация:', clean.raw)
                self.assertEqual(meta['removed_publication_credits'], 0)

    def test_signature_matches_original_author_and_preserves_identity(self):
        source = kontur('<p>Основное объяснение.</p><p><strong>Иван Петров</strong>, менеджер продукта <a href="/product">Программа</a></p>')
        before, original = previous(source, 'https://kontur.ru/articles/example')
        clean, meta = extract(source, 'https://kontur.ru/articles/example')
        self.assertIn('Иван Петров', before.raw)
        self.assertNotIn('Иван Петров', clean.raw)
        self.assertIn('Основное объяснение.', clean.raw)
        self.assertEqual(meta['removed_author_signatures'], 1)
        for key in ['title', 'author', 'date']:
            self.assertEqual(meta.get(key), original.get(key))

    def test_signature_mismatch_mixed_prose_or_followup_is_preserved(self):
        sign = '<p><strong>Иван Петров</strong>, менеджер продукта</p>'
        for body, author in [(sign, 'Мария Сидорова'),
                             (sign.replace('продукта', 'продукта. Это мой вывод.'), 'Иван Петров'),
                             (sign.replace('продукта', 'продукта, считает систему удобной'), 'Иван Петров'),
                             (sign + '<p>Продолжение автора.</p>', 'Иван Петров')]:
            with self.subTest(body=body, author=author):
                clean, meta = extract(kontur(body, author), 'https://kontur.ru/articles/example')
                self.assertIn('Иван Петров', clean.raw)
                self.assertEqual(meta['removed_author_signatures'], 0)

    def test_previous_cleanup_removed_signature_is_not_an_unresolved_block(self):
        source = ('<html><body><div class="content-block_article-announce">'
                  '<h1>Основная статья</h1><span class="article-announce-autor-block__name">Иван Петров</span>'
                  '</div><div id="ArticleItem"><div class="text"><p>Своя проза.</p>'
                  '<p><strong>Иван Петров</strong>, директор компании</p></div></div></body></html>')
        before, old_meta = previous(source, 'https://kontur.ru/articles/example')
        self.assertEqual(old_meta['removed_kontur_bylines'], 1)
        clean, meta = extract(source, 'https://kontur.ru/articles/example')
        self.assertEqual(clean, before)
        self.assertEqual(meta['unresolved_author_signatures'], 0)

    def test_editorial_intro_requires_first_paragraph_and_named_author(self):
        intro = '<p>Руководитель команды Иван Петров в колонке для «Нетологии» рассказывает, как строить систему.</p>'
        source = netology(intro + '<p>Мой собственный опыт.</p>')
        clean, meta = extract(source, 'https://netology.ru/blog/example')
        self.assertNotIn('Руководитель команды', clean.raw)
        self.assertIn('Мой собственный опыт.', clean.raw)
        self.assertEqual(meta['removed_editorial_introductions'], 1)
        for body, author in [(intro + '<p>Мой опыт.</p>', 'Мария Сидорова'),
                             ('<p>Мой опыт.</p>' + intro, 'Иван Петров'),
                             (intro.replace('систему.</p>', 'систему. Мой отдельный вывод.</p>'), 'Иван Петров')]:
            with self.subTest(body=body):
                clean, meta = extract(netology(body, author), 'https://netology.ru/blog/example')
                self.assertIn('Руководитель команды', clean.raw)
                self.assertEqual(meta['removed_editorial_introductions'], 0)

    def test_wrong_host_scope_and_previous_candidate_stay_unchanged(self):
        source = page('<p>Собственное «слово».</p>' + related())
        original = previous(source, 'https://elsewhere.test/article')
        clean, meta = extract(source, 'https://elsewhere.test/article')
        self.assertEqual(clean, original[0])
        self.assertEqual(meta['removed_related_widgets'], 0)
        self.assertEqual(meta['clean_version'], VERSION)
        self.assertEqual(previous(source, 'https://elsewhere.test/article'), original)


if __name__ == '__main__':
    unittest.main()
