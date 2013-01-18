import os.path
import buildploy
import unittest
import shutil

run = buildploy.run

class UnitTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), 'tmp/unit')
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.mkdir(self.test_dir)
        run('''cd %s &&
            git init upstream &&
            cd upstream &&
            touch a &&
            git add . &&
            git commit -m a &&
            git branch a &&
            touch b &&
            git add . &&
            git commit -m b &&
            git branch b &&
            cd .. &&
            git clone upstream cloned
        ''' % self.test_dir, shell=True)
    
    def test_git_list_remote_branches(self):
        branches = buildploy.git_list_remote_branches(os.path.join(self.test_dir, 'cloned'))
        assert 'origin/a' in branches

if __name__ == '__main__':
    unittest.main()
