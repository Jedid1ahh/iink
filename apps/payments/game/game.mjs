import { CHAIN_ID, CHAIN_NAME, NETWORK_KEY, formatIink, isHash, paymentStatus, quotePayment, rpc, verifyNetwork } from "../payments.mjs";
import { switchNetwork, watchMetaMask } from "../wallet.mjs";
import { canMove, move, SIZE, startRun, WALLS } from "./route.mjs";

const byId = id => document.getElementById(id);
const board = byId("board");
const statusLine = byId("shop-status");
const shopKey = `iink-game:${NETWORK_KEY}:shop`;
const pendingKey = `iink-game:${NETWORK_KEY}:pending`;
byId("network-name").textContent = `${CHAIN_NAME} · ${parseInt(CHAIN_ID, 16)}`;
const isAddress = value => typeof value === "string" && /^0x[\da-f]{40}$/i.test(value);
const shorten = value => value.slice(0, 8) + "…" + value.slice(-6);
const quantity = value => "0x" + value.toString(16);
const message = error => error.code === 4001 ? "Request declined in MetaMask." : error.message;
let run = startRun(false);
let wallet;
let account;
let chain;
let price;
let owned;
let busy = false;
let pending;
let refreshId = 0;
let artifact;
let shop = stored("localStorage", shopKey);

if (!isAddress(shop)) shop = null;
try {
  const saved = JSON.parse(stored("sessionStorage", pendingKey));
  if (isHash(saved?.hash) && isAddress(saved.account) &&
    (saved.kind === "deploy" || saved.kind === "buy" && isAddress(saved.shop))) pending = saved;
} catch { /* Ignore a damaged saved transaction. */ }

function stored(storageName, key, value) {
  try {
    const storage = window[storageName];
    if (value === null) storage.removeItem(key);
    else if (value !== undefined) storage.setItem(key, value);
    else return storage.getItem(key);
  } catch { /* The demo works without persistent browser storage. */ }
  return null;
}

function renderRun() {
  byId("moves").textContent = run.moves;
  byId("glimmers").textContent = 3 - run.remaining.size;
  byId("run-status").textContent = !run.remaining.size ? "All three glimmers recovered." :
    !run.moves ? "Out of moves. Start a new run to try another route." : "";
  board.replaceChildren();
  for (let tile = 0; tile < SIZE * SIZE; tile += 1) {
    const cell = document.createElement("button");
    cell.type = "button";
    cell.disabled = !canMove(run, tile);
    const kind = run.tile === tile ? "courier" : WALLS.has(tile) ? "wall" : run.remaining.has(tile) ? "gem" : "open";
    cell.setAttribute("aria-label", `Row ${Math.floor(tile / SIZE) + 1}, column ${tile % SIZE + 1}, ${kind}`);
    if (kind === "wall") cell.dataset.wall = "";
    if (kind === "gem" || kind === "courier") {
      const marker = document.createElement("span");
      marker.className = kind;
      cell.append(marker);
    }
    cell.addEventListener("click", () => tryMove(tile));
    board.append(cell);
  }
}

function tryMove(tile) {
  const next = move(run, tile);
  if (next === run) return;
  run = next;
  renderRun();
  board.focus({ preventScroll: true });
}

board.addEventListener("keydown", event => {
  const direction = { ArrowUp: -SIZE, ArrowDown: SIZE, ArrowLeft: -1, ArrowRight: 1 }[event.key];
  if (typeof direction !== "number") return;
  event.preventDefault();
  tryMove(run.tile + direction);
});
byId("restart").addEventListener("click", () => {
  run = startRun(owned === true);
  renderRun();
  board.focus({ preventScroll: true });
});

