# Amazon Scraper (Amazon US)

Collect product data from **amazon.com** into an Excel spreadsheet from the terminal. Prices are in **US dollars**, and every run delivers to **ZIP 10010** (New York). You can pick products in three ways:

| Mode | You give it | You get |
|---|---|---|
| **Keyword** | a search term + how many products | the search results, e.g. 500 "macbook" products |
| **ASIN Family** | one product (ASIN or link) | every variation of that product (all colors, sizes, bundles...) |
| **Ranking** | a Best Sellers / ranking page + N | the top N products with their real rank |

```bash
amazon macbook -n 200
amazon asin B0CG19QXWD
amazon ranking "https://www.amazon.com/gp/bestsellers/electronics" 20
```

Every run saves an `.xlsx` workbook, plus an optional `.csv`. Each workbook has the same 24 columns (price, list price/discount, rating, number of ratings, "bought in past month", stock, badges, delivery and more) and an **Info** sheet describing the run.

---

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Quick start](#quick-start)
- [The three modes](#the-three-modes)
- [All options](#all-options)
- [Marketplace and delivery location](#marketplace-and-delivery-location)
- [The spreadsheet](#the-spreadsheet)
- [Tips and troubleshooting](#tips-and-troubleshooting)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Known limitations](#known-limitations)
- [Responsible use](#responsible-use)
- [License](#license)

---

## Requirements

- **macOS** (Linux works too, except `--open`)
- **Python 3.10+** (developed on 3.13)
- **Google Chrome**, installed normally. The scraper drives your real Chrome, which is what lets it pass Amazon's bot check. You don't need to download any other browser.

## Installation

```bash
git clone https://github.com/sammyschen/amazon-scraper.git
cd amazon-scraper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Check that it runs:

```bash
.venv/bin/python amazon_scraper.py --help
```

### Optional: the `amazon` shortcut

This lets you type `amazon ...` from any folder instead of `.venv/bin/python amazon_scraper.py ...`. Run it **inside the project folder**:

```bash
echo "alias amazon='\"$PWD/.venv/bin/python\" \"$PWD/amazon_scraper.py\"'" >> ~/.zshrc
source ~/.zshrc
```

(Using bash? Replace `~/.zshrc` with `~/.bashrc`.) To remove the shortcut later, delete the `alias amazon=...` line from that file.

The rest of this guide uses `amazon`. Without the shortcut, write `.venv/bin/python amazon_scraper.py` instead.

## Quick start

```bash
amazon
```

With no arguments it asks what you want. Type a keyword, an ASIN, or a ranking-page link, and it works out the mode itself:

```
Delivery location: setting ZIP 10010 on amazon.com ...
Delivery location: New York 10010

Search Amazon US for (keyword, ASIN or ranking URL): dji mini 4 pro
How many products? [100]: 50
```

The finished spreadsheet is saved in the `output/` folder, and its path is printed at the end:

```
Saved 50 products -> .../output/amazon_dji_mini_4_pro_50_2026-09-24_1530.xlsx
```

---

## The three modes

### 1. Keyword mode: search results

```bash
amazon macbook -n 500            # 500 products
amazon macbook --500             # shorthand for the same thing
amazon dji mini 4 pro -n 200     # several words, no quotes needed
amazon keyword "iphone 15" 30    # explicit form: here the last number is the count
```

- The default is **100 products**.
- To reuse a search that has filters (price range, brand, Prime...), set it up in your browser and pass the link: `amazon --url "https://www.amazon.com/s?k=dji&rh=..." -n 300`. The link must be on amazon.com.
- **About large numbers:** Amazon shows a limited number of result pages per search (typically 20). If you ask for more, the scraper re-runs the same search with Amazon's other sort orders (*Price: high to low*, *Price: low to high*, *Newest arrivals*, *Best Sellers*, *Avg. customer review*) and merges the results without duplicates. A sort order that keeps returning products already collected is skipped after 4 pages. The `found_via` column shows which sort order found each product.
- All data comes from the search result cards, so this is the fastest mode: roughly 20–60 products every ~10 seconds.

> **Watch out:** without the `keyword` prefix, trailing numbers are part of the search. `amazon iphone 15` searches for "iphone 15". Use `-n` for the count: `amazon iphone 15 -n 50`.

### 2. ASIN Family mode: every variation of one product

```bash
amazon asin B0CG19QXWD                                   # an ASIN
amazon asin https://www.amazon.com/dp/B0CG19QXWD         # or a product link
amazon B0CG19QXWD                                        # a lone ASIN is detected automatically
amazon asin B0GS9Y71FP -n 20                             # only the first 20 of a big family
```

The **ASIN** is Amazon's product ID. It appears in every product link after `/dp/`, and under *Product information* on the page.

You can give it any of three kinds of ASIN:

- a **child**: one specific color/size. It finds the parent, then all the siblings.
- a **parent**: the product family itself. Amazon shows its default child, and the scraper collects every child.
- a **product with no variations**: it scrapes that single product.

Families are resolved **on amazon.com**, so they can differ from other Amazon sites. For example, the Osmo Pocket 3 has 4 US variations:

```
Mode: ASIN Family

Input ASIN: B0CG19QXWD
Parent ASIN: B0HHJBGVS1
Variation dimensions: Set name
Child ASINs found: 4

[1/4] B0CG19QXWD (Set name: Osmo Pocket 3) — ok: $439.00  DJI Osmo Pocket 3 Vlogging Camera ...
[2/4] B0GWD8599F (Set name: DJI Osmo Pocket 3 Vlog Bundle) — ok: $444.00  DJI Osmo Pocket 3 ...
[3/4] B0CG19FGQ5 (Set name: Osmo Pocket 3 Creator Combo) — ok: $549.00  DJI Osmo Pocket 3 ...
[4/4] B0H2MGVSHD (Set name: DJI Osmo Pocket 3 Mic 3 Bundle) — ok: $511.00  DJI Osmo Pocket 3 ...
```

- Each row's `subtitle` holds that child's variation, e.g. `Fit Type: Regular; Color: Navy; Size: Medium`.
- The default is **all children**. This mode opens every product page (about 10 s each), and clothing families can be huge: one T-shirt has 331 fit/color/size combinations, about 55 minutes. For families over 50 products it asks first. You can press Enter for all or type a number, or set a limit up front with `-n`.

### 3. Ranking mode: top N of a ranking page

```bash
amazon ranking "https://www.amazon.com/gp/bestsellers/electronics" 20
amazon ranking "https://www.amazon.com/gp/bestsellers/electronics"          # default: top 20
amazon --ranking "https://www.amazon.com/gp/new-releases/electronics" -n 50
```

- It works with **Best Sellers, New Releases, Movers & Shakers, Most Wished For and Gift Ideas** pages in any category or subcategory. Open the list on amazon.com and copy the link from the address bar.
- These lists hold up to **100** products (2 pages of 50), and the `rank` column is the **real position** on the Amazon US list.
- Any other amazon.com product list (for example a search results link) also works. It is ranked in page order, with ads skipped.
- Like ASIN Family mode, it opens each product's page (about 10 s each). The top 20 takes about 3–4 minutes.
- Ranked items that aren't regular products, such as a subscription plan, are listed under *Failed* ("not a standard product page") and the run carries on.

---

## All options

| Option | What it does |
|---|---|
| `keyword ...` | Search words (Keyword mode) |
| `-n N`, `--count N`, `--N` | How many products. Defaults: keyword **100**, ranking **20**, ASIN family **all** |
| `asin X` / `--asin X` | ASIN Family mode. `X` is an ASIN or a product link |
| `ranking URL [N]` / `--ranking URL` | Ranking mode (an amazon.com page) |
| `--url URL` | Keyword mode using a full amazon.com search link (keeps its filters) |
| `--csv` | Also save a `.csv` copy |
| `--open` | Open the spreadsheet when finished (macOS) |
| `--show-browser` | Show the Chrome window, needed if you must solve a CAPTCHA |
| `--out DIR` | Output folder (default: `output/` in the project folder) |
| `-h`, `--help` | Show help and examples |

---

## Marketplace and delivery location

| Setting | Value |
|---|---|
| Marketplace | Amazon US |
| Domain | amazon.com |
| Currency | USD (`price_usd`, `list_price_usd`) |
| Delivery ZIP | **10010** (New York, NY) |

**Why the ZIP matters.** Availability, delivery dates, stock, other offers, and sometimes search results depend on the delivery location. From outside the US, Amazon even shows **converted prices** (e.g. `GBP 112.26`) until a US ZIP is set.

**What the scraper does:**

1. **At the start of every run**, it enters ZIP 10010 in Amazon's own *Deliver to* box and checks that the header shows it:
   ```
   Delivery location: setting ZIP 10010 on amazon.com ...
   Delivery location: New York 10010
   ```
2. **It keeps the same browser session for the whole run**, so the ZIP is set once, not per product.
3. **It checks every page it opens.** If Amazon ever shows a different location, it prints a warning and applies the ZIP again.
4. **If the ZIP can't be set**, it prints a clear `WARNING` and carries on. The Info sheet then records `Delivery ZIP: 10010 - NOT applied` and the location Amazon actually showed.
5. **Prices are only recorded in dollars.** A price shown in another currency is left blank rather than stored as a wrong dollar amount.

**Changing it:** all of these values live in [`scraper/config.py`](scraper/config.py). Change `DELIVERY_ZIP` for another US ZIP code. The price column names and `$` format follow `CURRENCY` automatically.

---

## The spreadsheet

Files are named by mode:

```
output/amazon_macbook_500_2026-09-24_1530.xlsx                               keyword
output/amazon_family_B0HHJBGVS1_4_2026-09-24_1758.xlsx                       ASIN family (parent ASIN)
output/amazon_ranking_best_sellers_in_electronics_top20_2026-09-24_1802.xlsx ranking
```

**Opening in Google Sheets:** go to *File → Import → Upload*, choose the `.xlsx`, then *Insert new sheet(s)*.

### Products sheet: one row per product, always these 24 columns

| Column | Meaning |
|---|---|
| `rank` | **Keyword:** order found · **ASIN Family:** 1, 2, 3... (the product you entered first) · **Ranking:** the actual rank on Amazon's list |
| `asin` | The product's ASIN (for families, the child ASIN) |
| `brand` | Brand name |
| `title` | Product title |
| `subtitle` | **Keyword:** the short feature line under the title · **Family / Ranking:** the product's variation, e.g. `Color: Black; Size: M` |
| `condition` | `New` or `Renewed` (refurbished) |
| `price_usd` | Current price in US dollars |
| `list_price_usd` | The list price ("List:", "Typical price", "Was") in dollars, when Amazon shows one above the current price |
| `list_price_type` | `List Price`, `Typical` or `Was` |
| `discount_pct` | % below the list price |
| `rating` | Average stars out of 5 |
| `ratings_count` | Number of ratings |
| `bought_past_month` | e.g. `2K+ bought in past month` (only when Amazon shows it) |
| `stock` | Blank when simply in stock, otherwise e.g. `Only 3 left in stock`, `Currently unavailable` |
| `badge` | e.g. `Overall Pick`, `Best Seller in Camcorders` / `#1 Best Seller in Camcorders` |
| `deal` | e.g. `Limited time deal` |
| `advertised` | `Yes` if it appeared as a *Sponsored* ad in the search results (always `No` in Family / Ranking) |
| `delivery` | Delivery to ZIP 10010 for a non-Prime shopper, e.g. `FREE delivery Tue, Sep 29` |
| `other_offers` | Other sellers, e.g. `More Buying Choices $489.00 (13+ used & new offers)` or `New & Used (19) from $368.36` |
| `found_via` | **Keyword:** the sort order that found it (`Featured`, `Price: high to low`...) · `ASIN Family` · `Ranking` |
| `page` | Results page / ranking page it was found on (`1` for families) |
| `url` | `https://www.amazon.com/dp/<ASIN>` (clickable) |
| `image_url` | Full-size main product image |
| `scraped_at` | When it was collected (`YYYY-MM-DD HH:MM`) |

The header row is frozen, every column has a filter, and prices use the `$#,##0.00` format.

### Info sheet: a `field` / `value` summary of the run

Every run starts with the marketplace block:

| field | value |
|---|---|
| Marketplace | Amazon US |
| Domain | amazon.com |
| Delivery ZIP | 10010 |
| Currency | USD |
| Delivery location | New York 10010 *(what Amazon actually showed)* |

It then lists the details for that mode:

- **Keyword:** search, search URL, requested, collected, sort orders used, time, note.
- **ASIN Family:** input ASIN, parent ASIN, variation dimensions, requested, discovered, collected, failed, time, note.
- **Ranking:** ranking URL, list name, requested, discovered, collected, failed, time, note.

**Failed** lists any product that couldn't be scraped, with the reason. One failed product never stops the rest.

---

## Tips and troubleshooting

- **Stopping early:** press **Ctrl+C**. Everything collected so far is still saved.
- **"Amazon blocked the request (CAPTCHA)":** run the same command again with `--show-browser`. A Chrome window opens; solve the CAPTCHA there and the scraper carries on (it waits up to 3 minutes).
- **"WARNING: could not set the delivery ZIP":** Amazon's *Deliver to* box didn't respond. Run the command again. If it keeps happening, use `--show-browser` to watch what Amazon shows.
- **Blank prices:** the product has no current offer (e.g. `Currently unavailable`), or the delivery ZIP wasn't applied and Amazon showed another currency. Check `Delivery ZIP` in the Info sheet.
- **Speed:** there is a 4–8 second pause between page loads on purpose, because fast scraping gets blocked. Setting the ZIP adds about 15 seconds at the start of each run.
- **"page did not load after 3 attempts":** Amazon occasionally doesn't send a page. That product is listed under *Failed* and the run continues. Re-running later usually works.
- **Folder names with spaces:** quote them in the terminal, e.g. `cd "amazon data"`.

## How it works

```
 Session setup: open amazon.com in Chrome -> set "Deliver to" ZIP 10010 -> verify
        │
 Discovery layer                   Product layer                Export layer
 ───────────────                   ─────────────                ────────────
 Keyword  ─ search result cards ──────────────────────────┐
 ASIN Family ─ variation data on the product page ─┐      ├──> export_results() ──> .xlsx / .csv
 Ranking  ─ ranked list on the ranking page ───────┴──> scrape_product(asin) ──┘
                                                   (opens /dp/<ASIN>)
```

- Pages are opened in real Google Chrome through [Playwright](https://playwright.dev/python/), so Amazon's JavaScript bot check passes the same way it does for a normal visit. Plain HTTP requests just get the bot-check page.
- The delivery ZIP is set once through Amazon's *Deliver to* box. The same session, and its cookies, is reused for every page, and each page's *Deliver to* line is checked.
- **Keyword** reads everything from the search result cards, with no product pages opened.
- **ASIN Family** reads the variation data Amazon embeds in every product page with variations: the parent ASIN, each child ASIN, and its color/size/style values. Then it opens each child's page on amazon.com.
- **Ranking** reads the ranked list Amazon embeds in ranking pages (all 50 per page, with their ranks), then opens each product's page.
- If a product page comes back empty, the scraper retries with the cookies saved right after the ZIP was set, so the location is kept.

## Project structure

```
amazon_scraper.py        Command line: arguments, the three modes, progress and summary
scraper/
  config.py              Marketplace settings: amazon.com, USD, delivery ZIP 10010, locale
  browser.py             Shared Chrome session: page loading, pauses, CAPTCHA handling, delivery ZIP
  search.py              Keyword mode: search result cards, sort orders, de-duplication
  asin_family.py         ASIN Family discovery
  ranking.py             Ranking discovery
  variations.py          Reads Amazon's variation data (parent / child ASINs)
  product.py             Product page -> one spreadsheet row (shared by Family and Ranking)
  export.py              Writes the Products / Info workbook (used by every mode)
  utils.py               Small helpers (USD prices, counts, ASIN parsing)
docs/
  amazon_asin_scraper_implementation_spec.md   Design spec for the Family and Ranking modes
requirements.txt
output/                  Your spreadsheets (not uploaded to GitHub)
```

## Known limitations

- **amazon.com only.** Search and ranking links must be on amazon.com. A product link from another Amazon site is accepted in ASIN mode, but only its ASIN is used, and it is looked up on amazon.com.
- **Delivery location:** everything reflects ZIP 10010 for a shopper who isn't logged in and isn't a Prime member. If the ZIP can't be set, the run says so (see above).
- **Amazon changes its pages.** If a column suddenly comes back empty, the page layout has probably changed and the matching selector in `scraper/search.py` or `scraper/product.py` needs updating. Setting the ZIP depends on Amazon's *Deliver to* box.
- **Non-standard product pages** (subscription plans and similar digital services) can't be scraped and are reported as failed.
- **Search depth:** Keyword mode can't go beyond what Amazon's result pages × 6 sort orders show. Ranking lists stop at 100.
- **Variation data:** a product whose options aren't in Amazon's embedded variation data is treated as a single product.
- **Not collected:** Best Seller rank number, seller name and category. The spreadsheet has a fixed 24-column layout; the parent ASIN and variation dimensions are recorded in the Info sheet.
- **Speed:** Family and Ranking modes take about 10 seconds per product.

## Responsible use

Amazon's Conditions of Use don't allow automated data collection. Use this tool for small-scale, personal research only:

- keep the built-in pauses,
- don't run many copies at once,
- don't log in with your Amazon account while scraping,
- don't republish the data commercially.

## License

[MIT](LICENSE) © 2026 Sammy Chen. You're free to use, copy, modify and share this code, including in your own projects, as long as you keep the copyright notice. It comes with no warranty.

Found a bug, or has Amazon changed a page? [Open an issue](https://github.com/sammyschen/amazon-scraper/issues). Pull requests are welcome.
