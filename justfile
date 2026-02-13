@_default:
    just --list

lint:
    uv run ruff check scripts/*.py

format:
    uv run ruff format scripts/*.py
