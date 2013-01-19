import os
import os.path
import buildploy
import unittest
import shutil

run_in_dir = buildploy.run_in_dir

class UnitTest(unittest.TestCase):
    def setUp(self):
        test_tmp = os.environ.get('TESTS_TMP') or os.path.join(os.path.dirname(__file__), 'tmp')
        self.test_dir = os.path.join(test_tmp, 'unit')
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.mkdir(self.test_dir)
        run_in_dir(self.test_dir, '''
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
        ''', shell=True)
    
    def test_git_list_local_branches(self):
        branches = buildploy.git_list_local_branches(os.path.join(self.test_dir, 'upstream'))
        assert 'a' in branches
    
    def test_git_list_remote_branches(self):
        branches = buildploy.git_list_remote_branches(os.path.join(self.test_dir, 'cloned'))
        assert 'origin/a' in branches

if __name__ == '__main__':
    unittest.main()
