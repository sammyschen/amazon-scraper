"""
Amazon UK scraper package.

    Discovery layer      search.py (keyword), asin_family.py, ranking.py
          |                  -> a list of ASINs (+ rank / variation metadata)
    Product layer        product.py (+ variations.py for the embedded variation data)
          |                  -> rows in the approved 24-column schema
    Export layer         export.py  -> the Products / Info workbook

browser.py holds the one Chrome session every layer shares.
"""
