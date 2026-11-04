#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

repo=$PWD
frontier="$(dirname "$repo")/iink-frontier-2603"
revision=baf505d8feeaaa0ba636a003faa49e4ad897b592
upstream=https://github.com/polkadot-evm/frontier.git
node="$frontier/target/release/frontier-template-node"

case "${1:-}" in
  build)
    for tool in git rustup python3 clang cc pkg-config protoc; do
      if ! command -v "$tool" >/dev/null; then
        echo "Missing $tool. Use IINK's Codespaces development environment." >&2
        exit 1
      fi
    done
    python3 scripts/guard-build-disk.py
    if [[ ! -e "$frontier" ]]; then
      git init "$frontier"
    fi
    if [[ ! -d "$frontier/.git" ]]; then
      echo "Expected a Frontier checkout at $frontier." >&2
      exit 1
    fi
    if [[ -n "$(git -C "$frontier" status --porcelain --untracked-files=no)" ]]; then
      echo "Save the tracked changes in $frontier before building." >&2
      exit 1
    fi
    if ! git -C "$frontier" cat-file -e "$revision^{commit}" 2>/dev/null; then
      git -C "$frontier" fetch --depth 1 "$upstream" "$revision"
    fi
    git -C "$frontier" switch --detach "$revision"
    rustup toolchain install 1.88.0 --profile minimal \
      --component rust-src --target wasm32v1-none

    mkdir -p "$repo/artifacts"
    cd "$frontier"
    export CARGO_TARGET_DIR="$frontier/target"
    export CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 CARGO_PROFILE_RELEASE_DEBUG=0
    export CARGO_NET_GIT_FETCH_WITH_CLI=true
    unset SKIP_WASM_BUILD
    python3 "$repo/scripts/guard-build-disk.py" \
      cargo +1.88.0 build --locked --release --package frontier-template-node \
      2>&1 | tee "$repo/artifacts/frontier-build.log"
    ;;
  run)
    if [[ ! -x "$node" ]]; then
      echo "Frontier binary missing. Run bash scripts/frontier-spike.sh build first." >&2
      exit 1
    fi
    exec "$node" --dev --tmp --rpc-port 9966 --rpc-methods Safe \
      --listen-addr /ip4/127.0.0.1/tcp/30366 --no-mdns --no-prometheus
    ;;
  *)
    echo "Usage: bash scripts/frontier-spike.sh build|run" >&2
    exit 2
    ;;
esac
