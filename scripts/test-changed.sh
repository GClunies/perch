#!/bin/bash
# Run tests only for files changed vs origin/main.
# Maps src/perch/foo/bar.py -> tests/test_bar.py and includes changed test files directly.
# Falls back to running all tests if no specific test files are found.

set -euo pipefail

changed=$(git diff --name-only origin/main...HEAD -- 'src/' 'tests/' 2>/dev/null | grep -E '\.py$' || true)

if [ -z "$changed" ]; then
    echo "No Python changes to test"
    exit 0
fi

test_files=""

# Include directly changed test files
for f in $changed; do
    if [[ "$f" == tests/* ]] && [ -f "$f" ]; then
        test_files="$test_files $f"
    fi
done

# Map changed src files to their test files
for f in $changed; do
    if [[ "$f" == src/perch/* ]]; then
        # src/perch/services/git.py -> test_git_service.py (special case)
        # src/perch/widgets/foo.py -> test_foo.py
        # src/perch/app.py -> test_app.py
        basename=$(basename "$f" .py)
        for candidate in "tests/test_${basename}.py" "tests/test_${basename}_service.py"; do
            if [ -f "$candidate" ]; then
                test_files="$test_files $candidate"
            fi
        done
    fi
done

# Deduplicate
test_files=$(echo "$test_files" | tr ' ' '\n' | sort -u | tr '\n' ' ')

if [ -z "$test_files" ]; then
    echo "Changed files have no matching tests, running all tests"
    exec uv run pytest tests/ -x -q --no-cov --no-header
fi

echo "Running tests for changed files: $test_files"
exec uv run pytest $test_files -x -q --no-cov --no-header
