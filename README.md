# IINK development starter

IINK is a proposed independent Rust blockchain for payments and games. Token display: **$IINK**; chain metadata symbol: **IINK**.

This starter adapts the official Polkadot SDK standalone template. It is source scaffolding, not a tested network release. The Rust node has **not been compiled or run** in this preparation session. EVM, Move, production staking, production token economics, and public deployment are not implemented here.

## Included

- Upstream node/runtime and development pallets, with the original dependency lockfile.
- IINK development/local network names, distinct protocol identifiers, and test-token display metadata.
- A browser development-container configuration, with no automatic build or dependency installation.
- Build preflight, resource logging, local development launch, and RPC/finality smoke-check scripts.
- Source provenance in `UPSTREAM.json` and the current project brief in `docs/PROJECT_SCOPE.md`.

Upstream crate and binary names remain unchanged to keep the initial patch small. Development tokens use the inherited 12 decimal places. That display choice does not establish a production supply or fee schedule. The upstream default development accounts and privileged development key remain present and must never be used for real funds.

## Open in GitHub Codespaces

1. Open https://github.com/Jedid1ahh/iink and check your Codespaces usage and billing controls. Stay within your free quota and do not enable paid overages.
2. Select **Code → Codespaces → Create codespace on main**. Source files are already in the repository; no ZIP upload is needed.
3. Wait for the development environment to open. The configuration does not automatically install Rust dependencies, compile the chain, or open RPC ports.
4. Use the terminal inside Codespaces for the commands below. The development container requests at least two cores, 8 GB RAM, and 32 GB disk; these are starting resource requests, not a guarantee that the build will fit.

Codespaces account eligibility, remaining quota, and billing controls have not been verified. No Codespace has been created by this repository setup.

## Prepare the remote Linux environment

Run these in the remote Linux development terminal:

```bash
sudo apt-get update
sudo apt-get install -y build-essential clang libclang-dev pkg-config libssl-dev protobuf-compiler cmake
rustup toolchain install 1.84.1 --profile minimal --component rust-src --component rustfmt --component clippy --target wasm32-unknown-unknown
bash scripts/preflight.sh
```

If `rustup` is unavailable, follow the official Rust installer at https://www.rust-lang.org/tools/install inside the remote environment, then retry. The pinned version is an **evaluation candidate** based on the stable2503 SDK CI environment. It has not been validated against this complete scaffold. Do not silently update the lockfile or toolchain to bypass an error; retain the error and investigate.

The preflight thresholds are conservative experiment checks, not validated hardware specifications. A pass does not guarantee a successful build or sufficient monthly quota. The container image uses a version tag, not an immutable digest; this is not yet a fully reproducible environment.

## Build and inspect

```bash
bash scripts/build.sh
```

This builds one node package with the original lockfile and one compilation job. Logs and available resource measurements go to `artifacts/`. Stop if resources or quota are insufficient; do not purchase capacity automatically. If the build succeeds, run:

```bash
bash scripts/run-dev.sh
```

In a second terminal:

```bash
python3 scripts/check_rpc.py
```

The check verifies network metadata and observes an increase in finalized height. It does not test payments, multiple-node agreement, adversarial consensus, or production safety. RPC remains on loopback. Keep forwarded ports private; browser-wallet integration is a later step. `--tmp` intentionally discards development state on exit. Stop the node with Ctrl+C, then stop the Codespace when finished.

## Next evidence required

1. Successful node and Wasm build with recorded resource consumption.
2. RPC smoke check against the real compiled node.
3. Native transfer, fee, signature, replay, and supply-accounting tests.
4. A multi-node development network with agreement and restart checks.
5. A supported SDK/Frontier compatibility baseline and a separate Move feasibility experiment.

Move remains undecided. Aptos-style Move is only a candidate. The inherited SDK baseline is dated May 2025; it must be reviewed for maintenance and advisories before further adoption. No production security claim is made.

## Cost and automation

No automatic GitHub Actions workflows are active. Original workflow files are preserved as text in `docs/upstream-workflows/` because their automatic multi-platform builds are inappropriate for an unverified $0 account budget. No CI run has occurred. Check current provider allowances directly, preserve work in Git, and monitor storage even after stopping a codespace.

## Provenance and licensing

See `UPSTREAM.json`, `LICENSE`, the existing Cargo manifests, and `docs/UPSTREAM_README.md`. Original source and dependency notices are retained. Upstream manifest license declarations differ between workspace and node; review actual component licenses before distribution. This project is independent of Kraken's Ink chain and the ink! smart-contract language.
