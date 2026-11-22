import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('cc_extraction',Path(__file__).resolve().parents[1]/'scripts/cc/extraction.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class IdentityTest(unittest.TestCase):
    def test_collective_and_personal_groups(self):
        for author in ['Редакция','Редакция сайта','Команда проекта']:
            self.assertEqual(module.author_identity('https://example.org/post',{'author':author}),'domain:example.org')
        self.assertEqual(module.author_identity('https://example.org/post',{'author':'Ольга Иванова'}),'ольга иванова')
        self.assertEqual(module.author_identity('https://teletype.in/@writer/post',{}),'teletype.in@writer')


if __name__=='__main__':unittest.main()
