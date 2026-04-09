#!/usr/bin/env bash
set -e

# Run ruff
echo "Running ruff..."
ruff format src
ruff check --fix src || echo "Ruff found issues"


echo "Linting complete."
