import {
  RPC_URL, CHAIN_ID, CHAIN_NAME, formatIink, isHash, paymentRequest, paymentStatus,
  quotePayment, rpc, verifyNetwork,
} from "./payments.mjs";

const byId = id => document.getElementById(id);
const form = byId("payment-form");
const connect = byId("connect");
const submit = byId("submit");
const recipient = byId("recipient");
const amount = byId("amount");
const message = byId("message");
const storageKey = "iink-payments:31342:pending";
let wallet;
let account;
let chain;
let busy = false;
let tracking = false;
let quote;
let hash;
let version = 0;
let identityRequest = 0;

const ready = () => Boolean(account && chain === CHAIN_ID);
const shortAddress = address => address.slice(0, 8) + "…" + address.slice(-6);

function renderForm() {
  byId("account").textContent = account ? shortAddress(account) : "No wallet connected";
  byId("account").title = account ?? "";
  connect.textContent = ready() ? "MetaMask connected" : account ? "Switch to IINK" : "Connect MetaMask";
  connect.disabled = busy || ready();
  submit.textContent = busy ? "Please wait…" : tracking ? "Payment in progress" : quote ? "Continue to MetaMask" : "Review payment";
  submit.disabled = busy || tracking || !ready();
  byId("quote").hidden = !quote;
}

function clearQuote() {
  version += 1;
  quote = undefined;
  renderForm();
}

function explain(error) {
  if (error.code === 4001) return "Request declined in MetaMask. You can try again.";
  if (error.code === -32002) return "Open MetaMask to finish the request already waiting there.";
  if (error.name === "TimeoutError" || error instanceof TypeError) return "The local RPC is unavailable. Check the validator and private port tunnel.";
  return String(error.message ?? "Payment request failed.").slice(0, 240);
}

async function refreshIdentity() {
  const requestId = ++identityRequest;
  const [accounts, selectedChain] = await Promise.all([
    wallet.request({ method: "eth_accounts" }),
    wallet.request({ method: "eth_chainId" }),
  ]);
  if (requestId !== identityRequest) return;
  const newAccount = accounts[0];
  if (newAccount !== account || selectedChain !== chain) {
    account = newAccount;
    chain = selectedChain;
    message.textContent = "";
    clearQuote();
  }
  byId("balance").textContent = "—";
  if (!ready()) return;
  await verifyNetwork();
  const available = await rpc("eth_getBalance", [newAccount, "latest"]);
  if (requestId === identityRequest) byId("balance").textContent = formatIink(BigInt(available));
}

function attachWallet(provider) {
  if (wallet) return;
  wallet = provider;
  for (const event of ["accountsChanged", "chainChanged", "connect"]) {
    wallet.on?.(event, () => refreshIdentity().catch(error => { message.textContent = explain(error); }));
  }
  wallet.on?.("disconnect", () => {
    identityRequest += 1;
    account = chain = undefined;
    byId("balance").textContent = "—";
    clearQuote();
    message.textContent = "MetaMask disconnected. Reconnect to send a payment.";
  });
  refreshIdentity().catch(error => { message.textContent = explain(error); });
}

window.addEventListener("eip6963:announceProvider", event => {
  if (event.detail.info.rdns === "io.metamask") attachWallet(event.detail.provider);
});
window.dispatchEvent(new Event("eip6963:requestProvider"));

function findMetaMask() {
  const providers = window.ethereum?.providers ?? [window.ethereum];
  const provider = providers.find(candidate => candidate?.isMetaMask);
  if (provider) attachWallet(provider);
}

async function switchNetwork() {
  const params = [{ chainId: CHAIN_ID }];
  try {
    await wallet.request({ method: "wallet_switchEthereumChain", params });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await wallet.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: CHAIN_ID, chainName: CHAIN_NAME, rpcUrls: [RPC_URL],
        nativeCurrency: { name: "IINK", symbol: "IINK", decimals: 18 },
      }],
    });
    if (await wallet.request({ method: "eth_chainId" }) !== CHAIN_ID) {
      await wallet.request({ method: "wallet_switchEthereumChain", params });
    }
  }
}

