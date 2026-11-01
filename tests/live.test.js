// Election-night parser tests, run against frozen 2024 Wikipedia pages (same format as 2026).
const fs = require("fs");
const path = require("path");
const assert = require("assert");
const { JSDOM } = require("jsdom");
global.DOMParser = new JSDOM("").window.DOMParser;
const Live = require("../site/live.js");

const load = (f) => new DOMParser().parseFromString(fs.readFileSync(path.join(__dirname, "fixtures", f), "utf8"), "text/html");
let n = 0;
const t = (name, fn) => { fn(); n++; console.log("ok -", name); };

t("Pennsylvania Senate 2024: final count, called for the Republican", () => {
  const r = Live.parseRace(load("wiki_2024_sen_pa.html"), null);
  const [a, b] = r.candidates;
  assert.strictEqual(a.name, "Dave McCormick");
  assert.strictEqual(a.party, "REP");
  assert.strictEqual(b.name, "Bob Casey Jr.");
  assert.ok(Math.abs(a.pct - 48.78) < 0.01 && Math.abs(b.pct - 48.56) < 0.01);
  assert.ok(a.votes > 3300000 && r.total > 6900000);
  assert.strictEqual(r.called, true);
  assert.strictEqual(r.winner_party, "REP");
});

t("Washington House 2024: district 3 general, not the top-two primary", () => {
  const r = Live.parseRace(load("wiki_2024_house_wa.html"), "3");
  assert.strictEqual(r.candidates[0].name, "Marie Gluesenkamp Perez");
  assert.strictEqual(r.candidates[0].party, "DEM");
  assert.ok(Math.abs(r.candidates[0].pct - 51.7) < 0.05);
  assert.strictEqual(r.winner_party, "DEM");
});

t("New York House 2024: fusion voting lines combined per candidate", () => {
  const r = Live.parseRace(load("wiki_2024_house_ny.html"), "19");
  const riley = r.candidates.find((c) => c.name === "Josh Riley");
  assert.ok(riley && Math.abs(riley.pct - 51.1) < 0.05 && riley.party === "DEM");
  assert.ok(riley.votes > 190000);
  assert.strictEqual(r.winner_party, "DEM");
});

t("A 2026 page before Election Day has no votes and no call", () => {
  const r = Live.parseRace(load("wiki_2026_sen_tx.html"), null);
  assert.ok(!r || (r.total === 0 && !r.called));
});

t("Live odds lock in called races", () => {
  const races = [
    { race_id: "a", margin: -30, sd: 3, side_a_party: "DEM", side_b_party: "REP" },
    { race_id: "b", margin: 0, sd: 3, side_a_party: "DEM", side_b_party: "REP" },
  ];
  const called = { a: { called: true, winner_party: "DEM" }, b: { called: true, winner_party: "DEM" } };
  const o = Live.liveOdds(races, called, { nationalSd: 1, notUp: { dem: 49, rep: 49 }, demNeeds: 51, repNeeds: 50 });
  assert.strictEqual(o.p_dem, 1);
  const none = Live.liveOdds(races, {}, { nationalSd: 1, notUp: { dem: 49, rep: 49 }, demNeeds: 51, repNeeds: 50 });
  assert.strictEqual(none.p_dem, 0);
});

// ---- wikitext (what the live poller reads) ----
const wt = (f) => fs.readFileSync(path.join(__dirname, "fixtures", "wikitext", f), "utf8");

t("wikitext: Pennsylvania Senate 2024 called for McCormick", () => {
  const r = Live.parseWikitext(wt("2024_United_States_Senate_election_in_Pennsylvania.wiki"), null);
  assert.strictEqual(r.candidates[0].name, "Dave McCormick");
  assert.strictEqual(r.candidates[0].party, "REP");
  assert.ok(Math.abs(r.candidates[0].pct - r.candidates[1].pct - 0.2) < 0.15);
  assert.strictEqual(r.called, true);
  assert.strictEqual(r.winner_party, "REP");
});

