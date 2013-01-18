#!/usr/bin/env python

import re
import optparse
import subprocess
import os.path
import sys
import yaml
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

def build(build_dir, branch, config):
    run('cd %s && (%s)' % (build_dir, config['build_cmd']), shell=True)

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

def main():
    parser = optparse.OptionParser()
    parser.add_option('-p', '--push', action='store_true', dest='push')
    parser.add_option('-P', '--no-push', action='store_false', dest='push')
    parser.add_option('--reset-deploy-repo', action='store_true', dest='reset_deploy_repo')
    options, args = parser.parse_args()

    config_file = sys.argv[1]
    with open(config_file) as f:
        config = yaml.load(f)

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
    for branch in branches:
        if branch != 'master':
            run('cd %s && git checkout %s || git branch %s master' % (deploy_dir, branch, branch), shell=True)
        elif branch in git_list_remote_branches(deploy_dir):
            run('cd %s && git checkout %s && git reset --hard deploy/%s' % (deploy_dir, branch, branch), shell=True)

    for branch in branches:
        git_in_dir(local_src, ['checkout', branch])
        #checkout(build_dir, branch)
        copy(build_dir, branch, config)
        build(build_dir, branch, config)
        if options.reset_deploy_repo:
            # https://wincent.com/wiki/Creating_independent_branches_with_Git
            git_in_dir(deploy_dir, ['symbolic-ref', 'HEAD', 'refs/heads/newbranch'])
            run(['rm', '-f', os.path.join(deploy_dir, 'git/index')])
            run('cd %s && rm -rf `git ls-files -o`' % deploy_dir, shell=True)
            git_in_dir(deploy_dir, ['commit', '--allow-empty', '-m', 'New tree'])
        run('cd %s && if git status |grep -q "# Initial commit"; then git commit --allow-empty -m "Initial commit"; fi' % deploy_dir, shell=True)
        git_in_dir(deploy_dir, ['checkout', branch])
        if options.reset_deploy_repo:
            git_in_dir(deploy_dir, ['reset', '--hard', 'newbranch'])
            git_in_dir(deploy_dir, ['branch', '-D', 'newbranch'])
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