const ready = () => Boolean(account && chain === CHAIN_ID);
function renderShop() {
  byId("account").textContent = account ? shorten(account) : "Disconnected";
  byId("account").title = account ?? "";
  byId("shop-address").textContent = shop ? shorten(shop) : "Awaiting deployment";
  byId("shop-address").title = shop ?? "";
  const needsRefresh = ready() && shop && owned === undefined;
  byId("connect").textContent = needsRefresh ? "Refresh shop" : ready() ? "MetaMask connected" : account ? "Switch to IINK" : "Connect MetaMask";
  byId("connect").disabled = busy || ready() && !needsRefresh;
  byId("deploy").hidden = Boolean(shop);
  byId("deploy").disabled = !ready() || busy || Boolean(pending);
  byId("buy").hidden = !shop;
  byId("buy").disabled = !ready() || price === undefined || owned !== false || busy || Boolean(pending);
  byId("buy").textContent = owned ? "Pass owned" : "Buy Courier Pass";
  byId("price").textContent = price === undefined ? "0.1 IINK" : formatIink(price);
  byId("ownership").textContent = owned === true ? "Owned" : owned === false ? "Available" :
    account && !ready() ? "Switch to IINK" : "Awaiting verification";
  byId("shop-help").textContent = owned ? "Start a new run to use your 11 moves." :
    shop ? "Use a funded player account. MetaMask shows the network fee before approval." :
      "Deploy from your test shop account. Then switch to a funded player account.";
}

async function getArtifact() {
  if (artifact) return artifact;
  const response = await fetch("./CourierPass.json");
  if (!response.ok) throw new Error("The shop contract artifact could not load.");
  artifact = await response.json();
  return artifact;
}

async function matchesShop(address) {
  const contract = await getArtifact();
  const code = await rpc("eth_getCode", [address, "finalized"]);
  return code.toLowerCase() === contract.runtimeCode.toLowerCase();
}

async function readShop(address, signature, args = "") {
  const contract = await getArtifact();
  const result = await rpc("eth_call", [{ to: address, data: "0x" + contract.selectors[signature] + args }, "finalized"]);
  return BigInt(result);
}

async function ownsPass(address, buyer) {
  return await readShop(address, "ownsPass(address)", buyer.slice(2).padStart(64, "0")) === 1n;
}

async function refreshShop() {
  const id = ++refreshId;
  owned = undefined;
  price = undefined;
  renderShop();
  if (!wallet) return;
  const [accounts, currentChain] = await Promise.all([
    wallet.request({ method: "eth_accounts" }), wallet.request({ method: "eth_chainId" }),
  ]);
  if (id !== refreshId) return;
  [account] = accounts;
  chain = currentChain;
  renderShop();
  if (!ready() || !shop) return;

  await verifyNetwork();
  const selected = shop;
  if (!await matchesShop(selected)) {
    if (id !== refreshId || selected !== shop) return;
    shop = null;
    stored("localStorage", shopKey, null);
    if (!pending) statusLine.textContent = "The saved shop is missing on this chain. Deploy a demo shop to continue.";
    renderShop();
    return;
  }
  const [actualPrice, hasPass] = await Promise.all([readShop(selected, "PRICE()"), ownsPass(selected, account)]);
  if (id !== refreshId || selected !== shop) return;
  price = actualPrice;
  owned = hasPass;
  renderShop();
}

const refresh = () => refreshShop().catch(error => { statusLine.textContent = message(error); });
function attachWallet(provider) {
  if (wallet) return;
  wallet = provider;
  for (const event of ["accountsChanged", "chainChanged", "connect"]) wallet.on?.(event, refresh);
  wallet.on?.("disconnect", () => {
    refreshId += 1;
    account = chain = owned = undefined;
    renderShop();
  });
  refresh();
}

byId("connect").addEventListener("click", async () => {
  if (!wallet) findWallet();
  if (!wallet) {
    statusLine.textContent = "Open the game in a browser with MetaMask.";
    return;
  }
  busy = true;
  renderShop();
  try {
    if (!ready()) {
      await verifyNetwork();
      const accounts = await wallet.request({ method: "eth_requestAccounts" });
      if (accounts.length && await wallet.request({ method: "eth_chainId" }) !== CHAIN_ID) await switchNetwork(wallet);
    }
    await refreshShop();
  } catch (error) {
    statusLine.textContent = message(error);
  } finally {
    busy = false;
    renderShop();
  }
});