connect.addEventListener("click", async () => {
  message.textContent = "";
  if (!wallet) findMetaMask();
  if (!wallet) {
    message.textContent = "Open this page in a browser with the MetaMask extension.";
    return;
  }
  busy = true;
  renderForm();
  try {
    await verifyNetwork();
    const accounts = await wallet.request({ method: "eth_requestAccounts" });
    if (accounts.length && await wallet.request({ method: "eth_chainId" }) !== CHAIN_ID) await switchNetwork();
    await refreshIdentity();
  } catch (error) {
    message.textContent = explain(error);
  } finally {
    busy = false;
    renderForm();
  }
});

form.addEventListener("input", () => {
  message.textContent = "";
  clearQuote();
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  if (!ready() || busy || tracking) return;
  message.textContent = "";
  busy = true;
  renderForm();
  const revision = version;
  try {
    if (quote) {
      const payment = quote.transaction;
      await quotePayment(payment);
      const [chainId, accounts] = await Promise.all([
        wallet.request({ method: "eth_chainId" }), wallet.request({ method: "eth_accounts" }),
      ]);
      if (revision !== version || chainId !== CHAIN_ID || accounts[0] !== payment.from) {
        throw new Error("The wallet or payment changed. Review the payment again.");
      }
      message.textContent = "Review and approve the payment in MetaMask.";
      const txHash = await wallet.request({ method: "eth_sendTransaction", params: [payment] });
      if (!isHash(txHash)) throw new Error("MetaMask did not return a valid transaction hash. Check Activity.");
      message.textContent = "";
      clearQuote();
      track(txHash);
    } else {
      const transaction = paymentRequest(account, recipient.value, amount.value);
      const estimate = await quotePayment(transaction);
      if (revision !== version) return;
      byId("balance").textContent = formatIink(estimate.balance);
      byId("quote-amount").textContent = formatIink(BigInt(transaction.value));
      byId("quote-fee").textContent = formatIink(estimate.fee);
      byId("quote-total").textContent = formatIink(estimate.total);
      quote = { transaction };
    }
  } catch (error) {
    clearQuote();
    message.textContent = explain(error);
  } finally {
    busy = false;
    renderForm();
  }
});

function savePending(value) {
  try {
    if (value) sessionStorage.setItem(storageKey, value);
    else sessionStorage.removeItem(storageKey);
  } catch { /* The payment remains tracked for this page session. */ }
}

function renderReceipt(status) {
  const { stage, block, fee } = status;
  const terminal = stage === "finalized" || stage === "reverted";
  const statuses = {
    submitted: "Submitted. Waiting for a block.",
    included: "Included. Waiting for chain finality.",
    finalized: "Payment finalized.",
    reverted: "Transaction reverted and finalized. The transfer failed.",
  };
  byId("receipt-status").textContent = statuses[stage];
  byId("step-submitted").setAttribute("data-done", "");
  byId("step-included").toggleAttribute("data-done", stage !== "submitted");
  byId("step-finalized").toggleAttribute("data-done", terminal);
  byId("block").textContent = block?.toString() ?? "—";
  byId("actual-fee").textContent = fee == null ? "—" : formatIink(fee);
  return terminal;
}

function track(txHash) {
  hash = txHash;
  tracking = true;
  savePending(hash);
  byId("hash").textContent = hash;
  byId("receipt-data").hidden = false;
  byId("copy-hash").hidden = false;
  renderReceipt({ stage: "submitted" });
  renderForm();
  poll();
}

async function poll() {
  try {
    if (renderReceipt(await paymentStatus(hash))) {
      savePending();
      tracking = false;
      renderForm();
      if (wallet) refreshIdentity().catch(error => { message.textContent = explain(error); });
      return;
    }
  } catch {
    byId("receipt-status").textContent = "Waiting for the local RPC. Check the tunnel if this continues.";
  }
  window.setTimeout(poll, 3000);
}

byId("copy-hash").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(hash);
    byId("copy-hash").textContent = "Hash copied";
  } catch {
    byId("copy-hash").textContent = "Select the hash to copy";
  }
});

findMetaMask();
try {
  const pending = sessionStorage.getItem(storageKey);
  if (isHash(pending)) track(pending);
} catch { /* Storage is optional. */ }
renderForm();
