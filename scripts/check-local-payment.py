#!/usr/bin/env python3
"""Send one test payment and reconcile it on both local validators."""
import time

from substrateinterface import Keypair, SubstrateInterface
from substrateinterface.exceptions import SubstrateRequestException

AMOUNT = 10**12  # 1 IINK


def expect_rejection(node, transaction, label, reason, *, allow_duplicate=False):
    try:
        node.submit_extrinsic(transaction)
    except SubstrateRequestException as error:
        details = error.args[0] if error.args else None
        if isinstance(details, dict):
            code = details.get("code")
            if code == 1010 and details.get("data") == reason:
                return
            # The pool can reject an identical hash before validating its nonce.
            if allow_duplicate and code in (1012, 1013):
                return
        raise RuntimeError(f"{label} was rejected for an unexpected reason: {error}") from error
    raise RuntimeError(f"{label} was accepted.")


def snapshot(node, block, accounts):
    balances = []
    for account in accounts:
        state = node.query("System", "Account", [account], block_hash=block)
        balances.append(state.value["data"]["free"])
    issuance = node.query("Balances", "TotalIssuance", block_hash=block).value
    return (*balances, issuance)


def wait_for_peer(peer, block, height):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        finalized = peer.get_block_number(peer.get_chain_finalised_head())
        if finalized >= height:
            if peer.get_block_hash(height) != block:
                raise RuntimeError(f"Bob disagrees on the finalized payment block {height}.")
            return
        time.sleep(2)
    raise RuntimeError(f"Bob did not finalize payment block {height} within 60 seconds.")


def main():
    alice_node = SubstrateInterface(url="ws://127.0.0.1:9944")
    bob_node = SubstrateInterface(url="ws://127.0.0.1:9945")
    for node in (alice_node, bob_node):
        if node.chain != "IINK Local Testnet":
            raise RuntimeError(f"Expected IINK Local Testnet, got {node.chain!r}.")
    if alice_node.get_block_hash(0) != bob_node.get_block_hash(0):
        raise RuntimeError("The validators have different genesis blocks.")

    alice = Keypair.create_from_uri("//Alice")
    bob = Keypair.create_from_uri("//Bob")
    accounts = (alice.ss58_address, bob.ss58_address)
    head = alice_node.get_chain_finalised_head()
    alice_before, bob_before, supply_before = snapshot(alice_node, head, accounts)
    call = alice_node.compose_call("Balances", "transfer_keep_alive", {
        "dest": bob.ss58_address,
        "value": AMOUNT,
    })
    nonce = alice_node.get_account_nonce(alice.ss58_address)
    forged = alice_node.create_signed_extrinsic(
        call=call, keypair=alice, nonce=nonce, signature=bytes(64),
    )
    expect_rejection(alice_node, forged, "Invalid signature", "Transaction has a bad signature")
    print("PASS: Invalid signature rejected.")

    signed = alice_node.create_signed_extrinsic(call=call, keypair=alice, nonce=nonce)
    receipt = alice_node.submit_extrinsic(signed, wait_for_finalization=True)
    if not receipt.is_success:
        raise RuntimeError(f"Payment failed: {receipt.error_message}")
    print(f"Finalized payment: {receipt.extrinsic_hash}", flush=True)

    fee = receipt.total_fee_amount
    if fee <= 0:
        raise RuntimeError("The payment receipt did not report a positive fee.")
    block = receipt.block_hash
    height = alice_node.get_block_number(block)
    # The current runtime burns transaction fees.
    expected = (alice_before - AMOUNT - fee, bob_before + AMOUNT, supply_before - fee)
    actual = snapshot(alice_node, block, accounts)
    if actual != expected:
        raise RuntimeError(
            f"Payment accounting mismatch (Alice, Bob, supply). Expected {expected}, got {actual}."
        )
    print(f"PASS: Bob received 1 IINK. Alice paid {fee} base units, which were burned.")
    expect_rejection(
        alice_node, signed, "Duplicate transaction", "Transaction is outdated", allow_duplicate=True,
    )
    # Change the amount to test the used nonce without hitting the same pool hash.
    stale_call = alice_node.compose_call("Balances", "transfer_keep_alive", {
        "dest": bob.ss58_address,
        "value": 2 * AMOUNT,
    })
    stale = alice_node.create_signed_extrinsic(call=stale_call, keypair=alice, nonce=nonce)
    expect_rejection(alice_node, stale, "Used nonce", "Transaction is outdated")
    print("PASS: Duplicate submission and a new transaction using the same nonce were rejected.")

    wait_for_peer(bob_node, block, height)
    if snapshot(bob_node, block, accounts) != actual:
        raise RuntimeError(f"Validators disagree on balances or supply at block {height}.")
    print(f"PASS: Both validators agree on payment block {height}, balances, and supply.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, SubstrateRequestException) as error:
        raise SystemExit(f"FAIL: {error}")
