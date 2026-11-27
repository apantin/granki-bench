import unittest
from bench.candidates.blogspot_post import bind, extract, VERSION
from bench.candidates.technical_markup import extract as previous
from bench.html_structure import decode
from lxml import html


def page(body='<p>Собственная проза.</p>', title='<h3 class="post-title entry-title">Заголовок поста</h3>',
         blog='<h1>Название блога</h1>', role='itemprop="articleBody"'):
    return '<html><body>'+blog+'<div class="post hentry">'+title+'<div '+role+'>'+body+'</div><div class="post-footer">Подпись автора</div></div></body></html>'


class BlogspotPostTest(unittest.TestCase):
    url='https://example.blogspot.com/2020/01/post.html'

    def test_primary_title_replaces_blog_title_and_keeps_own_prose(self):
        clean, meta=extract(page(),self.url)
        self.assertTrue(clean.raw.startswith('# Заголовок поста\n\n'))
        self.assertIn('Собственная проза.',clean.raw)
        self.assertNotIn('Название блога',clean.raw)
        self.assertNotIn('Подпись автора',clean.raw)
        self.assertEqual(meta['title'],'Заголовок поста')
        self.assertEqual(meta['clean_version'],VERSION)
        self.assertEqual(meta['replaced_blogspot_site_titles'],1)

    def test_h1_h2_h3_and_both_explicit_body_roles_bind(self):
        for tag in ['h1','h2','h3']:
            for role in ['itemprop="articleBody"','class="post-body entry-content"']:
                with self.subTest(tag=tag,role=role):
                    clean, meta=extract(page(title=f'<{tag} class="post-title entry-title">Основной заголовок</{tag}>',role=role,blog=''),self.url)
                    self.assertTrue(clean.raw.startswith('# Основной заголовок\n\n'))
                    self.assertEqual(clean.raw.count('Основной заголовок'),1)
                    self.assertEqual(meta['unresolved_blogspot_posts'],0)

    def test_own_inner_heading_and_technical_meaning_are_kept(self):
        source=page(body='<h1>Свой раздел</h1><p>x<sup>2</sup> и H<sub>2</sub>O.</p><pre>echo one</pre><p>Конец.</p>',blog='')
        old,_=previous(source,self.url);clean,_=extract(source,self.url)
        self.assertEqual(clean.raw,'# Заголовок поста\n\n'+old.raw)
        self.assertIn('# Свой раздел',clean.raw);self.assertIn('x^(2)',clean.raw)
        self.assertIn('H_(2)O',clean.raw);self.assertEqual(clean.code_blocks,old.code_blocks)
        self.assertEqual(clean.raw.count('[КОД]'),1)

    def test_ambiguous_nested_empty_or_untyped_post_is_unchanged_and_flagged(self):
        sources=[page(title='<h3 class="post-title entry-title">Один</h3><h3 class="post-title entry-title">Два</h3>'),
                 page(title='<h3 class="post-title entry-title"></h3>'),
                 page(title='<h3>Заголовок без роли</h3>'),
                 page(body='<div class="post">Вложенная публикация</div>'),
                 page(role='class="unknown"'),
                 page().replace('class="post hentry"','class="unknown"')]
        for source in sources:
            with self.subTest(source=source):
                clean,meta=extract(source,self.url);old,_=previous(source,self.url)
                self.assertEqual(clean,old);self.assertEqual(meta['unresolved_blogspot_posts'],1)

    def test_multiple_bodies_or_title_inside_body_do_not_bind(self):
        for source in [page()+'<div itemprop="articleBody">Другой пост</div>',
                       page(title='',body='<h3 class="post-title entry-title">Внутри</h3><p>Проза.</p>')]:
            with self.subTest(source=source):
                self.assertIsNone(bind(html.fromstring(decode(source)),'example.blogspot.com'))

    def test_other_hosts_and_similar_domains_keep_previous_bytes(self):
        for url in ['https://example.org/post','https://blogspot.com/post','https://example.blogspot.com.evil.org/post']:
            clean,meta=extract(page(),url);old,_=previous(page(),url)
            self.assertEqual(clean,old);self.assertEqual(meta['bound_blogspot_posts'],0)
            self.assertEqual(meta['unresolved_blogspot_posts'],0)

    def test_html_comments_do_not_act_as_elements_or_hide_the_post(self):
        source=page(body='<!-- post-title entry-title --><p>Проза.</p>').replace('<h3','<!-- post --><h3')
        clean,meta=extract(source,self.url)
        self.assertTrue(clean.raw.startswith('# Заголовок поста\n\n'))
        self.assertEqual(meta['bound_blogspot_posts'],1)
        self.assertEqual(meta['unresolved_blogspot_posts'],0)
        self.assertNotIn('entry-title',clean.raw)


if __name__=='__main__':unittest.main()
