PYTHON ?= python3

.PHONY: check check-unit check-integration

check: check-unit check-integration

check-unit:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

check-integration:
	$(PYTHON) -m unittest discover -s tests/integration -p 'test_*.py' -v
