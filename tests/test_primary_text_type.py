import unittest

from bench.primary_text_type import POLICY, review


def page(body, title='Самостоятельная публикация', extra=''):
    return f'<html><body><h1>{title}</h1><article class="entry-content">{body}</article>{extra}</body></html>'


CREDIT = '<p><i>Перевод и адаптация материала Тестового автора <a href="https://source.example/original">Original article</a>.</i></p>'
OUTLINE = '<div class="container_video"><iframe></iframe></div><div class="incut"><p>Скачать презентацию: <a href="/slides.pdf">Файл</a>.</p></div><h2>План вебинара</h2><ol><li>Первый вопрос?</li><li>Второй вопрос?</li></ol>'
TITLE = '[Запись вебинара] Тестовая тема'


class PrimaryTextTypeTest(unittest.TestCase):
    def check(self, content, expected):
        result = review(content, 'https://example.org/article')
        self.assertEqual(result['policy'], POLICY)
        self.assertEqual(result['status'], expected)
        self.assertFalse(result['admitted'])

    def test_terminal_credit_binds_external_original(self):
        self.check(page('<p>Самостоятельное начало переведённой статьи.</p>'+CREDIT), 'explicit-translation-credit')
        self.check(page('<p>Основная статья.</p>'+CREDIT+'<div class="incut read"><p>Читайте также:</p><ul><li><a href="/other">Другое</a></li></ul></div><span>article</span>'), 'explicit-translation-credit')

    def test_quote_code_and_sidebar_do_not_declare_whole_article_translation(self):
        for wrapper in ['blockquote', 'q', 'pre', 'code', 'aside']:
            with self.subTest(wrapper=wrapper):
                self.check(page(f'<p>Авторский разбор примера.</p><{wrapper}>{CREDIT}</{wrapper}>'), 'no-explicit-marker')
        self.check(page('<p>Основная статья.</p>', extra=CREDIT), 'no-explicit-marker')

    def test_mentions_and_unbound_references_do_not_trigger(self):
        self.check(page('<p>Мы обсуждаем перевод и адаптацию материала.</p>'), 'no-explicit-marker')
        self.check(page(CREDIT.replace('<i>', '').replace('</i>', '')), 'no-explicit-marker')
        self.check(page(CREDIT.replace('https://source.example/original', '/original')), 'no-explicit-marker')
        self.check(page(CREDIT+'<p>Далее авторский разбор процитированного примера.</p>'), 'no-explicit-marker')

    def test_credit_followed_by_substantive_incut_is_not_terminal(self):
        self.check(page(CREDIT+'<div class="incut read"><p>Дополнительный авторский вывод.</p><ul><li><a href="/other">Источник</a></li></ul></div>'), 'no-explicit-marker')

    def test_recording_with_only_outline_and_service_material_is_not_article(self):
        self.check(page(OUTLINE, TITLE), 'explicit-webinar-outline')
        self.check(page(OUTLINE+'<h2>Ссылки на полезные материалы по теме:</h2><ul><li><a href="/one">Ссылка</a></li></ul>', TITLE), 'explicit-webinar-outline')

    def test_written_explanation_before_or_after_plan_is_preserved(self):
        self.check(page('<p>Самостоятельный письменный разбор.</p>'+OUTLINE, TITLE), 'no-explicit-marker')
        self.check(page(OUTLINE+'<p>Развёрнутый ответ на перечисленные вопросы.</p>', TITLE), 'no-explicit-marker')
        self.check(page(OUTLINE, 'Как подготовить запись вебинара'), 'no-explicit-marker')

    def test_outline_requires_plan_and_full_body_cannot_hide_in_plain_tail(self):
        self.check(page('<ul><li>Тема</li></ul>', TITLE), 'no-explicit-marker')
        self.check(page(OUTLINE+'Продолжение авторского разбора.', TITLE), 'no-explicit-marker')

    def test_ambiguous_or_empty_primary_scope_is_not_an_explicit_rejection(self):
        self.check('', 'not-applicable')
        self.check('<article class="entry-content">'+CREDIT+'</article><article class="entry-content">Текст</article>', 'not-applicable')


if __name__ == '__main__':
    unittest.main()
