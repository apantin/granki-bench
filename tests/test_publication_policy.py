import unittest
from bench.candidates.publication_policy import POLICY, review
from test_publication_body import xakep


class PublicationPolicyTests(unittest.TestCase):
    def test_primary_category_is_explicit_advertorial(self):
        source = xakep('<p>Публикация.</p>').replace('class="hentry ', 'class="hentry category-advert ', 1)
        self.assertIn('category-advert', source)
        result = review(source, 'https://xakep.ru/example/')
        self.assertEqual(result, dict(policy=POLICY, status='explicit-advertorial', markers=['category-advert'], admitted=False))

    def test_brand_word_and_sidebar_do_not_establish_role(self):
        source = xakep('<p>Сравнение товаров: достоинства, недостатки и реклама.</p>')
        source = source.replace('</body>', '<aside class="category-advert">Реклама</aside></body>')
        self.assertEqual(review(source, 'https://xakep.ru/example/')['status'], 'no-explicit-marker')

    def test_unbound_or_other_host_is_not_admitted_or_rejected_by_this_rule(self):
        for source, url, status in [('<article class="category-advert">Статья</article>', 'https://xakep.ru/example/', 'unresolved-primary-publication'),
                                    ('<article class="category-advert">Статья</article>', 'https://example.org/', 'not-applicable')]:
            with self.subTest(url=url):
                result = review(source, url)
                self.assertEqual(result['status'], status)
                self.assertEqual(result['markers'], [])
                self.assertFalse(result['admitted'])


if __name__ == '__main__':
    unittest.main()
