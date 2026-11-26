.PHONY: install test lint run backtest benchmark benchmark-all audit

install:
	pip install -r requirements.txt

test:
	pytest -q

lint:
	ruff check . --select E9,F --extend-exclude frontend
	node --check frontend/app.js

run:
	uvicorn backend.main:app --reload

backtest:
	python -m backend.app.cli backtest --window-end 1 --out backtest_curated.json

benchmark:
	python -m backend.app.cli backtest --dataset fomc --window-end 1 --out backtest_fomc.json
	python -m backend.app.cli backtest --dataset curated --window-end 1 --out backtest_curated.json

benchmark-all:
	python scripts/run_benchmarks.py

audit:
	python scripts/point_in_time_audit.py
	python scripts/hallucination_audit.py
	python scripts/kp_test.py
	python scripts/cross_sectional_eval.py
