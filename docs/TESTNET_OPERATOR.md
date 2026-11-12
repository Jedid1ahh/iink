# IINK operator handoff

The first handoff tests whether an independent operator can build the tested
IINK node and sync a fresh observer. An observer follows and verifies the
chain without voting on blocks. This lets the operator verify the build and
network connection before preparing validator keys.

## Tested baseline

The two-host rehearsal on chain 31343 passed on 12 November 2026. Both
validators finalized blocks, reconnected after a tunnel interruption, and
confirmed the Payments and Glimmer Run receipts. Validator B reopened its
database at block 441 and the Courier Pass at block 437 remained finalized
on both nodes. Reloading the game retained the player's eleven-move run.

The [rehearsal manifest](testnet-rehearsal.json) records the observed node
version, binary and chain spec SHA-256 hashes, source revisions, and checks.
Use the **node build commit** for rebuilding. The **rehearsal commit** also
contains the scripts and apps used to verify the network. The two validators
ran copies of the same executable. An independent rebuild and join are the
next tests.

## Build and check locally

Use an existing x86-64 Linux host or the project's development container.
The [container definition](../.devcontainer/Dockerfile) lists the native
packages. For a direct Linux build, install those packages and make `rustup`
available first. The [toolchain file](../rust-toolchain.toml) pins Rust and
the Wasm target. The build script runs the existing memory and disk preflight
and records its results under `artifacts/`.

In a new checkout, run:

```bash
git clone https://github.com/Jedid1ahh/iink.git iink-operator &&
cd iink-operator &&
git switch --detach 4ac582102116d34f9ccfdf03c711f393b8bddc30 &&
rustup toolchain install 1.88.0 --profile minimal --component rust-src --target wasm32v1-none &&
bash scripts/build.sh
```

With the default Cargo target directory, record:

```bash
git rev-parse HEAD &&
rustc --version &&
cargo --version &&
./target/release/iink-node --version &&
sha256sum ./target/release/iink-node
```

If you set an external Cargo target directory, use its `release/iink-node`
for the version and checksum and keep the same environment for the launch.
Compare the checksum with the tested binary in the manifest. If it differs,
record the build environment and investigate the difference before treating
the rebuilt file as the same release artifact.

Start a temporary development chain with `bash scripts/run-dev.sh`. In a
second terminal in the operator checkout, run `python3 scripts/check_rpc.py`.
It should report chain `IINK Development`, token metadata, and advancing
finality. Stop the development node after capturing the result. The full
development suite is documented in the [repository README](../README.md#verify-the-development-release).

## Join from the independent host

For the join test, the coordinator supplies a raw chain specification and
its SHA-256, a reachable bootnode multiaddress, and the genesis hash and
finalized checkpoint expected from the running rehearsal. Use a peer that
accepts this observer over the operator's network. The original two-host
rehearsal only configured the two reserved peers through SSH forwards.
Arranging a peer reachable directly from the operator host is part of the
handoff. The observer's RPC stays on the operator's loopback interface.

After comparing `sha256sum` of the received spec with the supplied hash,
run the observer from the operator checkout. Choose a new persistent data
directory for this network. Use the same directory on a restart.

```bash
read -r -p 'Path to the raw chain spec: ' spec &&
read -r -p 'Reachable bootnode multiaddress: ' bootnode &&
read -r -p 'Observer data directory: ' observer_data &&
node="${CARGO_TARGET_DIR:-${CARGO_BUILD_TARGET_DIR:-target}}/release/iink-node" &&
"$node" --chain "$spec" --base-path "$observer_data" --name 'IINK Handoff Observer' \
  --bootnodes "$bootnode" --listen-addr /ip4/127.0.0.1/tcp/30335 \
  --rpc-port 9946 --rpc-methods Safe --no-mdns --no-prometheus
```

In a second terminal in the operator checkout, enter the shared finalized
checkpoint height when prompted:

```bash
read -r -p 'Shared finalized checkpoint height: ' checkpoint_height &&
PYTHONPATH=scripts python3 - "$checkpoint_height" <<'PY'
import json
import sys

from check_rpc import finalized_height, rpc

url = 'http://127.0.0.1:9946'
checkpoint_height = int(sys.argv[1])
height = finalized_height(url=url)
print(json.dumps({
    'chain': rpc('system_chain', url=url),
    'chainId': int(rpc('eth_chainId', url=url), 16),
    'genesisHash': rpc('chain_getBlockHash', [0], url=url),
    'peers': rpc('system_health', url=url)['peers'],
    'finalizedHeight': height,
    'checkpointHeight': checkpoint_height,
    'checkpointHash': rpc('chain_getBlockHash', [checkpoint_height], url=url),
}, indent=2))
PY
```

The handoff passes when the observer has a peer, the chain and genesis match,
its finalized height reaches the shared checkpoint with the expected hash,
and a second reading shows advancing finality. Save these readings with
the operator's build evidence. Repeat after restarting the observer with
its saved data to check recovery.

## After the handoff

Use the build and sync evidence to prepare a fresh test-token network with
independent validators. Define who can approve a testnet runtime upgrade,
and exercise the upgrade, outage and catch-up procedures. Provide a
separate RPC endpoint for wallets and apps, with monitoring and limits,
before inviting public testers. The private rehearsal disabled its sudo key
and its two equal validators stalled when peering was interrupted. The
public testnet needs a tested upgrade path and a validator topology that
meets its outage requirements.
