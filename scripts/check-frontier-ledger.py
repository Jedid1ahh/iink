#!/usr/bin/env python3
"""Verify native funding and an Ethereum payment against one finalized ledger."""
import time
from hashlib import blake2b

from eth_account import Account
from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.ss58 import ss58_encode

from check_rpc import rpc

HTTP_URL = "http://127.0.0.1:9967"
WS_URL = "ws://127.0.0.1:9967"
CHAIN_ID = 31_337
UNIT = 10**12
FUNDING = 2 * UNIT


def eth(method, params=None):
    return rpc(method, params, url=HTTP_URL)


def native_address(ethereum_address):
    address = bytes.fromhex(ethereum_address[2:])
    account_id = blake2b(b"evm:" + address, digest_size=32).hexdigest()
    return ss58_encode(account_id, ss58_format=42)


def snapshot(node, block, addresses):
    balances = tuple(
        node.query("System", "Account", [address], block_hash=block).value["data"]["free"]
        for address in addresses
    )
    supply = node.query("Balances", "TotalIssuance", block_hash=block).value
    return balances, supply


def check_evm_balance(address, height, expected):
    actual = int(eth("eth_getBalance", [address, hex(height)]), 16)
    if actual != expected:
        raise RuntimeError(f"EVM balance for {address} at block {height}: {actual}, expected {expected}.")


def wait_for_receipt(node, tx_hash):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        receipt = eth("eth_getTransactionReceipt", [tx_hash])
        if receipt:
            height = int(receipt["blockNumber"], 16)
            head = node.get_chain_finalised_head()
            if node.get_block_number(head) >= height:
                block = eth("eth_getBlockByNumber", [hex(height), False])
                if block and block["hash"] == receipt["blockHash"]:
                    if receipt["status"] != "0x1":
                        raise RuntimeError(f"Ethereum payment reverted: {tx_hash}")
                    return receipt, height, node.get_block_hash(height)
        time.sleep(2)
    raise RuntimeError(f"Ethereum payment did not finalize within 90 seconds: {tx_hash}")


def main():
    properties = eth("system_properties")
    if (
        eth("system_chain") != "IINK Shared Ledger Lab"
        or int(eth("eth_chainId"), 16) != CHAIN_ID
        or properties.get("tokenSymbol") != "IINK"
        or properties.get("tokenDecimals") != 12
    ):
        raise RuntimeError("Expected the IINK shared ledger development chain on port 9967.")

    with SubstrateInterface(url=WS_URL) as node:
        alice = Keypair.create_from_uri("//Alice")
        sender = Account.create()
        recipient = Account.create()
        addresses = (native_address(sender.address), native_address(recipient.address))
        reserve = node.get_constant("Balances", "ExistentialDeposit").value
        if reserve != UNIT // 1_000:
            raise RuntimeError(f"Unexpected existential deposit: {reserve}.")
        call = node.compose_call("Balances", "transfer_keep_alive", {
            "dest": addresses[0],
            "value": FUNDING,
        })
        signed = node.create_signed_extrinsic(call=call, keypair=alice)
        funding = node.submit_extrinsic(signed, wait_for_finalization=True)
        if not funding.is_success:
            raise RuntimeError(f"Native funding failed: {funding.error_message}")

        height = node.get_block_number(funding.block_hash)
        balances, supply = snapshot(node, funding.block_hash, addresses)
        if balances != (FUNDING, 0):
            raise RuntimeError(f"Unexpected native balances after funding: {balances}.")
        check_evm_balance(sender.address, height, FUNDING - reserve)
        check_evm_balance(recipient.address, height, 0)
        print(f"PASS: A native transfer funded the Ethereum sender at finalized block {height}.", flush=True)

        base_fee = int(eth("eth_gasPrice"), 16)
        transaction = sender.sign_transaction({
            "type": 2,
            "chainId": CHAIN_ID,
            "nonce": 0,
            "gas": 100_000,
            "maxFeePerGas": 2 * base_fee,
            "maxPriorityFeePerGas": 0,
            "to": recipient.address,
            "value": UNIT,
        })
        tx_hash = eth("eth_sendRawTransaction", ["0x" + bytes(transaction.raw_transaction).hex()])
        print(f"Submitted {tx_hash}. Waiting for finality...", flush=True)
        receipt, height, block = wait_for_receipt(node, tx_hash)

        fee = int(receipt["gasUsed"], 16) * int(receipt["effectiveGasPrice"], 16)
        expected = ((FUNDING - UNIT - fee, UNIT), supply - fee)
        actual = snapshot(node, block, addresses)
        if fee <= 0 or actual != expected:
            raise RuntimeError(f"Balance or supply mismatch. Expected {expected}, got {actual}.")
        check_evm_balance(sender.address, height, expected[0][0] - reserve)
        check_evm_balance(recipient.address, height, UNIT - reserve)
        print(f"PASS: Both RPCs agree at finalized block {height}. The Ethereum payment moved 1 IINK and burned {fee} base units.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, SubstrateRequestException) as error:
        raise SystemExit(f"FAIL: {error}")
