#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1

python3 -m unittest discover -s "$skill_dir/tests" -p 'test_*.py' -v
python3 "$skill_dir/scripts/verify-wechat-compat.py" \
  "$skill_dir/assets/examples/blue-minimal.html"
python3 "$skill_dir/scripts/verify-output-contract.py" \
  "$skill_dir/assets/examples/blue-minimal.html"
python3 "$skill_dir/scripts/verify-wechat-compat.py" \
  "$skill_dir/assets/examples/dark-tech.html"
python3 "$skill_dir/scripts/verify-output-contract.py" \
  "$skill_dir/assets/examples/dark-tech.html"
