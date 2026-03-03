@_default:
    just --list

test:
    uv run pytest tests/

lint:
    uv run ruff check scripts/*.py

format:
    uv run ruff format scripts/*.py
