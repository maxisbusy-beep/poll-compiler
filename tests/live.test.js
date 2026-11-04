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

// ---- election night: running counts live in the infobox, results box still blank ----
const IB_TX = `{{Infobox election
| election_name = 2026 United States Senate election in Texas
| reporting = 53
| last_update = 8:03 PM
| nominee2 = [[Ken Paxton]]
| party2 = Republican Party (United States)
| popular_vote2 = 2,111,740
| percentage2 = 39%
| nominee1 = [[James Talarico]]
| party1 = Democratic Party (United States)
| popular_vote1 = 3,241,741
| percentage1 = 60%
| after_election =
}}
== General election ==
===Results===
{{Election box begin | title=x}}
{{Election box candidate with party link|party=Republican Party (United States)|candidate=[[Ken Paxton]]|votes=|percentage=}}
{{Election box candidate with party link|party=Democratic Party (United States)|candidate=[[James Talarico]]|votes=|percentage=}}
{{Election box total | votes= }}
{{Election box end}}`;
const IB_FL = `{{Infobox election
| reporting = 97
| nominee1 = '''[[Byron Donalds]]'''
| running_mate1 = '''[[Bryan Avila]]'''
| party1 = Republican Party (United States)
| popular_vote1 = '''3,942,784'''
| percentage1 = '''49.77%'''
| nominee2 = [[David Jolly]]
| party2 = Democratic Party (United States)
| popular_vote2 = 3,879,948
| percentage2 = 48.97%
| after_election = [[Byron Donalds]]
}}`;
const IB_IA = `{{Infobox election
| ongoing = yes
<!--
| reporting         = 0
-->
| nominee1 = [[Ashley Hinson]]
| party1 = Republican Party (United States)
| popular_vote1 =
| nominee2 = [[Josh Turek]]
| party2 = Democratic Party (United States)
| popular_vote2 =
}}`;
t("infobox: running count used while the results box is blank", () => {
  const r = Live.parseWikitext(IB_TX, null);
  assert.equal(r.source, "infobox");
  assert.equal(r.total, 3241741 + 2111740);
  assert.equal(r.candidates[0].name, "James Talarico");
  assert.equal(r.candidates[0].party, "DEM");
  assert.ok(Math.abs(r.candidates[0].pct - 60.55) < 0.1);
  assert.equal(r.reporting, 53);
  assert.equal(r.called, false);
  assert.ok(Math.abs(r.expected - r.total / 0.53) < 2);
});
t("infobox: bold numbers / after_election mean called", () => {
  const r = Live.parseWikitext(IB_FL, null);
  assert.equal(r.called, true);
  assert.equal(r.winner_party, "REP");
  assert.equal(r.candidates[0].name, "Byron Donalds");
});
t("infobox: blank or commented-out fields give nothing", () => {
  assert.equal(Live.parseInfobox(IB_IA), null);
});
t("infobox: not used for one district on a multi-district page", () => {
  const r = Live.parseWikitext(IB_TX, "3");
  assert.equal(r, null);
});
t("infobox: shares follow the votes, notes in parentheses dropped", () => {
  const r = Live.parseInfobox(`{{Infobox election
| reporting = 3
| nominee2 = [[Susan Collins]]
| party2 = Republican Party (United States)
| popular_vote2 = 14,020
| percentage2 = 44.4%
| nominee1 = [[Troy Jackson]] <!-- note -->(replacing [[Graham Platner]])
| party1 = Democratic Party (United States)
| popular_vote1 = 11,210
| percentage1 = 55.6%
}}`);
  assert.equal(r.candidates[0].name, "Susan Collins");
  assert.ok(r.candidates[0].pct > r.candidates[1].pct);
  assert.equal(r.candidates[1].name, "Troy Jackson");
});
