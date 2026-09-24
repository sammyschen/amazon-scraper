# Amazon ASIN Family & Ranking Scraper — Implementation Spec

# 0. NON-NEGOTIABLE OUTPUT COMPATIBILITY

The existing Excel output format is already approved and **must be preserved**.

The new ASIN Family Mode and Ranking Mode change only how products are discovered. They must NOT redesign the final spreadsheet.

The existing workbook contains two sheets:

```text
Products
Info
```

Both sheets must continue to exist.

## Products sheet — exact schema

The `Products` sheet must contain exactly these 24 columns, in exactly this order:

```text
rank
asin
brand
title
subtitle
condition
price_gbp
list_price_gbp
list_price_type
discount_pct
rating
ratings_count
bought_past_month
stock
badge
deal
advertised
delivery
other_offers
found_via
page
url
image_url
scraped_at
```

Do not:

- rename these columns
- reorder these columns
- remove existing columns
- insert new columns in the middle
- replace the schema with a new variation-oriented schema

If additional internal metadata such as `parent_asin`, variation attributes, discovery source, etc. is needed for scraping logic, keep it internally or place appropriate run-level metadata in the `Info` sheet. Do not break the approved `Products` schema.

## Existing formatting to preserve

The output workbook should match the current spreadsheet style as closely as possible, including:

- worksheet name: `Products`
- header row at row 1
- dark header styling with bold text
- frozen top row (`A2`)
- AutoFilter across the full Products table
- readable column widths
- wide `title`, `subtitle`, `url`, and `image_url` columns
- one product per row
- same value conventions already used by the existing scraper
- worksheet name: `Info`
- `Info` remains a simple two-column `field` / `value` table

The current Products widths are approximately:

```text
A rank               12
B asin               12
C brand              12
D title              60
E subtitle           45
F condition          12
G price_gbp          12
H list_price_gbp     16
I list_price_type    17
J discount_pct       14
K rating             12
L ratings_count      15
M bought_past_month  19
N stock              22
O badge              32
P deal               12
Q advertised         12
R delivery           28
S other_offers       40
T found_via          20
U page               12
V url                38
W image_url           45
X scraped_at         12
```

Exact pixel-perfect reproduction is less important than preserving the same overall organization, readability, schema, and styling.

## Meaning of columns in the new modes

The existing columns should continue to mean the same thing wherever possible.

### `rank`

For Ranking Mode:

```text
rank = the actual position on the Amazon ranking page
```

For ASIN Family Mode:

```text
rank = sequential output order: 1, 2, 3, ...
```

This allows the output to preserve the existing schema without adding a new position column.

### `asin`

Always store the child/product ASIN actually scraped.

For a product with no variations, store the input product ASIN.

### `found_via`

Use this field to identify the discovery method.

Recommended values:

```text
Keyword
ASIN Family
Ranking
```

If the existing project uses more detailed values, preserve its convention while clearly distinguishing the new modes.

### `page`

For Ranking Mode:

```text
page = ranking page number on which the product was found
```

For ASIN Family Mode:

```text
page = 1
```

unless the implementation genuinely paginates a variation-discovery source.

### `url`

Continue using the canonical Amazon product URL format already used by the project, for example:

```text
https://www.amazon.co.uk/dp/{ASIN}
```

### `scraped_at`

Continue using the same timestamp format already used by the project:

```text
YYYY-MM-DD HH:MM
```

## Info sheet compatibility

The `Info` sheet must remain:

| field | value |
|---|---|

Do not replace it with a different layout.

For the existing Keyword Mode, preserve the existing fields such as:

```text
Search
Search URL
Requested
Collected
Sort orders used
Scraped at
Note
rank
```

For ASIN Family Mode, use the same two-column format with appropriate run metadata, for example:

```text
Mode                 ASIN Family
Input ASIN           B0XXXXXXXXX
Parent ASIN          B0PARENTXXX
Requested            All discovered child ASINs
Collected            12
Scraped at           2026-09-24 15:34
Note                 Collected all discoverable child products under the parent ASIN.
rank                 Sequential output order for ASIN Family Mode.
```

For Ranking Mode:

```text
Mode                 Ranking
Ranking URL          https://www.amazon.co.uk/...
Requested            20
Collected            20
Scraped at           2026-09-24 15:34
Note                 Collected the requested ranked products.
rank                 Actual Amazon ranking position.
```

The exact field names may be adapted slightly to fit the current exporter, but the `Info` sheet must remain a simple `field` / `value` metadata table.

## Critical implementation rule

The safest implementation is:

