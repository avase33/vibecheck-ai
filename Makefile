.PHONY: install dev test lint demo seed serve docker clean

install:
	pip install -e .

dev:
	pip install -e ".[server,dev]"

test:
	pytest --cov=vibecheck --cov-report=term-missing

lint:
	ruff check vibecheck scripts

demo:
	python -m vibecheck demo --count 2000 --top 10

seed:
	python scripts/generate_mock_tickets.py -n 5000

serve:
	vibecheck serve

docker:
	docker compose up --build

clean:
	rm -f vibecheck.db ci.db *.jsonl
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info
