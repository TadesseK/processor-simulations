#!/usr/bin/env bash
set -euo pipefail
submission_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
make -C "$submission_dir/branch-prediction/src" all test
cd "$submission_dir/o3-simulator"
python3 -m unittest discover -s tests -v
