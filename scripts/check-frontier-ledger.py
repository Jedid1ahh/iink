#!/usr/bin/env python3
"""Verify finalized payments, contracts, and native returns on the shared ledger."""
import argparse
import time
from hashlib import blake2b

from eth_account import Account
from eth_utils import keccak, to_checksum_address
from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException
from substrateinterface.utils.ss58 import ss58_encode

from check_rpc import rpc
from frontier_counter import exercise_counter

HTTP_URL = "http://127.0.0.1:9944"
WS_URL = "ws://127.0.0.1:9944"
CHAIN_ID = 31_339
UNIT = 10**12
FUNDING = 2 * UNIT
NATIVE_TRANSFER = "0x0000000000000000000000000000000000000800"


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


def wait_for_receipt(node, tx_hash, expected_status):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        receipt = eth("eth_getTransactionReceipt", [tx_hash])
        if receipt:
            height = int(receipt["blockNumber"], 16)
            head = node.get_chain_finalised_head()
            if node.get_block_number(head) >= height:
                block = eth("eth_getBlockByNumber", [hex(height), False])
                if block and block["hash"] == receipt["blockHash"]:
                    if receipt["status"] != expected_status:
                        raise RuntimeError(
                            f"Ethereum transaction {tx_hash} finalized with status "
                            f"{receipt['status']}, expected {expected_status}."
                        )
                    return receipt
        time.sleep(2)
    raise RuntimeError(f"Ethereum transaction did not finalize within 90 seconds: {tx_hash}")


def fund_sender(node, destination, amount=FUNDING):
    call = node.compose_call("Balances", "transfer_keep_alive", {
        "dest": destination,
        "value": amount,
    })
    signed = node.create_signed_extrinsic(call=call, keypair=Keypair.create_from_uri("//Alice"))
    funding = node.submit_extrinsic(signed, wait_for_finalization=True)
    if not funding.is_success:
        raise RuntimeError(f"Native funding failed: {funding.error_message}")
    return funding.block_hash


