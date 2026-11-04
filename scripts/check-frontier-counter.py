#!/usr/bin/env python3
"""Deploy and call the Counter contract on the isolated Frontier development node."""
import hashlib
import json
import re
import time
from pathlib import Path

from eth_account import Account
from eth_utils import to_checksum_address

from check_rpc import rpc

REPO = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:9966"
CHAIN_ID = 42
ALITH_ADDRESS = "0xf24ff3a9cf04c71dbc94d0b566f7a27b94566cac"


def eth(method, params=None):
    return rpc(method, params, url=URL)


def test_account():
    template_readme = REPO.parent / "iink-frontier-2603" / "template" / "README.md"
    match = re.search(
        r"- Alith:\s*\* Public Address: 0x[0-9a-fA-F]{40}\s*"
        r"\* Private Key: (0x[0-9a-fA-F]{64})",
        template_readme.read_text(),
    )
    if match is None:
        raise RuntimeError("Could not find the upstream Alith development key.")
    account = Account.from_key(match[1])
    if account.address.lower() != ALITH_ADDRESS:
        raise RuntimeError("The upstream test key does not match Alith's address.")
    return account


def send(account, data, gas, to=None):
    transaction = {
        "chainId": CHAIN_ID,
        "nonce": int(eth("eth_getTransactionCount", [account.address, "pending"]), 16),
        "gasPrice": int(eth("eth_gasPrice"), 16),
        "gas": gas,
        "value": 0,
        "data": data,
    }
    if to is not None:
        transaction["to"] = to_checksum_address(to)
    signed = account.sign_transaction(transaction)
    tx_hash = eth("eth_sendRawTransaction", ["0x" + bytes(signed.raw_transaction).hex()])
    print(f"Submitted {tx_hash}. Waiting for finality...", flush=True)

    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        receipt = eth("eth_getTransactionReceipt", [tx_hash])
        if receipt is not None:
            if receipt["status"] != "0x1":
                raise RuntimeError(f"Transaction reverted: {tx_hash}")
            finalized = eth("eth_getBlockByNumber", ["finalized", False])
            if finalized and int(finalized["number"], 16) >= int(receipt["blockNumber"], 16):
                block = eth("eth_getBlockByNumber", [receipt["blockNumber"], False])
                if block and block["hash"] == receipt["blockHash"]:
                    return receipt
        time.sleep(2)
    raise RuntimeError(f"Transaction did not finalize within 90 seconds: {tx_hash}")


def main():
    if eth("system_chain") != "Development" or int(eth("eth_chainId"), 16) != CHAIN_ID:
        raise RuntimeError("Expected the Frontier development chain on port 9966.")

    account = test_account()
    if int(eth("eth_getBalance", [account.address, "latest"]), 16) == 0:
        raise RuntimeError("The Frontier Alith test account is unfunded.")
    contract_files = REPO / "experiments/frontier"
    artifact = json.loads((contract_files / "Counter.json").read_text())
    source_hash = hashlib.sha256((contract_files / "Counter.sol").read_bytes()).hexdigest()
    if source_hash != artifact["sourceSha256"]:
        raise RuntimeError("Counter.sol changed since the test bytecode was compiled.")

    deployment = send(account, "0x" + artifact["bytecode"], 600_000)
    contract = deployment["contractAddress"]
    expected_code = "0x" + artifact["deployedBytecode"]
    if not contract or eth("eth_getCode", [contract, deployment["blockNumber"]]) != expected_code:
        raise RuntimeError("The finalized deployment does not contain the compiled contract code.")

    read = {"to": contract, "data": "0x" + artifact["selectors"]["value()"]}
    before = int(eth("eth_call", [read, deployment["blockNumber"]]), 16)
    if before != 7:
        raise RuntimeError(f"Expected the initial counter value 7, got {before}.")
    change = send(account, "0x" + artifact["selectors"]["increment()"], 100_000, contract)
    after = int(eth("eth_call", [read, change["blockNumber"]]), 16)
    if after != 8:
        raise RuntimeError(f"Expected the counter value 8, got {after}.")

    print(f"PASS: Counter deployed at {contract} and advanced from {before} to {after}.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        raise SystemExit(f"FAIL: {error}")
