#!/usr/bin/env bash
# Regenerate tests/fixtures/eval_baseline.json with exactly the flags CI uses.
set -euo pipefail
for pack in health_stress manufacturing; do
  uv run leankg eval --domain "$pack" --setup B --fixtures --llm none \
    --skip gliner --skip embed \
    --baseline tests/fixtures/eval_baseline.json --update-baseline
done
