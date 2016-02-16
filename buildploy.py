#!/usr/bin/env python

# Note: rsync must be invoked with -I argument, as it is possible for
# files in different branches to have identical size, and if the filesystem
# is quick enough the files in different branches may have identical timestamp.

import shutil
import re
import optparse
import subprocess
import os.path
import sys
import time

debug = False

py3 = sys.version_info[0] == 3

if py3:
    base_exception = Exception
else:
    base_exception = StandardError

class ConfigurationFileError(base_exception):
    pass

def output_to_string(output):
    '''Converts output of a process invoked via subprocess module,
    which is of type bytes on python 3, to a string.
    '''
    
    if py3:
        return output.decode('utf8')
    else:
        return output

def run(cmd, **kwargs):
    if debug:
        print(repr(cmd), repr(kwargs))
        sys.stdout.flush()
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
    if 'return_code' in kwargs:
        del kwargs['return_code']
        fn = subprocess.call
    else:
        fn = subprocess.check_call
    return fn(cmd, **kwargs)

def git_in_dir(dir, args, **kwargs):
    cmd = ['git',
        '--git-dir', os.path.join(dir, '.git'),
        '--work-tree', dir]
    cmd.extend(args)
    return run(cmd, **kwargs)

def checkout(local_src, build_dir, branch):
    git_in_dir(local_src, ['checkout', 'src/%s' % branch])
    run(['rsync', '-aI', '--exclude', '.git', local_src + '/', build_dir, '--delete'])

def copy(src_dir, build_dir):
    run(['rsync', '-aI', '--exclude', '.git', src_dir + '/', build_dir, '--delete'])

def run_in_dir(dir, cmd, **kwargs):
    # for the benefit of fork-less platforms
    cwd = os.getcwd()
    os.chdir(dir)
    try:
        return run(cmd, **kwargs)
    finally:
        os.chdir(cwd)

def build(build_dir, branch, merged_config):
    return run_in_dir(build_dir, merged_config.build_cmd, shell=True)

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

def load_config_file(path, format='auto'):
    if format == 'auto':
        if path.endswith('.json'):
            format = 'json'
        else:
            format = 'yaml'
    elif format not in ['yaml', 'json']:
        raise ValueError('Invalid format: %s (must be `yaml` or `json`)' % format)
    if format == 'json':
        import json
        load_fn = json.load
    else:
        import yaml
        load_fn = yaml.load
    with open(path) as f:
        try:
            config = load_fn(f)
        except ValueError as exc:
            new_exc = ConfigurationFileError('Failed to load configuration file: %s: %s: %s' % (path, exc.__class__.__name__, str(exc)))
            new_exc.__cause__ = exc
            raise new_exc
    return config

class MergedConfig(object):
    def __init__(self, config, options):
        if options.branch:
            self.branches = [options.branch]
        elif config is not None:
            self.branches = config.get('branches', ['master'])
        else:
            self.branches = ['master']
    
        for key in ['src_repo', 'work_prefix', 'deploy_repo', 'build_cmd']:
            if getattr(options, key):
                value = getattr(options, key)
            elif config is not None:
                value = config[key]
            else:
                option_name = '--' + key.replace('_', '-')
                raise ValueError('%s option or %s config value must be set' % (option_name, key))
            setattr(self, key, value)
    
        for key in ['deploy_subdir']:
            if getattr(options, key):
                value = getattr(options, key)
            elif config is not None:
                value = config.get(key, None)
            else:
                value = None
            setattr(self, key, value)
            
        self.work_tree = options.work_tree
        
        if options.push is not None:
            self.push = options.push
        elif 'push' in config:
            self.push = config['push']
        else:
            self.push = True