async function submit(kind) {
  if (busy || pending || !ready()) return;
  const buyer = account;
  const selected = shop;
  const amount = price;
  busy = true;
  renderShop();
  statusLine.textContent = "Checking the transaction…";
  try {
    const contract = await getArtifact();
    const transaction = { from: buyer, value: "0x0", data: contract.creationCode };
    if (kind === "buy") {
      if (!selected || amount === undefined || owned !== false || !await matchesShop(selected)) {
        throw new Error("The shop or wallet changed. Check your pass before trying again.");
      }
      Object.assign(transaction, { to: selected, value: quantity(amount), data: "0x" + contract.selectors["buy()"] });
    }
    const estimate = await quotePayment(transaction);
    const [accounts, network] = await Promise.all([
      wallet.request({ method: "eth_accounts" }), wallet.request({ method: "eth_chainId" }),
    ]);
    if (accounts[0] !== buyer || account !== buyer || network !== CHAIN_ID || shop !== selected) {
      throw new Error("The shop or wallet changed. Review the transaction again.");
    }
    statusLine.textContent = `Estimated fee ${formatIink(estimate.fee)}. Review in MetaMask.`;
    const hash = await wallet.request({ method: "eth_sendTransaction", params: [transaction] });
    if (!isHash(hash)) throw new Error("MetaMask did not return a transaction hash. Check Activity.");
    pending = { kind, hash, account: buyer, shop: selected };
    stored("sessionStorage", pendingKey, JSON.stringify(pending));
    showPending();
    poll();
  } catch (error) {
    statusLine.textContent = message(error);
  } finally {
    busy = false;
    renderShop();
  }
}

function showPending() {
  byId("receipt").hidden = false;
  byId("receipt-hash").textContent = pending.hash;
  byId("receipt-block").textContent = "—";
  byId("receipt-fee").textContent = "—";
  statusLine.textContent = "Submitted. Waiting for finality.";
}

async function poll() {
  const transaction = pending;
  try {
    const result = await paymentStatus(transaction.hash);
    if (result.stage === "submitted" || result.stage === "included") {
      statusLine.textContent = result.stage === "included" ? "Included. Waiting for finality." : "Submitted. Waiting for a block.";
    } else {
      if (result.stage === "reverted") {
        statusLine.textContent = "The transaction reverted.";
      } else if (transaction.kind === "deploy") {
        if (!isAddress(result.contractAddress) || !await matchesShop(result.contractAddress)) {
          throw new Error("Waiting for the finalized shop code.");
        }
        shop = result.contractAddress;
        stored("localStorage", shopKey, shop);
        statusLine.textContent = "Shop deployed. Switch to a funded player account to buy a pass.";
      } else {
        if (!await ownsPass(transaction.shop, transaction.account)) throw new Error("Waiting for finalized pass ownership.");
        statusLine.textContent = "Pass purchased. Start a new run to use it.";
      }
      byId("receipt-block").textContent = result.block.toString();
      byId("receipt-fee").textContent = result.fee == null ? "—" : formatIink(result.fee);
      pending = undefined;
      stored("sessionStorage", pendingKey, null);
      await refresh();
      return;
    }
  } catch {
    statusLine.textContent = "Waiting for finalized chain data. Check Alice’s RPC if this continues.";
  }
  window.setTimeout(poll, 3000);
}

byId("deploy").addEventListener("click", () => submit("deploy"));
byId("buy").addEventListener("click", () => submit("buy"));
const findWallet = watchMetaMask(attachWallet);
renderRun();
renderShop();
if (pending) {
  showPending();
  poll();
}
