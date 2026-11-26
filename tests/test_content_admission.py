import unittest
from bench.content_admission import content_url_review


class ContentUrlAdmissionTest(unittest.TestCase):
    def test_explicit_adult_slugs_require_review(self):
        for path in ['/Porno-example-01-02','/free-porn/','/Порно-пример/','/hentai/example']:
            with self.subTest(path=path):self.assertTrue(content_url_review('https://example.org'+path))

    def test_sexual_numbered_gallery_requires_review(self):
        for path in ['/minet-i-seks-5-foto-01-02','/posle-seksa-10-foto-01-02','/секс-3-видео','/sex-5-video']:
            with self.subTest(path=path):self.assertTrue(content_url_review('https://example.org'+path))

    def test_topic_or_image_alone_does_not_establish_adult_content(self):
        for path in ['/seks-i-zdorove','/reklama-pro-seks','/foto-20-primerov','/seks-i-foto',
                     '/kanal-na-platforme','/deepnude-research','/seksizm-v-reklame','/pornographic-technology']:
            with self.subTest(path=path):self.assertFalse(content_url_review('https://example.org'+path))

    def test_query_host_and_fragment_do_not_become_title_tokens(self):
        for url in ['https://porno.example.org/ordinary','https://example.org/ordinary?tag=porn',
                    'https://example.org/ordinary#porno','https://example.org/ordinary?seks=5-foto']:
            with self.subTest(url=url):self.assertFalse(content_url_review(url))

    def test_encoded_case_and_token_boundaries(self):
        self.assertTrue(content_url_review('https://example.org/%70%6F%72%6E%6F_example'))
        self.assertFalse(content_url_review('https://example.org/spornova-01-02'))
        self.assertFalse(content_url_review('https://example.org/analitika-5-foto'))

    def test_invalid_or_non_web_url_is_not_classified(self):
        for url in ['', 'https://[', 'data:text/plain,porno', '/porno']:
            with self.subTest(url=url):self.assertFalse(content_url_review(url))


if __name__=='__main__':unittest.main()
