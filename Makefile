.PHONY: install test lint run backtest benchmark

install:
	pip install -r requirements.txt

test:
	pytest -q

lint:
	ruff check . --select E9,F --extend-exclude frontend

run:
	uvicorn backend.main:app --reload

backtest:
	python -m backend.app.cli backtest --window-end 1 --out backtest_curated.json

benchmark:
	python -m backend.app.cli backtest --dataset fomc --window-end 1 --out backtest_fomc.json
	python -m backend.app.cli backtest --dataset curated --window-end 1 --out backtest_curated.json
