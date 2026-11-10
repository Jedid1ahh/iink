# Two-host private testnet rehearsal

The setup is ready for a rehearsal on two existing Codespaces. This milestone
passes after both hosts demonstrate finalized agreement, restart recovery,
and working Payments and Glimmer Run transactions. It remains a test-token
network. Two authorities, disabled sudo, and no validator replacement
mechanism are not a production configuration.

Use your remaining included Codespaces allowance with paid usage blocked in
GitHub billing. Both running machines consume allowance. These instructions
do not create machines or enable paid usage. Windows relays private SSH
traffic and does not run a validator or compile Rust.

## Select the hosts

In Windows PowerShell:

```powershell
gh codespace list -R Jedid1ahh/iink
$ValidatorA = Read-Host "Full NAME of your current game Codespace"
$ValidatorB = Read-Host "Full NAME of the other existing Codespace"
if ($ValidatorA -eq $ValidatorB) { throw "Choose two different Codespaces" }
$Transfer = Join-Path $env:USERPROFILE "iink-private-transfer"
New-Item -ItemType Directory -Force -Path $Transfer | Out-Null
```

Use the `NAME` column, rather than a display name such as “stunning yodel”.
If only one exists, report the list before provisioning anything. Check your
remaining included usage in GitHub billing.

Open both Codespaces. In **each Codespace terminal**:

```bash
cd /workspaces/iink &&
git fetch origin &&
git switch experiment/private-testnet &&
git pull --ff-only origin experiment/private-testnet
```

Stop the old Alice, Bob, and app processes with Ctrl+C in their original
terminals. Stop the old Windows `gh codespace ports forward` session too,
freeing ports 9944 and 8000. Retain the old databases. The new network uses
separate directories and Ethereum chain ID **31343**.

## Copy the executable and prepare keys

In **B's Codespace terminal**:

```bash
mkdir -p /workspaces/iink-private-bin
```

In the original **Windows PowerShell**:

```powershell
gh codespace cp -c $ValidatorA remote:/workspaces/iink-frontier-2603/target/release/iink-node "$Transfer/iink-node"
if ($LASTEXITCODE -ne 0) { throw "Executable download failed" }
gh codespace cp -c $ValidatorB "$Transfer/iink-node" remote:/workspaces/iink-private-bin/iink-node
if ($LASTEXITCODE -ne 0) { throw "Executable upload failed" }
```

In **A's Codespace terminal**:

```bash
cd /workspaces/iink &&
python3 scripts/private-testnet.py prepare a
```

In **B's Codespace terminal**:

```bash
cd /workspaces/iink &&
chmod 700 /workspaces/iink-private-bin/iink-node &&
python3 scripts/private-testnet.py prepare b --node /workspaces/iink-private-bin/iink-node
```

Each host generates random Aura, GRANDPA, and networking keys. Repeating
preparation retains and verifies them. Exchange only `public.json`. Keep
`.suri` files, `network.key`, keystores, and wallet recovery phrases private
on their original hosts.

If GitHub CLI reports that the Codespace lacks an SSH server, run
`sudo apt-get update && sudo apt-get install -y openssh-server` in that
Codespace and retry. This does not require a container rebuild.

## Create and share the genesis

In the original **Windows PowerShell**:

```powershell
gh codespace cp -c $ValidatorB remote:/workspaces/iink-private-b/public.json "$Transfer/b-public.json"
if ($LASTEXITCODE -ne 0) { throw "Public identity download failed" }
gh codespace cp -c $ValidatorA "$Transfer/b-public.json" remote:/workspaces/b-public.json
if ($LASTEXITCODE -ne 0) { throw "Public identity upload failed" }
```

Choose two different MetaMask public account addresses for shop and player.
Existing test accounts can be used. In **A's Codespace terminal**:

```bash
cd /workspaces/iink &&
read -r -p "Shop public wallet address: " shop_wallet &&
read -r -p "Player public wallet address: " player_wallet &&
python3 scripts/private-testnet.py create \
  --a /workspaces/iink-private-a/public.json \
  --b /workspaces/b-public.json \
  --wallet "$shop_wallet" --wallet "$player_wallet" \
  --output /workspaces/iink-private-network
```

Each wallet starts with 1,000 test IINK. Its Ethereum spendable balance
excludes the 0.001 IINK native reserve. Public development accounts receive
no endowment; sudo is disabled. The creator refuses to overwrite an existing
network directory. Retain these specs; changing genesis creates a new chain.

Copy the public spec directory to B in the original **Windows PowerShell**:

```powershell
gh codespace cp -r -c $ValidatorA remote:/workspaces/iink-private-network $Transfer
if ($LASTEXITCODE -ne 0) { throw "Spec download failed" }
gh codespace cp -r -c $ValidatorB "$Transfer/iink-private-network" remote:/workspaces/
if ($LASTEXITCODE -ne 0) { throw "Spec upload failed" }
```

Launchers verify the spec and binary checksums and their local keys.
Public manifests record `CODESPACE_NAME` and reject identical host IDs.
This is self-reported metadata, not remote hardware attestation. Run each
validator in its selected Codespace and retain both names with the results.

