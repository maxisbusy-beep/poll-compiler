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

console.log(`${n} passed`);
