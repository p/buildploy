# buildploy - build projects into deployment repositories

## Background

Since 2005 or so, when Capistrano was invented, the deployment workflow
that worked for almost everyone has been as follows:

1. Put source code into version control.
2. Connect to server(s) via SSH.
3. Check source code out of version control.
4. Perform any build steps needed.
5. Symlink and restart.

This works fine for projects that don't do much building in step 4.
However this workflow has some disadvantages:

1. All tools needed for building must be installed on all servers.
The most famous blunder related to this was perhaps when Rails required
a JavaScript interpreter on all servers to compile CoffeeScript assets.
2. Build step is performed by all servers, when most of the time
the operation is exactly identical from one server to the next.
3. If the build step is CPU-intensive, application performance suffers
while a new version is being deployed.
4. There is no record of the code that was actually being used by
the application after old releases are cleaned up.

The solution that is often adopted is to place generated files into
(the one and only) source repository. This fixes most of the above
issues, but at the cost of creating new ones:

1. Rebuilding generated files on every commit is unnecessary, therefore
there needs to be tracking of whether generated files are up to date.
2. Because of this, generated files are frequently out of date. This
may cause confusion.
3. Source code repository is littered with files that most of the time
nobody cares about.

## Deployment Repository

The alternative is to maintain a separate repository for built code
that is ready to be deployed. This way all generated files go into the
deployment repository, the files are generated only when a deployment
is performed, and it is trivial to maintain history of deployed code.

The only difficulty with this approach is that two repositories must
be maintained.

## Buildploy

Buildploy automates management of the deployment repositories.
It uses configuration specified in the source repository, along with
the source repository itself, to create all necessary files in
deployment repository. The deployment workflow becomes:

1. Put source code into version control.
2. Invoke buildploy to create deployable version of the source code.
3. Connect to server(s) via SSH.
4. Check out deployable version of the source code from deployment repository.
5. Symlink and restart.

## Bonus Features

Since buildploy permits arbitrary transformations, this can be exploited
to further optimize deployment prorcess:

1. If original source files are translated into either other source files
or binary files, and original files are not used by the running application,
then original files may be deleted during the build phase to make deployment
process quicker.
2. Artwork and similar data files that are not directly used by the application
but are used by developers working on the code may be similarly removed
prior to deployment.
3. Precompilation that was considered cumbersome to perform on
production machines during deployment becomes much less problematic
to perform during the dedicated build phase.

## Usage

To use buildploy, you need:

1. Your original source repository.
2. A second, empty repository that will be used for deployable trees.
3. A configuration file informing buildploy of where the repositories are
and how the project should be built.

Configuration files can be in YAML or JSON format.
YAML configuration files look like this:

	src_repo: git@github.com:foo/foo.git
	deploy_repo: git@github.com:foo/foo-deploy.git
	work_prefix: /home/build/foo-build
	build_cmd: make

The required items are:

- ``src_repo`` - The source repository. This can be any repository url or
path accepted by Git, including a local filesystem path.
- ``deploy_repo`` - Where deployable trees are to be pushed.
- ``work_prefix`` - Path to a local directory that is used for building
deployable trees.
- ``build_cmd`` - Command used to perform the build.

Then, execute ``buildploy path/to/config.yaml``.

JSON configuration files use the same schema but serialized in JSON.
Buildploy detects configuration file type via its extension: .yaml and .yml
files are considered YAML files, .json files are considered JSON files.
The default for other extensions is currently YAML, although an automatic
detection facility may be added in the future.

JSON is part of Python standard library as of 2.6, and when using it
buildploy has no dependencies. Using YAML requires installing PyYAML.

## Branches

By default buildploy transforms the master branch of the source repository.
Alternate branches may be specified as follows:

	branches:
	  - staging
	  - production

If multiple branches are specified in the configuration file, they will
be all transformed. To transform a single branch use ``-b`` command line
argument.

## Deploying A Subdirectory Only

It is possible to deploy a subdirectory of the entire repository:

	deploy_subdir: build

The specified subdirectory will become the root of the deployable tree.

## Requirements

Buildploy is written in Python and tested on Python 2.6, 2.7, 3.2 and 3.3.

## Tests

Buildploy has a test suite. Execute

	make test

to run it.

The test suite is disk I/O intensive but does not need much space. If
you have a memory-backed /tmp partition you may want to use it as follows:

	mkdir /tmp/buildploy-tests
	ln -s /tmp/buildploy-tests tests/tmp

*Caution:* the test suite issues rather aggressive commands, including
extensive usage of `rm -rf`. To minimize the possibility of accidental data
loss, the test suite is designed to be run by an unprivileged user account.

There are two ways of accomplishing this:

1. Symlink tests/tmp to a directory owned by the unprivileged user, and
run the test suite as that user.
2. Specify TESTS_TMP environment variable as follows:

	TESTS_TMP=/tmp/buildploy-tests make test

<a href="https://travis-ci.org/p/buildploy"><img src="https://api.travis-ci.org/p/buildploy.png" alt="Travis build status" /></a>

## License

Buildploy is licensed under the 2 clause BSD license.
