import unittest
from bench.candidates.blogspot_uniform import extract,VERSION
from bench.candidates.keyboard_chords import extract as previous
from bench.candidates.blogspot_post import extract as old_blogspot
from test_blogspot_post import page


class BlogspotUniformTest(unittest.TestCase):
    url='https://example.blogspot.com/2020/01/post.html'

    def test_primary_title_and_complete_prose_match_prior_blogspot_candidate(self):
        content=page('<p>Собственная проза и примеры без изменений.</p>')
        clean,meta=extract(content,self.url);old,_=old_blogspot(content,self.url)
        self.assertEqual(clean,old);self.assertEqual(meta['clean_version'],VERSION)
        self.assertEqual(meta['unresolved_blogspot_posts'],0)

    def test_shared_chords_and_technical_markup_survive_with_post_title(self):
        content=page('<p>Пример <Alt + Tab> и x<sup>2</sup>.</p><pre>do something</pre><p>Последний абзац.</p>',
                     title='<h3 class="post-title entry-title">Клавиши <Alt + Tab></h3>')
        clean,meta=extract(content,self.url)
        self.assertTrue(clean.raw.startswith('# Клавиши <Alt + Tab>\n\n'))
        self.assertIn('<Alt + Tab>',clean.raw);self.assertIn('x^(2)',clean.raw)
        self.assertEqual(clean.raw.count('[КОД]'),1);self.assertEqual(meta['recovered_keyboard_chord_markup'],2)

    def test_other_hosts_keep_v22_bytes_and_all_prior_diagnostics(self):
        content=page('<p>Своя проза <Ctrl + F4>.</p>')
        for url in ['https://example.org/post','https://example.blogspot.com.evil.org/post']:
            old,oldmeta=previous(content,url);clean,meta=extract(content,url)
            self.assertEqual(clean,old)
            self.assertEqual({k:v for k,v in meta.items() if k not in {'clean_version','bound_blogspot_posts','unresolved_blogspot_posts','restored_blogspot_titles','replaced_blogspot_site_titles'}},
                             {k:v for k,v in oldmeta.items() if k!='clean_version'})

    def test_ambiguous_post_stays_unchanged_and_flagged(self):
        content=page(title='<h3>Неоднозначный заголовок</h3>')
        old,_=previous(content,self.url);clean,meta=extract(content,self.url)
        self.assertEqual(clean,old);self.assertEqual(meta['unresolved_blogspot_posts'],1)
