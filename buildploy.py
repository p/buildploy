#!/usr/bin/env python

import shutil
import re
import optparse
import subprocess
import os.path
import sys
import time

py3 = sys.version_info[0] == 3

def output_to_string(output):
    '''Converts output of a process invoked via subprocess module,
    which is of type bytes on python 3, to a string.
    '''
    
    if py3:
        return output.decode('utf8')
    else:
        return output

def run(cmd, **kwargs):
    print(repr(cmd), repr(kwargs))
    if 'return_stdout' in kwargs:
        return_stdout = kwargs.pop('return_stdout')
        if return_stdout:
            try:
                from cStringIO import StringIO
            except ImportError:
                from io import StringIO
            io = StringIO()
            kwargs['stdout'] = subprocess.PIPE
            p = subprocess.Popen(cmd, **kwargs)
            stdout, stderr = p.communicate()
            if p.returncode != 0:
                raise subprocess.CalledProcessError('Command failed with code %d' % p.returncocde)
            return stdout
    subprocess.check_call(cmd, **kwargs)

def git_in_dir(dir, args, **kwargs):
    cmd = ['git',
        '--git-dir', os.path.join(dir, '.git'),
        '--work-tree', dir]
    cmd.extend(args)
    return run(cmd, **kwargs)

def checkout(build_dir, branch):
    git_in_dir(local_src, ['checkout', branch])
    run(['rsync', '-a', local_src + '/', build_dir, '--delete'])

def copy(build_dir, branch, config):
    run(['rsync', '-a', '--exclude', '.git', config['src_repo'] + '/', build_dir, '--delete'])

def run_in_dir(dir, cmd, **kwargs):
    # for the benefit of fork-less platforms
    cwd = os.getcwd()
    os.chdir(dir)
    try:
        run(cmd, **kwargs)
    finally:
        os.chdir(cwd)

def build(build_dir, branch, config):
    run_in_dir(build_dir, config['build_cmd'], shell=True)

def git_list_local_branches(dir):
    branches = []
    output = git_in_dir(dir, ['branch'], return_stdout=True)
    output = output_to_string(output)
    for line in output.split("\n"):
        line = line.strip()
        match = re.match(r'(\*\s+)?(\S+)', line)
        if match:
            branches.append(match.group(2))
    return branches

def git_list_remote_branches(dir):
    branches = []
    output = git_in_dir(dir, ['branch', '-r'], return_stdout=True)
    output = output_to_string(output)
    for line in output.split("\n"):
        line = line.strip()
        match = re.match(r'(\S+)', line)
        if match:
            branches.append(match.group(1))
    return branches

def rm_f(path):
    if os.path.exists(path):
        os.unlink(path)

def rm_rf(path):
    '''Removes specified file or directory tree.
    '''
    
    if not os.path.exists(path):
        return
    
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.unlink(path)

def git_reset_to_empty_tree(deploy_dir, branch):
    # https://wincent.com/wiki/Creating_independent_branches_with_Git
    git_in_dir(deploy_dir, ['symbolic-ref', 'HEAD', 'refs/heads/newbranch'])
    index_path = os.path.join(deploy_dir, '.git/index')
    rm_f(index_path)
    output = git_in_dir(deploy_dir, ['ls-files', '-o'], return_stdout=True)
    files = output_to_string(output)
    for file in files.split("\n"):
        file = file.strip()
        if file:
            rm_rf(os.path.join(deploy_dir, file))
    git_in_dir(deploy_dir, ['commit', '--allow-empty', '-m', 'New tree'])
    # XXX test both paths
    if branch in git_list_local_branches(deploy_dir):
        git_in_dir(deploy_dir, ['checkout', branch])
        git_in_dir(deploy_dir, ['reset', '--hard', 'newbranch'])
    else:
        git_in_dir(deploy_dir, ['checkout', '-b', branch])
    git_in_dir(deploy_dir, ['branch', '-d', 'newbranch'])

def load_config_file(path):
    if path.endswith('.json'):
        import json
        load_fn = json.load
    else:
        import yaml
        load_fn = yaml.load
    with open(path) as f:
        config = load_fn(f)
    return config

