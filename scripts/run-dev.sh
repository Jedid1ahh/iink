#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
target_dir=${CARGO_TARGET_DIR:-${CARGO_BUILD_TARGET_DIR:-target}}
node="$target_dir/release/iink-node"
if [[ ! -x "$node" ]]; then
  echo "Node binary missing. Complete bash scripts/build.sh first." >&2
  exit 1
fi
# Well-known development keys only. RPC stays on loopback; no public port forwarding.
exec "$node" --dev --tmp --name iink-dev --rpc-methods Safe --rpc-port 9944 \
  --listen-addr /ip4/127.0.0.1/tcp/30333 --no-mdns --no-prometheus
