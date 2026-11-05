"""Deploy and exercise the compiled counter on a Frontier RPC endpoint."""
import hashlib
import json
from pathlib import Path

CONTRACT_FILES = Path(__file__).resolve().parent.parent / "experiments/frontier"


def exercise_counter(eth, send):
    """Verify the deployed bytecode and both finalized counter values."""
    artifact = json.loads((CONTRACT_FILES / "Counter.json").read_text())
    source_hash = hashlib.sha256((CONTRACT_FILES / "Counter.sol").read_bytes()).hexdigest()
    if source_hash != artifact["sourceSha256"]:
        raise RuntimeError("Counter.sol changed since the test bytecode was compiled.")

    deployment = send("0x" + artifact["bytecode"], 600_000)
    contract = deployment["contractAddress"]
    expected_code = "0x" + artifact["deployedBytecode"]
    if not contract or eth("eth_getCode", [contract, deployment["blockNumber"]]) != expected_code:
        raise RuntimeError("The finalized deployment does not contain the compiled contract code.")

    read = {"to": contract, "data": "0x" + artifact["selectors"]["value()"]}
    before = int(eth("eth_call", [read, deployment["blockNumber"]]), 16)
    if before != 7:
        raise RuntimeError(f"Expected the initial counter value 7, got {before}.")
    change = send("0x" + artifact["selectors"]["increment()"], 100_000, contract)
    after = int(eth("eth_call", [read, change["blockNumber"]]), 16)
    if after != 8:
        raise RuntimeError(f"Expected the counter value 8, got {after}.")

    return contract, deployment, change
