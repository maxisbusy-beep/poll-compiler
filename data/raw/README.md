# Wikipedia snapshots

Written by `.github/workflows/fetch.yml` (`python -m pipeline.fetch_wikipedia`).
Each file keeps only the headings and tables of one Wikipedia article, with the
article title and exact revision id in its first line. Parsed by
`python -m pipeline.load_wikipedia`.

Content from Wikipedia is licensed CC BY-SA 4.0; see each article's history
(`https://en.wikipedia.org/w/index.php?oldid=<revid>`) for authorship.
