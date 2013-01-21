all: doc test

doc: build/README.html

build/README.html: build README.md
	markdown_py -f build/README.html README.md

build:
	mkdir build

test:
	python tests/run-tests.py

spec-index:
	python tests/build-spec-index.py
