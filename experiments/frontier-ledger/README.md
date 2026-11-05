# IINK shared ledger experiment

The standalone Frontier counter test verified that two signed Ethereum
transactions can deploy and update a Solidity contract. This lab adds the
next integration check to the same pinned SDK and Frontier pair. It uses a
fresh genesis with funded native Alice and Bob accounts.

- Native transactions use `MultiSignature` and 32-byte accounts.
- Frontier maps each 20-byte Ethereum address into a 32-byte account using
  `blake2_256(b"evm:" || address)`. Both transaction paths use FRAME Balances.
- IINK has 12 decimals and a 0.001 IINK existential deposit in this lab.
  Ethereum RPC reports spendable balance. For these unencumbered funded
  accounts it excludes the existential deposit.
- Native EVM call and withdrawal entry points are disabled in this lab.
  Ethereum signatures authorize Ethereum transactions through Frontier.
  A secure return path to ordinary native accounts is a separate test gate.
- The base fee is burned. The test uses a zero priority fee and checks
  the supply reduction against the finalized Ethereum receipt.

The lab has temporary state, a distinct binary, RPC on port 9967, and a
development-only Ethereum chain ID of 31337. Keep the ports private.
The IINK native testnet on `main` has its own history and runtime.
This experiment does not migrate it.

## Build and verify in Codespaces

Stop the original Frontier lab with **Ctrl+C**. In the same terminal, on
`experiment/frontier-shared-ledger`, run:

```bash
bash scripts/frontier-spike.sh build-ledger &&
bash scripts/frontier-spike.sh run-ledger
```

The build reuses the original Frontier checkout and its Cargo target
directory. It produces a separate binary and writes
`artifacts/frontier-ledger-build.log`. The 2 GiB disk guard remains active.

When the node starts its RPC server, open a second terminal. This assumes
the Python environment used for the Frontier counter already exists:

```bash
/workspaces/iink-frontier-client/bin/python -m pip install --no-cache-dir substrate-interface==1.8.1 &&
/workspaces/iink-frontier-client/bin/python scripts/check-frontier-ledger.py
```

The script funds a fresh Ethereum address with a native transfer, waits
for finality, and verifies that Ethereum RPC sees the spendable funds.
It then sends a signed 1 IINK Ethereum payment and compares both mapped
accounts and total issuance at the finalized payment block. Each run
uses fresh test keys.

A successful run prints two `PASS` lines. Before any public testnet,
also verify the contract check below, the secure return path, replay
protection, wallet denomination, and multi-node finality.

## Deploy and exercise a Solidity contract

With the ledger node still running on port 9967, use the same Python
environment and run this in the second terminal:

```bash
/workspaces/iink-frontier-client/bin/python scripts/check-frontier-ledger.py --counter
```

The check uses a native transfer to fund a fresh deployer. It deploys the
same compiled Solidity counter from the isolated Frontier test and verifies
the finalized bytecode, the initial value of 7, and the value of 8 after
the increment. It also checks that both RPCs agree on the deployer's
remaining spendable balance and that native issuance decreased by the
gas fees for both transactions. Expect three `PASS` lines.
