# Frontier contract experiment

This is the historical experiment. Use the
[`experiment/frontier-shared-ledger` branch](https://github.com/Jedid1ahh/iink/tree/experiment/frontier-shared-ledger)
for the commands below. The integrated release uses the root workspace and the
commands in the repository README.

Build the upstream Frontier standalone template and exercise a Solidity contract on an isolated development chain. The test sends two signed Ethereum transactions, waits for each receipt's block to finalize, and checks that the deployed counter changes from 7 to 8.

## Pinned inputs

- [Frontier stable2603 template](https://github.com/polkadot-evm/frontier/tree/baf505d8feeaaa0ba636a003faa49e4ad897b592), commit `baf505d8feeaaa0ba636a003faa49e4ad897b592`.
- [SDK revision in Frontier's Cargo.lock](https://github.com/paritytech/polkadot-sdk/commit/d3dfb281ee0f62c3b8bcda36c35c46f82f2d8878), commit `d3dfb281ee0f62c3b8bcda36c35c46f82f2d8878`. The [stable2603 line received a patch release on October 29, 2026](https://github.com/paritytech/polkadot-sdk/releases/tag/polkadot-stable2603-8). The experiment uses Frontier's published lockfile revision. Compatibility with that later patch needs a separate build and test.
- Rust 1.88.0 with `rust-src` and `wasm32v1-none`. Solidity 0.8.30 compiled `Counter.sol` with target `paris`, default optimizer settings, and metadata bytecode hash disabled.

The template uses 20-byte Ethereum accounts. IINK's tested payment chain uses 32-byte accounts. A later integration must define the mapping between these accounts, preserve a single native balance ledger, and verify fees before enabling the EVM path on IINK. The lab uses the upstream development genesis and Alith test account.

## Run in Codespaces

From the IINK repository on this branch:

```bash
bash scripts/frontier-spike.sh build
```

This installs the additional Rust toolchain and builds one release node from the locked Frontier checkout. It stores Frontier source and build files in the sibling `/workspaces/iink-frontier-2603` directory. Expect a substantial compilation. Check free disk and Codespaces quota before starting. The existing disk guard checks for the 2 GiB reserve, and the build log is at `artifacts/frontier-build.log`.

Once it builds, start the lab node and leave that terminal running:

```bash
bash scripts/frontier-spike.sh run
```

The lab uses temporary chain data, local RPC port 9966, and local peer port 30366. Keep its ports private.

In another terminal:

```bash
python3 -m venv /workspaces/iink-frontier-client &&
/workspaces/iink-frontier-client/bin/python -m pip install eth-account==0.13.7 &&
/workspaces/iink-frontier-client/bin/python scripts/check-frontier-counter.py
```

Expect a `PASS` line showing the contract address and the change from 7 to 8. Each run deploys a new test contract. A finalized receipt with the wrong block hash, missing contract code, or unexpected counter value fails the check.
