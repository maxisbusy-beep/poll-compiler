/* Election-night results from Wikipedia, read directly by the browser.
   Pure parsing functions are exported for tests (node + jsdom); the poller runs in the page. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Live = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const API = "https://en.wikipedia.org/w/api.php";
  const SKIP = /primary|convention|caucus|runoff|jungle/i;
  const PARTY = [["democratic", "DEM"], ["republican", "REP"], ["independent", "IND"],
                 ["libertarian", "LIB"], ["green", "GRN"]];

  const text = (el) => (el ? el.textContent : "").replace(/\[[a-z0-9 ]{1,4}\]/gi, "").replace(/\s+/g, " ").trim();
  const num = (s) => { const d = String(s).replace(/[^\d]/g, ""); return d ? +d : 0; };
  const pct = (s) => { const m = String(s).replace(",", ".").match(/(\d+(?:\.\d+)?)/); return m ? +m[1] : null; };

  /** Headings and top-level tables in page order, each table tagged with its current headings. */
  function blocks(doc) {
    const out = [], heads = {};
    const order = ["H2", "H3", "H4", "H5"];
    doc.querySelectorAll("h2, h3, h4, h5, table").forEach((el) => {
      if (el.parentElement && el.parentElement.closest("table")) return;
      if (el.tagName === "TABLE") { out.push({ heads: { ...heads }, table: el }); return; }
      heads[el.tagName] = text(el);
      order.slice(order.indexOf(el.tagName) + 1).forEach((h) => delete heads[h]);
    });
    return out;
  }

  /** Rows of a table as arrays of cells, with rowspan/colspan expanded. */
  function grid(table) {
    const rows = [], pending = {};
    for (const tr of table.querySelectorAll("tr")) {
      if (tr.closest("table") !== table) continue;
      const row = [];
      let col = 0;
      const cells = Array.from(tr.children).filter((c) => c.tagName === "TD" || c.tagName === "TH");
      let i = 0;
      while (i < cells.length || pending[col]) {
        if (pending[col]) {
          row.push(pending[col].cell);
          if (--pending[col].left === 0) delete pending[col];
          col++; continue;
        }
        const c = cells[i++];
        const cs = Math.max(1, parseInt(c.getAttribute("colspan") || "1", 10) || 1);
        const rs = Math.max(1, parseInt(c.getAttribute("rowspan") || "1", 10) || 1);
        for (let k = 0; k < cs; k++) {
          row.push(c);
          if (rs > 1) pending[col + k] = { cell: c, left: rs - 1 };
        }
        col += cs;
      }
      rows.push(row);
    }
    return rows;
  }

  /** The tables for one race: a district's section on a House state page, or the whole page. */
  function raceBlocks(all, district) {
    if (!district) return all;
    return all.filter((b) => { const m = (b.heads.H2 || "").match(/^District (\d+)\b/); return m && +m[1] === +district; });
  }

  /** Same rule as the Python parser: from the first "General election" heading on, minus primaries. */
  function generalBlocks(bs) {
    const start = bs.findIndex((b) => Object.values(b.heads).some((h) => /general election/i.test(h)));
    return bs.slice(Math.max(start, 0)).filter((b) => !Object.values(b.heads).some((h) => SKIP.test(h)));
  }

  /** Read a results table. Returns null if it isn't one. */
  function readResults(table) {
    const rows = grid(table);
    if (!rows.length) return null;
    const head = rows[0].map((c) => text(c).toLowerCase());
    const ci = head.indexOf("candidate"), vi = head.indexOf("votes"), pi = head.indexOf("%");
    if (ci < 0 || vi < 0) return null;
    const partyCols = head.map((h, j) => (h === "party" ? j : -1)).filter((j) => j >= 0);
    const pa = partyCols.length ? partyCols[partyCols.length - 1] : -1;
    const lines = new Map();
    let total = 0, called = false;
    for (const r of rows.slice(1)) {
      const all = r.map(text).join(" ");
      if (/\b(hold|gain from)\b/i.test(all)) { called = true; continue; }
      const nameCell = r[ci];
      if (!nameCell) continue;
      const rawName = text(nameCell);
      if (/^total votes/i.test(text(r[0])) || /^total votes/i.test(rawName)) { total = num(text(r[vi])); continue; }
      if (!rawName || /^(majority|plurality|turnout|write|registered|eligible|blank|invalid|rejected)/i.test(rawName)) continue;
      const name = rawName.replace(/\s*\((incumbent|write-in)\)/gi, "").trim();
      const ptxt = pa >= 0 ? text(r[pa]).toLowerCase() : "";
      const party = ptxt === "total" ? "TOTAL" : ((PARTY.find(([k]) => ptxt.includes(k)) || [])[1] || "OTH");
      const bold = !!nameCell.querySelector("b");
      const v = num(text(r[vi])), p = pi >= 0 ? pct(text(r[pi])) : null;
      if (!lines.has(name)) lines.set(name, []);
      lines.get(name).push({ party, votes: v, pct: p, bold });
    }
    const cands = [];
    for (const [name, ls] of lines) {
      const tot = ls.find((l) => l.party === "TOTAL");
      const real = ls.filter((l) => l.party !== "TOTAL");
      const parties = real.map((l) => l.party);
      const party = ["DEM", "REP"].find((p) => parties.includes(p)) || parties[0] || "OTH";
      cands.push({
        name, party,
        votes: tot ? tot.votes : real.reduce((s, l) => s + l.votes, 0),
        pct: tot ? tot.pct : real.reduce((s, l) => s + (l.pct || 0), 0),
        winner: ls.some((l) => l.bold),
      });
    }
    if (cands.length < 1) return null;
    cands.sort((a, b) => b.votes - a.votes || (b.pct || 0) - (a.pct || 0));
    if (!total) total = cands.reduce((s, c) => s + c.votes, 0);
    const winner = cands.find((c) => c.winner);
    return { candidates: cands, total, called: called && !!(winner || cands[0].votes), winner_party: called ? (winner || cands[0]).party : null };
  }

  /** Results for one race from a parsed Wikipedia page document. */
  function parseRace(doc, district) {
    const gen = generalBlocks(raceBlocks(blocks(doc), district));
    for (const b of gen) {
      if (!/result/i.test(Object.values(b.heads).join(" "))) continue;
      const r = readResults(b.table);
      if (r) return r;
    }
    return null;
  }

  // ---- wikitext: what the poller actually reads -----------------------------------
  // Wikipedia's results boxes are templates ({{Election box candidate with party link|
  // party=...|candidate=...|votes=...}}), and a call shows up as a "winning candidate"
  // line plus a "hold"/"gain" line. Reading the raw wikitext is one cheap request per
  // page, instead of asking Wikipedia to render megabytes of HTML.

  function sections(wt) {
    const re = /^(={2,6})\s*(.+?)\s*\1\s*$/gm;
    const out = [{ level: 1, title: "", start: 0, body: "" }];
    let m;
    while ((m = re.exec(wt))) out.push({ level: m[1].length, title: stripMarkup(m[2]), start: m.index, end: re.lastIndex });
    for (let i = 0; i < out.length; i++) {
      const from = i === 0 ? 0 : out[i].end;
      const to = i + 1 < out.length ? out[i + 1].start : wt.length;
      out[i].body = wt.slice(from, to);
    }
    return out;
  }

  /** Top-level {{templates}} in a string, with their parameters. */
  function templates(str) {
    const out = [];
    let i = 0;
    while ((i = str.indexOf("{{", i)) >= 0) {
      let depth = 0, j = i;
      for (; j < str.length - 1; j++) {
        if (str[j] === "{" && str[j + 1] === "{") { depth++; j++; }
        else if (str[j] === "}" && str[j + 1] === "}") { depth--; j++; if (depth === 0) break; }
      }
      const inner = str.slice(i + 2, j - 1);
      const parts = [];
      let buf = "", d1 = 0, d2 = 0;
      for (let k = 0; k < inner.length; k++) {
        const c = inner[k], n = inner[k + 1];
        if (c === "{" && n === "{") { d1++; buf += "{{"; k++; continue; }
        if (c === "}" && n === "}") { d1--; buf += "}}"; k++; continue; }
        if (c === "[" && n === "[") { d2++; buf += "[["; k++; continue; }
        if (c === "]" && n === "]") { d2--; buf += "]]"; k++; continue; }
        if (c === "|" && d1 === 0 && d2 === 0) { parts.push(buf); buf = ""; continue; }
        buf += c;
      }
      parts.push(buf);
      const name = parts.shift().trim().toLowerCase().replace(/_/g, " ").replace(/\s+/g, " ");
      const params = {};
      parts.forEach((p, k) => {
        const eq = p.indexOf("=");
        if (eq > 0 && /^[\w ]+$/.test(p.slice(0, eq).trim())) params[p.slice(0, eq).trim().toLowerCase()] = p.slice(eq + 1).trim();
        else params[k + 1] = p.trim();
      });
      out.push({ name, params });
      i = j + 1;
    }
    return out;
  }

  function stripMarkup(s) {
    let t = String(s || "")
      .replace(/<ref[^>]*\/>/gi, "").replace(/<ref[\s\S]*?<\/ref>/gi, "").replace(/<!--[\s\S]*?-->/g, "");
    // unwrap formatting templates that hold the text itself, innermost first
    for (let k = 0; k < 4; k++) {
      const before = t;
      t = t.replace(/\{\{\s*(?:nowrap|nobr|no wrap|small|nowrap begin)\s*\|([^{}]*)\}\}/gi, "$1")
           .replace(/\{\{\s*sortname\s*\|([^|{}]*)\|([^|{}]*)[^{}]*\}\}/gi, "$1 $2");
      if (t === before) break;
    }
    return t
      .replace(/\{\{[^{}]*\}\}/g, "")
      .replace(/\[\[(?:[^\]|]*\|)?([^\]]*)\]\]/g, "$1")
      .replace(/'{2,}/g, "").replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ")
      .replace(/\s+/g, " ").trim();
  }

  const partyOf = (s) => { const t = stripMarkup(s).toLowerCase(); if (t === "total") return "TOTAL";
    return (PARTY.find(([k]) => t.includes(k)) || [])[1] || "OTH"; };

  /** The results boxes of one race from a page's wikitext. */
  function parseWikitext(wt, district) {
    let secs = sections(wt);
    if (district) {
      const i = secs.findIndex((x) => x.level === 2 && (x.title.match(/^District (\d+)\b/) || [])[1] == +district);
      if (i < 0) return null;
      const j = secs.findIndex((x, k) => k > i && x.level === 2);
      secs = secs.slice(i + 1, j < 0 ? undefined : j);
    }
    const g = secs.findIndex((x) => /general election/i.test(x.title));
    const after = g >= 0 ? secs.slice(g) : secs;
    let skip = false, idx = -1;
    for (let k = 0; k < after.length; k++) {
      const x = after[k];
      if (x.level <= 3) skip = SKIP.test(x.title);
      if (/^results?$/i.test(x.title) && !skip) { idx = k; break; }
    }
    if (idx < 0) return null;
    // the results section plus its own subsections
    let body = "";
    for (let k = idx; k < after.length; k++) {
      if (k > idx && after[k].level <= after[idx].level) break;
      body += after[k].body;
    }
    const lines = new Map();
    let total = 0, called = false, holdParty = null;
    for (const t of templates(body)) {
      if (!t.name.startsWith("election box")) continue;
      if (/\b(hold|gain)\b/.test(t.name)) { called = true; holdParty = partyOf(t.params.winner || ""); continue; }
      if (/total/.test(t.name)) { total = num(t.params.votes || "") || total; continue; }
      if (!/candidate/.test(t.name)) continue;
      const name = stripMarkup(t.params.candidate || "").replace(/\s*\((incumbent|write-in)\)/gi, "").trim();
      if (!name || /^(total|majority|turnout)/i.test(name)) continue;
      const party = partyOf(t.params.party || "");
      if (!lines.has(name)) lines.set(name, []);
      lines.get(name).push({ party, votes: num(t.params.votes || ""), pct: pct(t.params.percentage || ""),
                             win: /winning/.test(t.name) });
    }
    if (!lines.size) return null;
    const cands = [];
    for (const [name, ls] of lines) {
      const tot = ls.find((l) => l.party === "TOTAL");
      const real = ls.filter((l) => l.party !== "TOTAL");
      const parties = real.map((l) => l.party);
      cands.push({ name, party: ["DEM", "REP"].find((p) => parties.includes(p)) || parties[0] || "OTH",
                   votes: tot ? tot.votes : real.reduce((a, l) => a + l.votes, 0), winner: ls.some((l) => l.win) });
    }
    const sum = cands.reduce((a, c) => a + c.votes, 0);
    cands.forEach((c) => (c.pct = sum ? 100 * c.votes / sum : null));
    cands.sort((a, b) => b.votes - a.votes);
    const winner = cands.find((c) => c.winner);
    const isCalled = (called || !!winner) && sum > 0;
    return { candidates: cands, total: total || sum, called: isCalled,
             winner_party: isCalled ? (winner ? winner.party : (holdParty && holdParty !== "OTH" ? holdParty : cands[0].party)) : null };
  }

  // ---- in-page poller ------------------------------------------------------------
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  async function wikiJSON(params, tries = 3) {
    const u = API + "?" + new URLSearchParams({ ...params, format: "json", formatversion: "2", origin: "*", maxlag: "5" });
    for (let k = 0; k < tries; k++) {
      try {
        const r = await fetch(u);
        const body = await r.text();
        if (r.ok && body.startsWith("{")) {
          const d = JSON.parse(body);
          if (!d.error) return d;
        }
      } catch (e) { /* retry */ }
      await sleep(2000 * (k + 1));      // Wikipedia asks clients to back off when busy
    }
    throw new Error("Wikipedia did not answer");
  }

  /** Latest revision id and time for many titles, 50 per request. */
  async function revisions(titles) {
    const out = {};
    for (let i = 0; i < titles.length; i += 50) {
      const d = await wikiJSON({ action: "query", prop: "revisions", rvprop: "ids|timestamp",
                                 titles: titles.slice(i, i + 50).join("|"), redirects: "1" });
      const back = {};
      (d.query.normalized || []).forEach((r) => (back[r.to] = r.from));
      (d.query.redirects || []).forEach((r) => (back[r.to] = back[r.from] || r.from));
      for (const p of d.query.pages || []) {
        if (!p.revisions) continue;
        out[back[p.title] || p.title] = { revid: p.revisions[0].revid, ts: p.revisions[0].timestamp };
      }
    }
    return out;
  }

  async function wikitext(title) {
    const d = await wikiJSON({ action: "query", prop: "revisions", rvprop: "content", rvslots: "main",
                               titles: title, redirects: "1" });
    const p = d.query.pages[0];
    return p && p.revisions ? p.revisions[0].slots.main.content : "";
  }

  /** Check every few minutes; download only pages whose revision changed (one light request each). */
  // want(raceId): which races to keep current (e.g. only the tab on screen, to save phone data).
  function poller(liveTable, onUpdate, { intervalMs = 180000, concurrency = 3, want = () => true } = {}) {
    const seen = {}, results = {};
    let timer = null, running = false, again = false;
    async function tick() {
      if (running) { again = true; return; }   // asked again mid-check: run once more right after
      running = true;
      const pages = [...new Set(Object.entries(liveTable.races)
        .filter(([rid, r]) => r.page && want(rid)).map(([, r]) => r.page))];
      try {
        const revs = await revisions(pages);
        const changed = pages.filter((t) => revs[t] && revs[t].revid !== seen[t]);
        for (let i = 0; i < changed.length; i += concurrency) {
          await Promise.all(changed.slice(i, i + concurrency).map(async (t) => {
            try {
              const wt = await wikitext(t);
              for (const [rid, info] of Object.entries(liveTable.races)) {
                if (info.page !== t) continue;
                const r = parseWikitext(wt, info.single_district ? null : info.district);
                if (r) results[rid] = { ...r, expected: info.expected_votes, page: t, edited: revs[t].ts };
              }
              seen[t] = revs[t].revid;
            } catch (e) { /* try this page again next time */ }
          }));
          if (i % (concurrency * 5) === 0) onUpdate({ results, checked: new Date(), partial: true });
        }
        onUpdate({ results, checked: new Date(), changed: changed.length });
      } catch (e) {
        onUpdate({ results, checked: new Date(), error: e.message });
      } finally {
        running = false;
        if (again) { again = false; tick(); }
      }
    }
    return {
      start() { tick(); timer = setInterval(tick, intervalMs); },
      stop() { clearInterval(timer); },
      now: tick,
    };
  }

  // ---- live odds: called races locked, the rest from the pre-election forecast ----------
  function liveOdds(races, results, opts) {
    // partyOnly: only a Democrat counts for D (governors: an independent winner counts for neither side)
    const { nationalSd, nSims = 4000, notUp = { dem: 0, rep: 0 }, demNeeds, repNeeds, uncommitted = [], partyOnly = false } = opts;
    let seed = 12345;
    const rand = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };
    const gauss = () => { let u = 0, v = 0; while (!u) u = rand(); v = rand(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };
    const rs = races.map((r) => ({
      r, res: results[r.race_id],
      sdRace: Math.sqrt(Math.max(r.sd * r.sd - nationalSd * nationalSd, 1)),
      unc: uncommitted.includes(r.race_id),
    }));
    let dem = 0, rep = 0, und = 0;
    const seats = [];
    for (let s = 0; s < nSims; s++) {
      const nat = gauss() * nationalSd;
      let d = notUp.dem, rr = notUp.rep, u = 0;
      for (const x of rs) {
        let party, aWins;
        if (x.res && x.res.called) { party = x.res.winner_party; aWins = party === x.r.side_a_party; }
        else { aWins = x.r.margin + nat + gauss() * x.sdRace > 0; party = aWins ? x.r.side_a_party : x.r.side_b_party; }
        if (party === "REP") rr++;
        else if (aWins && x.unc) u++;
        else if (partyOnly && party !== "DEM") u++;
        else d++;
      }
      seats.push(d);
      if (d >= demNeeds) dem++; else if (rr >= repNeeds) rep++; else und++;
    }
    seats.sort((a, b) => a - b);
    return { p_dem: dem / nSims, p_rep: rep / nSims, p_und: und / nSims,
             median: seats[Math.floor(nSims / 2)], p10: seats[Math.floor(nSims * 0.1)], p90: seats[Math.floor(nSims * 0.9)] };
  }

  return { blocks, grid, raceBlocks, generalBlocks, readResults, parseRace, sections, templates, stripMarkup,
           parseWikitext, poller, liveOdds, revisions };
});
