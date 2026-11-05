#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

python=${1:-python3}
"$python" -c 'import eth_account, substrateinterface'
"$python" scripts/check_rpc.py
"$python" scripts/check-frontier-ledger.py
"$python" scripts/check-frontier-ledger.py --counter
"$python" scripts/check-frontier-ledger.py --return
"$python" scripts/check-frontier-ledger.py --replay
