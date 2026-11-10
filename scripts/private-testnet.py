#!/usr/bin/env python3
"""Prepare and verify the two-host IINK private testnet using an existing binary."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time

from check_rpc import check_chain, finalized_height, rpc

CHAIN_ID = 31_343
CHAIN_NAME = "IINK Private Testnet"
SPEC_ID = "iink_private_31343"
ROLES = ("a", "b")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    with Path(path).open("x") as output:
        json.dump(value, output, indent=2)
        output.write("\n")


def command(node, *args):
    result = subprocess.run([str(node), *map(str, args)], capture_output=True, text=True)
    # A failed key command may include secret material in its diagnostics.
    require(result.returncode == 0, f"Node command {args[0]!r} failed (exit {result.returncode}).")
    return result.stdout


def node_path(value):
    target = Path(os.environ.get("CARGO_TARGET_DIR", os.environ.get("CARGO_BUILD_TARGET_DIR", "target")))
    candidates = [Path(value)] if value else [target / "release/iink-node",
        Path("/workspaces/iink-frontier-2603/target/release/iink-node")]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
    raise RuntimeError("Node binary missing. Set --node to your existing iink-node executable.")


def root_path(role, value):
    root = Path(value).resolve() if value else Path(__file__).resolve().parents[2] / f"iink-private-{role}"
    repository = Path(__file__).resolve().parents[1]
    require(root != repository and repository not in root.parents, "Keep private keys outside the git repository.")
    return root


def host_id():
    return os.environ.get("CODESPACE_NAME") or socket.gethostname()


def public_identity(path):
    identity = read_json(path)
    require(identity.get("schema") == 1 and identity.get("role") in ROLES, "Invalid public identity.")
    for name in ("aura", "grandpa"):
        require(re.fullmatch(r"0x[0-9a-fA-F]{64}", identity.get(name, "")), f"Invalid {name} public key.")
    require(re.fullmatch(r"12D3KooW[1-9A-HJ-NP-Za-km-z]{44}", identity.get("peerId", "")), "Invalid peer ID.")
    require(re.fullmatch(r"[0-9a-f]{64}", identity.get("binarySha256", "")), "Invalid binary checksum.")
    require(isinstance(identity.get("host"), str) and identity["host"], "Missing host identifier.")
    return identity


def validate_pair(identities):
    require([item["role"] for item in identities] == list(ROLES), "Supply validator A, then validator B.")
    for field in ("aura", "grandpa", "peerId", "host"):
        require(identities[0][field] != identities[1][field], f"Validators have the same {field}.")
    require(identities[0]["binarySha256"] == identities[1]["binarySha256"], "Copy the same binary to both hosts.")


def prepare(args):
    node = node_path(args.node)
    root = root_path(args.role, args.root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    with (root / ".setup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = root / "public.json"
        if manifest.exists():
            identity = public_identity(manifest)
            require(identity["role"] == args.role, "This directory belongs to a different validator.")
            require(identity["host"] == host_id(), "These validator keys were prepared on a different host.")
            require(identity["binarySha256"] == digest(node), "Prepared binary changed; use the original executable.")
            verify_keys(node, root, identity)
            print(f"Existing keys retained. Public identity: {manifest}")
            return
        identity = {"schema": 1, "role": args.role,
                    "host": host_id(),
                    "binarySha256": digest(node)}
        for field, scheme in (("aura", "Sr25519"), ("grandpa", "Ed25519")):
            secret = root / f"{field}.suri"
            # Recover an interrupted setup without replacing an existing key.
            if secret.exists():
                generated = json.loads(command(node, "key", "inspect", "--scheme", scheme,
                                               "--output-type", "json", secret))
            else:
                generated = json.loads(command(node, "key", "generate", "--scheme", scheme,
                                               "--output-type", "json"))
                with secret.open("x") as output:
                    output.write(generated["secretSeed"])
            secret.chmod(0o600)
            identity[field] = generated["publicKey"]
        network_key = root / "network.key"
        if not network_key.exists():
            command(node, "key", "generate-node-key", "--file", network_key)
        network_key.chmod(0o600)
        identity["peerId"] = command(node, "key", "inspect-node-key", "--file", network_key).strip()
        write_json(manifest, identity)
        public_identity(manifest)
        print(f"Keys prepared for validator {args.role.upper()}. Public identity: {manifest}")
        print("Copy only public.json. Keep the .suri files and network.key on this host.")


def verify_keys(node, root, identity):
    for field, scheme in (("aura", "Sr25519"), ("grandpa", "Ed25519")):
        inspected = json.loads(command(node, "key", "inspect", "--scheme", scheme,
                                       "--output-type", "json", root / f"{field}.suri"))
        require(inspected["publicKey"] == identity[field], f"Stored {field} key does not match public.json.")
    peer = command(node, "key", "inspect-node-key", "--file", root / "network.key").strip()
    require(peer == identity["peerId"], "Stored network key does not match public.json.")


def create(args):
    node = node_path(args.node)
    identities = [public_identity(path) for path in (args.a, args.b)]
    validate_pair(identities)
    require(digest(node) == identities[0]["binarySha256"], "Use the binary recorded in the public identities.")
    wallets = list(dict.fromkeys(address.lower() for address in args.wallet))
    require(len(wallets) >= 2 and all(re.fullmatch(r"0x[0-9a-f]{40}", item) and int(item, 16) for item in wallets),
            "Provide at least two different public Ethereum wallet addresses using --wallet.")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    require(not any(output.iterdir()), "Output directory must be empty; existing network files will not be replaced.")
    spec = json.loads(command(node, "build-spec", "--chain", "local", "--disable-default-bootnode"))
    spec.update(name=CHAIN_NAME, id=SPEC_ID, chainType="Live", protocolId="iink-private-31343",
                bootNodes=[], telemetryEndpoints=None)
    require(spec["properties"].get("tokenDecimals") == 18, "The binary must use 18-decimal IINK.")
    patch = spec["genesis"]["runtimeGenesis"]["patch"]
    patch["aura"] = {"authorities": [item["aura"] for item in identities]}
    patch["grandpa"] = {"authorities": [[item["grandpa"], 1] for item in identities]}
    patch["evmChainId"] = {"chainId": CHAIN_ID}
    patch["manualSeal"] = {"enable": False}
    patch["sudo"] = {"key": None}
    patch["balances"] = {"balances": [
        ["0x" + hashlib.blake2b(b"evm:" + bytes.fromhex(wallet[2:]), digest_size=32).hexdigest(), 1_000 * 10**18]
        for wallet in wallets
    ]}
    write_json(output / "plain-spec.json", spec)
    raw = json.loads(command(node, "build-spec", "--chain", output / "plain-spec.json",
                             "--raw", "--disable-default-bootnode"))
    require("raw" in raw["genesis"], "Node did not produce a raw chain spec.")
    write_json(output / "chain-spec.json", raw)
    write_json(output / "network.json", {"schema": 1, "name": CHAIN_NAME, "chainId": CHAIN_ID,
        "chainSpecSha256": digest(output / "chain-spec.json"), "binarySha256": digest(node),
        "validators": identities, "wallets": wallets})
    print(f"Created {output}. Copy this entire public directory to validator B.")
    print("Each listed wallet starts with 1,000 test IINK minus its 0.001 IINK account reserve. Sudo is disabled.")


def network_file(path):
    network = read_json(path)
    require(network.get("schema") == 1 and network.get("name") == CHAIN_NAME
            and network.get("chainId") == CHAIN_ID, "Unexpected private network configuration.")
    validate_pair(network["validators"])
    spec = Path(path).resolve().with_name("chain-spec.json")
    require(digest(spec) == network["chainSpecSha256"], "Chain spec checksum does not match network.json.")
    return network, spec


def run(args):
    node = node_path(args.node)
    network, spec = network_file(args.network)
    root = root_path(args.role, args.root)
    own = public_identity(root / "public.json")
    require(own["host"] == host_id(), "These validator keys were prepared on a different host.")
    index = ROLES.index(args.role)
    require(own == network["validators"][index], "This validator identity is not in the chain spec manifest.")
    require(digest(node) == network["binarySha256"], "Binary checksum does not match network.json.")
    verify_keys(node, root, own)
    # Hold this lock in the parent process until the child node exits.
    with (root / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for field, scheme, key_type in (("aura", "Sr25519", "aura"), ("grandpa", "Ed25519", "gran")):
            command(node, "key", "insert", "--chain", spec, "--base-path", root / "data",
                    "--keystore-path", root / "keystore", "--scheme", scheme,
                    "--key-type", key_type, "--suri", root / f"{field}.suri")
        peer = network["validators"][1 - index]["peerId"]
        peer_port = 13034 if index == 0 else 13033
        argv = [str(node), "--chain", str(spec), "--validator", "--name", f"IINK Private {args.role.upper()}",
                "--base-path", str(root / "data"), "--keystore-path", str(root / "keystore"),
                "--node-key-file", str(root / "network.key"), "--no-mdns", "--no-prometheus",
                "--listen-addr", f"/ip4/127.0.0.1/tcp/{30333 + index}",
                "--rpc-methods", "Safe", "--rpc-port", str(9944 + index),
                "--reserved-only", "--reserved-nodes", f"/ip4/127.0.0.1/tcp/{peer_port}/p2p/{peer}"]
        print(f"Starting validator {args.role.upper()} with persistent data in {root / 'data'}.", flush=True)
        with subprocess.Popen(argv) as process:
            try:
                code = process.wait()
            except KeyboardInterrupt:
                try:
                    code = process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    code = process.wait()
        require(code == 0, f"Validator exited with status {code}.")


def agreed(urls):
    height = min(finalized_height(url=url) for url in urls)
    hashes = [rpc("chain_getBlockHash", [height], url=url) for url in urls]
    require(hashes[0] and hashes[0] == hashes[1], f"Validators disagree at finalized block {height}.")
    return height, hashes[0]


def receipt_check(urls, tx_hash, height):
    require(re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash), "Invalid transaction hash.")
    receipts = [rpc("eth_getTransactionReceipt", [tx_hash], url=url) for url in urls]
    require(all(receipts) and receipts[0] == receipts[1], "Transaction receipts are missing or differ.")
    receipt = receipts[0]
    require(receipt["transactionHash"].lower() == tx_hash.lower() and receipt["status"] == "0x1",
            "Expected a successful transaction receipt.")
    require(int(receipt["blockNumber"], 16) <= height, "Transaction has not finalized on both nodes.")
    for url in urls:
        block = rpc("eth_getBlockByNumber", [receipt["blockNumber"], False], url=url)
        require(block and block["hash"] == receipt["blockHash"], "Transaction is not canonical.")
    print(f"PASS: Both validators finalized transaction {tx_hash} at block {int(receipt['blockNumber'], 16)}.")


def check(args):
    network, _ = network_file(args.network)
    urls = (args.a_rpc, args.b_rpc)
    genesis = []
    for identity, url in zip(network["validators"], urls):
        check_chain(url, CHAIN_NAME, CHAIN_ID)
        require(rpc("system_localPeerId", url=url) == identity["peerId"], "RPC is serving the wrong validator.")
        require(rpc("system_health", url=url)["peers"] >= 1, "Validator has no connected peers. Check both SSH tunnels.")
        genesis.append(rpc("chain_getBlockHash", [0], url=url))
    require(genesis[0] and genesis[0] == genesis[1], "Validators have different genesis blocks.")
    before, _ = agreed(urls)
    checkpoint = Path(args.checkpoint).resolve()
    if checkpoint.exists():
        saved = read_json(checkpoint)
        require(saved["chainSpecSha256"] == network["chainSpecSha256"] and saved["genesisHash"] == genesis[0],
                "Checkpoint belongs to a different chain.")
        require(before >= saved["height"], "A node has not caught up to the saved checkpoint. Wait and retry.")
        for url in urls:
            require(rpc("chain_getBlockHash", [saved["height"]], url=url) == saved["hash"],
                    "Saved finalized history changed.")
        print(f"Saved finalized block {saved['height']} is intact on both validators.", flush=True)
    print(f"Both validators agree at finalized block {before}. Waiting for progress...", flush=True)
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        after, block_hash = agreed(urls)
        if after > before:
            if args.transaction:
                receipt_check(urls, args.transaction, after)
            saved = {"chainSpecSha256": network["chainSpecSha256"], "genesisHash": genesis[0],
                     "height": after, "hash": block_hash, "hosts": [item["host"] for item in network["validators"]]}
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            temporary = checkpoint.with_name(checkpoint.name + ".tmp")
            with temporary.open("w") as output:
                json.dump(saved, output, indent=2)
                output.write("\n")
            temporary.replace(checkpoint)
            print(f"PASS: Both validators advanced from finalized block {before} to {after}. Checkpoint: {checkpoint}")
            return
        time.sleep(2)
    raise RuntimeError("Finality did not advance. Both of the two validators must be online and connected.")


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("prepare", prepare), ("create", create), ("run", run), ("check", check)):
        sub = commands.add_parser(name)
        sub.set_defaults(handler=handler)
        if name != "check":
            sub.add_argument("--node", help="path to the existing iink-node binary")
        if name in ("prepare", "run"):
            sub.add_argument("role", choices=ROLES)
            sub.add_argument("--root", help="persistent private key and database directory outside the repository")
        if name in ("run", "check"):
            sub.add_argument("--network", required=True, help="path to public network.json")
        if name == "create":
            sub.add_argument("--a", required=True, help="validator A public.json")
            sub.add_argument("--b", required=True, help="validator B public.json")
            sub.add_argument("--wallet", required=True, action="append", help="public test wallet address, repeat for each wallet")
            sub.add_argument("--output", required=True, help="new public network directory")
        if name == "check":
            sub.add_argument("--a-rpc", default="http://127.0.0.1:9944")
            sub.add_argument("--b-rpc", default="http://127.0.0.1:9945")
            sub.add_argument("--checkpoint", required=True, help="saved finalized history, reuse after restart")
            sub.add_argument("--timeout", type=int, default=90)
            sub.add_argument("--transaction", help="also verify a payment or game transaction on both validators")
    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        raise SystemExit(f"FAIL: {error}")
