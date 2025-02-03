PROJECT_VERSION=$(shell python setup.py --version)

# Workaround for targets with the same name as a directory
.PHONY: doc tests

# Tests
tests:
	pytest tests

coverage:
	pytest --cov=escapy --cov-report term-missing -vv
	@-coverage-badge -f -o images/coverage.svg

branch_coverage:
	pytest --cov=escapy --cov-report term-missing --cov-branch -vv

docstring_coverage:
	interrogate -v escapy/ \
	    -e escapy/__init__.py \
	    -e escapy/encodings/__init__.py \
	    -e escapy/handlers/__init__.py \
	    --badge-style flat --generate-badge images/

# Code formatting
black:
	black escapy

# Run the service locally
run:
	python -m escapy

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
	pip pyscape uninstall

sdist: clean
	@echo Building the distribution package...
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
	prospector escapy/
	check-manifest

missing_doc:
	# Remove D213 antagonist of D212
	prospector escapy/ | grep "escapy/\|Line\|Missing docstring"

archive:
	# Create upstream src archive
	git archive HEAD --prefix='escapy-$(PROJECT_VERSION).orig/' | gzip > ../escapy-$(PROJECT_VERSION).orig.tar.gz

reset_patches:
	# Force the removal of the current patches
	-quilt pop -af

sync_manpage:
	-help2man -o debian/escapy.1 escapy

debianize: archive reset_patches
	dpkg-buildpackage -us -uc -b -d

debcheck:
	lintian -EvIL +pedantic ../escapy_*.deb
