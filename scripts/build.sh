#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash scripts/preflight.sh
if [[ "${SKIP_WASM_BUILD:-}" != "" ]]; then
  echo "Unset SKIP_WASM_BUILD: the development node needs its runtime Wasm." >&2
  exit 1
fi
mkdir -p artifacts
{
  date -u +'%Y-%m-%dT%H:%M:%SZ'
  rustc --version
  cargo --version
  df -h .
} > artifacts/build-environment.txt
# Keep memory pressure and debug artifact size down; preserve Cargo.lock.
export CARGO_BUILD_JOBS=1
export CARGO_INCREMENTAL=0
export CARGO_PROFILE_RELEASE_DEBUG=0
if [[ -x /usr/bin/time ]]; then
  /usr/bin/time -v -o artifacts/build-resources.txt \
    cargo build --locked --release --package solochain-template-node 2>&1 | tee artifacts/build.log
else
  cargo build --locked --release --package solochain-template-node 2>&1 | tee artifacts/build.log
fi
echo "Build finished. The inherited binary name remains solochain-template-node."
