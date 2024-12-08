PROJECT_VERSION=$(shell python setup.py --version)

# Workaround for targets with the same name as a directory
.PHONY: doc tests

# Tests
tests:
	pytest tests
	@#python setup.py test --addopts "tests escparser -vv"

coverage:
	pytest --cov=escparser --cov-report term-missing -vv
	@#python setup.py test --addopts "--cov escparser tests"
	@-coverage-badge -f -o images/coverage.svg

branch_coverage:
	pytest --cov=escparser --cov-report term-missing --cov-branch -vv

docstring_coverage:
	interrogate -v escparser/ \
	    -e escparser/__init__.py \
	    -e escparser/handlers/__init__.py \
	    --badge-style flat --generate-badge images/

# Code formatting
black:
	black escparser

# Run the service locally
run:
	python -m escparser

clean:
	rm -rf eps pcl pdf png raw txt txt_jobs hpgl ps txt_stream dist csv escparser.egg-info
	-$(MAKE) -C ./doc clean

doc:
	$(MAKE) -C ./doc html

# development & release cycle
fullrelease:
	fullrelease
install:
	@# Replacement for python setup.py develop which doesn't support extra_require keyword.
	@# Install a project in editable mode.
	pip install -e .[dev]
uninstall:
	pip escparser uninstall

sdist:
	@echo Building the distribution package...
	python setup.py sdist

upload: clean sdist
	python setup.py bdist_wheel
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
	git archive HEAD --prefix='libre-printer-$(PROJECT_VERSION).orig/' | gzip > ../libre-printer-$(PROJECT_VERSION).orig.tar.gz

reset_patches:
	# Force the removal of the current patches
	-quilt pop -af

debianize: archive reset_patches
	dpkg-buildpackage -us -uc -b -d

debcheck:
	lintian -EvIL +pedantic ../libre-printer_*.deb

