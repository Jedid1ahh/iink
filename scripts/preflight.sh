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
mem_kb=$(awk '/MemTotal:/ {print $2}' /proc/meminfo)
printf 'Host memory: %s KiB\n' "$mem_kb"
echo "Container limits may be lower than reported host memory. Check Codespaces machine settings."
if (( mem_kb < 7 * 1024 * 1024 )); then
  echo "Less than about 7 GiB host RAM: use a larger remote environment." >&2
  missing=1
fi
if (( missing )); then exit 1; fi
python3 scripts/guard-build-disk.py
rustc --version
cargo --version
echo "Preflight passed. This does not check account billing or guarantee that compilation fits."
