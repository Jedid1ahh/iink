#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

validator=${1:-}
case "$validator" in
  alice) network_port=30333; rpc_port=9944 ;;
  bob) network_port=30334; rpc_port=9945 ;;
  *) echo "Usage: bash scripts/run-local-validator.sh alice|bob" >&2; exit 2 ;;
esac

target_dir=${CARGO_TARGET_DIR:-${CARGO_BUILD_TARGET_DIR:-target}}
node="$target_dir/release/iink-node"
if [[ ! -x "$node" ]]; then
  echo "Node binary missing. Complete bash scripts/build.sh first." >&2
  exit 1
fi

base_path="$(dirname "$PWD")/iink-wallet-local-$validator"
key_path="$base_path/chains/iink_wallet_local/network/secret_ed25519"
bootnodes=()
if [[ "$validator" == bob ]]; then
  if ! peer_id=$(cd scripts && python3 -c 'from check_rpc import rpc; print(rpc("system_localPeerId"))'); then
    echo "Start Alice and wait for her RPC server on port 9944, then retry Bob." >&2
    exit 1
  fi
  bootnodes=(--bootnodes "/ip4/127.0.0.1/tcp/30333/p2p/$peer_id")
fi

umask 077
mkdir -p "$base_path"
exec 9>"$base_path/.iink-validator.lock"
if ! flock -n 9; then
  echo "The $validator validator already has this data directory open." >&2
  exit 1
fi
if [[ ! -f "$key_path" ]]; then
  "$node" key generate-node-key --chain local --base-path "$base_path"
fi

exec "$node" --chain local "--$validator" --base-path "$base_path" \
  --listen-addr "/ip4/127.0.0.1/tcp/$network_port" \
  --rpc-methods Safe --rpc-port "$rpc_port" --no-mdns --no-prometheus \
  "${bootnodes[@]}"