## Connect the hosts privately

Open **two new Windows PowerShell windows**. Enter the full Codespace name
again; variables are not shared between windows. Leave both commands running.

In **PowerShell A**:

```powershell
$ValidatorA = Read-Host "Validator A full Codespace NAME"
gh codespace ssh -c $ValidatorA -- -N `
  -L 127.0.0.1:13033:127.0.0.1:30333 `
  -R 127.0.0.1:13034:127.0.0.1:13034 `
  -R 127.0.0.1:9945:127.0.0.1:19945 `
  -L 127.0.0.1:9944:127.0.0.1:9944 `
  -L 127.0.0.1:8000:127.0.0.1:8000 `
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3
```

In **PowerShell B**:

```powershell
$ValidatorB = Read-Host "Validator B full Codespace NAME"
gh codespace ssh -c $ValidatorB -- -N `
  -L 127.0.0.1:13034:127.0.0.1:30334 `
  -R 127.0.0.1:13033:127.0.0.1:13033 `
  -L 127.0.0.1:19945:127.0.0.1:9945 `
  -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3
```

Nodes listen only on loopback and use each other as reserved peers. SSH
carries their connections through Windows. It also connects A's port 9945
to B's RPC, and Windows ports 9944 and 8000 to A's RPC and apps. No port
needs public visibility. A bind failure means a port is already occupied;
stop the old process and retry. Keep Windows awake during the rehearsal.

## Start and verify the validators

In **A's Codespace terminal**:

```bash
cd /workspaces/iink &&
python3 scripts/private-testnet.py run a \
  --network /workspaces/iink-private-network/network.json
```

In **B's Codespace terminal**:

```bash
cd /workspaces/iink &&
python3 scripts/private-testnet.py run b \
  --node /workspaces/iink-private-bin/iink-node \
  --network /workspaces/iink-private-network/network.json
```

Leave both running. In another **A terminal**:

```bash
cd /workspaces/iink &&
python3 scripts/private-testnet.py check \
  --network /workspaces/iink-private-network/network.json \
  --checkpoint /workspaces/iink-private-finality.json
```

The check verifies chain identity, token metadata, expected peer IDs,
matching genesis, connected peers, and advancing finalized agreement. It
saves a finalized hash for recovery checks. Distinct RPC URLs alone do not
prove separate machines.

## Exercise Payments and Glimmer Run

In another **A terminal**:

```bash
cd /workspaces/iink &&
python3 apps/payments/serve.py --network /workspaces/iink-private-network/network.json
```

Reload [IINK Payments](http://127.0.0.1:8000/) on Windows. Its header must
show **IINK Private Testnet**. Connect MetaMask and approve adding/switching
to chain **31343**, RPC `http://127.0.0.1:9944`, currency IINK. The app checks
the chain name and ID before quoting or tracking a transaction and uses
separate saved state for this private network.

Send 0.1 test IINK between the funded accounts and wait for finality. Open
[Glimmer Run](http://127.0.0.1:8000/game/), deploy a new shop from the shop
account, switch to the player, buy a pass, and start an eleven-move run
after finality. Do not reuse the local-chain shop contract. Record fees
and hashes. Check each payment, deployment, and purchase hash from **A**:

```bash
cd /workspaces/iink &&
read -r -p "Transaction hash: " tx_hash &&
python3 scripts/private-testnet.py check \
  --network /workspaces/iink-private-network/network.json \
  --checkpoint /workspaces/iink-private-finality.json \
  --transaction "$tx_hash"
```

This requires matching successful canonical receipts finalized on both
validators. It does not replace the earlier balance and issuance checks.

## Restart and reconnect

1. Keep the saved checkpoint. Stop B's validator with Ctrl+C. Both equal
   authorities are needed for finality; a pause during B's absence is
   expected. This two-validator topology does not provide outage tolerance.
2. Restart B with the exact same `run b` command and saved files. After
   reconnection, repeat the finality checker. The saved finalized hash must
   remain intact and both nodes must advance finality.
3. Stop PowerShell B's SSH command with Ctrl+C, restart that same command,
   and repeat the checker after reconnection. Record this result too.
4. Reload the game with the player selected. The finalized pass must still
   be owned and the next run must have eleven moves. Recheck the original
   purchase hash after recovery.

Retain data if a restart fails; report the error for inspection. Do not
regenerate genesis or delete databases as a recovery step. Finish by stopping
the validators, app, SSH sessions, and both Codespaces. Later restarts use
the same files, tunnels, and launch commands.

Milestone completion requires two distinct Codespace names and peer IDs,
matching executable/spec checksums, advancing finality before and after
restart and tunnel reconnection, finalized Payments/game receipts on both
nodes, and retained eleven-move player access after recovery.

References: [GitHub CLI SSH](https://cli.github.com/manual/gh_codespace_ssh),
[file copying](https://cli.github.com/manual/gh_codespace_cp), and
[included usage](https://docs.github.com/en/billing/reference/product-usage-included).
