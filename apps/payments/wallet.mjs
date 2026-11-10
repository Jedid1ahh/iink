import { RPC_URL, CHAIN_ID, CHAIN_NAME } from "./payments.mjs";

export function watchMetaMask(attach) {
  window.addEventListener("eip6963:announceProvider", event => {
    if (event.detail?.info?.rdns === "io.metamask") attach(event.detail.provider);
  });
  window.dispatchEvent(new Event("eip6963:requestProvider"));
  function findMetaMask() {
    const providers = window.ethereum?.providers ?? [window.ethereum];
    const provider = providers.find(candidate => candidate?.isMetaMask);
    if (provider) attach(provider);
  }
  findMetaMask();
  return findMetaMask;
}

export async function switchNetwork(wallet) {
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
