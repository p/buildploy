#!/usr/bin/env python

import re
import sys
import yaml
import os
import os.path

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from buildploy import run

def discover_tests(test_specs_dir):
    tests = []
    for entry in os.listdir(test_specs_dir):
        if entry[0] == '.':
            continue
        tests.append(entry)
    return tests

test_root = os.path.dirname(__file__)
test_root = os.path.realpath(test_root)
test_specs_dir = os.path.join(test_root, 'specs')
test_tmp = os.path.join(test_root, 'tmp')

tests = discover_tests(test_specs_dir)
if len(sys.argv) > 1:
    requested_tests = sys.argv[1:]
    found_tests = []
    for test in requested_tests:
        test = os.path.basename(test)
        if '.' not in test:
            test += '.yaml'
        if test not in tests:
            raise ValueError('Test not found: %s' % test)
        found_tests.append(test)
    tests = found_tests

if not os.path.exists(test_tmp):
    os.mkdir(test_tmp)

run('nosetests')

for test in tests:
    print('Running %s' % test)
    
    test_dir = os.path.join(test_tmp, re.sub(r'\..*', '', test))
    
    path = os.path.join(test_specs_dir, test)
    with open(path) as f:
        spec = yaml.load(f)
    
    run('cd %s && rm -rf %s && mkdir %s && cd %s && (%s)' %
        (test_tmp, test_dir, test_dir, test_dir, spec['prepare']), shell=True)
    
    if 'config' in spec:
        config_path = os.path.join(test_dir, 'config')
        with open(config_path, 'w') as f:
            case_config = dict(spec['config'])
            for key in ['src_repo', 'deploy_repo', 'work_prefix']:
                value = case_config[key]
                value = os.path.join(test_dir, value)
                case_config[key] = value
            yaml.dump(case_config, f)
    
    if 'options' in spec:
        # XXX escape options
        options = ' '.join(spec['options'])
    else:
        options = ''
    print('Building')
    build_script = os.path.join(test_root, '../buildploy.py')
    run('cd %s && %s %s/config %s' % (test_tmp, build_script, test_dir, options), shell=True)
    
    if 'deploy_tree' in spec:
        run('cd %s && git clone %s check' % (
            test_dir,
            spec['config']['deploy_repo'],
        ), shell=True)
        
        relative_paths = []
        start = os.path.join(test_dir, 'check')
        for root, dirs, files in os.walk(start):
            if '.git' in dirs:
                dirs.remove('.git')
            for file in files:
                relative_paths.append(os.path.join(root, file)[len(start)+1:])
        relative_paths.sort()
        
        expected_paths = list(spec['deploy_tree']['master'])
        expected_paths.sort
        
        assert relative_paths == expected_paths
    
    if 'check' in spec:
        run('cd %s && (%s)' % (
            test_dir,
            spec['check'],
        ), shell=True)