```text
NEW discovery logic
        ↓
normalize discovered products into the SAME record structure
        ↓
existing export function
        ↓
same Excel workbook format
```

Prefer modifying the discovery layer rather than rewriting the Excel export layer.

If the existing export function already produces the approved workbook, reuse it directly.

The new implementation should ideally finish with the same exporter for all modes:

```python
export_results(results, metadata)
```

where `results` follows the exact existing 24-column schema.

## Backward compatibility test

Before considering the task complete:

1. Run the existing Keyword Mode.
2. Confirm its output still has the same two sheets.
3. Confirm `Products` still has the exact same 24 headers and order.
4. Run ASIN Family Mode.
5. Confirm it produces the same 24-column Products layout.
6. Run Ranking Mode.
7. Confirm it produces the same 24-column Products layout.
8. Confirm all three modes use the same approved Excel styling/export path.

The existing workbook should be treated as the **reference output template**.



## 1. Goal

Extend the existing Amazon scraper so that it no longer depends only on a keyword search.

The current scraper already supports a workflow similar to:

```text
keyword + number of products
        ↓
Amazon search results
        ↓
collect product ASINs / URLs
        ↓
scrape product details
        ↓
export table
```

The new version should **reuse the existing product-detail scraping logic** as much as possible, but add two new ways to discover ASINs:

1. **ASIN Family Mode**
   - Input one ASIN.
   - Detect its parent ASIN if it is a child/variation ASIN.
   - Discover all child ASINs under the same parent.
   - Scrape the data for all child products.

2. **Ranking Mode**
   - Input an Amazon ranking / bestseller / category ranking page.
   - Extract the top N ranked products, defaulting to 20.
   - Scrape the data for those products.

The important design idea is:

```text
Different discovery methods
        ↓
produce a list of ASINs
        ↓
reuse one common product scraper
        ↓
export structured data
```

---

## 2. Do Not Rewrite the Existing Scraper Unless Necessary

Before changing code:

1. Inspect the current project structure.
2. Identify the existing function(s) responsible for:
   - Amazon search
   - extracting ASINs
   - opening product pages
   - scraping product details
   - saving CSV / Excel files
3. Reuse the current product-detail scraping function wherever possible.
4. Refactor only when necessary to make the scraper accept a generic ASIN list.

Ideally, the final architecture should look like:

```text
                    ┌────────────────────┐
                    │ Existing Keyword   │
                    │ Search Mode        │
                    └─────────┬──────────┘
                              │
                              ▼
                    List of product ASINs
                              │
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        │                     │                     │
        ▼                     ▼                     ▼
Keyword Discovery     ASIN Family Discovery    Ranking Discovery
                              │                     │
                              └──────────┬──────────┘
                                         ▼
                                  List of ASINs
                                         │
                                         ▼
                               scrape_product(asin)
                                         │
                                         ▼
                                  DataFrame / table
                                         │
                                         ▼
                                    CSV / Excel
```

---

# 3. Mode 1 — ASIN Family Mode

## 3.1 User Input

The user provides a single Amazon ASIN.

Example:

```bash
python main.py asin B0XXXXXXXXX
```

or an equivalent CLI interface that fits the current project.

The input ASIN may be:

- a parent ASIN
- a child ASIN
- a variation ASIN

The program should handle all three cases automatically.

---

## 3.2 Required Workflow

Given one input ASIN:

```text
Input ASIN
   ↓
Open product page / fetch product data
   ↓
Determine parent ASIN
   ↓
Discover all child / variation ASINs
   ↓
Deduplicate ASINs
   ↓
Scrape each child ASIN
   ↓
Combine results
   ↓
Export table
```

If the input ASIN is already the parent ASIN, use it directly.

If the input ASIN is a child ASIN, first find its parent.

If the product has no variations, treat the input ASIN as a single-product family.

---

## 3.3 Variation Discovery

The scraper should try to discover all product variations associated with the parent product.

Possible variation dimensions include:

- color
- size
- style
- model
- capacity
- pack size
- quantity
- configuration
- flavor
- pattern

The implementation should not assume that every product has the same variation structure.

The scraper should collect, when available:

```text
parent_asin
child_asin
variation_type
variation_value
```

Example:

| parent_asin | child_asin | color | size |
|---|---|---|---|
| B0PARENT01 | B0CHILD001 | Black | M |
| B0PARENT01 | B0CHILD002 | Black | L |
| B0PARENT01 | B0CHILD003 | White | M |

If variation metadata cannot be fully determined, still keep the child ASIN.

---

## 3.4 Expected Behaviour

Example:

```bash
python main.py asin B0CHILD001
```

Program:

