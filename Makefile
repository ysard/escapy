PROJECT_VERSION=$(shell python setup.py --version)
PACKAGE_NAME=escapy

# Workaround for targets with the same name as a directory
.PHONY: doc tests

# Tests
tests:
	pytest tests

coverage:
	pytest --cov=$(PACKAGE_NAME) --cov-report term-missing -vv
	@-coverage-badge -f -o images/coverage.svg

branch_coverage:
	pytest --cov=$(PACKAGE_NAME) --cov-report term-missing --cov-branch -vv

docstring_coverage:
	interrogate -v $(PACKAGE_NAME)/ \
	    -e $(PACKAGE_NAME)/__init__.py \
	    -e $(PACKAGE_NAME)/encodings/__init__.py \
	    -e $(PACKAGE_NAME)/handlers/__init__.py \
	    --badge-style flat --generate-badge images/

# Code formatting
black:
	black $(PACKAGE_NAME)

# Run the service locally
run:
	python -m $(PACKAGE_NAME)

clean:
	rm -rf *.egg-info
	python setup.py clean --all
	-$(MAKE) -C ./doc clean

doc:
	$(MAKE) -C ./doc html

# development & release cycle
fullrelease:
	@# From zest.releaser
	@echo DO NOT forget to update debian/changelog version before!
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
	prospector $(PACKAGE_NAME)/
	check-manifest

missing_doc:
	# Remove D213 antagonist of D212
	prospector $(PACKAGE_NAME)/ | grep "$(PACKAGE_NAME)/\|Line\|Missing docstring"

archive:
	# Create upstream src archive
	git archive HEAD --prefix='$(PACKAGE_NAME)-$(PROJECT_VERSION).orig/' | gzip > ../$(PACKAGE_NAME)-$(PROJECT_VERSION).orig.tar.gz

reset_patches:
	# Force the removal of the current patches
	-quilt pop -af

sync_manpage:
	-help2man -o debian/$(PACKAGE_NAME).1 $(PACKAGE_NAME)

debianize: archive reset_patches
	dpkg-buildpackage -us -uc -b -d

debcheck:
	lintian -EvIL +pedantic ../$(PACKAGE_NAME)_*.deb
