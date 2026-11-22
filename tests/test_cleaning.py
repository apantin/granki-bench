import unittest
from bench.cleaning import markdown, typography, words


class CleaningTest(unittest.TestCase):
    def test_structure_and_raw_typography(self):
        source = '# Заголовок\n\n"Текст" - это **пример**. Ёж.\n\n* Один\n* Два\n\n> Чужая цитата\n\n```python\nx=1\n```\n'
        out = markdown(source)
        self.assertIn('"Текст" -', out.raw)
        self.assertIn('«Текст» —', out.norm)
        self.assertIn('Ёж', out.norm)
        self.assertIn('# Заголовок', out.raw)
        self.assertIn('- Один', out.raw)
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
