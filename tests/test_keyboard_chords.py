"""Типизированные клавиши восстанавливаются, соседняя проза и код сохраняются."""
import unittest
from bench.candidates.keyboard_chords import repair_markup,extract,VERSION
from bench.candidates.editorial_roles import extract as previous


class KeyboardChordsTest(unittest.TestCase):
    def test_chords_preserve_original_case_spacing_and_other_bytes(self):
        text='<p>Клавиши <Alt + Tab>, затем <Ctrl + Shift + F4>. Другой текст.</p>'
        fixed,count=repair_markup(text)
        self.assertEqual(count,2)
        self.assertEqual(fixed,text.replace('<Alt + Tab>','&lt;Alt + Tab&gt;').replace('<Ctrl + Shift + F4>','&lt;Ctrl + Shift + F4&gt;'))

    def test_nonprose_and_existing_markup_are_unchanged(self):
        values=['<pre><Alt + Tab></pre>','<code><Alt + F4></code>',
                '<script>let key="<Alt + Tab>";</script>',
                '<p title="<Alt + Tab>">Данные</p>','<!-- <Alt + Tab> -->',
                '<p><alt class="tab">Компонент</alt></p>',
                '<p>&lt;Alt + Tab&gt; уже экранировано.</p>',
                '<p>Тип <T>не является клавишей</T>.</p>',
                '<p>Неизвестная конструкция <Alt + Something>.</p>',
                '<p>Обычный тег <input name="Alt">.</p>']
        for text in values:
            with self.subTest(text=text):self.assertEqual(repair_markup(text),(text,0))

    def test_character_offsets_do_not_confuse_other_line_separators(self):
        text='<p>Один\x85символ и\nтекст <Alt + F4></p>'
        self.assertEqual(repair_markup(text),(text.replace('<Alt + F4>','&lt;Alt + F4&gt;'),1))

    def test_modifiers_compact_spelling_and_boundaries(self):
        for value in ['<Ctrl+C>','<Alt+F12>','<Shift + Home>','<Win + R>']:
            with self.subTest(value=value):
                fixed,count=repair_markup('<p>Начало'+value+'конец</p>')
                self.assertEqual(count,1)
                self.assertTrue(fixed.startswith('<p>Начало&lt;'))
                self.assertTrue(fixed.endswith('&gt;конец</p>'))

    def test_real_extractor_keeps_both_chords_and_surrounding_prose(self):
        body='<p>Начальный содержательный абзац.</p><p>Выбор <Alt + Tab>, <Alt + F4> и клавиши Win.</p><p>Последний содержательный абзац.</p>'
        page='<html><body><h1>Клавиши</h1><div class="bdaia-post-content">'+body+'</div></body></html>'
        old,oldmeta=previous(page,'https://xakep.ru/example/')
        new,meta=extract(page,'https://xakep.ru/example/')
        self.assertIn('<Alt + Tab>',new.raw)
        self.assertIn('<Alt + F4>',new.norm)
        self.assertIn('Начальный содержательный абзац.',new.raw)
        self.assertIn('Последний содержательный абзац.',new.raw)
        self.assertNotIn('<Alt + Tab>',old.raw)
        self.assertEqual(meta['clean_version'],VERSION)
        self.assertEqual(meta['recovered_keyboard_chord_markup'],2)
        self.assertEqual(new.code_blocks,old.code_blocks)
        self.assertEqual({k:v for k,v in meta.items() if k not in {'clean_version','recovered_keyboard_chord_markup'}},
                         {k:v for k,v in oldmeta.items() if k!='clean_version'})


if __name__=='__main__':unittest.main()
