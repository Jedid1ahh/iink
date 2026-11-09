# Validation status — 3 November 2026

Passed during starter preparation:
- Shell syntax checks for preflight, build, and development-run scripts.
- JSON and TOML parsing.
- Python RPC-checker syntax parsing.
- Upstream commit identity verification.
- Confirmation that Cargo.lock is unchanged.
- Confirmation that no automatic GitHub Actions workflow is active.
- Git whitespace/diff checks.

The preflight correctly refused to proceed in this preparation environment because Rust and several native build prerequisites are missing.

Not performed: Rust compilation, runtime Wasm build, dependency advisory audit, actual node execution, RPC calls against a blockchain node, transaction tests, multi-node consensus testing, EVM integration, or Move integration. This package must not be described as a working or audited blockchain.

## Environment repair — 4 November 2026

Replaced the universal development image with a focused Ubuntu Noble Dockerfile. Native prerequisites and the Rust toolchain from rust-toolchain.toml are installed during image creation. A post-create command verifies the tools are callable. Existing Codespaces must pull the change and perform a Full Rebuild.

Validated JSON/TOML/Python parsing, shell syntax (including Dockerfile RUN instructions), installer command generation against the pinned toolchain, and installer failure propagation. Docker/Podman are unavailable in the preparation environment, so the image itself has not been built here. Node compilation and available disk after Codespaces rebuild remain unverified.

## Integrated development release — 5 November 2026

A clean target directory produced the optimized `iink-node` and embedded
runtime Wasm using the locked dependencies, Rust 1.88.0, Clang 19 and
LLD. The Linux build took 13 minutes 28 seconds with five Cargo jobs.
Build outputs occupied about 6 GiB, excluding the dependency download
cache. A subsequent build stamped the source commit into the executable
and produced the same compressed Wasm hash.

Both chain specifications loaded with their own chain and protocol IDs,
the IINK symbol, 12 decimals, and embedded Wasm. The development spec used
Ethereum chain ID 31339 and one Aura authority. The local spec used 31340
and two Aura authorities.

The development node advanced finality and passed all 16 live transaction
checks in `scripts/check-development.sh`:

| Check | Observed result |
| --- | --- |
| Native funding and Ethereum payment | 1 IINK transferred at finalized block 7. Both RPCs agreed on balances and the 10,500,000,000-base-unit fee burn. |
| Solidity counter | The finalized counter advanced from 7 to 8. Deployment and increment burned 82,679,000,000 base units in total. |
| Ethereum-to-native return | The node rejected malformed calldata, attached value, and overspending. A valid return credited native Bob 1 IINK at finalized block 31. |
| Replay protection | A valid return finalized at block 37. The node rejected the duplicate, reused nonce, and wrong-chain signatures. Balances, supply, and the sender nonce held through finalized block 38. |

## Two-validator agreement and restart recovery — 5 November 2026

The published development candidate rejected a native payment block when a
second validator replayed it. Block import recorded storage proofs while
Aura authoring ran without a recorder. That difference affected runtime
weight accounting and produced a different block digest. Aura authoring
and import now both run without a recorder. Manual sealing keeps proof
recording enabled. The locked release rebuild reproduced the same embedded
Wasm hash.

Alice and Bob ran the `local` chain spec with Ethereum chain ID 31340.
The checks read both validators independently at finalized blocks.

| Check | Observed result |
| --- | --- |
| Peering and finality | Distinct validator peer IDs, matching genesis, and matching finalized hashes as finality advanced from block 1 to 4. |
| Native payment | Both nodes agreed on the finalized 1 IINK transfer, balances, and issuance at block 7. The check rejected an invalid signature, a duplicate submission, and a different transaction using the same nonce. |
| Ethereum-to-native return | Both nodes agreed on the receipt, balances, fee burn, and issuance at block 13. |
| Solidity counter | Both nodes agreed on deployment and increment receipts and gas accounting. Each read the value 8 at finalized block 19. |
| Restart and catch-up | Bob stopped at block 19. With a non-voting observer connected, Alice included a native payment at block 23 while finality held at 19. Bob restarted with the same peer ID. Both validators finalized the payment and agreed on balances, issuance, and the historical Solidity state. Shared finality advanced to block 24. |

## Wallet compatibility candidate — 9 November 2026

The network parameter validator shipped in MetaMask Chrome 13.56.0 returned
JSON-RPC error `-32602` for a 12-decimal native currency and accepted the
18-decimal IINK configuration. This check ran the shipped validator in
isolation. [MetaMask Chrome release](https://github.com/MetaMask/metamask-extension/releases/tag/v13.56.0)

The candidate uses new test chain IDs 31341 and 31342 with separate databases.
Both chain specs serialized the exact genesis endowment of 1,000,000 IINK per
funded account at 18 decimals. The optimized node and embedded Wasm built with
the workspace lockfile and an external target directory.

On chain 31342, native funding finalized at block 5. Ethereum RPC reported
1.999 spendable IINK, a 21,000-gas transfer estimate, and populated fee history.
MetaMask HD Keyring 15.0.1 signed a one-IINK EIP-1559 payment. Both validators
finalized it at block 8 and agreed on the receipt, balances, total issuance,
and the 0.0105 IINK fee burn. The native one-IINK payment also finalized on
both validators at block 11. Invalid signature and replay checks passed.

The full `scripts/check-development.sh` suite passed on chain 31341. Native
funding, an Ethereum payment, Solidity deployment and increment, and an
Ethereum-to-native return all finalized. Malformed calldata, attached value,
overspending, and all replay cases were rejected. The final check reconciled
balances, issuance, and nonce through block 38.

The MetaMask extension still needs an interactive check of network setup,
balance display, fee confirmation, and signing in the browser. The workspace
browser could not start an isolated extension profile. The README has the
steps for running that check through a private localhost tunnel.
