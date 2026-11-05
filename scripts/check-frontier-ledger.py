#!/usr/bin/env python3
"""Verify native funding and finalized Ethereum payments or contracts."""
import argparse
import time
from hashlib import blake2b

from eth_account import Account
from eth_utils import to_checksum_address
from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.ss58 import ss58_encode

from check_rpc import rpc
from frontier_counter import exercise_counter

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
                        raise RuntimeError(f"Ethereum transaction reverted: {tx_hash}")
                    return receipt
        time.sleep(2)
    raise RuntimeError(f"Ethereum transaction did not finalize within 90 seconds: {tx_hash}")


def fund_sender(node, destination):
    call = node.compose_call("Balances", "transfer_keep_alive", {
        "dest": destination,
        "value": FUNDING,
    })
    signed = node.create_signed_extrinsic(call=call, keypair=Keypair.create_from_uri("//Alice"))
    funding = node.submit_extrinsic(signed, wait_for_finalization=True)
    if not funding.is_success:
        raise RuntimeError(f"Native funding failed: {funding.error_message}")
    return funding.block_hash


def send_evm(node, sender, nonce, gas, *, value=0, data="0x", to=None):
    base_fee = int(eth("eth_gasPrice"), 16)
    transaction = {
        "type": 2,
        "chainId": CHAIN_ID,
        "nonce": nonce,
        "gas": gas,
        "maxFeePerGas": 2 * base_fee,
        "maxPriorityFeePerGas": 0,
        "value": value,
        "data": data,
    }
    if to is not None:
        transaction["to"] = to_checksum_address(to)
    signed = sender.sign_transaction(transaction)
    tx_hash = eth("eth_sendRawTransaction", ["0x" + bytes(signed.raw_transaction).hex()])
    print(f"Submitted {tx_hash}. Waiting for finality...", flush=True)
    return wait_for_receipt(node, tx_hash)


def gas_fee(receipt):
    fee = int(receipt["gasUsed"], 16) * int(receipt["effectiveGasPrice"], 16)
    if fee <= 0:
        raise RuntimeError("The finalized Ethereum receipt did not report a positive gas fee.")
    return fee


def check_payment(node, reserve):
    sender = Account.create()
    recipient = Account.create()
    addresses = (native_address(sender.address), native_address(recipient.address))
    funding_block = fund_sender(node, addresses[0])
    height = node.get_block_number(funding_block)
    balances, supply = snapshot(node, funding_block, addresses)
    if balances != (FUNDING, 0):
        raise RuntimeError(f"Unexpected native balances after funding: {balances}.")
    check_evm_balance(sender.address, height, FUNDING - reserve)
    check_evm_balance(recipient.address, height, 0)
    print(f"PASS: A native transfer funded the Ethereum sender at finalized block {height}.", flush=True)

    receipt = send_evm(node, sender, 0, 100_000, value=UNIT, to=recipient.address)
    height = int(receipt["blockNumber"], 16)
    fee = gas_fee(receipt)
    expected = ((FUNDING - UNIT - fee, UNIT), supply - fee)
    actual = snapshot(node, node.get_block_hash(height), addresses)
    if actual != expected:
        raise RuntimeError(f"Balance or supply mismatch. Expected {expected}, got {actual}.")
    check_evm_balance(sender.address, height, expected[0][0] - reserve)
    check_evm_balance(recipient.address, height, UNIT - reserve)
    print(f"PASS: Both RPCs agree at finalized block {height}. The Ethereum payment moved 1 IINK and burned {fee} base units.")


def check_counter(node, reserve):
    sender = Account.create()
    addresses = (native_address(sender.address),)
    funding_block = fund_sender(node, addresses[0])
    height = node.get_block_number(funding_block)
    balances, supply = snapshot(node, funding_block, addresses)
    if balances != (FUNDING,):
        raise RuntimeError(f"Unexpected native deployer balance after funding: {balances}.")
    check_evm_balance(sender.address, height, FUNDING - reserve)
    print(f"PASS: A native transfer funded the contract deployer at finalized block {height}.", flush=True)

    def send(data, gas, to=None):
        nonce = int(eth("eth_getTransactionCount", [sender.address, "latest"]), 16)
        return send_evm(node, sender, nonce, gas, data=data, to=to)

    contract, deployment, change = exercise_counter(eth, send)
    print(f"PASS: Counter deployed at {contract} and advanced from 7 to 8.")

    spent = 0
    for receipt in (deployment, change):
        spent += gas_fee(receipt)
        height = int(receipt["blockNumber"], 16)
        expected = ((FUNDING - spent,), supply - spent)
        actual = snapshot(node, node.get_block_hash(height), addresses)
        if actual != expected:
            raise RuntimeError(f"Gas accounting mismatch at block {height}. Expected {expected}, got {actual}.")
        check_evm_balance(sender.address, height, expected[0][0] - reserve)
    print(f"PASS: Both RPCs agree. Deployment and increment burned {spent} base units in total.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--counter", action="store_true", help="deploy and increment the Solidity counter")
    args = parser.parse_args()
    properties = eth("system_properties")
    if (
        eth("system_chain") != "IINK Shared Ledger Lab"
        or int(eth("eth_chainId"), 16) != CHAIN_ID
        or properties.get("tokenSymbol") != "IINK"
        or properties.get("tokenDecimals") != 12
    ):
        raise RuntimeError("Expected the IINK shared ledger development chain on port 9967.")

    with SubstrateInterface(url=WS_URL) as node:
        reserve = node.get_constant("Balances", "ExistentialDeposit").value
        if reserve != UNIT // 1_000:
            raise RuntimeError(f"Unexpected existential deposit: {reserve}.")
        if args.counter:
            check_counter(node, reserve)
        else:
            check_payment(node, reserve)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, SubstrateRequestException) as error:
        raise SystemExit(f"FAIL: {error}")
