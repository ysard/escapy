PROJECT_VERSION=$(shell python setup.py --version)

# Workaround for targets with the same name as a directory
.PHONY: doc tests

# Tests
tests:
	pytest tests

coverage:
	pytest --cov=escparser --cov-report term-missing -vv
	@-coverage-badge -f -o images/coverage.svg

branch_coverage:
	pytest --cov=escparser --cov-report term-missing --cov-branch -vv

docstring_coverage:
	interrogate -v escparser/ \
	    -e escparser/__init__.py \
	    -e escparser/encodings/__init__.py \
	    -e escparser/handlers/__init__.py \
	    --badge-style flat --generate-badge images/

# Code formatting
black:
	black escparser

# Run the service locally
run:
	python -m escparser

clean:
	rm -rf *.egg-info
	python setup.py clean --all
	-$(MAKE) -C ./doc clean

doc:
	$(MAKE) -C ./doc html

# development & release cycle
fullrelease:
	fullrelease
install:
	@# Install a project in editable mode.
	pip install -e .[dev]
uninstall:
	pip escparser uninstall

sdist: clean
	@echo Building the distribution package...
	cp escparser.conf escparser/data/ # TODO delete this & move file
	python -m build --sdist

wheel: clean
	@echo Building the wheel package...
	python -m build --wheel

upload:
	@echo Building the distribution + wheel packages...
	python -m build
	twine upload dist/* -r pypi

check_setups:
	pyroma .

check_code:
	prospector escparser/
	check-manifest

missing_doc:
	# Remove D213 antagonist of D212
	prospector escparser/ | grep "escparser/\|Line\|Missing docstring"

archive:
	# Create upstream src archive
	git archive HEAD --prefix='escparser-$(PROJECT_VERSION).orig/' | gzip > ../escparser-$(PROJECT_VERSION).orig.tar.gz

reset_patches:
	# Force the removal of the current patches
	-quilt pop -af

debianize: archive reset_patches
	dpkg-buildpackage -us -uc -b -d

debcheck:
	lintian -EvIL +pedantic ../escparser_*.deb
