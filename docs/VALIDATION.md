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

Multi-validator execution and restart recovery for this integrated build
are the next validation milestone.