def main():
    usage = 'Usage: buildploy [options] path/to/config.{yaml|json}'
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--src-repo', dest='src_repo',
        help='Remote location of source repository')
    parser.add_option('--deploy-repo', dest='deploy_repo',
        help='Remote location of deployment repository')
    parser.add_option('--deploy-subdir', dest='deploy_subdir',
        help='Deploy to the specified subdirectory of deployment repo')
    parser.add_option('--work-prefix', dest='work_prefix',
        help='Path to directory in which to build')
    parser.add_option('--build-cmd', dest='build_cmd',
        help='Command to run to build the sources')
    parser.add_option('-w', '--work-tree', action='store_true', dest='work_tree',
        help='Build the work tree at source repo rather than committed changes')
    parser.add_option('-b', '--branch', action='store', dest='branch',
        help='Transform specified branch')
    parser.add_option('-p', '--push', action='store_true', dest='push',
        help='Push built tree to deployment repository (default)')
    parser.add_option('-P', '--no-push', action='store_false', dest='push',
        help='Do not push built tree to deployment repository (local build only)')
    parser.add_option('--yaml-config', action='store_true', dest='yaml_config',
        help='Interpret configuration as YAML')
    parser.add_option('--json-config', action='store_true', dest='json_config',
        help='Interpret configuration as JSON')
    parser.add_option('--discard-deploy-history', action='store_true', dest='discard_deploy_history',
        help='Discard history of branches being transformed in deployment repository')
    options, args = parser.parse_args()
    
    if options.yaml_config and options.json_config:
        raise ValueError('--yaml-config and --json-config cannot be both specified')

    if len(args) > 1:
        parser.print_help()
        exit(10)
    elif len(args) == 1:
        config_file = args[0]
        if options.yaml_config:
            format = 'yaml'
        elif options.json_config:
            format = 'json'
        else:
            format = 'auto'
    else:
        format = None
    if format is not None:
        config = load_config_file(config_file, format)
    else:
        config = {}
    
    merged_config = MergedConfig(config, options)
    del config
    
    if merged_config.work_tree:
        if len(merged_config.branches) > 1:
            raise ValueError('Using --work-tree requires specifying --branch if multiple branches are configured')
        if merged_config.src_repo[0] != '/':
            # XXX allow file:// urls also
            raise ValueError('Using --work-tree requires a filesystem path for src repo')
    
    if not os.path.exists(merged_config.work_prefix):
        os.mkdir(merged_config.work_prefix)
    
    if not options.work_tree:
        local_src = os.path.join(merged_config.work_prefix, 'src')
        if not os.path.exists(local_src):
            run(['git', 'init', local_src])
            git_in_dir(local_src, ['remote', 'add', 'src', merged_config.src_repo, '-f'])
        else:
            fetch_branches = ['src/' + branch for branch in merged_config.branches]
            git_in_dir(local_src, ['fetch', 'src'])

    build_dir = os.path.join(merged_config.work_prefix, 'build')
    if not os.path.exists(build_dir):
        os.mkdir(build_dir)

    deploy_dir = os.path.join(merged_config.work_prefix, 'deploy')
    if not os.path.exists(deploy_dir):
        run(['git', 'init', deploy_dir])
        git_in_dir(deploy_dir, ['remote', 'add', 'deploy', merged_config.deploy_repo, '-f'])
    git_in_dir(deploy_dir, ['fetch', 'deploy'])
    local_branches = git_list_local_branches(deploy_dir)
    remote_branches = git_list_remote_branches(deploy_dir)
    for branch in merged_config.branches:
        if options.work_tree:
            copy(merged_config.src_repo, build_dir)
        else:
            checkout(local_src, build_dir, branch)
        build(build_dir, branch, merged_config)
        
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
        
        if options.discard_deploy_history and not already_reset:
            git_reset_to_empty_tree(deploy_dir, branch)
        
        if merged_config.deploy_subdir is not None:
            deploy_src = os.path.join(build_dir, merged_config.deploy_subdir)
        else:
            deploy_src = build_dir
        run(['rsync', '-aI', '--exclude', '.git', deploy_src + '/', deploy_dir, '--delete'])
        git_in_dir(deploy_dir, ['add', '-u'])
        git_in_dir(deploy_dir, ['add', '.'])
        git_in_dir(deploy_dir, ['commit', '--allow-empty', '-m', 'Built at %s' % time.strftime('%a %b %d %H:%M:%S %Y %z')])

    push = merged_config.push
    if push:
        cmd = ['push', 'deploy'] + merged_config.branches
        if options.discard_deploy_history:
            cmd += ['-f']
        git_in_dir(deploy_dir, cmd)

if __name__ == '__main__':
    main()
