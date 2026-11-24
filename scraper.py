import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_FILE = Path("prices.json")

# Add the specific Best Buy MacBook / product URLs you want to monitor
URLS = [
    # M4 MacBook Pro 14" (example listing)
    "https://www.bestbuy.com/site/apple-macbook-pro-14-laptop-m4-chip-built-for-apple-intelligence-16gb-memory-512gb-ssd-space-black/6534640.p?skuId=6534640",
    # M4 MacBook Pro 14" 24GB
    "https://www.bestbuy.com/site/apple-macbook-pro-14-laptop-m4-pro-chip-built-for-apple-intelligence-24gb-memory-512gb-ssd-space-black/6534641.p?skuId=6534641",
]

PROXY_SERVER = os.getenv("PROXY_URL", "").strip()


def parse_price_cents(price_str: str) -> int:
    digits = re.sub(r"[^\d.]", "", price_str)
    try:
        return int(float(digits) * 100)
    except (ValueError, TypeError):
        return 0


def scrape_bestbuy():
    results = []
    print(f"Starting Playwright scraper for {len(URLS)} items...")
    if PROXY_SERVER:
        print("Using proxy configuration.")

    with sync_playwright() as p:
        launch_args = {
            "headless": True,
            "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        }
        if PROXY_SERVER:
            launch_args["proxy"] = {"server": PROXY_SERVER}

        browser = p.chromium.launch(**launch_args)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for url in URLS:
            print(f"Visiting: {url}")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)

                # Extract title
                title_el = page.locator("h1").first
                title = title_el.inner_text().strip() if title_el.count() else "Best Buy Product"

                # Extract price
                price_el = page.locator('[data-testid="customer-price"] span, .priceView-hero-price span').first
                price_text = price_el.inner_text().strip() if price_el.count() else "$0.00"
                cents = parse_price_cents(price_text)

                # Extract status / availability
                btn_el = page.locator("[data-button-state]").first
                status = btn_el.get_attribute("data-button-state") if btn_el.count() else "AVAILABLE"

                sku_match = re.search(r"skuId=(\d+)", url)
                sku = sku_match.group(1) if sku_match else str(hash(url))

                results.append({
                    "id": f"bb:{sku}",
                    "title": title,
                    "condition": "Brand New" if status == "ADD_TO_CART" else status,
                    "cents": cents,
                    "price_display": price_text,
                    "url": url,
                    "specs": "Apple M4 / Monitored Product"
                })
                print(f"  -> Extracted: {title[:40]}... Price: {price_text} ({status})")

            except Exception as e:
                print(f"  -> Error scraping {url}: {e}", file=sys.stderr)

        browser.close()

    # Load existing state or initialize new
    state = json.loads(STATE_FILE.read_text("utf-8")) if STATE_FILE.exists() else {"sources": {}, "drops": []}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    bb_source = state["sources"].setdefault("Best Buy", {"items": [], "checked": None})

    if results:
        bb_source["items"] = results
        bb_source["checked"] = now
        bb_source["status"] = "Updated"
    else:
        bb_source["status"] = "No items scraped (Check proxy or block)"

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scrape completed: {len(results)} items saved to {STATE_FILE.name}")


if __name__ == "__main__":
    scrape_bestbuy()