```text
Input ASIN: B0CHILD001
Parent ASIN found: B0PARENT01
Child ASINs found: 8

Scraping 1/8...
Scraping 2/8...
...
Scraping 8/8...

Saved:
output/B0PARENT01_family.xlsx
```

---

# 4. Mode 2 — Ranking Mode

## 4.1 User Input

The user provides an Amazon ranking page URL and optionally a number of products.

Example:

```bash
python main.py ranking "AMAZON_RANKING_PAGE_URL" 20
```

Default:

```text
limit = 20
```

If the user does not specify a limit, scrape the top 20 products.

---

## 4.2 Ranking Page Types

The program should be designed to work with Amazon pages such as:

- Best Sellers
- category ranking pages
- subcategory ranking pages
- other Amazon ranking/list pages containing ordered product results

Do not hard-code a single category.

---

## 4.3 Required Workflow

```text
Ranking Page URL
      ↓
Load ranking page
      ↓
Identify ranked product cards
      ↓
Extract rank + ASIN + product URL
      ↓
Sort by rank
      ↓
Take first N products
      ↓
Scrape each product using existing scraper
      ↓
Merge ranking metadata
      ↓
Export table
```

For each ranked product, preserve its ranking position.

Example:

| rank | asin |
|---:|---|
| 1 | B0AAAAAAA1 |
| 2 | B0AAAAAAA2 |
| 3 | B0AAAAAAA3 |
| ... | ... |
| 20 | B0AAAAAA20 |

---

# 5. Shared Product Scraping Layer

Both new modes must ultimately call the same product-detail scraper.

Prefer a reusable interface similar to:

```python
def scrape_product(asin: str) -> dict:
    ...
```

or:

```python
def scrape_product(url: str) -> dict:
    ...
```

If the current project does not have a clean reusable function, refactor the existing logic into one.

Then both modes should work like:

```python
asins = discover_asins(...)
results = []

for asin in asins:
    result = scrape_product(asin)
    results.append(result)
```

---

# 6. Product Fields

Reuse all fields already collected by the existing project.

Where available, the dataset should ideally contain:

```text
asin
parent_asin
title
brand
price
currency
rating
review_count
category
bsr
seller
availability
product_url
image_url
variation_type
variation_value
rank
scraped_at
```

Not every field must exist for every product.

Missing fields should use a consistent null value rather than crashing the scraper.

For example:

```python
None
```

or an empty cell in the exported spreadsheet.

---

# 7. Output Requirements

Support the current project's existing output format.

Prefer:

- CSV
- XLSX

Example output names:

### ASIN Family Mode

```text
B0PARENT01_family.xlsx
```

### Ranking Mode

```text
ranking_top_20_2026-09-24.xlsx
```

The exact naming convention can be adapted to the existing project.

---

# 8. Recommended CLI

Keep the current keyword mode if it already works.

Suggested interface:

```bash
# Existing feature
python main.py keyword "wireless mouse" 20

# New feature: parent / child family
python main.py asin B0XXXXXXXXX

# New feature: ranking page
python main.py ranking "https://www.amazon..." 20
```

If the project already uses a different CLI structure, preserve that style instead of forcing this exact syntax.

---

# 9. Error Handling

The scraper should fail gracefully.

Handle at least:

```text
invalid ASIN
product does not exist
product page unavailable
parent ASIN cannot be detected
variation list cannot be detected
ranking page cannot be parsed
fewer than N ranking products exist
duplicate ASINs
product page timeout
temporary request failure
missing product fields
```

One failed product should not stop the entire batch.

Example:

```text
[12/20] B0XXXXXXX — success
[13/20] B0YYYYYYY — failed: page unavailable
[14/20] B0ZZZZZZZ — success
```

Continue processing after individual failures.

At the end, report:

```text
Total requested: 20
Successful: 18
Failed: 2
```

---

# 10. Deduplication

Before scraping product details:

```python
asins = deduplicate(asins)
```

ASINs should preserve their original order after deduplication.

This is especially important for:

- ranking pages
- variation lists
- pages where the same ASIN appears multiple times

For ranking mode, preserve the first valid ranking position.

---

# 11. Logging / Progress

Provide clear terminal feedback.

Example:

```text
Mode: ASIN Family

Input ASIN: B0XXXXXXX
Parent ASIN: B0PARENT01
Variations discovered: 12

[1/12] Scraping B0AAA...
[2/12] Scraping B0BBB...
...
```

Ranking example:

```text
Mode: Ranking

Ranking page loaded
Products discovered: 50
Requested: Top 20

[1/20] Rank #1 — B0AAA...
[2/20] Rank #2 — B0BBB...
...
```

