#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
# Recover a user-installed Rust toolchain in terminals opened before installation.
if [[ -f "$HOME/.cargo/env" ]]; then
  source "$HOME/.cargo/env"
fi
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
if (( missing )); then
  echo "In Codespaces: pull main, then use Codespaces: Rebuild Container and choose Full Rebuild." >&2
  echo "The project's development image installs these prerequisites automatically." >&2
fi
free_kb=$(df -Pk . | awk 'NR==2 {print $4}')
mem_kb=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
printf 'Available disk: %s KiB\nHost memory: %s KiB\n' "$free_kb" "$mem_kb"
echo "Container limits may be lower than reported host memory. Check Codespaces machine settings."
# Conservative experiment thresholds, not proven minimum requirements.
if (( free_kb < 20 * 1024 * 1024 )); then
  awk -v available="$free_kb" 'BEGIN {printf "Available disk: %.2f GiB; %.2f GiB below the 20 GiB starting-space policy.\n", available/1048576, (20971520-available)/1048576}' >&2
  echo "This is an unbenchmarked precaution, not a measured compiler minimum." >&2
  echo "A Codespaces Full Rebuild clears old image caches. If space remains low, inspect df/du output before deleting files." >&2
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
