#!/usr/bin/env python3
"""Verify agreement and finality progress on the two local validators."""
import time

from check_rpc import finalized_height, rpc

ALICE = "http://127.0.0.1:9944"
BOB = "http://127.0.0.1:9945"


def agreed_height():
    height = min(finalized_height(url=ALICE), finalized_height(url=BOB))
    alice_hash = rpc("chain_getBlockHash", [height], url=ALICE)
    bob_hash = rpc("chain_getBlockHash", [height], url=BOB)
    if not alice_hash or alice_hash != bob_hash:
        raise RuntimeError(f"Validators disagree at finalized block {height}.")
    return height


def main():
    for name, url in (("Alice", ALICE), ("Bob", BOB)):
        chain = rpc("system_chain", url=url)
        if chain != "IINK Local Testnet":
            raise RuntimeError(f"{name} is serving {chain!r}; expected IINK Local Testnet.")

    before = agreed_height()
    print(f"Both nodes agree at finalized block {before}. Waiting 20 seconds...", flush=True)
    time.sleep(20)
    after = agreed_height()
    if after <= before:
        raise RuntimeError(f"No shared finality progress in 20 seconds (block {after}).")

    print(f"PASS: Both nodes advanced from finalized block {before} to {after}.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"FAIL: {error}")