t("wikitext: New York 19th, fusion lines and Total lines", () => {
  const r = Live.parseWikitext(wt("2024_United_States_House_of_Representatives_elections_in_New_York.wiki"), "19");
  const riley = r.candidates.find((c) => c.name === "Josh Riley");
  assert.strictEqual(riley.votes, 192647);
  assert.strictEqual(riley.party, "DEM");
  assert.strictEqual(r.winner_party, "DEM");
  assert.strictEqual(r.total, 376937);
});

t("wikitext: Washington 3rd, general not top-two primary", () => {
  const r = Live.parseWikitext(wt("2024_United_States_House_of_Representatives_elections_in_Washington.wiki"), "3");
  assert.strictEqual(r.candidates[0].name, "Marie Gluesenkamp Perez");
  assert.ok(Math.abs(r.candidates[0].pct - 51.7) < 0.3);
  assert.strictEqual(r.winner_party, "DEM");
});

t("wikitext: every Texas district 2024 parses and is called", () => {
  const page = wt("2024_United_States_House_of_Representatives_elections_in_Texas.wiki");
  const bad = [];
  for (let d = 1; d <= 38; d++) {
    const r = Live.parseWikitext(page, String(d));
    if (!r || !r.called || !r.total) bad.push(d);
  }
  assert.deepStrictEqual(bad, []);
});

t("wikitext: Wyoming at-large and Nebraska independent", () => {
  const wy = Live.parseWikitext(wt("2024_United_States_House_of_Representatives_election_in_Wyoming.wiki"), null);
  assert.strictEqual(wy.winner_party, "REP");
  const ne = Live.parseWikitext(wt("2024_United_States_Senate_election_in_Nebraska.wiki"), null);
  assert.ok(ne.candidates.some((c) => c.party === "IND" && /Osborn/.test(c.name)));
  assert.strictEqual(ne.winner_party, "REP");
});

t("wikitext: 2026 pages before Election Day show no votes and no calls", () => {
  const tx = Live.parseWikitext(wt("2026_United_States_Senate_election_in_Texas.wiki"), null);
  assert.ok(!tx || (!tx.called && !tx.total));
  const pa = wt("2026_United_States_House_of_Representatives_elections_in_Pennsylvania.wiki");
  for (let d = 1; d <= 17; d++) {
    const r = Live.parseWikitext(pa, String(d));
    assert.ok(!r || (!r.called && !r.total), "PA-" + d);
  }
});

t("If every current leader wins: called, counting, not started, independents", () => {
  const races = [
    { race_id: "A", side_a_party: "DEM", side_b_party: "REP", p_a: 0.3 },   // called D
    { race_id: "B", side_a_party: "DEM", side_b_party: "REP", p_a: 0.9 },   // R ahead in the count
    { race_id: "C", side_a_party: "DEM", side_b_party: "REP", p_a: 0.6 },   // no votes yet: forecast D
    { race_id: "NE", side_a_party: "IND", side_b_party: "REP", p_a: 0.4 },  // independent ahead, uncommitted
  ];
  const res = {
    A: { called: true, winner_party: "DEM", total: 100, candidates: [{ party: "DEM", votes: 60 }, { party: "REP", votes: 40 }] },
    B: { called: false, total: 50, candidates: [{ party: "REP", votes: 30 }, { party: "DEM", votes: 20 }] },
    NE: { called: false, total: 10, candidates: [{ party: "IND", votes: 6 }, { party: "REP", votes: 4 }] },
  };
  const h = Live.ifLeadersHold(races, res, { notUp: { dem: 10, rep: 10 }, uncommitted: ["NE"] });
  assert.deepStrictEqual(h, { dem: 12, rep: 11, other: 1, counting: 2 });
  const g = Live.ifLeadersHold(races.slice(0, 3), res, { partyOnly: true });
  assert.deepStrictEqual(g, { dem: 2, rep: 1, other: 0, counting: 1 });
});

console.log(`${n} passed`);
