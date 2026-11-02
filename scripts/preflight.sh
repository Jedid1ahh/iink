#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ "$(uname -s)" != Linux ]]; then
  echo "Use the remote Linux development environment for this starter." >&2
  exit 1
fi
missing=0
for tool in git rustup cargo rustc clang cc make pkg-config protoc python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing prerequisite: $tool" >&2
    missing=1
  fi
done
free_kb=$(df -Pk . | awk 'NR==2 {print $4}')
mem_kb=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
printf 'Available disk: %s KiB\nHost memory: %s KiB\n' "$free_kb" "$mem_kb"
echo "Container limits may be lower than reported host memory. Check Codespaces machine settings."
# Conservative experiment thresholds, not proven minimum requirements.
if (( free_kb < 20 * 1024 * 1024 )); then
  echo "Less than 20 GiB free: do not start this build experiment yet." >&2
  missing=1
fi
if (( mem_kb < 7 * 1024 * 1024 )); then
  echo "Less than about 7 GiB host RAM: use a larger remote environment." >&2
  missing=1
fi
if (( missing )); then exit 1; fi
rustc --version
cargo --version
echo "Preflight passed. This does not check account billing or guarantee that compilation fits."
