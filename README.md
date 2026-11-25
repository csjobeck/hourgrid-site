# Hourgrid website

Home, privacy policy and support pages for the Hourgrid iOS app, served with GitHub Pages from the `gh-pages` branch.
Plain HTML and CSS; no build step.

## Time-difference pages

`time-difference/` holds one page per city pair, a hub page, and `sitemap.xml` at the root, all generated:

```sh
python3 tools/gen_pairs.py
```

Edit `CITIES`, `HUBS` and `EXTRA` in `tools/gen_pairs.py` to add cities or pairs. Facts on each page are
computed from the Mac's IANA time-zone rules (version printed on the page); rerun after a tzdata change
and once a year to roll the table to the next year (`YEAR`). The live grid is `time-difference/grid.js`
and uses the visitor's browser rules.
