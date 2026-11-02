#!/usr/bin/env python3
"""Check the development RPC and observe finality progress; not a consensus audit."""
import json
import time
import urllib.request

URL = "http://127.0.0.1:9944"


def rpc(method, params=None):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params or []}).encode()
    request = urllib.request.Request(URL, data=payload,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        result = json.load(response)
    if "error" in result:
        raise RuntimeError(result["error"])
    return result["result"]


def finalized_height():
    head = rpc("chain_getFinalizedHead")
    return int(rpc("chain_getHeader", [head])["number"], 16)


def main():
    chain = rpc("system_chain")
    properties = rpc("system_properties")
    if chain != "IINK Development":
        raise RuntimeError(f"Unexpected chain: {chain!r}")
    if properties.get("tokenSymbol") != "IINK" or properties.get("tokenDecimals") != 12:
        raise RuntimeError(f"Unexpected development token metadata: {properties!r}")
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
