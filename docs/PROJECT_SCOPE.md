# IINK project scope

## Product objective

An independent Rust blockchain for payments and games, with very low native-token fees and an eventual EVM-and-Move contract environment. The chain name is IINK; the display ticker is $IINK; protocol token metadata uses IINK.

## Current development baseline

This repository contains an evaluation-only standalone Polkadot SDK template with IINK development-network metadata. It retains the upstream development balances, native fees, Aura/GRANDPA implementation, and development administration. It does not implement EVM, Move, a production validator economy, or a public network.

The original source commit and proposed toolchain are recorded in UPSTREAM.json. This baseline is not an assertion of current security support. Review SDK maintenance, advisories, and Frontier compatibility before further adoption. Move dialect remains unresolved; Aptos-style Move is a candidate only.

## First milestone acceptance criteria

1. Compile the native node and embedded runtime Wasm using the recorded toolchain and lockfile.
2. Record build memory, elapsed time, disk consumption, and dependency failures.
3. Verify IINK chain/token metadata and advancing finality through the local RPC.
4. Demonstrate native transfers, defined fee handling, invalid-signature rejection, replay rejection, and supply accounting.
5. Demonstrate consistent finalized state across multiple simulated nodes and successful restart/synchronization.

Each criterion needs observed execution evidence. Source presence, syntax checks, and a generated script do not establish that a criterion passed.

## Subsequent milestones

- Select a supported SDK/Frontier combination and test EVM contract deployment, transactions, RPC behavior, and wallet compatibility.
- Run a Move integration experiment covering deterministic execution, authentication, resource metering, and storage commits before choosing a dialect.
- Specify the canonical native-token ledger and explicit cross-VM interfaces.
- Specify and test validator admission, economics, upgrades, and recovery.
- Recruit independent operators and complete the appropriate security reviews before production use.

Payments initially mean test-token transfers. Games initially mean a small on-chain asset or purchase example. Fiat services, a full game client, bridges, and production token distribution are outside the starter milestone.

## Operating constraints

Use a browser-based Linux development environment and free included capacity. No paid infrastructure, automatic heavy CI workflows, or public deployment is enabled by this repository. Track usage and stop work when free capacity is exhausted. Keep development RPC private.

## Production decisions still open

Supported dependency versions, Move dialect, account/address mapping, consensus and validator admission parameters, public identifiers, token supply and allocation, fee targets, governance, production funding, and audit scope all require decisions and evidence before launch.
