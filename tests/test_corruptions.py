import unittest
from bench.corruptions import mutate,mutate_quantity_v2

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

    def test_quantity_v2_fixes_case_without_rewriting_legacy(self):
        text='Он говорил более 40 минут.'
        legacy=mutate(text,'specificity','weak',4)
        current=mutate_quantity_v2(text,'weak',4)
        self.assertEqual(legacy.text,'Он говорил более несколько минут.')
        self.assertEqual(current.text,'Он говорил более нескольких минут.')
        self.assertEqual(legacy.version,'corrupt-v1');self.assertEqual(current.version,'quantity-v2')

    def test_quantity_v2_distinguishes_genitive_and_accusative(self):
        for text,want in [('В течение 10 минут.','В течение нескольких минут.'),
                          ('От 3 до 7 минут.','От 3 до нескольких минут.'),
                          ('Через 10 дней.','Через несколько дней.'),
                          ('Для 5 человек.','Для нескольких человек.')]:
            self.assertEqual(mutate_quantity_v2(text,'weak',1).text,want)

    def test_quantity_v2_skips_unsupported_context_and_zero(self):
        for text in ['Обработка длится 10 минут.','Около 0 человек.','В течение\n10 минут.','В 2021 году.']:
            result=mutate_quantity_v2(text,'strong',1)
            self.assertEqual(result.changes,0);self.assertEqual(result.text,text)


if __name__ == '__main__':
    unittest.main()
