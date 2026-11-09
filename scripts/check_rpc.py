#!/usr/bin/env python3
"""Check the development RPC and observe finality progress; not a consensus audit."""
import json
import time
import urllib.request

URL = "http://127.0.0.1:9944"
TOKEN_DECIMALS = 18
UNIT = 10**TOKEN_DECIMALS
DEVELOPMENT_CHAIN_ID = 31_341
LOCAL_CHAIN_ID = 31_342


def rpc(method, params=None, *, url=URL):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params or []}).encode()
    request = urllib.request.Request(url, data=payload,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["result"]


def finalized_height(*, url=URL):
    head = rpc("chain_getFinalizedHead", url=url)
    return int(rpc("chain_getHeader", [head], url=url)["number"], 16)


def check_chain(url, name, chain_id):
    chain = rpc("system_chain", url=url)
    actual_id = int(rpc("eth_chainId", url=url), 16)
    if chain != name or actual_id != chain_id:
        raise RuntimeError(f"Expected {name} with chain ID {chain_id} at {url}, got {chain} with ID {actual_id}.")
    properties = rpc("system_properties", url=url)
    if properties.get("tokenSymbol") != "IINK" or properties.get("tokenDecimals") != TOKEN_DECIMALS:
        raise RuntimeError(f"Unexpected token metadata at {url}: {properties!r}")
    return properties


def main():
    chain = "IINK Development"
    properties = check_chain(URL, chain, DEVELOPMENT_CHAIN_ID)
    first = finalized_height()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        current = finalized_height()
        if current > first:
            print(json.dumps({"chain": chain, "properties": properties,
                              "finalized_height_before": first,
                              "finalized_height_after": current}, indent=2))
            return
        time.sleep(2)
    raise RuntimeError("No finality progress observed within 90 seconds.")


if __name__ == "__main__":
    main()
