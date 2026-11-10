// Verify the shared payment logic selects the configured chain and rejects the other one.
import assert from "node:assert/strict";
import { mkdtemp, mkdir, copyFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const directory = await mkdtemp(join(tmpdir(), "iink-network-check-"));
try {
  for (const privateNetwork of [false, true]) {
    const name = privateNetwork ? "private" : "local";
    const id = privateNetwork ? "0x7a6f" : "0x7a6e";
    const chain = privateNetwork ? "IINK Private Testnet" : "IINK Local Testnet";
    // Use a separate directory per module graph so Node cannot reuse the other network's config.
    const graph = join(directory, name);
    await mkdir(graph);
    await copyFile(new URL("../apps/payments/payments.mjs", import.meta.url), join(graph, "payments.mjs"));
    if (privateNetwork) {
      await writeFile(join(graph, "network.mjs"),
        `export const CHAIN_ID = ${JSON.stringify(id)}; export const CHAIN_NAME = ${JSON.stringify(chain)}; export const NETWORK_KEY = "private";`);
    } else {
      await copyFile(new URL("../apps/payments/network.mjs", import.meta.url), join(graph, "network.mjs"));
    }
    const module = await import(pathToFileURL(join(graph, "payments.mjs")));
    assert.equal(module.CHAIN_ID, id);
    assert.equal(module.NETWORK_KEY, privateNetwork ? "private" : "31342");
    const request = async method => ({ eth_chainId: id, system_chain: chain })[method];
    await module.verifyNetwork(request);
    await assert.rejects(module.verifyNetwork(async method => method === "eth_chainId" ? "0x1" : chain));
    assert.equal(module.parseAmount("0.1"), 100000000000000000n);
    assert.equal(module.formatIink(10500000000000000n), "0.0105 IINK");
    // Both apps must use the same configured chain to add a network in MetaMask.
    await copyFile(new URL("../apps/payments/wallet.mjs", import.meta.url), join(graph, "wallet.mjs"));
    const { switchNetwork } = await import(pathToFileURL(join(graph, "wallet.mjs")));
    const calls = [];
    await switchNetwork({ request: async call => {
      calls.push(call);
      if (call.method === "wallet_switchEthereumChain") throw Object.assign(new Error(), { code: 4902 });
      if (call.method === "eth_chainId") return id;
    }});
    const added = calls.find(call => call.method === "wallet_addEthereumChain").params[0];
    assert.equal(added.chainId, id);
    assert.equal(added.chainName, chain);
    assert.equal(added.nativeCurrency.decimals, 18);
    assert.deepEqual(added.rpcUrls, ["http://127.0.0.1:9944"]);
    console.log(`PASS: ${chain} configuration, wallet parameters, and amount handling.`);
  }
} finally {
  await rm(directory, { recursive: true, force: true });
}