---

# 12. Rate Limiting and Existing Anti-Blocking Logic

Reuse all existing request/session/browser logic already present in the project.

Do not remove existing:

- delays
- retries
- session handling
- cookies
- headers
- browser automation logic
- proxy support, if already implemented

The new discovery modes should integrate into the existing scraping infrastructure.

Avoid sending unnecessary duplicate requests.

---

# 13. Suggested Internal Structure

Adapt this to the existing codebase rather than rebuilding everything.

Possible structure:

```text
project/
│
├── main.py
├── scraper/
│   ├── product.py
│   ├── search.py
│   ├── asin_family.py
│   └── ranking.py
│
├── utils/
│   ├── export.py
│   ├── logging.py
│   └── helpers.py
│
└── output/
```

Suggested responsibilities:

```python
# asin_family.py
get_parent_asin(asin)
get_child_asins(parent_asin)
discover_asin_family(asin)

# ranking.py
get_ranked_products(url, limit=20)

# product.py
scrape_product(asin)

# export.py
export_results(results, filename)
```

Again: only refactor into this structure if it improves the current project.

---

# 14. Preferred Data Structures

ASIN family discovery could return:

```python
[
    {
        "asin": "B0CHILD001",
        "parent_asin": "B0PARENT01",
        "variation": {
            "color": "Black",
            "size": "M"
        }
    },
    ...
]
```

Ranking discovery could return:

```python
[
    {
        "rank": 1,
        "asin": "B0AAAAAAA1",
        "url": "..."
    },
    {
        "rank": 2,
        "asin": "B0AAAAAAA2",
        "url": "..."
    }
]
```

The product scraper then enriches those records.

---

# 15. Important Implementation Principle

Do not mix product discovery logic with product-detail extraction.

Use:

```text
Discovery Layer
        ↓
ASIN list + metadata
        ↓
Product Scraping Layer
        ↓
Structured results
        ↓
Export Layer
```

This will make it easy to add more discovery modes later.

For example:

```text
keyword
brand page
seller page
search URL
category page
ASIN family
ranking page
```

All of them can eventually feed the same product scraper.

---

# 16. Backward Compatibility

The existing keyword feature should continue working unless technically impossible.

Do not break:

```text
keyword + number of products → scrape results
```

The goal is to add functionality, not replace the current working workflow.

---

# 17. Acceptance Criteria

The implementation is complete when all of the following work.

## Test A — Child ASIN Input

Input:

```text
a child ASIN
```

Expected:

```text
detect parent
find all available child ASINs
scrape all children
export one table
```

---

## Test B — Parent ASIN Input

Input:

```text
a parent ASIN
```

Expected:

```text
find all available child ASINs
scrape all children
export one table
```

---

## Test C — Product Without Variations

Input:

```text
ASIN with no parent/variation family
```

Expected:

```text
scrape that single product successfully
```

---

## Test D — Ranking Top 20

Input:

```text
Amazon ranking page
limit = 20
```

Expected:

```text
extract ranks 1–20
scrape those products
preserve rank column
export one table
```

---

## Test E — Partial Failure

If 2 out of 20 product pages fail:

```text
do not terminate the batch
save the successful 18 products
record/report the 2 failures
```

---

# 18. Claude Code Instructions

Please first inspect the existing repository before writing new code.

Then:

1. Explain briefly how the current scraper works.
2. Identify which current components can be reused.
3. Implement the smallest clean set of changes required.
4. Add ASIN Family Mode.
5. Add Ranking Mode.
6. Preserve the existing Keyword Mode.
7. Reuse the existing product-detail scraper.
8. Add robust error handling and progress logging.
9. Test each new mode.
10. Do not rewrite working code unnecessarily.
11. After implementation, summarize:
    - files changed
    - functions added
    - how to run each mode
    - any known limitations

If Amazon page structure makes one extraction method unreliable, implement the most robust approach available in the current stack and clearly document the limitation.

---

# Final Product Behaviour

The final tool should support three discovery workflows:

```text
1. Keyword
keyword + N
↓
N product ASINs

2. ASIN Family
one ASIN
↓
parent ASIN
↓
all child ASINs

3. Ranking
ranking URL + N
↓
top N ranked ASINs
```

All three should feed into:

```text
ASIN list
↓
existing product scraper
↓
structured product data
↓
CSV / Excel
```

The two new features required for this task are:

> **Given one ASIN, collect data for all child products under its parent ASIN.**

and

> **Given an Amazon ranking page, collect data for the top 20 products, or another user-specified N.**
