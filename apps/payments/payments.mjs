export const RPC_URL = "http://127.0.0.1:9944";
export const CHAIN_ID = "0x7a6e"; // 31342
export const CHAIN_NAME = "IINK Local Testnet";
const UNIT = 10n ** 18n;
const MAX_BALANCE = (1n << 128n) - 1n;

export const isHash = value => typeof value === "string" && /^0x[\da-f]{64}$/i.test(value);

export function parseAmount(text) {
  const match = /^(\d{1,39})(?:\.(\d{1,18}))?$/.exec(text.trim());
  if (!match) throw new Error("Enter an amount with up to 18 decimal places.");
  const amount = BigInt(match[1]) * UNIT + BigInt((match[2] ?? "").padEnd(18, "0"));
  if (amount === 0n || amount > MAX_BALANCE) throw new Error("Enter a positive IINK amount within the supported range.");
  return amount;
}

export function formatIink(value) {
  const fraction = (value % UNIT).toString().padStart(18, "0").replace(/0+$/, "");
  return `${value / UNIT}${fraction ? "." + fraction : ""} IINK`;
}

export function paymentRequest(from, recipient, amount) {
  const to = recipient.trim();
  if (!/^0x[\da-f]{40}$/i.test(to) || /^0x0{40}$/i.test(to)) {
    throw new Error("Enter a valid Ethereum recipient address.");
  }
  if (from.toLowerCase() === to.toLowerCase()) throw new Error("Choose a different recipient account.");
  return { from, to, value: "0x" + parseAmount(amount).toString(16) };
}

export async function rpc(method, params = []) {
  const response = await fetch("/rpc", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
    signal: AbortSignal.timeout(6000),
  });
  if (response.status === 502) throw new Error("Alice’s local RPC is unavailable. Check the validator.");
  if (!response.ok) throw new Error(`The app server returned HTTP ${response.status}.`);
  const data = await response.json();
  if (data.error) throw new Error(data.error.message);
  if (!("result" in data)) throw new Error("The local node returned an incomplete response.");
  return data.result;
}

export async function verifyNetwork(request = rpc) {
  const [id, name] = await Promise.all([request("eth_chainId"), request("system_chain")]);
  if (id !== CHAIN_ID || name !== CHAIN_NAME) throw new Error("The local RPC must serve IINK Local Testnet, chain 31342.");
}

export async function quotePayment(transaction, request = rpc) {
  await verifyNetwork(request);
  const [gas, price, available] = await Promise.all([
    request("eth_estimateGas", [transaction]),
    request("eth_gasPrice"),
    request("eth_getBalance", [transaction.from, "latest"]),
  ]);
  const balance = BigInt(available);
  const fee = BigInt(gas) * BigInt(price);
  const total = BigInt(transaction.value) + fee;
  if (total > balance) throw new Error("Your spendable balance is too low for this amount and the estimated fee.");
  return { balance, fee, total };
}

export async function paymentStatus(hash, request = rpc) {
  await verifyNetwork(request);
  const receipt = await request("eth_getTransactionReceipt", [hash]);
  if (!receipt || receipt.transactionHash?.toLowerCase() !== hash.toLowerCase()) return { stage: "submitted" };

  const finalized = await request("eth_getBlockByNumber", ["finalized", false]);
  const block = BigInt(receipt.blockNumber);
  if (!finalized || BigInt(finalized.number) < block) return { stage: "included", block };

  const canonical = await request("eth_getBlockByNumber", [receipt.blockNumber, false]);
  if (!canonical || canonical.hash !== receipt.blockHash) return { stage: "submitted" };
  if (receipt.status !== "0x0" && receipt.status !== "0x1") throw new Error("Receipt status unavailable.");

  const fee = receipt.effectiveGasPrice == null ? null : BigInt(receipt.gasUsed) * BigInt(receipt.effectiveGasPrice);
  return { stage: receipt.status === "0x1" ? "finalized" : "reverted", block, fee };
}
