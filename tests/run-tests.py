#!/usr/bin/env python

import re
import sys
import yaml
import os
import os.path
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from buildploy import run, run_in_dir, git_in_dir, rm_rf

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
test_tmp = os.environ.get('TESTS_TMP') or os.path.join(test_root, 'tmp')

def remove_extension(basename):
    if '.' in basename:
        return basename[:basename.find('.')]
    else:
        return basename

def find_files_under(start_path):
    relative_paths = []
    for root, dirs, files in os.walk(start_path):
        if '.git' in dirs:
            dirs.remove('.git')
        for file in files:
            relative_paths.append(os.path.join(root, file)[len(start_path)+1:])
    relative_paths.sort()
    return relative_paths

def run_spec(test):
    print('Running %s' % test)
    
    spec_path = os.path.join(test_specs_dir, test)
    with open(spec_path) as f:
        spec = yaml.load(f)
    
    test_dir = os.path.join(test_tmp, remove_extension(test))
    
    print('==> Preparing %s' % test)
    rm_rf(test_dir)
    os.mkdir(test_dir)
    run_in_dir(test_dir, spec['prepare'], shell=True)
    
    if 'config' in spec:
        config_file_name = spec.get('config_file_name', 'config')
        config_path = os.path.join(test_dir, config_file_name)
        with open(config_path, 'w') as f:
            case_config = dict(spec['config'])
            for key in ['src_repo', 'deploy_repo', 'work_prefix']:
                value = case_config[key]
                value = os.path.join(test_dir, value)
                case_config[key] = value
            yaml.dump(case_config, f)
    
    print('==> Building %s' % test)
    options = spec.get('options') or []
    build_script = os.path.join(test_root, '../buildploy.py')
    build_output_path = os.path.join(test_dir, 'build_output')
    with open(build_output_path, 'w+') as build_output_f:
        code = run_in_dir(test_tmp, [build_script, config_path] + options,
            return_code=True,
            stdout=build_output_f, stderr=subprocess.STDOUT,
            )
        if spec.get('expect_failure'):
            ok = code != 0
        else:
            ok = code == 0
        if not ok:
            if spec.get('expect_failure'):
                msg = 'Failure expected but build completed successfully'
            else:
                msg = 'Build failed'
            build_output_f.seek(0)
            output = build_output_f.read()
            print(output)
            print(msg)
            assert ok
        
        print('==> Checking %s' % test)
        if 'deploy_tree' in spec:
            run_in_dir(test_dir, ['git', 'clone', spec['config']['deploy_repo'], 'check'])
            
            check_dir = os.path.join(test_dir, 'check')
            for branch in spec['deploy_tree']:
                git_in_dir(check_dir, ['checkout', 'origin/%s' % branch])
                expected_paths = list(spec['deploy_tree'][branch])
                expected_paths.sort()
                
                start = os.path.join(test_dir, 'check')
                relative_paths = find_files_under(start)
                
                if relative_paths != expected_paths:
                    msg = "Post-build paths did not match expected list:\n"
                    msg += "Expected:\n"
                    for path in expected_paths:
                        msg += " - %s\n" % path
                    msg += "Actual:\n"
                    for path in relative_paths:
                        msg += " - %s\n" % path
                    raise AssertionError(msg)
        
        if 'check' in spec:
            run_in_dir(test_dir, spec['check'], shell=True)
        
        if 'check_output' in spec:
            build_output_f.seek(0)
            run_in_dir(test_dir, spec['check_output'], shell=True, stdin=build_output_f)

tests = discover_tests(test_specs_dir)
if len(sys.argv) > 1:
    requested_tests = sys.argv[1:]
    found_tests = []
    for test in requested_tests:
        test = os.path.basename(test)
        if '.' not in test:
            test += '.yml'
        if test not in tests:
            raise ValueError('Test not found: %s' % test)
        found_tests.append(test)
    tests = found_tests

if not os.path.exists(test_tmp):
    os.mkdir(test_tmp)

run('nosetests')

for test in tests:
    run_spec(test)
