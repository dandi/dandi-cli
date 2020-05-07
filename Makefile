PYTHON ?= python3

all:
	echo "Nothing by default"

release-pypi:
	# better safe than sorry
	test ! -e dist
	$(PYTHON) setup.py sdist
	$(PYTHON) setup.py bdist_wheel
	twine upload dist/*
