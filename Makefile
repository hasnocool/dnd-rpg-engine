# Makefile
.PHONY: install test coverage compile demo serve clean

install:
	python -m pip install -e '.[all,dev]'

test:
	pytest -q

coverage:
	pytest --cov=dnd_rpg_engine --cov-report=term-missing

compile:
	python -m compileall -q src

demo:
	rpg-engine demo --mode hybrid --seconds 20 --timeout 5

serve:
	rpg-engine serve --host 127.0.0.1 --port 8000

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov build dist *.egg-info
