"""Русский/украинский и ошибки модели; проверяем настоящий классификатор."""
import unittest
from unittest.mock import patch

from bench.language_review import POLICY, RussianLanguageReview, load_review


class LanguageReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = load_review(POLICY)

    def test_cyrillic_is_not_russian(self):
        russian = self.review.check('Это русский текст. Автор объясняет работу программы '
                                    'и приводит полезные примеры для читателей.')
        ukrainian = self.review.check('Це український текст. Автор розповідає про роботу '
                                      'програми та наводить корисні приклади для читачів.')
        self.assertEqual((russian['language'], russian['review_required']), ('ru', False))
        self.assertEqual((ukrainian['language'], ukrainian['review_required']), ('uk', True))
        self.assertFalse(russian['admitted'])

    def test_english_numeric_and_empty_are_held(self):
        for text, language in [('This article explains the program and provides useful examples.', 'en'),
                               ('1234567890', 'zxx'), (' \n\t', 'und')]:
            result = self.review.check(text)
            self.assertEqual(result['language'], language)
            self.assertTrue(result['review_required'])

    def test_foreign_identifiers_do_not_reject_russian_prose(self):
        text = ('Функция get_data принимает строку и возвращает список записей. '
                'После вызова await client.connect() проверим результат. '
                'Сначала нужно открыть соединение, затем прочитать данные и закрыть файл.')
        self.assertFalse(self.review.check(text)['review_required'])

    def test_tie_is_held_even_if_russian_is_first(self):
        with patch.object(type(self.review.identifier), 'rank', return_value=[('ru', -10.), ('uk', -10.)]):
            self.assertTrue(self.review.check('пример')['review_required'])

    def test_input_and_policy_are_strict(self):
        with self.assertRaises(TypeError):
            self.review.check(b'not silently decoded')
        for policy in [None, '', 'future', 42]:
            with self.assertRaises(ValueError):
                load_review(policy)

    def test_changed_version_and_weights_fail_closed(self):
        with patch('bench.language_review.version', return_value='future'):
            with self.assertRaisesRegex(ValueError, 'py3langid'):
                RussianLanguageReview()
        with patch('bench.language_review.MODEL_SHA256', 'bad'):
            with self.assertRaisesRegex(ValueError, 'модель'):
                RussianLanguageReview()


if __name__ == '__main__':
    unittest.main()
