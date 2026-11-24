# MacBook price watch

A phone-friendly GitHub Pages site for US MacBook Air and Pro listings with an M4 or M5 family chip, at least 24 GB of memory and at least 512 GB of SSD storage. GitHub Actions runs the two standard-library Python scripts hourly; your phone and computer don't have to stay online.

## Set up

1. Unzip into the **root of a dedicated GitHub repository**, including `.github/workflows/watch.yml`, and push to the default branch. This workflow owns the repository's Pages site and commits `prices.json` to preserve observations. The default branch must allow Actions to push.
2. In **Settings → Secrets and variables → Actions**, add credentials for one or both sources. For Best Buy, use `BESTBUY_API_KEY` from [Best Buy Developer](https://developer.bestbuy.com/). For eBay, use production `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET` from [eBay Developers](https://developer.ebay.com/my/keys); your app needs production [Browse API access](https://developer.ebay.com/api-docs/buy/browse/overview.html). Sandbox keys won't return real deals. Never put secrets in site files.
3. In **Settings → Pages → Source**, select **GitHub Actions**. Open **Actions → MacBook price watch → Run workflow** on the default branch. Open the deployment link on your phone. Future checks are scheduled at 17 minutes past the hour; GitHub can delay them.
4. For optional phone notifications, subscribe to the page's **Subscribe to price drops (RSS)** link in a feed reader with alerts enabled. The first run establishes a baseline. A later lower price for the same listing and condition creates a feed entry, not a notification for every new listing. Delivery depends on your reader's refresh interval.

## What gets compared

- **Best Buy USA:** Apple notebook catalog offers available online or in-store, plus separately priced open-box grades from the [Buying Options API](https://bestbuyapis.github.io/api-documentation/). Open-box coverage is limited to offers the API reports; check availability at your ZIP code.
- **eBay US:** Up to 600 best-match, fixed-price US-located laptop listings per chip per check. Includes new, open-box, refurbished and used listings. Excludes identified parts-only and variation groups. Auctions are not comparable to purchase prices.
- Both sources require a recognizable model and unambiguous capacities **in the listing title**. Incomplete titles may be missed, and seller descriptions can be wrong. Confirm the configuration, condition, shipping, tax and return policy before buying.
- Prices are USD before shipping and tax. The page sorts matching prices; it doesn't assume each listing is a sale. Drops compare consecutive successful source snapshots, not different sellers or different grades. The latest 100 drop events are retained. If a retailer fails, its last successful snapshot is labeled rather than erased.

## Run locally

Set the same credentials as environment variables, then run `python check_deals.py`, `python build_page.py`, and `python -m http.server 8000 --bind 127.0.0.1 --directory site` from this directory. Visit `http://localhost:8000`. With no credentials the collector writes source status and exits nonzero; the page builder still works. `prices.json` contains public listing data, not credentials.
