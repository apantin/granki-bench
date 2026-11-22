import unittest
from bench.corruptions import mutate

TEXT = '\n\n'.join('В работе участвуют 25 человек, поскольку требуется проверить несколько вариантов обработки. '
                    'Первое предложение объясняет задачу. Второе раскрывает детали. Третье подводит итог. '
                    'Четвёртое уточняет границы вывода.' for _ in range(6)) + '\n'


class CorruptionsTest(unittest.TestCase):
    def test_reproducibility_and_scope(self):
        for kind in ('typo', 'punctuation', 'specificity', 'paragraph_order', 'repeat', 'structure', 'sentence_order'):
            a,b = mutate(TEXT,kind,'weak',42),mutate(TEXT,kind,'weak',42)
            self.assertEqual(a,b)
            if kind != 'paragraph_order':
                self.assertGreater(a.changes,0)
                self.assertNotEqual(a.text,TEXT)
        self.assertEqual(mutate('Коротко.','sentence_order','weak',0).changes,0)

    def test_specificity_only_counted_quantity(self):
        text = 'В 2021 году прошло 25 дней. Цена — 40 рублей.\n'
        out = mutate(text,'specificity','strong',4)
        self.assertIn('2021',out.text)
        self.assertIn('несколько',out.text)


if __name__ == '__main__':
    unittest.main()
