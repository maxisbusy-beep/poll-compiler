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

  // ---- in-page poller ------------------------------------------------------------
  async function wikiJSON(params) {
    const u = API + "?" + new URLSearchParams({ ...params, format: "json", formatversion: "2", origin: "*" });
    const r = await fetch(u);
    if (!r.ok) throw new Error("Wikipedia " + r.status);
    return r.json();
  }

  /** Revision ids for many titles, 50 per request. */
  async function revisions(titles) {
    const out = {};
    for (let i = 0; i < titles.length; i += 50) {
      const d = await wikiJSON({ action: "query", prop: "revisions", rvprop: "ids|timestamp",
                                 titles: titles.slice(i, i + 50).join("|"), redirects: "1" });
      const back = {};
      (d.query.redirects || []).forEach((r) => (back[r.to] = r.from));
      (d.query.normalized || []).forEach((r) => (back[r.to] = back[r.to] || r.from));
      for (const p of d.query.pages || []) {
        if (!p.revisions) continue;
        out[back[p.title] || p.title] = { revid: p.revisions[0].revid, ts: p.revisions[0].timestamp };
      }
    }
    return out;
  }

  async function fetchSection(title, index) {
    const d = await wikiJSON({ action: "parse", page: title, prop: "text", section: String(index),
                               redirects: "1", disableeditsection: "1", disabletoc: "1" });
    return new DOMParser().parseFromString(d.parse.text, "text/html");
  }

  const strip = (h) => String(h).replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();

  /** Index of the general-election "Results" section for a district (or the whole page).
      Same rule as the table parser: after the first "General election" heading, skipping
      anything under a primary or runoff heading. Downloading just that section keeps each
      check small (whole state pages run to several megabytes). */
  function resultSection(sections, district) {
    let subs = sections;
    if (district) {
      const i = sections.findIndex((s) => s.level === "2" && (strip(s.line).match(/^District (\d+)\b/) || [])[1] == +district);
      if (i < 0) return null;
      const j = sections.findIndex((s, k) => k > i && s.level === "2");
      subs = sections.slice(i + 1, j < 0 ? undefined : j);
    }
    const g = subs.findIndex((s) => /general election/i.test(strip(s.line)));
    const after = g >= 0 ? subs.slice(g) : subs;
    let parentSkip = false;
    for (const s of after) {
      const line = strip(s.line);
      if (+s.level <= 3) parentSkip = SKIP.test(line);
      if (/^results?$/i.test(line) && !parentSkip) return s.index;
    }
    return null;
  }

  /** Poll Wikipedia; only pages whose revision changed are downloaded again. */
  function poller(liveTable, onUpdate, { intervalMs = 180000, concurrency = 8 } = {}) {
    const seen = {}, results = {}, pageTime = {};
    const pages = [...new Set(Object.values(liveTable.races).map((r) => r.page).filter(Boolean))];
    let timer = null, running = false;
    async function tick() {
      if (running) return;
      running = true;
      try {
        const revs = await revisions(pages);
        const changed = pages.filter((t) => revs[t] && revs[t].revid !== seen[t]);
        // one job per race: the small "Results" section of its page
        const jobs = [];
        for (let i = 0; i < changed.length; i += concurrency) {
          await Promise.all(changed.slice(i, i + concurrency).map(async (t) => {
            let sections;
            try { sections = (await wikiJSON({ action: "parse", page: t, prop: "sections", redirects: "1" })).parse.sections; }
            catch (e) { return; }
            for (const [rid, info] of Object.entries(liveTable.races)) {
              if (info.page !== t) continue;
              const idx = resultSection(sections, info.single_district ? null : info.district);
              if (idx != null) jobs.push({ rid, info, t, idx });
            }
            seen[t] = revs[t].revid;
            pageTime[t] = revs[t].ts;
          }));
        }
        for (let i = 0; i < jobs.length; i += concurrency) {
          await Promise.all(jobs.slice(i, i + concurrency).map(async ({ rid, info, t, idx }) => {
            try {
              const doc = await fetchSection(t, idx);
              const r = parseRace(doc, null);
              if (r) results[rid] = { ...r, expected: info.expected_votes, page: t, edited: revs[t].ts };
            } catch (e) { /* one bad section should not stop the rest */ }
          }));
          if (i % (concurrency * 10) === 0) onUpdate({ results, checked: new Date(), partial: true });
        }
        onUpdate({ results, checked: new Date(), changed: changed.length });
      } catch (e) {
        onUpdate({ results, checked: new Date(), error: e.message });
      } finally {
        running = false;
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
    const { nationalSd, nSims = 4000, notUp = { dem: 0, rep: 0 }, demNeeds, repNeeds, uncommitted = [] } = opts;
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
        else d++;
      }
      seats.push(d);
      if (d >= demNeeds) dem++; else if (rr >= repNeeds) rep++; else und++;
    }
    seats.sort((a, b) => a - b);
    return { p_dem: dem / nSims, p_rep: rep / nSims, p_und: und / nSims,
             median: seats[Math.floor(nSims / 2)], p10: seats[Math.floor(nSims * 0.1)], p90: seats[Math.floor(nSims * 0.9)] };
  }

  return { blocks, grid, raceBlocks, generalBlocks, readResults, parseRace, resultSection, poller, liveOdds, revisions };
});
