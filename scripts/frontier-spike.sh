#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

repo=$PWD
frontier="$(dirname "$repo")/iink-frontier-2603"
revision=baf505d8feeaaa0ba636a003faa49e4ad897b592
upstream=https://github.com/polkadot-evm/frontier.git
node="$frontier/target/release/frontier-template-node"
ledger_node="$frontier/target/release/iink-frontier-ledger-node"

ledger_revision() (
    index_dir=$(mktemp -d)
    trap 'rm -f "$index_dir/index"; rmdir "$index_dir"' EXIT
    export GIT_INDEX_FILE="$index_dir/index"
    git read-tree "$revision"
    git apply --cached --whitespace=error "$repo/experiments/frontier-ledger/frontier.patch"
    tree=$(git write-tree)
    GIT_AUTHOR_DATE=$(git show -s --format=%cI "$revision")
    export GIT_AUTHOR_DATE GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"
    git -c user.name=IINK -c user.email=iink-ledger@example.invalid \
      commit-tree --no-gpg-sign "$tree" -p "$revision" -m 'Apply the IINK shared-ledger experiment'
)

mode=${1:-}
case "$mode" in
  build|build-ledger)
    for tool in git rustup python3 clang cc pkg-config protoc flock; do
      if ! command -v "$tool" >/dev/null; then
        echo "Missing $tool. Use IINK's Codespaces development environment." >&2
        exit 1
      fi
    done
    python3 scripts/guard-build-disk.py
    exec 9>"$frontier.build.lock"
    if ! flock -n 9; then
      echo "Another Frontier build is using $frontier." >&2
      exit 1
    fi
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
    build_revision=$revision
    bin=frontier-template-node
    log=frontier-build.log
    if [[ "$mode" == build-ledger ]]; then
      build_revision=$(cd "$frontier" && ledger_revision)
      bin=iink-frontier-ledger-node
      log=frontier-ledger-build.log
    fi
    git -C "$frontier" switch --detach "$build_revision"
    rustup toolchain install 1.88.0 --profile minimal \
      --component rust-src --target wasm32v1-none

    mkdir -p "$repo/artifacts"
    cd "$frontier"
    export CARGO_TARGET_DIR="$frontier/target"
    export CARGO_BUILD_JOBS=1 CARGO_INCREMENTAL=0 CARGO_PROFILE_RELEASE_DEBUG=0
    export CARGO_NET_GIT_FETCH_WITH_CLI=true
    unset SKIP_WASM_BUILD
    python3 "$repo/scripts/guard-build-disk.py" \
      cargo +1.88.0 build --locked --release --package frontier-template-node --bin "$bin" \
      2>&1 | tee "$repo/artifacts/$log"
    ;;
  run)
    if [[ ! -x "$node" ]]; then
      echo "Frontier binary missing. Run bash scripts/frontier-spike.sh build first." >&2
      exit 1
    fi
    exec "$node" --dev --tmp --rpc-port 9966 --rpc-methods Safe \
      --listen-addr /ip4/127.0.0.1/tcp/30366 --no-mdns --no-prometheus
    ;;
  run-ledger)
    if [[ ! -x "$ledger_node" ]]; then
      echo "Ledger lab binary missing. Run bash scripts/frontier-spike.sh build-ledger first." >&2
      exit 1
    fi
    exec "$ledger_node" --dev --tmp --rpc-port 9967 --rpc-methods Safe \
      --listen-addr /ip4/127.0.0.1/tcp/30367 --no-mdns --no-prometheus
    ;;
  *)
    echo "Usage: bash scripts/frontier-spike.sh build|run|build-ledger|run-ledger" >&2
    exit 2
    ;;
esac
