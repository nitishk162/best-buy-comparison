"""Collect US MacBook prices. Run from the repository root."""
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

STATE = Path("prices.json")


def request(url, params, *, headers=None, post=False):
    data = urlencode(params).encode()
    req = Request(url if post else url + "?" + data.decode(),
                  data=data if post else None, headers=headers or {})
    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f"Retailer returned HTTP {exc.code}") from None
            time.sleep(2 ** (attempt + 1))


def specs(title):
    text = title.lower()
    chips = set(re.findall(r"\bm([1-9])\b", text))
    if (not re.search(r"\bmacbook\s+(air|pro)\b", text) or chips not in ({"4"}, {"5"})
            or re.search(r"\b(for parts|parts only|locked|broken|case|cover|replacement|shell|choose|select your)\b", text)):
        return None
    # Apple silicon MacBooks have internal SSD storage. Accept unlabeled
    # capacities only when one memory size and one SSD size are unambiguous.
    caps = re.findall(r"(?<![\w.])(\d+)\s*(gb|tb)\b", text)
    gb = {int(n) * (1024 if unit == "tb" else 1) for n, unit in caps}
    ram = gb & {8, 16, 18, 24, 32, 36, 48, 64, 96, 128}
    disk = {n for n in gb if n >= 256}
    if len(ram) == len(disk) == 1 and min(ram) >= 24 and min(disk) >= 512:
        return f"M{next(iter(chips))} · {min(ram)} GB RAM · {min(disk):,} GB SSD"


def listing(key, title, condition, price, url, host):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {host, "www." + host}:
        raise ValueError("Unexpected retailer link")
    cents = int(Decimal(str(price)) * 100)
    if cents <= 0:
        raise ValueError("Unexpected nonpositive price")
    return dict(id=key, title=title, specs=specs(title), condition=condition,
                cents=cents, url=parsed._replace(scheme="https").geturl())


def bestbuy():
    key = os.environ["BESTBUY_API_KEY"]
    base = "https://api.bestbuy.com"
    products = {}
    page = 1
    while True:
        data = request(base + "/v1/products(categoryPath.id=abcat0502000&manufacturer=Apple)",
                       dict(apiKey=key, format="json", pageSize=100, page=page,
                            show="sku,name,salePrice,url,onlineAvailability,inStoreAvailability,condition"))
        for p in data["products"]:
            if specs(p["name"]):
                products[str(p["sku"])] = p
                if p["onlineAvailability"] or p["inStoreAvailability"]:
                    yield listing(f"bb:{p['sku']}:catalog", p["name"], p["condition"] or "Not specified",
                                  p["salePrice"], p["url"], "bestbuy.com")
        if page >= data["totalPages"]:
            break
        page += 1
    skus = list(products)
    for i in range(0, len(skus), 10):
        batch = ",".join(skus[i:i + 10])
        data = request(f"{base}/beta/products/openBox(sku%20in({batch}))", dict(apiKey=key))
        for item in data["results"]:
            sku = str(item["sku"])
            for offer in item["offers"]:
                grade = offer["condition"]
                yield listing(f"bb:{sku}:open:{grade}", products[sku]["name"], "Open box: " + grade,
                              offer["prices"]["current"], item["links"]["web"], "bestbuy.com")


def ebay():
    auth = base64.b64encode(f"{os.environ['EBAY_CLIENT_ID']}:{os.environ['EBAY_CLIENT_SECRET']}".encode()).decode()
    token = request("https://api.ebay.com/identity/v1/oauth2/token",
                    dict(grant_type="client_credentials", scope="https://api.ebay.com/oauth/api_scope"),
                    headers={"Authorization": "Basic " + auth}, post=True)["access_token"]
    for chip in ("M4", "M5"):
        for offset in range(0, 600, 200):
            data = request("https://api.ebay.com/buy/browse/v1/item_summary/search",
                           dict(q="MacBook " + chip, category_ids="111422", limit=200, offset=offset,
                                filter="itemLocationCountry:US,buyingOptions:{FIXED_PRICE}"),
                           headers={"Authorization": "Bearer " + token, "X-EBAY-C-MARKETPLACE-ID": "EBAY_US"})
            for item in data.get("itemSummaries", []):
                if (specs(item["title"]) and item["price"]["currency"] == "USD"
                        and item.get("conditionId") != "7000" and not item.get("itemGroupType")):
                    yield listing("ebay:" + item["itemId"], item["title"], item.get("condition", "Not specified"),
                                  item["price"]["value"], item["itemWebUrl"], "ebay.com")
            if not data.get("next"):
                break


def main():
    state = json.loads(STATE.read_text("utf-8")) if STATE.exists() else {"sources": {}, "drops": []}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ok = 0
    for name, fetch, keys in [
        ("Best Buy", bestbuy, ["BESTBUY_API_KEY"]),
        ("eBay", ebay, ["EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET"]),
    ]:
        src = state["sources"].setdefault(name, {"items": [], "checked": None})
        if not all(os.getenv(k) for k in keys):
            src["status"] = "Not configured"
            continue
        try:
            items = {}
            for row in fetch():
                if row["id"] not in items or row["cents"] < items[row["id"]]["cents"]:
                    items[row["id"]] = row
        except (RuntimeError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            src["status"] = str(exc) if isinstance(exc, RuntimeError) else f"Check failed ({type(exc).__name__})"
            print(f"{name}: {src['status']}", file=sys.stderr)
            continue
        for old in src["items"]:
            new = items.get(old["id"])
            if new and new["condition"] == old["condition"] and new["cents"] < old["cents"]:
                state["drops"].insert(0, dict(new, previous=old["cents"], date=now, store=name))
        src.update(items=list(items.values()), checked=now, status="Updated")
        ok += 1
    state["drops"] = state["drops"][:100]
    temp = STATE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    temp.replace(STATE)
    if not ok:
        print("Warning: No retailer refreshed. Check API credentials and source status.", file=sys.stderr)
        return


if __name__ == "__main__":
    main()
