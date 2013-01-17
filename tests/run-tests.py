#!/usr/bin/env python

import yaml
import os
import os.path
import subprocess

tests = ['specs/basic.yaml', 'specs/deploy_subdir.yaml']

def run(cmd, **kwargs):
    print repr(cmd), repr(kwargs)
    subprocess.check_call(cmd, **kwargs)


test_root = os.path.dirname(__file__)
test_root = os.path.realpath(test_root)
test_tmp = os.path.join(test_root, 'tmp')

if not os.path.exists(test_tmp):
    os.mkdir(test_tmp)

for test in tests:
    path = os.path.join(test_root, test)
    with open(path) as f:
        spec = yaml.load(f)
    
    run('cd %s && rm -rf scratch && mkdir scratch && cd scratch && (%s)' %
        (test_tmp, spec['prepare']), shell=True)
    
    if 'config' in spec:
        config_path = os.path.join(test_tmp, 'scratch/config')
        with open(config_path, 'w') as f:
            print spec['config']
            case_config = dict(spec['config'])
            for key in ['src_repo', 'deploy_repo', 'work_prefix']:
                value = case_config[key]
                value = os.path.join(test_tmp, 'scratch', value)
                case_config[key] = value
            yaml.dump(case_config, f)
    
    run('cd %s && ../../build scratch/config' % (test_tmp), shell=True)
    
    run('cd %s && git clone %s check' % (
        os.path.join(test_tmp, 'scratch'),
        spec['config']['deploy_repo'],
    ), shell=True)
    
    relative_paths = []
    start = os.path.join(test_tmp, 'scratch/check')
    for root, dirs, files in os.walk(start):
        if '.git' in dirs:
            dirs.remove('.git')
        for file in files:
            relative_paths.append(os.path.join(root, file)[len(start)+1:])
    relative_paths.sort()
    
    expected_paths = list(spec['deploy_tree']['master'])
    expected_paths.sort
    
    assert relative_paths == expected_paths
