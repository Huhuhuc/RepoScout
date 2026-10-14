#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.lock.txt
if [[ ! -f .env ]]; then cp .env.example .env; fi
echo 'RepoScout: http://127.0.0.1:8011'
exec .venv/bin/python -m uvicorn reposcout.app:app --host 127.0.0.1 --port 8011
