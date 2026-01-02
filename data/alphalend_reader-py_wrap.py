import json
import os
import subprocess

def alphafi_get_market_json(market_id: int, rpc_url: str = "https://rpc.mainnet.sui.io", network: str = "mainnet"):
    env = os.environ.copy()
    env["SUI_RPC_URL"] = rpc_url
    env["ALPHAFI_NETWORK"] = network
    env["ALPHAFI_MARKET_ID"] = str(market_id)

    res = subprocess.run(
        ["node", "alphalend_reader-sdk.mjs"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if res.returncode != 0:
        raise RuntimeError(f"AlphaFi node script failed:\n{res.stderr}\nSTDOUT:\n{res.stdout}")

    return json.loads(res.stdout)


# Example
data = alphafi_get_market_json(1)
print(data.keys())
print(json.dumps(data, indent=2)[:1000])
