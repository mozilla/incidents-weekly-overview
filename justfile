@_default:
    just --list

test:
    uv run pytest tests/

lint:
    uv run ruff check src/ tests/

format:
    uv run ruff format src/ tests/
