/* poll-compiler front end. Reads site/data/*.json written by the pipeline. */
(() => {
  "use strict";

  const FIPS = {"01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE","11":"DC","12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA","20":"KS","21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN","28":"MS","29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM","36":"NY","37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI","45":"SC","46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA","54":"WV","55":"WI","56":"WY"};
  const NAMES = {AL:"Alabama",AK:"Alaska",AZ:"Arizona",AR:"Arkansas",CA:"California",CO:"Colorado",CT:"Connecticut",DE:"Delaware",DC:"District of Columbia",FL:"Florida",GA:"Georgia",HI:"Hawaii",ID:"Idaho",IL:"Illinois",IN:"Indiana",IA:"Iowa",KS:"Kansas",KY:"Kentucky",LA:"Louisiana",ME:"Maine",MD:"Maryland",MA:"Massachusetts",MI:"Michigan",MN:"Minnesota",MS:"Mississippi",MO:"Missouri",MT:"Montana",NE:"Nebraska",NV:"Nevada",NH:"New Hampshire",NJ:"New Jersey",NM:"New Mexico",NY:"New York",NC:"North Carolina",ND:"North Dakota",OH:"Ohio",OK:"Oklahoma",OR:"Oregon",PA:"Pennsylvania",RI:"Rhode Island",SC:"South Carolina",SD:"South Dakota",TN:"Tennessee",TX:"Texas",UT:"Utah",VT:"Vermont",VA:"Virginia",WA:"Washington",WV:"West Virginia",WI:"Wisconsin",WY:"Wyoming"};
  // small eastern states get a tappable box beside the map, as on most election maps
  const CALLOUTS = ["VT", "NH", "MA", "RI", "CT", "NJ", "DE", "MD"];
  const RATINGS = [
    ["safe-d", "Safe D"], ["likely-d", "Likely D"], ["lean-d", "Lean D"], ["toss", "Toss-up"],
    ["lean-r", "Lean R"], ["likely-r", "Likely R"], ["safe-r", "Safe R"], ["ind", "Independent favoured"],
  ];
  const DARK_TEXT = new Set(["lean-d", "toss", "lean-r", "none"]);

  const $ = (id) => document.getElementById(id);
  const fmtPct = (p) => (p >= 0.995 ? ">99" : p <= 0.005 ? "<1" : Math.round(p * 100)) + "%";
  const fmtMargin = (m, a = "D", b = "R") => (Math.abs(m) < 0.05 ? "Even" : (m > 0 ? a : b) + "+" + Math.abs(m).toFixed(1));
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmtDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString([], { month: "short", day: "numeric" });
  const letter = (party) => ({ DEM: "D", REP: "R", IND: "I", LIB: "L", GRN: "G" }[party] || party[0]);

  const state = { forecast: null, allRaces: [], pollsters: {}, topo: null, selected: null, chamber: "senate",
                  showAll: false, closeOnly: true, houseTopo: null, houseGeo: null, houseZoom: null,
                  live: null, liveMode: null, liveTable: null, liveChecked: null, liveError: null,
                  view: "races", pollsterMeta: null, ballot: null, pollsterHistory: null,
                  pv: { window: "all_time", sort: "weight", q: "", active: false, all: false } };

  const liveRes = (r) => (state.live ? state.live[r.race_id] : null);
  // Races that can't be settled on the night: majority-or-runoff and ranked-choice states.
  function slowCount(r) {
    if (r.state === "GA") return "Georgia needs a majority: if no one gets 50%, the top two meet in a runoff on December 1.";
    if (r.state === "AK") return "Alaska uses ranked-choice voting. If no one tops 50%, later choices are counted about two weeks after Election Day.";
    if (r.state === "ME" && r.chamber !== "governor")
      return "Maine uses ranked-choice voting for Congress. If no one tops 50%, counting later choices takes several days.";
    return null;
  }
  // Election night: which way the rest of the count usually moves, from each state's counting
  // order (mail first vs mail last). States with no clear pattern get no note. Statewide reasons
  // name cities, so House districts get the plain version.
  const SHIFT = {
    PA: ["DEM", "Mail ballots are counted late"],
    WI: ["DEM", "Absentee ballots are counted late", "Milwaukee's absentees are counted late"],
    MI: ["DEM", "Absentee ballots are counted late", "Detroit and Ann Arbor absentees are counted late"],
    NH: ["DEM", "Mail ballots are counted late"],
    VA: ["DEM", "Big-city precincts report late", "Northern Virginia and the big cities report late"],
    NV: ["DEM", "Late mail ballots have leaned Democratic"],
    CA: ["DEM", "Late mail ballots, counted over days, lean Democratic"],
    WA: ["DEM", "Late mail ballots, counted over days, lean Democratic"],
    OR: ["DEM", "Late mail ballots, counted over days, lean Democratic"],
    FL: ["REP", "Mail votes were counted first"],
    NC: ["REP", "Mail votes were counted first"],
    OH: ["REP", "Mail votes were counted first"],
    AZ: ["REP", "Late drop-off ballots have leaned Republican"],
  };
  function countShift(r, lr) {
    const s = SHIFT[r.state];
    if (!s || !lr || lr.called || !(lr.total > 0) || !lr.candidates || !lr.candidates[0]) return null;
    const share = lr.expected ? 100 * lr.total / lr.expected : null;
    if (share != null && share >= 95) return null;
    const [party, plain, statewide] = s;
    const why = (r.chamber !== "house" && statewide) || plain;
    const L = party === "DEM" ? "D" : "R";
    const mark = `<span class="${L === "D" ? "d" : "r"}">▲ ${L}</span>`;
    if (share != null && share >= 85) return `${mark} slight edge. Little is left, but ${why.charAt(0).toLowerCase() + why.slice(1)}.`;
    const c1 = lr.candidates[0], c2 = lr.candidates[1];
    const name = esc(String(c1.name).trim().split(/\s+/).slice(-1)[0]);
    const tail = c2 && c1.votes === c2.votes ? ""
      : c1.party === party ? `, so ${name}'s lead should grow`
      : c1.party === "DEM" || c1.party === "REP" ? `, so ${name}'s lead should shrink` : "";
    return `${mark} likely gains. ${why}${tail}.`;
  }
  function wikiLink(r) {
    const t = state.pages && state.pages[r.race_id];
    if (!t || !t.page) return null;
    const anchor = r.chamber === "house" && !t.single_district ? "#District_" + r.district : "";
    return "https://en.wikipedia.org/wiki/" + encodeURIComponent(t.page.replace(/ /g, "_")) + anchor;
  }
  // Who is ahead: "a", "b", or null for a dead heat. Once votes are counted, the vote
  // leader (or the called winner); before that, the forecast favorite. 50/50 shows no leader.
  function leaderSide(r) {
    const lr = liveRes(r);
    if (lr && lr.total > 0 && lr.candidates && lr.candidates.length) {
      const cs = lr.candidates;
      const top = (lr.called && cs.find((c) => c.winner)) || cs[0];
      if (!(lr.called) && cs[1] && cs[0].votes === cs[1].votes) return null;
      const last = (n) => String(n).trim().split(/\s+/).slice(-1)[0].toLowerCase();
      const t = last(top.name);
      if (last(r.side_a) === t) return "a";
      if (last(r.side_b) === t) return "b";
      if (r.side_a_party !== r.side_b_party) {
        if (top.party === r.side_a_party) return "a";
        if (top.party === r.side_b_party) return "b";
      }
    }
    if (Math.round(r.p_a * 100) === 50) return null;
    return r.p_a > 0.5 ? "a" : "b";
  }
  function category(r) {
    const lr = liveRes(r);
    if (lr && lr.called) {
      const w = lr.winner_party;
      return w === "DEM" ? "safe-d" : w === "REP" ? "safe-r" : "ind";
    }
    const pFav = Math.max(r.p_a, 1 - r.p_a);
    const favParty = r.p_a >= 0.5 ? r.side_a_party : r.side_b_party;
    if (pFav < 0.6) return "toss";
    if (favParty !== "DEM" && favParty !== "REP") return "ind";
    const side = favParty === "DEM" ? "d" : "r";
    return (pFav < 0.8 ? "lean-" : pFav < 0.95 ? "likely-" : "safe-") + side;
  }

  async function getJSON(path) {
    const r = await fetch(path, { cache: "no-store" });
    if (!r.ok) throw new Error(`${path}: ${r.status}`);
    return r.json();
  }

  // ---- scoreboard ----------------------------------------------------------
  const races = () => state.allRaces.filter((r) => r.chamber === state.chamber);

  function renderBoard() {
    const f = state.forecast, house = state.chamber === "house", gov = state.chamber === "governor";
    const s = house ? f.house : gov ? f.governor : f.senate;
    const total = house ? 435 : gov ? 50 : 100;
    const notUp = house ? { dem: 0, rep: 0 } : s.not_up;
    const need = house ? s.need : gov ? s.majority : s.dem_needs;
    let pD = s.p_dem_control, pR = s.p_rep_control, lo = null;
    if (state.live) {
      lo = Live.liveOdds(races(), state.live, {
        nationalSd: f.national_sd || 2.65, notUp, demNeeds: need, repNeeds: house || gov ? need : s.rep_needs,
        uncommitted: house || gov ? [] : (s.uncommitted_races || []), partyOnly: gov });
      pD = lo.p_dem; pR = lo.p_rep;
    }
    $("pd").textContent = fmtPct(pD);
    $("pr").textContent = fmtPct(pR);
    const side = (state.newsSide || {})[state.chamber];
    faceForTab(pD, pR, !state.live && side ? { side } : null);
    const win = gov ? "hold most governorships" : "win control";
    $("wd").textContent = state.live ? "Democrats, with called races locked in" : `Democrats ${win}`;
    $("wr").textContent = state.live ? "Republicans, with called races locked in" : `Republicans ${win}`;
    $("mid").innerHTML = gov ? `<strong>${need}</strong>of 50 governors<br>for a majority`
      : house ? `<strong>${need}</strong>of 435 seats<br>for control`
      : `<strong>${need}</strong><span class="long">seats for control<br>(${s.rep_needs} for Republicans,<br>with the VP's vote)</span><span class="short">seats to win<br>(R: ${s.rep_needs})</span>`;

    const counts = Object.fromEntries(RATINGS.map(([k]) => [k, 0]));
    races().forEach((r) => counts[category(r)]++);
    const segs = [["safe-d", notUp.dem, "Not up (D)"],
      ...RATINGS.filter(([k]) => k !== "ind").map(([k, l]) => [k, counts[k], l]),
      ["ind", counts.ind, "Independent"], ["safe-r", notUp.rep, "Not up (R)"]];
    const bar = $("bar");
    bar.innerHTML = "";
    segs.forEach(([k, n, label], i) => {
      if (!n) return;
      const sp = document.createElement("span");
      sp.style.width = (100 * n / total) + "%";
      sp.style.background = `var(--${k})`;
      if (i === 0 || i === segs.length - 1) { sp.style.opacity = ".55"; sp.classList.add("notup"); }
      sp.title = `${label}: ${n}`;
      bar.appendChild(sp);
    });
    const mark = document.createElement("i");
    mark.className = "mark";
    mark.style.left = `calc(${(100 * (need - 0.5) / total).toFixed(2)}% - 1px)`;
    bar.appendChild(mark);
    const dFav = notUp.dem + counts["safe-d"] + counts["likely-d"] + counts["lean-d"];
    const rFav = notUp.rep + counts["safe-r"] + counts["likely-r"] + counts["lean-r"];
    $("bl").textContent = `Democrats ${dFav}`;
    // governors: 14 states don't vote this year; their governors sit at the ends of the bar
    $("bm").textContent = `${counts.toss} toss-up${counts.toss === 1 ? "" : "s"}`;
    $("br").textContent = `Republicans ${rFav}`;
    bar.setAttribute("aria-label", `Democrats ${dFav} seats including leaning races, Republicans ${rFav}, ${counts.toss} toss-ups`);
    const unit = gov ? "governorships" : "seats";
    const ends = notUp.dem + notUp.rep ? "Striped ends: not on the ballot this year. " : "";
    let extra = `${ends}Bar counts ${unit} where each party is favored, even slightly. `
      + `Most likely result: ${lo ? lo.median : s.dem_seats_median} Democratic ${unit}; in 8 of 10 simulations, between ${lo ? lo.p10 : s.dem_seats_p10} and ${lo ? lo.p90 : s.dem_seats_p90}.`;
    if (state.live) {
      const rs = races().map(liveRes).filter(Boolean);
      const cd = rs.filter((x) => x.called && x.winner_party === "DEM").length;
      const cr = rs.filter((x) => x.called && x.winner_party === "REP").length;
      const ci = rs.filter((x) => x.called && x.winner_party !== "DEM" && x.winner_party !== "REP").length;
      const counting = rs.filter((x) => !x.called && x.total > 0).length;
      const h = Live.ifLeadersHold(races(), state.live, { notUp, uncommitted: house || gov ? [] : (s.uncommitted_races || []), partyOnly: gov });
      $("bm").textContent += ` · ${counting} counting`;
      faceLive(state.chamber, h, need, cd, cr, notUp);
      state.leadersLine = `If every current leader wins: Democrats ${h.dem}, Republicans ${h.rep}${h.other ? `, other ${h.other}` : ""}.`;
      extra = `Called: ${cd} D, ${cr} R${ci ? `, ${ci} other` : ""}. Still counting: ${counting}. `
        + `The odds lock in a race only once it's called; leaders can change as late ballots come in. Races with no votes yet count for the forecast favorite.`;
    }
    if (house && !state.live) extra += ` ${s.races_with_polls} districts have polls; the rest go by how the district usually votes, plus incumbency.`;
    if (gov) {
      if (!state.live) extra += ` ${s.races_up} states elect a governor this year.`;
      const pn = state.live ? lo.p_und : s.p_neither;
      if (pn >= 0.005) extra += ` ${fmtPct(pn)} chance neither party reaches ${need} (a 25–25 split, or an independent wins).`;
    }
    const pUnc = state.live ? lo.p_und : s.p_uncommitted_decides;
    if (!gov && !house && pUnc >= 0.005) {
      const u = races().find((r) => (s.uncommitted_races || []).includes(r.race_id));
      const who = u ? (u.side_a_party === "REP" ? u.side_b : u.side_a) : "an independent";
      extra += ` ${fmtPct(pUnc)} chance control comes down to ${who}, an independent who says he'll join neither party.`;
    }
    $("extra").innerHTML = (state.live && state.leadersLine ? `<strong class="leaders">${esc(state.leadersLine)}</strong>` : "") + esc(extra);
  }

  // ---- map -----------------------------------------------------------------
  function ringPath(ring) {
    return "M" + ring.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L") + "Z";
  }
  function geoPath(geom) {
    const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
    return polys.map((poly) => poly.map(ringPath).join("")).join("");
  }
  function labelPoint(geom) {
    const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
    let best = null, bestA = 0;
    for (const poly of polys) {
      const ring = poly[0];
      let a = 0, cx = 0, cy = 0;
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const f = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
        a += f; cx += (ring[j][0] + ring[i][0]) * f; cy += (ring[j][1] + ring[i][1]) * f;
      }
      if (Math.abs(a) > bestA) { bestA = Math.abs(a); best = [cx / (3 * a), cy / (3 * a)]; }
    }
    return { pt: best, area: bestA / 2 };
  }

  function renderMap() {
    if (state.chamber === "house") return renderHouseMap();
    if (!state.topo || typeof topojson === "undefined") {
      $("map").innerHTML = `<p class="note">The map didn't load. The odds and race list below are up to date.</p>`;
      return;
    }
    const byState = {};
    races().forEach((r) => (byState[r.state] = byState[r.state] || []).push(r));
    const geo = topojson.feature(state.topo, state.topo.objects.states);
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 1000 620");
    svg.setAttribute("role", "group");
    const labels = [];
    for (const f of geo.features) {
      const st = FIPS[f.id];
      if (!st) continue;
      const races = byState[st];
      const cat = races ? category(races[0]) : "none";
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", geoPath(f.geometry));
      p.setAttribute("fill", `var(--${cat})`);
      if (state.live && races && !(liveRes(races[0]) || {}).called) p.style.opacity = ".4";
      p.dataset.state = st;
      if (!races) p.classList.add("none");
      else {
        p.setAttribute("tabindex", "0");
        p.setAttribute("role", "button");
        p.setAttribute("aria-label", `${NAMES[st]}: ${RATINGS.find(([k]) => k === cat)[1]}`);
        p.addEventListener("click", () => openRace(races[0].race_id));
        p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openRace(races[0].race_id); } });
      }
      svg.appendChild(p);
      const { pt, area } = labelPoint(f.geometry);
      if (races && pt && area > 1500 && !CALLOUTS.includes(st)) labels.push([st, pt, cat]);
    }
    for (const [st, pt, cat] of labels) {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", pt[0]); t.setAttribute("y", pt[1] + 5); t.setAttribute("text-anchor", "middle");
      if (!DARK_TEXT.has(cat)) t.classList.add("light");
      const called = state.live && (liveRes(byState[st][0]) || {}).called;
      t.textContent = called ? "✓" + st : st;
      svg.appendChild(t);
    }
    CALLOUTS.forEach((st, i) => {
      const races = byState[st];
      const y = 170 + i * 44;
      const g = document.createElementNS(NS, "g");
      const rect = document.createElementNS(NS, "path");
      rect.setAttribute("d", `M922 ${y}h66v36h-66z`);
      const cat = races ? category(races[0]) : "none";
      rect.setAttribute("fill", `var(--${cat})`);
      if (state.live && races && !(liveRes(races[0]) || {}).called) rect.style.opacity = ".4";
      if (!races) rect.classList.add("none");
      else {
        rect.setAttribute("tabindex", "0");
        rect.setAttribute("role", "button");
        rect.setAttribute("aria-label", `${NAMES[st]}: ${RATINGS.find(([k]) => k === cat)[1]}`);
        rect.addEventListener("click", () => openRace(races[0].race_id));
      }
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", 955); t.setAttribute("y", y + 27); t.setAttribute("text-anchor", "middle");
      if (!DARK_TEXT.has(cat)) t.classList.add("light");
      t.textContent = state.live && races && (liveRes(races[0]) || {}).called ? "✓" + st : st;
      g.append(rect, t);
      svg.appendChild(g);
    });
    $("map").innerHTML = "";
    $("map").appendChild(svg);
    $("key").innerHTML = RATINGS.map(([k, l]) => `<span><i style="background:var(--${k})"></i>${l}</span>`).join("")
      + `<span><i style="background:var(--none)"></i>No race this year</span>`
      + (state.live ? `<span>Bright = called (✓). Faded = not called yet, shown by forecast.</span>` : "");
  }

  // ---- House map: real district boundaries (Census, simplified) ------------------
  // Phones can't tap tiny city districts on a national map, so the first tap on a
  // state zooms to it; inside a state, a tap opens the district.
  const ST_ABBR = Object.fromEntries(Object.entries(FIPS).map(([f, a]) => [f, a]));

  function houseGeo() {
    if (state.houseGeo) return state.houseGeo;
    const topo = state.houseTopo;
    const districts = topojson.feature(topo, topo.objects.districts).features;
    const states = topojson.feature(topo, topo.objects.states).features;
    const bbox = (geoms) => {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      const walk = (c) => { if (typeof c[0] === "number") { x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]); y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]); } else c.forEach(walk); };
      geoms.forEach((g) => walk(g.geometry.coordinates));
      return [x0, y0, x1, y1];
    };
    const all = bbox(districts);
    const W = 1000, k = W / (all[2] - all[0]), H = (all[3] - all[1]) * k;
    const P = (c) => [(c[0] - all[0]) * k, (all[3] - c[1]) * k];           // projected metres -> SVG, y flipped
    const path = (geom) => {
      const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
      return polys.map((poly) => poly.map((ring) => "M" + ring.map((c) => P(c).map((v) => v.toFixed(1)).join(",")).join("L") + "Z").join("")).join("");
    };
    const box = (geoms) => { const b = bbox(geoms); const a = P([b[0], b[3]]), z = P([b[2], b[1]]); return [a[0], a[1], z[0] - a[0], z[1] - a[1]]; };
    const byState = {};
    districts.forEach((f) => (byState[f.properties.st] = byState[f.properties.st] || []).push(f));
    state.houseGeo = {
      W, H,
      districts: districts.map((f) => {
        const st = ST_ABBR[f.properties.st], cd = parseInt(f.properties.cd, 10) || 1;
        return { st, fips: f.properties.st, race_id: `${state.forecast.cycle}-HOUSE-${st}-${cd}`, d: path(f.geometry) };
      }),
      states: states.map((f) => ({ fips: f.properties.st, d: path(f.geometry) })),
      stateBox: Object.fromEntries(Object.entries(byState).map(([fips, fs]) => [fips, box(fs)])),
    };
    return state.houseGeo;
  }

  async function renderHouseMap() {
    if (typeof topojson === "undefined") {
      $("map").innerHTML = `<p class="note">The map didn't load. The odds and district list below are up to date.</p>`;
      return;
    }
    if (!state.houseTopo) {
      $("map").innerHTML = `<p class="note">Loading district map…</p>`;
      try { state.houseTopo = await getJSON("data/house_map.json"); }
      catch (e) { $("map").innerHTML = `<p class="note">Couldn't load the district map. Reload to try again.</p>`; return; }
      if (state.chamber !== "house") return;
    }
    const g = houseGeo();
    const byId = Object.fromEntries(races().map((r) => [r.race_id, r]));
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    const zoom = state.houseZoom;
    let vb = [0, 0, g.W, g.H];
    if (zoom && g.stateBox[zoom]) {
      const [x, y, w, h] = g.stateBox[zoom];
      const pad = Math.max(w, h) * 0.06, aspect = g.W / g.H;
      let W2 = w + 2 * pad, H2 = h + 2 * pad;
      if (W2 / H2 < aspect) W2 = H2 * aspect; else H2 = W2 / aspect;
      vb = [x + w / 2 - W2 / 2, y + h / 2 - H2 / 2, W2, H2];
    }
    const base = vb.slice();
    for (const dist of g.districts) {
      const r = byId[dist.race_id];
      const cat = r ? category(r) : "none";
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", dist.d);
      p.setAttribute("fill", `var(--${cat})`);
      p.setAttribute("class", "district");
      if (state.live && r && !(liveRes(r) || {}).called) p.style.opacity = ".4";
      if (zoom && dist.fips !== zoom) p.style.opacity = ".25";
      p.dataset.race = dist.race_id;
      if (r) {
        p.setAttribute("tabindex", "0");
        p.setAttribute("role", "button");
        p.setAttribute("aria-label", `${raceLabel(r)}: ${RATINGS.find(([k]) => k === cat)[1]}`);
        const act = () => {
          const single = g.districts.filter((x) => x.fips === dist.fips).length === 1;
          if (state.houseZoom === dist.fips || single) openRace(r.race_id);
          else { state.houseZoom = dist.fips; renderHouseMap(); }
        };
        p.addEventListener("click", act);
        p.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(); } });
      }
      svg.appendChild(p);
    }
    for (const st of g.states) {
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", st.d);
      p.setAttribute("class", "state-line");
      svg.appendChild(p);
    }
    $("map").innerHTML = "";
    const bar = document.createElement("div");
    bar.className = "zoombar";
    bar.innerHTML = (zoom ? `<strong>${NAMES[ST_ABBR[zoom]]}</strong><span class="zhint">Tap a district</span>`
                          : `<span class="zhint">Pinch to zoom or tap a state</span>`)
      + `<span class="zbtns"><button id="zin" aria-label="Zoom in">+</button><button id="zout" aria-label="Zoom out">−</button>`
      + (zoom ? `<button id="unzoom">Whole map</button>` : "") + `</span>`;
    $("map").appendChild(bar);
    if (zoom) bar.querySelector("#unzoom").addEventListener("click", () => { state.houseZoom = null; state.houseView = null; renderHouseMap(); });
    const wrap = document.createElement("div");
    wrap.className = "mapframe";
    wrap.appendChild(svg);
    $("map").appendChild(wrap);
    const pz = panZoom(svg, base, [0, 0, g.W, g.H], zoom || "us");
    bar.querySelector("#zin").addEventListener("click", () => pz.zoomBy(1.6));
    bar.querySelector("#zout").addEventListener("click", () => pz.zoomBy(1 / 1.6));
    $("key").innerHTML = RATINGS.map(([k, l]) => `<span><i style="background:var(--${k})"></i>${l}</span>`).join("")
      + `<span>${zoom ? "" : "Tap a state to zoom in. "}District lines: Census, 2026 maps.</span>`
      + (state.live ? `<span>Bright = called. Faded = not called yet, shown by forecast.</span>` : "");
  }

  // Pinch / drag / wheel zoom inside the map only. The page itself never zooms:
  // the map sets touch-action so the browser leaves two-finger gestures to us.
  // One finger scrolls the page unless the map is zoomed in, then it pans the map.
  function panZoom(svg, base, full, key) {
    const aspect = base[3] / base[2];
    const ext = [Math.min(full[0], base[0]), Math.min(full[1], base[1]),
                 Math.max(full[0] + full[2], base[0] + base[2]), Math.max(full[1] + full[3], base[1] + base[3])];
    let vb = state.houseViewKey === key && state.houseView ? state.houseView.slice() : base.slice();
    const zoomed = () => vb[2] < base[2] * 0.98;
    function apply() {
      const minW = base[2] / 12;
      vb[2] = Math.min(Math.max(vb[2], minW), base[2]); vb[3] = vb[2] * aspect;
      if (!zoomed()) { vb = base.slice(); }
      else {
        vb[0] = Math.min(Math.max(vb[0], ext[0]), ext[2] - vb[2]);
        vb[1] = Math.min(Math.max(vb[1], ext[1]), ext[3] - vb[3]);
      }
      svg.setAttribute("viewBox", vb.map((v) => v.toFixed(1)).join(" "));
      svg.classList.toggle("zoomed", zoomed());
      state.houseView = vb.slice(); state.houseViewKey = key;
    }
    function zoomAt(f, cx, cy) {
      const r = svg.getBoundingClientRect();
      const fx = (cx - r.left) / r.width, fy = (cy - r.top) / r.height;
      const px = vb[0] + fx * vb[2], py = vb[1] + fy * vb[3];
      vb[2] /= f; vb[3] = vb[2] * aspect;
      vb[0] = px - fx * vb[2]; vb[1] = py - fy * vb[3];
    }
    function panBy(dx, dy) {
      const r = svg.getBoundingClientRect();
      vb[0] -= dx * vb[2] / r.width; vb[1] -= dy * vb[3] / r.height;
    }
    let moved = 0, prev = null;
    const pts = (e) => [...e.touches].map((t) => [t.clientX, t.clientY]);
    const mid = (a) => [(a[0][0] + a[1][0]) / 2, (a[0][1] + a[1][1]) / 2];
    const dist = (a) => Math.hypot(a[0][0] - a[1][0], a[0][1] - a[1][1]);
    svg.addEventListener("touchstart", (e) => { if (e.touches.length === 1) moved = 0; prev = pts(e); }, { passive: true });
    svg.addEventListener("touchmove", (e) => {
      const cur = pts(e);
      if (cur.length >= 2 && prev && prev.length >= 2) {
        e.preventDefault();
        const m0 = mid(prev), m1 = mid(cur);
        zoomAt(dist(cur) / Math.max(dist(prev), 1), m1[0], m1[1]);
        panBy(m1[0] - m0[0], m1[1] - m0[1]);
        moved += 10; apply();
      } else if (cur.length === 1 && prev && prev.length === 1 && zoomed()) {
        e.preventDefault();
        const dx = cur[0][0] - prev[0][0], dy = cur[0][1] - prev[0][1];
        moved += Math.abs(dx) + Math.abs(dy);
        panBy(dx, dy); apply();
      }
      prev = cur;
    }, { passive: false });
    svg.addEventListener("touchend", (e) => { prev = pts(e); }, { passive: true });
    // mouse: drag to pan when zoomed, wheel to zoom
    let drag = null;
    svg.addEventListener("pointerdown", (e) => {
      if (e.pointerType === "mouse" && zoomed()) { drag = [e.clientX, e.clientY]; moved = 0; }
    });
    svg.addEventListener("pointermove", (e) => {
      if (!drag || !(e.buttons & 1)) { drag = null; return; }
      const dx = e.clientX - drag[0], dy = e.clientY - drag[1];
      moved += Math.abs(dx) + Math.abs(dy); drag = [e.clientX, e.clientY]; panBy(dx, dy); apply();
    });
    svg.addEventListener("pointerup", () => { drag = null; });
    svg.addEventListener("wheel", (e) => {
      if (!e.ctrlKey) return;   // plain wheel scrolls the page; trackpad pinch (ctrl+wheel) zooms the map
      e.preventDefault(); zoomAt(Math.exp(-e.deltaY * 0.002), e.clientX, e.clientY); apply();
    }, { passive: false });
    // a drag or pinch is not a tap: don't open a district after one
    svg.addEventListener("click", (e) => { if (moved > 8) { e.stopPropagation(); e.preventDefault(); } moved = 0; }, true);
    apply();
    return {
      zoomBy(f) { const r = svg.getBoundingClientRect(); zoomAt(f, r.left + r.width / 2, r.top + r.height / 2); apply(); },
    };
  }

  const ordinal = (n) => { const t = ["th", "st", "nd", "rd"], v = n % 100; return n + (t[(v - 20) % 10] || t[v] || t[0]); };
  function raceLabel(r) {
    if (r.chamber === "house") {
      const atLarge = state.allRaces.filter((x) => x.chamber === "house" && x.state === r.state).length === 1;
      return `${NAMES[r.state]} ${atLarge ? "at-large" : ordinal(+r.district)} district`;
    }
    if (r.chamber === "governor") return `${NAMES[r.state]} governor`;
    return `${NAMES[r.state]} Senate${r.race_id.endsWith("-S") ? " (special)" : ""}`;
  }
  const shortLabel = (r) => r.chamber === "house" ? `${r.state}-${r.district}${r.redrawn_2026 ? "*" : ""}` : r.state;

  // ---- list ----------------------------------------------------------------
  // Watch list: races always shown and pinned to the top, whatever their margin.
  const WATCH = ["2026-HOUSE-TX-6"];
  const CLOSE = 20;   // "close" = within this many points
  try { if (localStorage.getItem("closeOnly") === "0") state.closeOnly = false; } catch (e) { /* storage blocked */ }
  // Gap between the top two, in points: the vote count once counting starts, else the forecast.
  function gapNow(r) {
    const lr = liveRes(r);
    if (lr && lr.total > 0 && lr.candidates && lr.candidates.length) {
      const c = lr.candidates;
      return c[1] ? Math.abs((c[0].pct || 0) - (c[1].pct || 0)) : 100;
    }
    return Math.abs(r.margin);
  }
  const isClose = (r) => gapNow(r) <= CLOSE;

  function renderList() {
    const house = state.chamber === "house";
    // election night: races being counted first (closest count first), then not started, then called
    const liveGroup = (r) => { const lr = liveRes(r); return !lr ? 1 : lr.called ? 2 : lr.total > 0 ? 0 : 1; };
    const countGap = (r) => { const c = liveRes(r).candidates; return c[1] ? Math.abs((c[0].pct || 0) - (c[1].pct || 0)) : 100; };
    const order = (a, b) => {
      if (state.live) {
        const ga = liveGroup(a), gb = liveGroup(b);
        if (ga !== gb) return ga - gb;
        if (ga === 0) return countGap(a) - countGap(b);
      }
      return Math.abs(a.p_a - 0.5) - Math.abs(b.p_a - 0.5);
    };
    const watched = (r) => WATCH.includes(r.race_id);
    const sorted = races().slice().sort(order);
    const all = sorted.filter(watched).concat(sorted.filter((r) => !watched(r) && (!state.closeOnly || isClose(r))));
    const list = house ? all.slice(0, state.showAll ? 435 : 40) : all;
    const anyCounting = state.live && all.some((r) => liveGroup(r) === 0);
    $("races").classList.toggle("house-list", house);
    $("list-title").textContent = anyCounting ? (house && !state.showAll ? "Still counting, closest first (top 40)" : "Still counting, closest first")
      : house ? (state.showAll ? "All districts, closest first" : "40 closest districts") : "Races, closest first";
    const nHidden = races().length - all.length;
    $("list-filter").innerHTML = `<button id="close-toggle" aria-pressed="${state.closeOnly}">${state.closeOnly ? `Within ${CLOSE} pts` : "All races"}</button>`
      + `<span>${state.closeOnly ? (nHidden ? `${nHidden} lopsided ${nHidden === 1 ? "race" : "races"} hidden` : "None hidden") : `Tap to hide races not within ${CLOSE} pts`}</span>`;
    $("close-toggle").addEventListener("click", () => {
      state.closeOnly = !state.closeOnly;
      try { localStorage.setItem("closeOnly", state.closeOnly ? "1" : "0"); } catch (e) { /* storage blocked */ }
      renderList();
    });
    $("races").innerHTML = list.map((r) => {
      const cat = category(r);
      const fav = r.p_a >= 0.5;
      const pFav = Math.max(r.p_a, 1 - r.p_a);
      const favName = fav ? r.side_a : r.side_b;
      const lr = liveRes(r);
      const tossName = Math.round(r.p_a * 100) === 50 ? "Toss-up" : esc(favName.split(" ").slice(-1)[0]);
      let right = `${fmtPct(pFav)}<small>${tossName} · ${fmtMargin(r.margin, letter(r.side_a_party), letter(r.side_b_party))}</small>`;
      if (lr && lr.total > 0) {
        const [c1, c2] = lr.candidates;
        const m = c2 ? ((c1.pct || 0) - (c2.pct || 0)) : 100;
        const lead = `${esc(c1.name.split(" ").slice(-1)[0])} +${m.toFixed(1)}`;
        const counted = lr.expected ? `~${Math.min(99, Math.round(100 * lr.total / lr.expected))}% in` : `${(lr.total / 1000).toFixed(0)}k votes`;
        const tag = lr.called ? `<span class="won ${lr.winner_party === "DEM" ? "d" : lr.winner_party === "REP" ? "r" : "i"}">Won</span> ` : "";
        right = `${tag}${lead}<small>${lr.called ? "Called" : counted}</small>`;
      }
      const lead = leaderSide(r);
      const nameA = `${esc(r.side_a)} (${letter(r.side_a_party)})`, nameB = `${esc(r.side_b)} (${letter(r.side_b_party)})`;
      const top = `<span class="${lead ? "lead" : ""}">${lead === "b" ? nameB : nameA}</span>`;
      const bottom = `<span class="${lead ? "trail" : ""}">${lead === "b" ? nameA : nameB}</span>`;
      return `<li><button data-race="${esc(r.race_id)}">
        <span class="chip${watched(r) ? " watch" : ""}" style="background:var(--${cat});color:${DARK_TEXT.has(cat) ? "#0f1526" : "#fff"}">${shortLabel(r)}</span>
        <span class="names${lead ? "" : " even"}">${top}${bottom}</span>
        <span class="odds">${right}</span>
      </button></li>`;
    }).join("");
    if (house && !state.showAll && all.length > 40) $("races").innerHTML += `<li><button class="more" id="show-all">Show all ${all.length === 435 ? 435 : all.length} districts</button></li>`;
    if (house && state.liveMode) $("races").innerHTML += `<li class="foot">Wikipedia hasn't posted most House counts yet. Tap a district for a live-count link.</li>`;
    if (house) $("races").innerHTML += `<li class="foot">* District lines redrawn mid-decade for 2026 (the whole state map was replaced; some districts changed little). Tap a district to see who drew its map.</li>`;
    $("races").querySelectorAll("button[data-race]").forEach((b) => b.addEventListener("click", () => openRace(b.dataset.race)));
    const more = $("show-all");
    if (more) more.addEventListener("click", () => { state.showAll = true; renderList(); });
  }

  // ---- race sheet ----------------------------------------------------------
  function pollsterLine(id) {
    const p = state.pollsters[id];
    if (!p) return "New pollster: no record yet";
    const w = p.windows, a = w.all_time, l2 = w.last_two;
    if (!a || a.n < 5) return `Too few graded races (${a ? a.n : 0})`;
    let s = `Misses by ${a.mean_abs_error.toFixed(1)} on avg over ${a.n} races`;
    const b = (l2 && l2.n >= 5 && l2.bias != null) ? l2.bias : a.bias;
    if (b != null && Math.abs(b) >= 1) s += `, leans ${b > 0 ? "D" : "R"}+${Math.abs(b).toFixed(1)}`;
    return s;
  }

  // Live count box for a race sheet (r: race with race_id/state/chamber; lr: its live result).
  function pollRowsHTML(r, A, B) {
    return (r.polls || []).slice(0, 25).map((p) => {
      const pol = state.pollsters[p.pollster_id];
      const name = p.name || (pol ? pol.name : p.pollster_id);
      const grade = p.sb_grade ? ` <span class="sbg" title="Silver Bulletin grade">(${esc(p.sb_grade)}${p.sb_banned ? ", banned" : ""})</span>` : "";
      const adj = Math.abs(p.bias_correction) >= 0.05 ? `<span class="pq">counted as ${fmtMargin(p.margin, A, B)}</span>` : "";
      return `<tr><td>${esc(name)}${grade}<span class="pq">${esc(pollsterLine(p.pollster_id))}</span></td>
        <td class="num">${fmtDate(p.end)}</td>
        <td class="num">${fmtMargin(p.margin_raw, A, B)}${adj}</td>
        <td class="num">${(p.weight_share * 100).toFixed(0)}%</td></tr>`;
    }).join("");
  }
  const POLL_NOTE = "Weight is each poll's share of the average: newer, larger, likely-voter polls from pollsters with better records count more. A pollster that has historically leaned one way is counted with that lean taken out. Letter grades in brackets are Silver Bulletin's (January 2026) and are shown for reference only; they don't change any weight.";
  function liveBoxHTML(r, lr, lead) {
    if (!(lr && lr.total > 0)) return "";
    const share = lr.expected ? Math.min(100, 100 * lr.total / lr.expected) : null;
    const [l1, l2] = lr.candidates;
    const lastName = (n) => esc(String(n).trim().split(/\s+/).slice(-1)[0]);
    const gapPts = l2 ? ((l1.pct || 0) - (l2.pct || 0)).toFixed(1) : null;
    const headline = lr.called
      ? `Called for ${esc((lr.candidates.find((c) => c.winner) || l1).name)}`
      : l2 && l1.votes === l2.votes ? "Tied"
      : `${lastName(l1.name)} leads${gapPts ? ` by ${gapPts} pts` : ""}${share != null ? ` with ~${Math.min(99, Math.round(share))}% counted` : ""}`;
    return `<div class="livebox">
      <div class="livehead">${headline}</div>
      <table>${lr.candidates.slice(0, 4).map((c, i) => `<tr class="${i === 0 && lead ? "lead" : "trail"}"><td>${esc(c.name)} (${letter(c.party)})${c.winner && lr.called ? ' <span class="won ' + (c.party === "DEM" ? "d" : c.party === "REP" ? "r" : "i") + '">Won</span>' : ""}</td>
        <td class="num">${c.votes.toLocaleString()}</td><td class="num">${c.pct != null ? c.pct.toFixed(1) + "%" : ""}</td></tr>`).join("")}</table>
      ${share != null ? `<div class="meter"><span style="width:${share.toFixed(0)}%"></span></div>` : ""}
      <div class="note">${lr.total.toLocaleString()} votes counted${lr.reporting != null ? `, ${lr.reporting}% reporting per Wikipedia` : share != null ? `, about ${share.toFixed(0)}% of the vote we expect (estimate from 2024 turnout)` : ""}.
      ${lr.called ? "Called, per Wikipedia." : "Not called yet."} Wikipedia last edited ${new Date(lr.edited).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.</div>
      ${(() => { const s = countShift(r, lr); return s ? `<div class="shift">${s}</div>` : ""; })()}
    </div>`;
  }

  // Election night, no count on Wikipedia yet: a link to a search that shows the live count
  // (news results boxes, from AP). The app can't read those feeds itself.
  function countLink(r, title) {
    if (!state.liveMode) return "";
    const lr = liveRes(r);
    if (lr && lr.total > 0) return "";
    const q = title || (r.chamber === "house"
      ? `${NAMES[r.state]} ${state.allRaces.filter((x) => x.chamber === "house" && x.state === r.state).length === 1 ? "at-large" : ordinal(+r.district)} congressional district election results`
      : r.chamber === "governor" ? `${NAMES[r.state]} governor election results`
      : `${NAMES[r.state]} Senate election results`);
    const url = "https://www.google.com/search?q=" + encodeURIComponent(q + " 2026");
    return `<a class="countlink" href="${esc(url)}" target="_blank" rel="noopener">Live count ↗</a>`
      + `<div class="note">Wikipedia has no count for this race yet. The link opens a search whose results box shows the running count.</div>`;
  }

  function openRace(id) {
    const r = state.allRaces.find((x) => x.race_id === id);
    if (!r) return;
    state.selected = id;
    document.querySelectorAll(".map path.sel").forEach((p) => p.classList.remove("sel"));
    if (r.chamber === "house" && state.houseGeo) {
      const fips = Object.keys(FIPS).find((f) => FIPS[f] === r.state);
      if (state.houseZoom !== fips) { state.houseZoom = fips; renderHouseMap(); }
    }
    const sel = r.chamber === "house" ? `.map path[data-race="${r.race_id}"]` : `.map path[data-state="${r.state}"]`;
    document.querySelectorAll(sel).forEach((p) => p.classList.add("sel"));
    $("sheet-title").textContent = raceLabel(r);
    const A = letter(r.side_a_party), B = letter(r.side_b_party);
    const pollRows = pollRowsHTML(r, A, B);
    const pa = r.p_a;
    const lr = liveRes(r);
    const lead = leaderSide(r);
    const liveBox = liveBoxHTML(r, lr, lead) + countLink(r);
    const colour = (L) => (L === "D" ? "dem" : L === "R" ? "rep" : "ind");
    const sideA = { name: r.side_a, L: A, p: pa, cls: lead === "a" ? "lead" : lead ? "trail" : "" };
    const sideB = { name: r.side_b, L: B, p: 1 - pa, cls: lead === "b" ? "lead" : lead ? "trail" : "" };
    const [first, second] = lead === "b" ? [sideB, sideA] : [sideA, sideB];
    const duel = [first, second].map((x, i) => `<div class="${i ? "r " : ""}${x.cls}"><div class="n">${esc(x.name)} (${x.L})</div><div class="p" style="color:var(--${colour(x.L)})">${fmtPct(x.p)}</div></div>`).join("");
    $("sheet-body").innerHTML = liveBox + `
      ${lr && lr.total > 0 ? `<div class="note">Pre-election forecast, chance of winning:</div>` : ""}
      <div class="duel">${duel}</div>
      <dl class="facts">
        <dt>Forecast margin</dt><dd>${fmtMargin(r.margin, A, B)} (typical miss ±${r.sd.toFixed(1)})</dd>
        ${r.poll_average != null ? `<dt>Polling average</dt><dd>${fmtMargin(r.poll_average, A, B)} from ${r.n_polls} poll${r.n_polls === 1 ? "" : "s"}, latest ${fmtDate(r.last_poll)}</dd>` : `<dt>Polls</dt><dd>None published. Forecast is from partisan lean only.</dd>`}
        ${r.lean_prior != null ? `<dt>Partisan lean</dt><dd>${fmtMargin(r.lean_prior, "D", "R")} ${r.chamber === "house" ? leanNote(r) : r.chamber === "governor" && r.basis === "polls" ? "(state's 2024 result moved by the national mood; shown for reference only: in past governor races, mixing it in made forecasts worse, because governors often run far from their state's presidential lean)" : "(state's 2024 result moved by the national mood)"}</dd>` : ""}
        ${r.basis === "unopposed" ? `<dt>Note</dt><dd>No major-party opponent on the ballot.</dd>` : ""}
        ${r.redrawn_2026 ? `<dt>New map*</dt><dd>${esc(r.map_note)}</dd>` : ""}
        ${slowCount(r) ? `<dt>Count</dt><dd>${esc(slowCount(r))}</dd>` : ""}
        ${wikiLink(r) ? `<dt>Source</dt><dd><a href="${esc(wikiLink(r))}" target="_blank" rel="noopener">This race on Wikipedia</a>${state.live ? " (live results are read from here)" : ""}</dd>` : ""}
        ${r.uncommitted ? `<dt>Note</dt><dd>${esc(r.side_a)} says he will join neither party's caucus.</dd>` : ""}
      </dl>
      ${pollRows ? `<table class="polls"><thead><tr><th>Pollster</th><th class="num">Ended</th><th class="num">Result</th><th class="num">Weight</th></tr></thead><tbody>${pollRows}</tbody></table>
      <p class="note">Weight is each poll's share of the average: newer, larger, likely-voter polls from pollsters with better records count more. A pollster that has historically leaned one way is counted with that lean taken out. Letter grades in brackets are Silver Bulletin's (January 2026) and are shown for reference only; they don't change any weight.</p>` : ""}`;
    document.body.classList.add("sheet-open");
    history.replaceState(null, "", location.pathname + location.search + "#" + id);
    $("close").focus();
  }
  function leanNote(r) {
    const src = { "PVI": "from the district's Cook PVI and the national mood",
      "2026 PVI": "from the district's 2026 PVI and the national mood",
      "expert ratings (new map)": "from expert ratings, because this state redrew its map",
      "expert ratings": "from expert ratings" }[r.lean_source] || "";
    const inc = r.incumbent_party ? `; includes an edge for the ${r.incumbent_party === "DEM" ? "Democratic" : "Republican"} incumbent` : "";
    return `(${src}${r.lean_source && r.lean_source.startsWith("expert") ? "" : inc})`;
  }
  function closeRace() {
    document.body.classList.remove("sheet-open");
    document.querySelectorAll(".map path.sel").forEach((p) => p.classList.remove("sel"));
    history.replaceState(null, "", location.pathname + location.search);
  }

  // ---- my ballot -------------------------------------------------------------
  // One voter's ballot (config/my_ballot.yaml): races the model covers, Florida Cabinet races
  // run through the governor method, and county races with no odds (the county posts those counts).
  const ballotItems = () => (state.ballot ? state.ballot.sections.flatMap((s) => s.races) : []);
  // A race object the list helpers understand (race_id, sides, p_a), or null when there are no odds.
  function ballotRace(item) {
    if (item.kind === "model") return state.allRaces.find((x) => x.race_id === item.id) || null;
    if (item.kind === "polls" && item.odds) return { race_id: item.id, chamber: "cabinet", state: "FL", matchup: "D-R", ...item.odds };
    return null;
  }
  const partyTag = (p) => (p ? ` (${{ DEM: "D", REP: "R", NPA: "NPA", LPF: "L" }[p] || p})` : "");

  function oddsCell(r) {
    const lr = liveRes(r);
    if (lr && lr.total > 0) {
      const [c1, c2] = lr.candidates;
      const m = c2 ? ((c1.pct || 0) - (c2.pct || 0)) : 100;
      const counted = lr.expected ? `~${Math.min(99, Math.round(100 * lr.total / lr.expected))}% in` : `${(lr.total / 1000).toFixed(0)}k votes`;
      const tag = lr.called ? `<span class="won ${lr.winner_party === "DEM" ? "d" : lr.winner_party === "REP" ? "r" : "i"}">Won</span> ` : "";
      return `${tag}${esc(c1.name.split(" ").slice(-1)[0])} +${m.toFixed(1)}<small>${lr.called ? "Called" : counted}</small>`;
    }
    const pFav = Math.max(r.p_a, 1 - r.p_a);
    const favName = r.p_a >= 0.5 ? r.side_a : r.side_b;
    const who = Math.round(r.p_a * 100) === 50 ? "Toss-up" : esc(favName.split(" ").slice(-1)[0]);
    return `${fmtPct(pFav)}<small>${who} · ${fmtMargin(r.margin, letter(r.side_a_party), letter(r.side_b_party))}</small>`;
  }

  function ballotRow(item) {
    const r = ballotRace(item);
    let chipStyle = "background:var(--none);color:var(--ink)", names, right;
    if (r) {
      const cat = category(r);
      chipStyle = `background:var(--${cat});color:${DARK_TEXT.has(cat) ? "#0f1526" : "#fff"}`;
      const lead = leaderSide(r);
      const nA = `${esc(r.side_a)} (${letter(r.side_a_party)})`, nB = `${esc(r.side_b)} (${letter(r.side_b_party)})`;
      names = `<span class="mb-label">${esc(item.label)}</span><span class="${lead ? "lead" : ""}">${lead === "b" ? nB : nA}</span><span class="${lead ? "trail" : ""}">${lead === "b" ? nA : nB}</span>`;
      right = oddsCell(r);
    } else if (item.kind === "measure") {
      names = `<span class="mb-label">${esc(item.label)}</span><span class="mb-sum">${esc(item.summary)}</span>`;
      right = `Yes/No<small>Count: county site</small>`;
    } else {
      const cs = (item.candidates || []).slice(0, 2);
      names = `<span class="mb-label">${esc(item.label)}</span>` + cs.map(([n, p]) => `<span>${esc(n)}${partyTag(p)}</span>`).join("");
      right = `–<small>No polls</small>`;
    }
    return `<li><button data-ballot="${esc(item.id)}">
      <span class="chip" style="${chipStyle}">${esc(item.chip)}</span>
      <span class="names mb-names">${names}</span>
      <span class="odds">${right}</span>
    </button></li>`;
  }

  function renderBallot() {
    const b = state.ballot;
    if (!b) {
      $("mb-intro").textContent = "";
      $("mb-body").innerHTML = `<p class="note">Couldn't load the ballot. Punch the face to try again.</p>`;
      return;
    }
    const url = esc(b.county_results_url);
    $("mb-intro").innerHTML = `${esc(b.county)} · ZIP ${esc(b.zip)} · ballot style ${esc(b.ballot_style)}. `
      + (state.live ? "Federal and state races update from Wikipedia every 2 minutes." : "Chance of winning from the polls; tap a race for details.");
    const isCounty = (s) => s.races.some((x) => x.kind === "local" || x.kind === "measure");
    const lastCounty = b.sections.filter(isCounty).slice(-1)[0];
    $("mb-body").innerHTML = b.sections.map((s) => `<h2>${esc(s.name)}</h2><ul class="races mb-list">${s.races.map(ballotRow).join("")}</ul>`
      + (s === lastCounty ? `<p class="note mb-county">Live counts for county races: <a href="${url}" target="_blank" rel="noopener">${esc(b.county_results_name)}</a>. Wikipedia doesn't carry them, and the county's site can't be read from this page.</p>` : "")).join("");
    $("mb-foot").textContent = "State constitutional amendments and judicial retention votes are on this ballot too but aren't shown here.";
    $("mb-body").querySelectorAll("button[data-ballot]").forEach((el) => el.addEventListener("click", () => openBallot(el.dataset.ballot)));
  }

  function openBallot(id) {
    const item = ballotItems().find((x) => x.id === id);
    if (!item) return;
    if (item.kind === "model") return openRace(id);
    state.selected = id;
    const b = state.ballot;
    const countyLink = `<a href="${esc(b.county_results_url)}" target="_blank" rel="noopener">${esc(b.county_results_name)}</a>`;
    $("sheet-title").textContent = item.label;
    let html = "";
    const r = ballotRace(item);
    if (r) {
      const A = letter(r.side_a_party), B = letter(r.side_b_party);
      const lr = liveRes(r), lead = leaderSide(r);
      const colour = (L) => (L === "D" ? "dem" : L === "R" ? "rep" : "ind");
      const sa = { name: r.side_a, L: A, p: r.p_a, cls: lead === "a" ? "lead" : lead ? "trail" : "" };
      const sb = { name: r.side_b, L: B, p: 1 - r.p_a, cls: lead === "b" ? "lead" : lead ? "trail" : "" };
      const duel = (lead === "b" ? [sb, sa] : [sa, sb]).map((x, i) => `<div class="${i ? "r " : ""}${x.cls}"><div class="n">${esc(x.name)} (${x.L})</div><div class="p" style="color:var(--${colour(x.L)})">${fmtPct(x.p)}</div></div>`).join("");
      const wiki = item.page ? "https://en.wikipedia.org/wiki/" + encodeURIComponent(item.page.replace(/ /g, "_")) : null;
      const rows = pollRowsHTML(r, A, B);
      html = liveBoxHTML(r, lr, lead) + countLink(r, `Florida ${item.label} election results`)
        + (lr && lr.total > 0 ? `<div class="note">Pre-election forecast, chance of winning:</div>` : "")
        + `<div class="duel">${duel}</div>
        <dl class="facts">
          <dt>Forecast margin</dt><dd>${fmtMargin(r.margin, A, B)} (typical miss ±${r.sd.toFixed(1)})</dd>
          <dt>Polling average</dt><dd>${fmtMargin(r.poll_average, A, B)} from ${r.n_polls} poll${r.n_polls === 1 ? "" : "s"}, latest ${fmtDate(r.last_poll)}</dd>
          <dt>Method</dt><dd>Same poll average and error formula as the governor races. Cabinet races aren't in the backtest, and with this few polls the typical miss is wide.</dd>
          ${wiki ? `<dt>Source</dt><dd><a href="${esc(wiki)}" target="_blank" rel="noopener">This race on Wikipedia</a>${state.live ? " (live results are read from here)" : ""}</dd>` : ""}
          <dt>Hillsborough</dt><dd>County-level count: ${countyLink}</dd>
        </dl>
        ${rows ? `<table class="polls"><thead><tr><th>Pollster</th><th class="num">Ended</th><th class="num">Result</th><th class="num">Weight</th></tr></thead><tbody>${rows}</tbody></table><p class="note">${esc(POLL_NOTE)}</p>` : ""}`;
    } else if (item.kind === "measure") {
      html = `<p>${esc(item.summary)}</p>
        <dl class="facts"><dt>Passes with</dt><dd>A simple majority of county voters</dd>
        <dt>Live count</dt><dd>${countyLink}</dd></dl>`;
    } else {
      html = `<ul class="mb-cands">${(item.candidates || []).map(([n, p]) => `<li>${esc(n)}${partyTag(p)}</li>`).join("")}</ul>
        <dl class="facts"><dt>Odds</dt><dd>None: no public polls for this race.</dd>
        <dt>Live count</dt><dd>${countyLink}. Results start after polls close at 7 pm Eastern (01:00 Berlin).</dd></dl>`;
    }
    $("sheet-body").innerHTML = html;
    document.body.classList.add("sheet-open");
    history.replaceState(null, "", location.pathname + location.search + "#" + id);
    $("close").focus();
  }

  // ---- election night ------------------------------------------------------------
  function liveModeFromURL(electionDate) {
    const q = new URLSearchParams(location.search).get("live");
    if (q === "0") return null;
    if (q === "2024") return "test";
    if (q === "1") return "on";
    const start = new Date(electionDate + "T22:00:00Z").getTime();   // first polls close 23:00 UTC
    const now = Date.now();
    return now >= start && now < start + 10 * 86400000 ? "on" : null;
  }

  // A page left open before results start switches itself to live at 23:00 Berlin on
  // election night, no reload needed. Checked once a minute so a sleeping phone catches up.
  function scheduleLiveStart(electionDate) {
    if (state.liveMode || new URLSearchParams(location.search).get("live") === "0") return;
    const timer = setInterval(() => {
      if (state.liveMode) return clearInterval(timer);
      if (liveModeFromURL(electionDate)) {
        clearInterval(timer);
        startLive(electionDate).then(() => { renderBoard(); renderMap(); renderList(); })
          .catch((e) => { state.liveError = e.message; renderLiveBar(); });
      }
    }, 60000);
  }

  function renderLiveBar() {
    const el = $("livebar");
    if (!state.liveMode) { el.hidden = true; return; }
    el.hidden = false;
    const t = state.liveChecked ? state.liveChecked.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "…";
    el.innerHTML = `<span class="dot"></span><span>Live results from Wikipedia · checked ${t}${state.liveError ? " · last check failed, retrying" : ""}</span>`
      + (state.liveMode === "test" ? `<span class="test">Test: showing 2024 results</span>` : "")
      + `<button id="refresh">Refresh now</button>`;
    $("refresh").addEventListener("click", () => state.poller && state.poller.now());
  }

  // Test only (?live=2024&partial=1): turn final 2024 results into a mid-count night. About a
  // third of races stay called; the rest show 20-90% of their votes with no call, and each
  // "Refresh now" calls a few more, so the narrator can be tested.
  function partialCount(results) {
    const out = {};
    for (const [rid, r] of Object.entries(results)) {
      let h = 0;
      for (const ch of rid) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
      if (h % 3 === 0 || (h % 11) < (state.liveSteps || 0) - 1) { out[rid] = r; continue; }   // each refresh calls a few more
      const f = 0.2 + (h % 71) / 100;
      out[rid] = { ...r, called: false, winner_party: null, total: Math.round(r.total * f),
                   candidates: r.candidates.map((c) => ({ ...c, winner: false, votes: Math.round(c.votes * f) })) };
    }
    return out;
  }

  async function startLive(electionDate) {
    state.liveMode = liveModeFromURL(electionDate);
    if (!state.liveMode) return;
    const table = await getJSON("data/live.json");
    if (state.ballot && state.ballot.live) Object.assign(table.races, state.ballot.live);   // Cabinet races on My ballot
    if (state.liveMode === "test") {
      for (const v of Object.values(table.races)) if (v.page) v.page = v.page.replace(/^2026 /, "2024 ");
    }
    state.liveTable = table;
    state.live = {};
    renderLiveBar();
    state.poller = Live.poller(table, ({ results, checked, error, partial }) => {
      if (!partial) state.liveSteps = (state.liveSteps || 0) + 1;
      state.live = state.liveMode === "test" && new URLSearchParams(location.search).get("partial") ? partialCount(results) : results;
      state.liveChecked = checked; state.liveError = error || null;
      renderLiveBar(); renderBoard(); renderMap(); renderList();
      if (state.view === "ballot") renderBallot();
      narrate();
      if (state.selected && document.body.classList.contains("sheet-open")) {
        if (state.view === "ballot") openBallot(state.selected); else openRace(state.selected);
      }
    }, { intervalMs: 120000 });   // all three tabs every 2 minutes, so calls anywhere show up and every scoreboard stays current
    state.poller.start();
  }

  // ---- punch to refresh ------------------------------------------------------
  // Re-fetches the forecast (and, on election night, checks Wikipedia right away) without
  // reloading the page, so the tab, zoom and any open race stay put. The face spins
  // 3 times a second until the new data is in, at least one second, and stops square.
  function showUpdated() {
    const t = new Date(state.forecast.generated_utc);
    $("updated").textContent = `Updated ${t.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;
  }
  async function refreshData() {
    const [f, rs, pollsters, ballot] = await Promise.all([
      getJSON("data/forecast.json"), getJSON("data/races.json"), getJSON("data/pollsters.json"),
      getJSON("data/my_ballot.json").catch(() => state.ballot)]);
    state.ballot = ballot;
    state.forecast = f;
    state.allRaces = rs.races;
    pollsters.pollsters.forEach((p) => (state.pollsters[p.id] = p));
    state.pollsterMeta = pollsters;
    if (state.poller) await state.poller.now();
    showUpdated();
    renderBoard(); renderMap(); renderList();
    if (state.view === "pollsters") renderPollsters();
    else if (state.view === "ballot") {
      renderBallot();
      if (state.selected && document.body.classList.contains("sheet-open")) openBallot(state.selected);
    }
    else if (state.selected && document.body.classList.contains("sheet-open")) openRace(state.selected);
  }
  // ---- the face: mascot that carries information --------------------------------
  // Looks toward whoever gained since your last visit (or the favorite), tells you what
  // changed, narrates election night, and refreshes the data when punched.
  const QUIPS = [
    "Ow!", "Not the face!", "I'm just the messenger!", "Margin of error, pal.",
    "That was outside the margin of error!", "I'm {p}% sure that hurt.", "Correlated error!",
    "Likely voter screen: you.", "Recency-weighted ouch.", "My pollster grade just dropped.",
    "Undecided on whether that hurt.", "Regression to the mean, please.", "Statistically significant ouch.",
    "It's a toss-up, like my face.", "Bayes would never.", "Weighting that punch at 0.3×.",
    "Ask me again in 6 hours.", "Herding? I'm being punched!",
  ];
  const CALL_QUIPS = ["I'm shocked. I'm not shocked.", "Called it. Well, Wikipedia did.", "The model nods knowingly.",
    "Write that down.", "Somewhere a pollster exhales.", "Another one."];
  const MOVES = ["spin", "jelly", "bounce", "flip", "knock"];
  const CH_NAME = { senate: "Senate", house: "House", governor: "Governors" };
  const pick = (a) => a[Math.floor(Math.random() * a.length)];
  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: no memory */ } },
  };

  const Face = {
    el: null, body: null, bubble: null, timer: null, lockUntil: 0,
    init() {
      this.el = $("face"); this.body = this.el.querySelector(".face-body"); this.bubble = this.el.querySelector(".bubble");
    },
    // priority messages (news) hold the bubble; punch quips don't talk over them
    say(text, ms = 1800, important = false) {
      if (!this.el) return;
      if (!important && Date.now() < this.lockUntil) return;
      if (important) this.lockUntil = Date.now() + ms;
      this.bubble.textContent = text;
      this.bubble.classList.remove("show"); void this.bubble.offsetWidth; this.bubble.classList.add("show");
      clearTimeout(this.timer);
      this.timer = setTimeout(() => this.bubble.classList.remove("show"), ms);
    },
    move(m) {
      this.body.className = "face-body"; void this.body.offsetWidth; this.body.classList.add("m-" + m);
    },
    look(side) { if (this.el) this.el.dataset.look = side; },          // "d" = left (blue), "r" = right (red)
    mood(m) { if (this.el) this.el.dataset.mood = m; },
  };

  // what the viewer saw last time, per tab: control odds and every race's odds
  const SNAP_KEY = "ml-last-visit";
  let prevSnap = null;
  function snapshot() {
    const f = state.forecast, ch = {};
    for (const c of ["senate", "house", "governor"]) if (f[c]) ch[c] = f[c].p_dem_control;
    const races = {};
    state.allRaces.forEach((r) => (races[r.race_id] = r.p_a));
    return { gen: f.generated_utc, seen: Date.now(), ch, races };
  }
  function sinceWhen(ms) {
    const d = new Date(ms), now = new Date();
    const days = Math.round((now - d) / 86400000);
    if (days < 1 && d.getDate() === now.getDate()) return "earlier today";
    if (days <= 1) return "yesterday";
    if (days < 7) return d.toLocaleDateString([], { weekday: "long" }).replace(/^/, "");
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }
  // compare this tab with the last visit; returns {text, side} or null
  function changeNote(ch) {
    const f = state.forecast, s = f[ch];
    if (!s) return null;
    const pD = s.p_dem_control, lead = pD >= 0.5 ? "Democrats" : "Republicans", pLead = Math.max(pD, 1 - pD);
    if (!prevSnap) return { text: `Hi! I'm ${fmtPct(pLead)} sure ${lead} win the ${CH_NAME[ch]}${ch === "governor" ? " majority" : ""}. Punch me to refresh.`, side: pD >= 0.5 ? "d" : "r" };
    if (prevSnap.gen === f.generated_utc)
      return { text: `Same numbers as your last visit. New polls arrive every 6 hours.`, side: null };
    const before = prevSnap.ch[ch];
    const when = sinceWhen(prevSnap.seen);
    let mover = null;
    state.allRaces.filter((r) => r.chamber === ch).forEach((r) => {
      const was = prevSnap.races[r.race_id];
      if (was == null) return;
      const d = r.p_a - was;
      if (!mover || Math.abs(d) > Math.abs(mover.d)) mover = { r, d };
    });
    const moverTxt = mover && Math.abs(mover.d) >= 0.03
      ? ` Biggest mover: ${raceShort(mover.r)}, ${mover.d > 0 === (mover.r.side_a_party === "DEM") ? "toward D" : "toward R"} ${Math.round(Math.abs(mover.d) * 100)} pts.` : "";
    if (before == null || Math.abs(pD - before) < 0.01)
      return { text: `${CH_NAME[ch]}: no real change since ${when}.${moverTxt || " Go to bed."}`, side: null };
    return { text: `${CH_NAME[ch]}: Democrats ${fmtPct(before)} → ${fmtPct(pD)} since ${when}.${moverTxt}`, side: pD > before ? "d" : "r" };
  }
  const raceShort = (r) => r.chamber === "house" ? `${r.state}-${r.district}` : `${NAMES[r.state]}${r.chamber === "governor" ? " governor" : ""}`;

  // which way to look and how to feel, for the tab on screen
  function faceForTab(pD, pR, news) {
    const side = news && news.side ? news.side : pD >= pR ? "d" : "r";
    Face.look(side);
    const top = Math.max(pD, pR);
    Face.mood(top >= 0.85 ? "smug" : top < 0.62 ? "nervous" : "calm");
  }

  function greet() {
    prevSnap = store.get(SNAP_KEY);
    state.newsSide = {};
    for (const c of ["senate", "house", "governor"]) { const x = changeNote(c); if (x && x.side && prevSnap) state.newsSide[c] = x.side; }
    const n = changeNote(state.chamber);
    if (n) { setTimeout(() => Face.say(n.text, 6500, true), 700); }
    const s = state.forecast[state.chamber];
    if (s) faceForTab(s.p_dem_control, s.p_rep_control, n);
    store.set(SNAP_KEY, snapshot());
  }
  function onTab(ch) {
    if (state.live) return;               // on election night the narrator talks about calls instead
    const n = changeNote(ch);
    if (n && prevSnap) Face.say(n.text, 5500, true);
  }

  // election night: announce new calls, sweat when it's close, celebrate control
  // A race is announced only if we saw it uncalled first, so opening the page at 2 a.m.
  // (or switching tabs) doesn't read out every call made so far.
  const narr = { known: {}, controlSaid: {} };
  function narrate() {
    const res = state.live || {}, fresh = [];
    for (const [k, v] of Object.entries(res)) {
      if (k in narr.known && !narr.known[k] && v.called) fresh.push(k);
      narr.known[k] = !!v.called;
    }
    const here = fresh.map((k) => state.allRaces.find((r) => r.race_id === k)).filter((r) => r && r.chamber === state.chamber);
    if (here.length === 1) {
      const r = here[0], lr = res[r.race_id], w = lr.candidates.find((c) => c.winner) || lr.candidates[0];
      Face.say(`Called: ${raceShort(r)} for ${w.name} (${letter(w.party)}). ${pick(CALL_QUIPS)}`, 6000, true);
      Face.move(w.party === "DEM" || w.party === "REP" ? "bounce" : "jelly");
    } else if (here.length > 1) {
      Face.say(`${here.length} new calls: ${here.slice(0, 5).map(raceShort).join(", ")}${here.length > 5 ? "…" : ""}. ${pick(CALL_QUIPS)}`, 6500, true);
      Face.move("spin");
    }
  }
  // called from renderBoard with the numbers on screen
  function faceLive(ch, h, need, cd, cr, notUp) {
    const lockedD = notUp.dem + cd, lockedR = notUp.rep + cr;
    const key = ch + (lockedD >= need ? "D" : lockedR >= need ? "R" : "");
    if (key.length > ch.length && !narr.controlSaid[key]) {
      narr.controlSaid[key] = true;
      const who = lockedD >= need ? "Democrats" : "Republicans";
      const what = ch === "governor" ? "a majority of governorships" : `the ${CH_NAME[ch]}`;
      Face.say(`${who} have won ${what}, per Wikipedia's calls. The model would like a word.`, 9000, true);
      Face.move("spin");
      Face.look(lockedD >= need ? "d" : "r");
      Face.mood("smug");
      return;
    }
    if (h) {
      const close = Math.abs(h.dem - need) <= 2 || Math.abs(h.rep - need) <= 2;
      if (close) Face.mood("sweat");
      Face.look(h.dem >= h.rep ? "d" : "r");
    }
  }

  function setupPunch() {
    Face.init();
    const face = Face.el;
    let busy = false, lastMove = "", lastQuip = -1;
    const quip = () => {
      let i;
      do { i = Math.floor(Math.random() * QUIPS.length); } while (i === lastQuip);
      lastQuip = i;
      const f = state.forecast, s = f && f[state.chamber];
      const p = s ? Math.round(100 * Math.max(s.p_dem_control, s.p_rep_control)) : 72;
      return QUIPS[i].replace("{p}", Math.min(p, 99));
    };
    face.addEventListener("click", async () => {
      let m;
      do { m = pick(MOVES); } while (m === lastMove);
      lastMove = m;
      Face.move(m);
      Face.say(quip());
      if (busy) return;
      busy = true;
      face.setAttribute("aria-busy", "true");
      const was = $("updated").textContent;
      $("updated").textContent = "Refreshing…";
      try { await refreshData(); }
      catch (e) { $("updated").textContent = "Couldn't refresh. Punch again to retry."; }
      if ($("updated").textContent === "Refreshing…") $("updated").textContent = was;
      face.removeAttribute("aria-busy");
      busy = false;
    });
  }

  // ---- pollsters -----------------------------------------------------------
  const WINDOW_SHORT = { same_type: "Last midterm", last_two: "Last 2 elections", all_time: "All time" };
  function polls2026() {
    const n = {};
    state.allRaces.forEach((r) => (r.polls || []).forEach((p) => (n[p.pollster_id] = (n[p.pollster_id] || 0) + 1)));
    return n;
  }
  const leanText = (b) => (b == null ? "–" : Math.abs(b) < 0.5 ? "None" : (b > 0 ? "D+" : "R+") + Math.abs(b).toFixed(1));
  const beatText = (x) => (x == null ? "–" : Math.abs(x) < 0.05 ? "0.0" : (x < 0 ? "+" : "−") + Math.abs(x).toFixed(1));
  const beatCls = (x) => (x == null || Math.abs(x) < 0.5 ? "" : x < 0 ? "good" : "bad");
  const leanCls = (b) => (b == null || Math.abs(b) < 0.5 ? "" : b > 0 ? "d" : "r");
  let gradeMap = null;
  const sbGrade = (id) => {
    if (!gradeMap) {
      gradeMap = {};
      state.allRaces.forEach((r) => (r.polls || []).forEach((x) => { if (x.sb_grade) gradeMap[x.pollster_id] = x.sb_grade; }));
    }
    return gradeMap[id] || null;
  };

  function renderPollsters() {
    const meta = state.pollsterMeta, pv = state.pv;
    if (!meta) return;
    const min = (meta.settings && meta.settings.min_n_display) || 5;
    const yrs = meta.windows.all_time.label.match(/\((.*)\)/);
    $("pv-intro").textContent = `Each pollster's final poll in ${meta.scored_races.toLocaleString()} past races `
      + `(${yrs ? yrs[1] : "all years"}), checked against the actual result. `
      + `"vs others" is the key number: how many points closer to the result it was than other polls of the same race (+ is better). `
      + `"Called" is how often it had the right candidate ahead, which flatters pollsters of safe races. `
      + `"Miss" is how many points it was off on the gap between the top two. "Lean" is which party its misses tended to favor.`;
    $("pv-window").innerHTML = Object.keys(WINDOW_SHORT).map((k) =>
      `<button type="button" data-w="${k}" aria-pressed="${pv.window === k}" title="${esc(meta.windows[k].label)}">${WINDOW_SHORT[k]}<small>${esc((meta.windows[k].label.match(/\((.*)\)/) || ["", ""])[1])}</small></button>`).join("");
    $("pv-window").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { pv.window = b.dataset.w; renderPollsters(); }));
    const n26 = polls2026();
    const q = pv.q.trim().toLowerCase();
    let rows = meta.pollsters.map((p) => ({ p, w: p.windows[pv.window] })).filter(({ p, w }) =>
      w && w.n >= (q ? 1 : min) && (!q || p.name.toLowerCase().includes(q)) && (!pv.active || n26[p.id]));
    const by = {
      weight: (a, b) => (b.p.model ? b.p.model.weight : 1) - (a.p.model ? a.p.model.weight : 1) || b.w.n - a.w.n,
      beat: (a, b) => (a.w.excess_error ?? 99) - (b.w.excess_error ?? 99) || b.w.n - a.w.n,
      called: (a, b) => b.w.win_call_pct - a.w.win_call_pct || b.w.n - a.w.n,
      miss: (a, b) => a.w.mean_abs_error - b.w.mean_abs_error || b.w.n - a.w.n,
      n: (a, b) => b.w.n - a.w.n,
      name: (a, b) => a.p.name.localeCompare(b.p.name),
    }[pv.sort];
    rows.sort(by);
    const total = rows.length;
    if (!pv.all) rows = rows.slice(0, 60);
    $("pv-list").innerHTML = rows.map(({ p, w }) => {
      const g = sbGrade(p.id);
      const sub = `${w.n} race${w.n === 1 ? "" : "s"}${n26[p.id] ? ` · ${n26[p.id]} poll${n26[p.id] === 1 ? "" : "s"} in 2026` : ""}`;
      return `<li><button class="pv-row" data-pollster="${esc(p.id)}">
        <span class="names"><span class="lead">${esc(p.name)}${g ? ` <span class="sbg">(${esc(g)})</span>` : ""}</span><span class="trail">${sub}</span></span>
        <span class="pv-num ${beatCls(w.excess_error)}">${beatText(w.excess_error)}</span>
        <span class="pv-num">${w.win_call_pct != null ? Math.round(w.win_call_pct) + "%" : "–"}</span>
        <span class="pv-num">${w.mean_abs_error != null ? w.mean_abs_error.toFixed(1) : "–"}</span>
        <span class="pv-num ${leanCls(w.bias)}">${leanText(w.bias)}</span>
      </button></li>`;
    }).join("") || `<li class="foot">No pollsters match.</li>`;
    if (!pv.all && total > rows.length)
      $("pv-list").innerHTML += `<li><button class="more" id="pv-more">Show all ${total}</button></li>`;
    const more = $("pv-more");
    if (more) more.addEventListener("click", () => { pv.all = true; renderPollsters(); });
    $("pv-list").querySelectorAll("button[data-pollster]").forEach((b) => b.addEventListener("click", () => openPollster(b.dataset.pollster)));
    $("pv-foot").textContent = `${total} pollster${total === 1 ? "" : "s"} shown. Pollsters with fewer than ${min} graded races in this period are hidden; search to find them. `
      + `"Best record" ranks by how much each pollster's polls count in our averages: how much closer to the result it has been than other polls of the same races, `
      + `trusted more the more races it has. Letter grades in brackets are Silver Bulletin's (January 2026), for reference.`;
  }

  function raceName(id) {
    const [cyc, type, st, d] = id.split("-");
    const n = NAMES[st] || st;
    if (type === "SEN") return `${cyc} ${n} Senate`;
    if (type === "GOV") return `${cyc} ${n} governor`;
    if (type === "PRES") return st === "US" ? `${cyc} President (national)` : `${cyc} ${n} President`;
    if (type === "HOUSE") return `${cyc} ${st}-${d}`;
    return `${cyc} ${id.split("-").slice(1).join(" ")}`;
  }

  async function openPollster(id) {
    const p = state.pollsters[id];
    if (!p) return;
    const meta = state.pollsterMeta, n26 = polls2026()[id] || 0, g = sbGrade(id);
    $("sheet-title").textContent = p.name;
    const row = (k) => {
      const w = p.windows[k];
      if (!w || !w.n) return `<tr><td>${WINDOW_SHORT[k]}<span class="pq">${esc(meta.windows[k].label)}</span></td><td class="num" colspan="5">No graded races</td></tr>`;
      return `<tr><td>${WINDOW_SHORT[k]}<span class="pq">${esc(meta.windows[k].label)}</span></td>
        <td class="num">${w.n}</td><td class="num ${beatCls(w.excess_error)}">${beatText(w.excess_error)}</td><td class="num">${Math.round(w.win_call_pct)}%</td>
        <td class="num">${w.mean_abs_error.toFixed(1)}</td><td class="num ${leanCls(w.bias)}">${leanText(w.bias)}</td></tr>`;
    };
    const m = p.model || {};
    const wt = m.weight != null ? m.weight : 1;
    const ex = m.shrunk_excess;
    $("sheet-body").innerHTML = `
      <dl class="facts">
        ${g ? `<dt>Silver Bulletin</dt><dd>${esc(g)} (their grade, January 2026; not used in our weights)</dd>` : ""}
        <dt>In our averages</dt><dd>Each poll counts ${wt.toFixed(2)}× as much as a pollster with an average record${ex != null && Math.abs(ex) >= 0.05 ? `. Over its graded races it has been ${Math.abs(ex).toFixed(1)} pts ${ex < 0 ? "closer to" : "further from"} the result than other polls of the same race` : ""}.</dd>
        ${m.shrunk_bias != null && Math.abs(m.shrunk_bias) >= 0.5 ? `<dt>Lean we remove</dt><dd>${leanText(m.shrunk_bias)} taken out of each new poll</dd>` : ""}
        <dt>2026</dt><dd>${n26 ? `${n26} poll${n26 === 1 ? "" : "s"} in this year's averages` : "No polls in this year's averages"}</dd>
      </dl>
      <table class="polls"><thead><tr><th>Period</th><th class="num">Races</th><th class="num">vs others</th><th class="num">Called</th><th class="num">Avg miss</th><th class="num">Lean</th></tr></thead>
        <tbody>${["same_type", "last_two", "all_time"].map(row).join("")}</tbody></table>
      <h4 class="pv-sub">Graded races</h4>
      <div id="pv-hist"><p class="note">Loading…</p></div>`;
    document.body.classList.add("sheet-open");
    history.replaceState(null, "", location.pathname + location.search + "#pollster-" + id);
    $("close").focus();
    try {
      if (!state.pollsterHistory) state.pollsterHistory = await getJSON("data/pollster_history.json");
      const hs = (state.pollsterHistory[id] || []).slice().sort((a, b) => b.poll_date.localeCompare(a.poll_date));
      $("pv-hist").innerHTML = hs.length ? `<table class="polls"><thead><tr><th>Race</th><th class="num">Poll</th><th class="num">Result</th><th class="num">Off by</th></tr></thead><tbody>`
        + hs.slice(0, 40).map((h) => `<tr><td>${esc(raceName(h.race_id))}${h.called === 0 ? ' <span class="miss">wrong winner</span>' : ""}<span class="pq">${fmtDate(h.poll_date)}</span></td>
          <td class="num">${fmtMargin(h.margin_poll)}</td><td class="num">${fmtMargin(h.margin_actual)}</td><td class="num">${h.error.toFixed(1)}</td></tr>`).join("")
        + `</tbody></table>${hs.length > 40 ? `<p class="note">Showing the latest 40 of ${hs.length}.</p>` : ""}<p class="note">Margins are Democrat minus Republican (or the two leading candidates).</p>`
        : `<p class="note">No graded races.</p>`;
    } catch (e) { $("pv-hist").innerHTML = `<p class="note">Couldn't load the race history.</p>`; }
  }

  // ---- boot ----------------------------------------------------------------
  async function boot() {
    setupPunch();
    $("close").addEventListener("click", closeRace);
    $("sheet-bg").addEventListener("click", closeRace);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeRace(); });
    const setTab = (which) => {
      $("tab-senate").setAttribute("aria-selected", String(which === "senate"));
      $("tab-house").setAttribute("aria-selected", String(which === "house"));
      $("tab-governor").setAttribute("aria-selected", String(which === "governor"));
      $("tab-pollsters").setAttribute("aria-selected", String(which === "pollsters"));
      $("tab-ballot").setAttribute("aria-selected", String(which === "ballot"));
    };
    const show = (which) => {
      setTab(which); closeRace();
      const pv = which === "pollsters", mb = which === "ballot";
      state.view = pv ? "pollsters" : mb ? "ballot" : "races";
      $("race-view").hidden = pv || mb;
      $("pollster-view").hidden = !pv;
      $("ballot-view").hidden = !mb;
      if (pv) { renderPollsters(); return; }
      if (mb) { renderBallot(); return; }
      const changed = state.chamber !== which;
      state.chamber = which; state.houseZoom = null;
      renderBoard(); renderMap(); renderList();
      if (changed && state.poller) state.poller.now();   // bring the new tab's results up to date now
      if (changed) onTab(which);
    };
    $("tab-pollsters").addEventListener("click", () => show("pollsters"));
    $("pv-search").addEventListener("input", (e) => { state.pv.q = e.target.value; renderPollsters(); });
    $("pv-sort").addEventListener("change", (e) => { state.pv.sort = e.target.value; renderPollsters(); });
    $("pv-active").addEventListener("change", (e) => { state.pv.active = e.target.checked; renderPollsters(); });
    $("tab-house").addEventListener("click", () => show("house"));
    $("tab-senate").addEventListener("click", () => show("senate"));
    $("tab-governor").addEventListener("click", () => show("governor"));
    $("tab-ballot").addEventListener("click", () => show("ballot"));
    try {
      const [f, races, pollsters, topo, pagesTable, ballot] = await Promise.all([
        getJSON("data/forecast.json"), getJSON("data/races.json"), getJSON("data/pollsters.json"),
        getJSON("vendor/states-albers-10m.json").catch(() => null),   // no map is better than no page
        getJSON("data/live.json").catch(() => null),                   // Wikipedia page for each race
        getJSON("data/my_ballot.json").catch(() => null),              // My ballot tab
      ]);
      state.pages = pagesTable ? pagesTable.races : {};
      state.ballot = ballot;
      state.forecast = f;
      state.allRaces = races.races;
      pollsters.pollsters.forEach((p) => (state.pollsters[p.id] = p));
      state.pollsterMeta = pollsters;
      state.topo = topo;

      showUpdated();
      renderBoard(); renderMap(); renderList();
      if (!liveModeFromURL(f.election_date)) greet();
      startLive(f.election_date).catch((e) => { state.liveError = e.message; renderLiveBar(); });
      scheduleLiveStart(f.election_date);
      if (location.hash.length > 1) {
        const id = decodeURIComponent(location.hash.slice(1));
        if (id.startsWith("pollster-")) { show("pollsters"); openPollster(id.slice(9)); return; }
        if (id === "ballot") { show("ballot"); return; }
        if (ballotItems().some((x) => x.id === id && x.kind !== "model")) { show("ballot"); openBallot(id); return; }
        if (id.includes("-HOUSE-")) show("house");
        else if (id.includes("-GOV-")) show("governor");
        openRace(id);
      }
    } catch (e) {
      $("map").innerHTML = `<p class="note">Couldn't load the forecast (${esc(e.message)}). Reload the page to try again.</p>`;
    }
  }
  boot();
})();