def sign_evm(sender, nonce, gas, *, value=0, data="0x", to=None, chain_id=CHAIN_ID):
    base_fee = int(eth("eth_gasPrice"), 16)
    transaction = {
        "type": 2,
        "chainId": chain_id,
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
    return "0x" + bytes(signed.raw_transaction).hex()


def submit_evm(node, raw, expected_status="0x1"):
    tx_hash = eth("eth_sendRawTransaction", [raw])
    print(f"Submitted {tx_hash}. Waiting for finality...", flush=True)
    return wait_for_receipt(node, tx_hash, expected_status)


def send_evm(node, sender, nonce, gas, *, value=0, data="0x", to=None):
    return submit_evm(node, sign_evm(sender, nonce, gas, value=value, data=data, to=to))


def expect_rejection(raw, label, *messages):
    try:
        tx_hash = eth("eth_sendRawTransaction", [raw])
    except RuntimeError as error:
        details = error.args[0] if error.args else None
        if (
            isinstance(details, dict)
            and details.get("code") == -32603
            and details.get("message") in messages
        ):
            print(f"PASS: Rejected {label} ({details['message']}).", flush=True)
            return
        raise RuntimeError(f"Unexpected rejection for {label}: {error}") from error
    raise RuntimeError(f"The node accepted {label} as {tx_hash}.")


def wait_for_finality_progress(node):
    height = node.get_block_number(node.get_chain_finalised_head())
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        head = node.get_chain_finalised_head()
        current = node.get_block_number(head)
        if current > height:
            return head, current
        time.sleep(2)
    raise RuntimeError("Finality did not advance within 90 seconds after the replay attempts.")


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


def check_native_return(node, reserve, *, replay=False):
    sender = Account.create()
    bob = Keypair.create_from_uri("//Bob")
    addresses = (native_address(sender.address), bob.ss58_address, native_address(NATIVE_TRANSFER))
    # Leave enough funds for a second full return if nonce checks were missing.
    funded_amount = 3 * UNIT if replay else FUNDING
    funding_block = fund_sender(node, addresses[0], funded_amount)
    height = node.get_block_number(funding_block)
    (sender_balance, bob_balance, precompile_balance), supply = snapshot(node, funding_block, addresses)
    if sender_balance != funded_amount:
        raise RuntimeError(f"Unexpected native sender balance after funding: {sender_balance}.")
    check_evm_balance(sender.address, height, funded_amount - reserve)
    print(f"PASS: A native transfer funded the Ethereum sender at finalized block {height}.", flush=True)

    selector = keccak(text="transferToNative(bytes32,uint128)")[:4]
    prefix = "0x" + (selector + bob.public_key).hex()
    transfer = prefix + UNIT.to_bytes(32, "big").hex()
    overspend = prefix + FUNDING.to_bytes(32, "big").hex()
    successful_return = ("Returned 1 IINK to native Bob", transfer, 0, "0x1", UNIT)
    cases = (successful_return,) if replay else (
        ("Rejected truncated calldata", transfer[:-2], 0, "0x0", 0),
        ("Rejected attached Ethereum value", transfer, UNIT, "0x0", 0),
        ("Rejected an amount above the spendable balance", overspend, 0, "0x0", 0),
        successful_return,
    )
    for nonce, (label, data, value, status, credit) in enumerate(cases):
        raw = sign_evm(sender, nonce, 200_000, data=data, value=value, to=NATIVE_TRANSFER)
        receipt = submit_evm(node, raw, status)
        fee = gas_fee(receipt)
        height = int(receipt["blockNumber"], 16)
        sender_balance -= fee + credit
        bob_balance += credit
        supply -= fee
        expected = ((sender_balance, bob_balance, precompile_balance), supply)
        actual = snapshot(node, node.get_block_hash(height), addresses)
        if actual != expected:
            raise RuntimeError(f"Accounting mismatch at block {height}. Expected {expected}, got {actual}.")
        check_evm_balance(sender.address, height, sender_balance - reserve)
        print(f"PASS: {label} at finalized block {height}. Gas burned {fee} base units.")

    if replay:
        expect_rejection(raw, "the exact finalized transaction", "already known", "nonce too low")
        different_amount = prefix + (UNIT // 2).to_bytes(32, "big").hex()
        stale = sign_evm(sender, 0, 200_000, data=different_amount, to=NATIVE_TRANSFER)
        expect_rejection(stale, "a different return with the same nonce", "nonce too low")
        wrong_chain = sign_evm(
            sender, 1, 200_000, data=different_amount, to=NATIVE_TRANSFER, chain_id=CHAIN_ID + 1,
        )
        expect_rejection(wrong_chain, "a return signed for the wrong chain", "invalid chain id")

        block, height = wait_for_finality_progress(node)
        actual = snapshot(node, block, addresses)
        nonce = int(eth("eth_getTransactionCount", [sender.address, hex(height)]), 16)
        if actual != expected or nonce != 1:
            raise RuntimeError(f"Replay changed finalized state at block {height}: {actual}, nonce {nonce}.")
        check_evm_balance(sender.address, height, sender_balance - reserve)
        print(f"PASS: Bob received exactly 1 IINK. Balances, supply, and nonce held through finalized block {height}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    checks = parser.add_mutually_exclusive_group()
    checks.add_argument("--counter", action="store_true", help="deploy and increment the Solidity counter")
    checks.add_argument("--return", dest="native_return", action="store_true", help="send IINK back to a native account")
    checks.add_argument("--replay", action="store_true", help="reject replay attempts against a finalized native return")
    args = parser.parse_args()
    properties = eth("system_properties")
    if (
        eth("system_chain") != "IINK Development"
        or int(eth("eth_chainId"), 16) != CHAIN_ID
        or properties.get("tokenSymbol") != "IINK"
        or properties.get("tokenDecimals") != 12
    ):
        raise RuntimeError("Expected the integrated IINK development chain on port 9944.")
    if (args.native_return or args.replay) and eth("state_getRuntimeVersion")["specVersion"] < 2:
        raise RuntimeError("The native return and replay checks need IINK runtime v2 or later.")

    with SubstrateInterface(url=WS_URL) as node:
        reserve = node.get_constant("Balances", "ExistentialDeposit").value
        if reserve != UNIT // 1_000:
            raise RuntimeError(f"Unexpected existential deposit: {reserve}.")
        if args.counter:
            check_counter(node, reserve)
        elif args.native_return or args.replay:
            check_native_return(node, reserve, replay=args.replay)
        else:
            check_payment(node, reserve)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, SubstrateRequestException) as error:
        raise SystemExit(f"FAIL: {error}")
