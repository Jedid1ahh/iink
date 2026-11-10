# IINK integrated development release

IINK is an independent Rust blockchain project for payments and games. The
development network uses **IINK** test tokens with 18 decimal places. The
`iink-node` binary exposes native and Ethereum RPCs over one balance ledger.
The runtime supports Solidity contracts and transfers between native and
Ethereum accounts through the shared ledger.

The development chains use public test keys. Keep RPC and forwarded ports
private and use test funds. The wallet compatibility development genesis uses
Ethereum chain ID 31341 and its two-validator local testnet uses 31342. Their
chain and protocol identifiers separate them from the earlier 12-decimal
development networks and Frontier lab. Each chain starts with fresh test funds.

## Build and run

Use the Linux development container or install the prerequisites from
[`.devcontainer/Dockerfile`](.devcontainer/Dockerfile). Rust 1.88.0 and the
`wasm32v1-none` target are declared in [`rust-toolchain.toml`](rust-toolchain.toml).
In an existing Codespace, keep your files under `/workspaces` and use
**Codespaces: Rebuild Container** if the pinned tools are missing.

```bash
bash scripts/build.sh
bash scripts/run-dev.sh
```

The locked build embeds runtime Wasm and writes its log and resource
measurements to `artifacts/`. It defaults to one build job to reduce memory
pressure. The disk guard stops the build at its 2 GiB reserve. Monitor free disk
and included Codespaces quota. To reuse a build cache, set the same absolute
`CARGO_TARGET_DIR` for the build and launch. The development launch keeps RPC
on loopback port 9944 and uses temporary chain state.

## Verify the development release

Leave the node running. In a second terminal, use your existing
`/workspaces/iink-frontier-client` environment or set up a client:

```bash
python3 -m venv /workspaces/iink-frontier-client
/workspaces/iink-frontier-client/bin/python -m pip install --no-cache-dir \
  eth-account==0.13.7 substrate-interface==1.8.1
```

Run the checks sequentially on a quiet development node:

```bash
bash scripts/check-development.sh /workspaces/iink-frontier-client/bin/python
```

The checks cover finality, native funding of an Ethereum payment, Solidity
deployment and calls, Ethereum-to-native transfers, rejection of malformed
returns and replays, and fee and supply accounting at finalized blocks.
The payment and contract checks use fresh test accounts.

## Run two local validators

Use a separate terminal for each validator. Free ports 9944 and 9945 before
starting Alice and Bob.

```bash
bash scripts/run-local-validator.sh alice
```

When Alice's RPC is available, run this in the second terminal:

```bash
bash scripts/run-local-validator.sh bob
```

Then run `python3 scripts/check-local-finality.py` from a third terminal.
The validator launchers save each node's data under
`/workspaces/iink-wallet-local-alice` and `/workspaces/iink-wallet-local-bob`
in Codespaces. Use the same launch commands to restart with the saved keys
and databases. The existing `scripts/check-local-payment.py` checks a signed
native transfer, replay protection, and fee accounting across both nodes.

## Check a MetaMask payment

Run both local validators and wait for `scripts/check-local-finality.py` to
pass. If the validators are in Codespaces, forward Alice's RPC privately to
your desktop. Run this in a terminal on your computer and select the Codespace.
[GitHub's port forwarding guide](https://docs.github.com/en/codespaces/developing-in-a-codespace/forwarding-ports-in-your-codespace?tool=cli)

```bash
gh codespace ports forward 9944:9944
```

Add a custom network to the MetaMask extension with these settings. Use a
fresh test account and a different Ethereum address as the recipient.
[MetaMask's custom network guide](https://support.metamask.io/configure/networks/how-to-add-a-custom-network-rpc)

| Setting | Value |
| --- | --- |
| Network name | IINK Local Testnet |
| RPC URL | `http://127.0.0.1:9944` |
| Chain ID | `31342` |
| Currency symbol | `IINK` |

Fund the sender by running this in the Codespace with the Python environment
from the development checks. Supply the sender's public Ethereum address.

```bash
/workspaces/iink-frontier-client/bin/python scripts/check-frontier-ledger.py \
  --fund-wallet 0xSENDER_ADDRESS
```

MetaMask should show about 1.999 spendable IINK after funding. The shared
ledger reserves 0.001 IINK to keep the account alive. Send exactly 1 IINK to
the recipient in MetaMask. Review the network fee and copy the transaction
hash from the activity details. While the validators are otherwise idle,
verify the hash from the Codespace.

```bash
/workspaces/iink-frontier-client/bin/python scripts/check-frontier-ledger.py \
  --wallet-payment 0xTRANSACTION_HASH
```

The verifier waits for finality on both validators and checks the receipt,
native and Ethereum balances, and fee burn. On a fresh recipient account,
the 1 IINK credit leaves 0.999 spendable IINK.

## Run the payments dApp

Keep Alice and Bob running on the wallet testnet. The dApp uses the installed
MetaMask extension for approval. The app server relays read-only requests to
Alice for fee estimates and finalized receipts. Start it in a separate
Codespace terminal.

```bash
python3 apps/payments/serve.py
```

Keep the private tunnel for port 9944 open. From a second terminal on your
computer, forward port 8000 to the same Codespace.

```bash
gh codespace ports forward 8000:8000
```

Open `http://127.0.0.1:8000` in the browser that has MetaMask. Connect the
wallet, select the funded test account, and enter a different Ethereum
address and an amount. Review the estimated fee in the dApp, then check the
amount and fee shown in MetaMask before approving. The receipt displays the
transaction hash immediately and the actual fee once the payment finalizes.

For a 1 IINK transfer, copy the receipt hash and use the wallet payment
verifier above to reconcile it independently on both validators.

## Play Glimmer Run

Start or restart the app server and keep both localhost tunnels from the
payments dApp setup. Open `http://127.0.0.1:8000/game/`. Collect the three
glimmers within eight moves using the arrow keys or the neighboring tiles.

Connect a funded test shop account and choose **Deploy demo shop**. Approve
the deployment in MetaMask and wait for it to finalize. Switch to a different
funded test account and choose **Buy Courier Pass**. The price is 0.1 test
IINK plus the network fee. The shop contract sends the price to the account
that deployed it and records one pass per buyer.

When the purchase finalizes, the game shows **Pass owned**. Choose **New run**
and check that the move counter starts at 11. The game rechecks finalized
ownership on reload and when you change wallets.

## Source and scope

The [source record](UPSTREAM.json) lists the exact Frontier, Polkadot SDK,
and EVM revisions. The local node and runtime adapt Frontier's template
with IINK's verified shared-ledger changes. Their manifests retain the
upstream Unlicense declaration. Dependency licenses are recorded in their
respective sources. See [the project scope](docs/PROJECT_SCOPE.md) and
[validation notes](docs/VALIDATION.md) for development evidence and remaining
work. The repository has no automatic build workflow.
