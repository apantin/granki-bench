import hashlib
import unittest
from bench.corpus_selection import quota,group_hashes


class SelectionTest(unittest.TestCase):
    def fixtures(self):
        return [dict(id=str(i),snapshot='CC-MAIN-2021-04',url=f'https://example.org/{i}',
                     sha256=hashlib.sha256(str(i).encode()).hexdigest(),domain=f'd{i%5}.org',
                     subgenre='personal',author=f'a{i%40}',split='scouting') for i in range(100)]

    def test_private_fields_and_input_order_do_not_change_selection(self):
        docs=self.fixtures()
        params=dict(seed='v1',target=50,subgenres=['personal'],domain_cap=.3,author_cap=2)
        a=quota(docs,**params)
        for row in docs:row.update(split='hidden-C',salt='different',viewed=True)
        b=quota(list(reversed(docs)),**params)
        self.assertEqual([r['id'] for r in a],[r['id'] for r in b])
        self.assertEqual(group_hashes(a),group_hashes(b))
        self.assertEqual(len(a),50)

    def test_dedup_earliest_independent_of_parts(self):
        try:from bench.corpus_selection import deduplicate
        except ImportError:self.skipTest('Нет необязательной зависимости datasketch')
        try:import datasketch
        except ImportError:self.skipTest('Нет необязательной зависимости datasketch')
        a=self.fixtures()[0]|{'text':'достаточно длинный текст из нескольких слов для проверки дубликатов'}
        b=a|{'id':'later','snapshot':'CC-MAIN-2022-05','split':'hidden-A'}
        keep,dups=deduplicate([b,a])
        self.assertEqual([r['id'] for r in keep],[a['id']])
        self.assertEqual(dups,{'later':a['id']})


if __name__ == '__main__':
    unittest.main()
