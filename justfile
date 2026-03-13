@_default:
    just --list

test:
    uv run pytest tests/

lint:
    uv run ruff check src/ tests/

format:
    uv run ruff format src/ tests/

typecheck:
    uv run ty check src/iim/

check:
    uv run ruff format --check src/ tests/
    just lint
    just test
    just typecheck
