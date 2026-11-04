# IINK development starter

IINK is a proposed independent Rust blockchain for payments and games. Token display: **$IINK**; chain metadata symbol: **IINK**.

This starter adapts the official Polkadot SDK standalone template. It is source scaffolding, not a tested network release. The Rust node has **not been compiled or run** in this preparation session. EVM, Move, production staking, production token economics, and public deployment are not implemented here.

## Included

- Upstream node/runtime and development pallets, with the original dependency lockfile.
- IINK development/local network names, distinct protocol identifiers, and test-token display metadata.
- An Ubuntu 24.04 development image that installs the pinned Rust toolchain and native build dependencies automatically; blockchain compilation is started manually.
- Build preflight, resource logging, local development launch, and RPC/finality smoke-check scripts.
- Source provenance in `UPSTREAM.json` and the current project brief in `docs/PROJECT_SCOPE.md`.

Upstream crate and binary names remain unchanged to keep the initial patch small. Development tokens use the inherited 12 decimal places. That display choice does not establish a production supply or fee schedule. The upstream default development accounts and privileged development key remain present and must never be used for real funds.

## Open in GitHub Codespaces

1. Open https://github.com/Jedid1ahh/iink and check your Codespaces usage and billing controls. Stay within your free quota and do not enable paid overages.
2. Select **Code → Codespaces → Create codespace on main**. Source files are already in the repository; no ZIP upload is needed.
3. Wait for the development image to install its dependencies and open. The creation log must finish successfully. The post-create check prints Rust and Protobuf versions. Blockchain compilation is started manually.
4. Use the terminal inside Codespaces for the commands below. The development container requests at least two cores, 8 GB RAM, and 32 GB disk; these are starting resource requests, not a guarantee that the build will fit.

Codespaces account eligibility, remaining quota, and billing controls have not been verified. No Codespace has been created by this repository setup.

## Prepare or repair the Codespaces environment

The image installs `rustup`, `cargo`, `rustc`, the Wasm target, `rust-src`, Clippy, rustfmt, and native packages including `protobuf-compiler`. Rust's version and component list are read from `rust-toolchain.toml`. There is no separate Yarn package repository to repair in this image.

If your existing Codespace reports missing Rust tools or an unrelated Yarn signing-key error:

1. Save files in `/workspaces/iink`. A rebuild preserves `/workspaces`, but other container-local installations and files can be lost; copy any files you need from elsewhere into the workspace first.
2. Run `git pull --ff-only origin main`. If Git reports local changes or a conflict, preserve those changes and resolve it before rebuilding; do not use a hard reset.
3. Press **Ctrl+Shift+P**, select **Codespaces: Rebuild Container**, then select **Full Rebuild**. This clears old image caches and applies the repository's new Dockerfile. Do not delete the Codespace.
4. Wait for setup to finish, then run:

```bash
rustc --version
cargo --version
protoc --version
bash scripts/preflight.sh
```

Full rebuild behavior and persistence are documented at https://docs.github.com/en/codespaces/developing-in-a-codespace/rebuilding-the-container-in-a-codespace . Setup consumes Codespaces time and storage from the account's allowance. Check remaining quota; this change does not select a paid machine or enable overages.

If creation fails, share the first error from the creation log. If the build stops because of low disk space, collect these read-only measurements:

```bash
df -h /workspaces/iink
du -xhd1 /workspaces "$HOME/.cargo" "$HOME/.rustup" /var/cache/apt 2>/dev/null | sort -h
```

The preflight reports available space and allows starting below the 20 GiB estimate. The build samples free space in the workspace, Cargo cache, and target directory (including a target directory set through an environment variable). It stops the compiler when a sample reaches the 2 GiB reserve and preserves the log and intermediate files. Actual build size remains unmeasured.

The Rust version remains an evaluation candidate from stable2503 SDK CI; node compilation has not yet been validated. The base image uses the Ubuntu `noble` tag rather than an immutable digest, so this is not yet a fully reproducible environment.

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

## Run the local two-validator testnet

Stop any nodes using ports 9944 or 9945 with **Ctrl+C** in their terminals. Use the existing release binary from the repository.

1. In **Terminal 1**, run `bash scripts/run-local-validator.sh alice` and wait for the RPC server message.
2. In **Terminal 2**, run `bash scripts/run-local-validator.sh bob`. The script finds Alice's peer ID and uses it to connect Bob.
3. In **Terminal 3**, run `python3 scripts/check-local-finality.py`. It checks both finalized block hashes, waits 20 seconds, and checks that finality advanced.

In Codespaces the launch script uses `/workspaces/iink-local-alice` and `/workspaces/iink-local-bob`. It creates a network key only if that validator's key is missing. Use the same launch commands after a restart to keep each node's key and database. The check uses system Python. After starting both nodes, a `Pre-sealed block` line in each terminal shows that both are authoring blocks.

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
