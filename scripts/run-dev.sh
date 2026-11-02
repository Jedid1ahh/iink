#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
node=./target/release/solochain-template-node
if [[ ! -x "$node" ]]; then
  echo "Node binary missing. Complete bash scripts/build.sh first." >&2
  exit 1
fi
# Well-known development keys only. RPC stays on loopback; no public port forwarding.
exec "$node" --dev --tmp --name iink-dev --rpc-methods Safe --rpc-port 9944