def main():
    parser = optparse.OptionParser()
    parser.add_option('-p', '--push', action='store_true', dest='push')
    parser.add_option('-P', '--no-push', action='store_false', dest='push')
    parser.add_option('--reset-deploy-repo', action='store_true', dest='reset_deploy_repo')
    options, args = parser.parse_args()

    config_file = sys.argv[1]
    config = load_config_file(config_file)

    branches = config.get('branches', ['master'])

    local_src = os.path.join(config['work_prefix'], 'src')
    if not os.path.exists(local_src):
        run(['git', 'init', local_src])
        git_in_dir(local_src, ['remote', 'add', 'src', config['src_repo'], '-f'])
    else:
        fetch_branches = ['src/' + branch for branch in branches]
        git_in_dir(local_src, ['fetch', 'src'])

    build_dir = os.path.join(config['work_prefix'], 'build')
    if not os.path.exists(build_dir):
        os.mkdir(build_dir)

    deploy_dir = os.path.join(config['work_prefix'], 'deploy')
    if not os.path.exists(deploy_dir):
        run(['git', 'init', deploy_dir])
        git_in_dir(deploy_dir, ['remote', 'add', 'deploy', config['deploy_repo'], '-f'])
    local_branches = git_list_local_branches(deploy_dir)
    remote_branches = git_list_remote_branches(deploy_dir)
    for branch in branches:
        copy(build_dir, branch, config)
        build(build_dir, branch, config)
        
        # Initial branch checkout:
        # 1. Branch exists in local deploy repo - check it out
        # 1.1. Branch also exists in remote deploy repo - hard reset to remote
        # 1.2. Branch does not exist in remote - do nothing, will create
        #      when pushing
        # 2. Branch does not exist in local deploy repo:
        # 2.1. Branch exists in remote deploy repo - create a new local branch
        #      tracking the corresponding remote branch
        # 2.2. Branch does not exist in remote:
        #      We can start with current master or an empty tree.
        #      Let's start with master if it exists, otherwise an empty tree.
        # XXX test all paths
        already_reset = False
        if branch in local_branches:
            git_in_dir(deploy_dir, ['checkout', branch])
            if 'deploy/%s' % branch in remote_branches:
                git_in_dir(deploy_dir, ['reset', '--hard', 'deploy/%s' % branch])
        else:
            if 'deploy/%s' % branch in remote_branches:
                git_in_dir(deploy_dir, ['checkout', '-b', branch, '--track', 'deploy/%s' % branch])
            else:
                # no local and no remote branch
                done = False
                if branch != 'master':
                    # attempt to copy from master
                    have_master = False
                    if 'master' in local_branches:
                        git_in_dir(deploy_dir, ['checkout', 'master'])
                        if 'master' in remote_branches:
                            git_in_dir(deploy_dir, ['reset', '--hard', 'deploy/master'])
                        have_master = True
                    elif 'master' in remote_branches:
                        git_in_dir(deploy_dir, ['checkout', '-b', 'master', '--track', 'deploy/master'])
                        have_master = True
                    if have_master:
                        # copies master
                        git_in_dir(deploy_dir, ['checkout', '-b', branch])
                        done = True
                if not done:
                    # no master to copy from or we are dealing with master
                    # branch itself; create an empty tree initial commit
                    git_reset_to_empty_tree(deploy_dir, branch)
                    already_reset = True
        
        if options.reset_deploy_repo and not already_reset:
            git_reset_to_empty_tree(deploy_dir, branch)
        
        if 'deploy_subdir' in config:
            deploy_src = os.path.join(build_dir, config['deploy_subdir'])
        else:
            deploy_src = build_dir
        run(['rsync', '-a', '--exclude', '.git', deploy_src + '/', deploy_dir, '--delete'])
        git_in_dir(deploy_dir, ['add', '-u'])
        git_in_dir(deploy_dir, ['add', '.'])
        git_in_dir(deploy_dir, ['commit', '--allow-empty', '-m', 'Built at %s' % time.time()])

    push = config.get('push', True)
    if options.push is not None:
        push = options.push
    if push:
        cmd = ['push', 'deploy'] + branches
        if options.reset_deploy_repo:
            cmd += ['-f']
        git_in_dir(deploy_dir, cmd)

if __name__ == '__main__':
    main()
