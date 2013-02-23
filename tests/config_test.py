import os.path
import buildploy
import unittest
import mock

try:
    # py 2
    base_exception = StandardError
except NameError:
    # py 3
    base_exception = Exception

class YamlDisabled(base_exception):
    pass

def disabled_yaml(*args):
    raise YamlDisabled

class ConfigTest(unittest.TestCase):
    def setUp(self):
        super(ConfigTest, self).setUp()
        
        self.fixtures_dir = os.path.join(os.path.dirname(__file__), 'fixtures')
    
    def test_yaml(self):
        self.check('yaml_config.yaml')
    
    def test_yml(self):
        self.check('yaml_config.yml')
    
    @mock.patch('yaml.load', disabled_yaml)
    def test_yaml_patching(self):
        # this just checks that our patch works
        try:
            self.check('yaml_config.yml')
        except YamlDisabled:
            pass
        else:
            self.fail('Patch did not work')
    
    @mock.patch('yaml.load', disabled_yaml)
    def test_json(self):
        self.check('json_config.json')
    
    def check(self, config_file_path):
        config = buildploy.load_config_file(os.path.join(self.fixtures_dir, config_file_path))
        
        expected = {
            'src_repo': '/path/to/src/repo',
            'deploy_repo': 'git@github.com:user/deploy.git',
            'work_prefix': '/path/to/work',
            'build_cmd': 'make',
            'deploy_subdir': 'build',
        }
        self.assertEqual(expected, config)

if __name__ == '__main__':
    unittest.main()
