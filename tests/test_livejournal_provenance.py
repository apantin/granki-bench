import unittest
from bench.livejournal_provenance import livejournal_source_marker as review


def credit(author='guest',origin='guest',language='ru'):
    prefix,connector=('Оригинал взят у','в') if language=='ru' else ('Originally posted by','at')
    host=author.replace('_','-')
    return (prefix+f' <span class="ljuser i-ljuser" data-ljuser="{author}">'
        f'<a class="i-ljuser-profile" href="https://{host}.livejournal.com/profile"><img></a>'
        f'<a class="i-ljuser-username" href="https://{host}.livejournal.com/"><b>{author}</b></a>'
        f'</span> {connector} <a href="https://{origin}.livejournal.com/123.html">Исходный пост</a>')


def page(body):return '<html><body><article class="b-singlepost-body entry-content">'+body+'</article></body></html>'


class LivejournalProvenanceTest(unittest.TestCase):
    url='https://owner.livejournal.com/456.html'

    def test_explicit_ru_and_en_primary_credit_including_third_publisher(self):
        for language in ['ru','en']:
            for origin in ['guest','another']:
                result=review(page(credit(origin=origin,language=language)+'<p>Текст перепечатки.</p>'),self.url)
                self.assertEqual(result['status'],'explicit-repost-credit');self.assertFalse(result['admitted'])

    def test_comment_and_prose_example_are_not_primary_repost(self):
        for body in ['<p>Я объясняю, как устроена строка «Оригинал взят у».</p>'+credit(),
                     '<p>Собственное введение.</p><blockquote>'+credit()+'</blockquote>']:
            self.assertEqual(review(page(body),self.url)['status'],'no-explicit-repost-credit')
        source=page('<p>Своя статья.</p>')+'<div class="comment">'+credit()+'</div>'
        self.assertEqual(review(source,self.url)['status'],'no-explicit-repost-credit')

    def test_own_account_credit_is_not_asserted_foreign_and_underscores_match(self):
        self.assertEqual(review(page(credit(author='owner',origin='owner')),self.url)['status'],'self-repost-credit')
        self.assertEqual(review(page(credit(author='own_er',origin='own-er')),'https://own-er.livejournal.com/456.html')['status'],'self-repost-credit')

    def test_incomplete_conflicting_or_spoofed_profile_is_uncertain(self):
        variants=[credit(origin='owner'),credit().replace('data-ljuser="guest"','data-ljuser="other"'),
            credit().replace('guest.livejournal.com/profile','guest.livejournal.com.evil.org/profile'),
            credit().replace('/123.html','/profile'),credit().replace('> в <','> также <')]
        for value in variants:
            with self.subTest(value=value):self.assertEqual(review(page(value),self.url)['status'],'unresolved-repost-credit')

    def test_transparent_leading_wrapper_and_comments_do_not_hide_credit(self):
        for body in ['<div>'+credit()+'<p>Проза.</p></div>','<!-- example -->'+credit()+'<p>Проза.</p>',credit().replace('/123.html','/123.html#cut')]:
            self.assertEqual(review(page(body),self.url)['status'],'explicit-repost-credit')

    def test_multiple_articles_and_non_post_urls_do_not_bind(self):
        self.assertEqual(review(page(credit())+page('Другая'),self.url)['status'],'unresolved-primary-publication')
        for url in ['https://example.org/456.html','https://owner.livejournal.com.evil.org/456.html',
                    'https://owner.livejournal.com/profile','https://owner.livejournal.com/']:
            with self.subTest(url=url):self.assertEqual(review(page(credit()),url)['status'],'not-applicable')
