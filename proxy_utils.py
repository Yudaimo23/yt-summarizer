import requests, random

def get_free_proxy() -> dict | None:
    try:
        data = requests.get(
            "https://proxylist.geonode.com/api/proxy-list?limit=20&protocols=http"
        ).json()["data"]
        p = random.choice(data)
        addr = f"http://{p['ip']}:{p['port']}"
        return {"http": addr, "https": addr}
    except Exception:
        return None
