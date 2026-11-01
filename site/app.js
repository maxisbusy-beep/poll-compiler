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
                  showAll: false, houseTopo: null, houseGeo: null, houseZoom: null,
                  live: null, liveMode: null, liveTable: null, liveChecked: null, liveError: null };

  const liveRes = (r) => (state.live ? state.live[r.race_id] : null);
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
    const f = state.forecast, house = state.chamber === "house";
    const s = house ? f.house : f.senate;
    const total = house ? 435 : 100;
    const notUp = house ? { dem: 0, rep: 0 } : s.not_up;
    const need = house ? s.need : s.dem_needs;
    let pD = s.p_dem_control, pR = s.p_rep_control, lo = null;
    if (state.live) {
      lo = Live.liveOdds(races(), state.live, {
        nationalSd: f.national_sd || 2.65, notUp, demNeeds: need, repNeeds: house ? need : s.rep_needs,
        uncommitted: house ? [] : (s.uncommitted_races || []) });
      pD = lo.p_dem; pR = lo.p_rep;
    }
    $("pd").textContent = fmtPct(pD);
    $("pr").textContent = fmtPct(pR);
    $("wd").textContent = state.live ? "Democrats, with called races locked in" : "Democrats win control";
    $("wr").textContent = state.live ? "Republicans, with called races locked in" : "Republicans win control";
    $("mid").innerHTML = `<strong>${need}</strong>seats for a<br>Democratic majority`;

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
      if (i === 0 || i === segs.length - 1) sp.style.opacity = ".55";
      sp.title = `${label}: ${n}`;
      bar.appendChild(sp);
    });
    const mark = document.createElement("i");
    mark.className = "mark";
    mark.style.left = `calc(${(100 * (need - 0.5) / total).toFixed(2)}% - 1px)`;
    bar.appendChild(mark);
    const dFav = notUp.dem + counts["safe-d"] + counts["likely-d"] + counts["lean-d"];
    const rFav = notUp.rep + counts["safe-r"] + counts["likely-r"] + counts["lean-r"];
    $("bl").textContent = `D ${dFav} incl. lean`;
    $("bm").textContent = `${counts.toss} toss-up${counts.toss === 1 ? "" : "s"}`;
    $("br").textContent = `R ${rFav} incl. lean`;
    bar.setAttribute("aria-label", `Democrats ${dFav} seats including leaning races, Republicans ${rFav}, ${counts.toss} toss-ups`);
    let extra = `Most likely Democratic seats: ${lo ? lo.median : s.dem_seats_median} (80% range ${lo ? lo.p10 : s.dem_seats_p10}–${lo ? lo.p90 : s.dem_seats_p90}).`;
    if (state.live) {
      const rs = races().map(liveRes).filter(Boolean);
      const cd = rs.filter((x) => x.called && x.winner_party === "DEM").length;
      const cr = rs.filter((x) => x.called && x.winner_party === "REP").length;
      const ci = rs.filter((x) => x.called && x.winner_party !== "DEM" && x.winner_party !== "REP").length;
      const counting = rs.filter((x) => !x.called && x.total > 0).length;
      extra = `Called so far: ${cd} D, ${cr} R${ci ? `, ${ci} other` : ""}. Counting in ${counting} more. ` + extra
        + " Races not yet called use the pre-election forecast, since early counts can lean either way.";
    }
    if (house) extra += ` ${s.races_with_polls} districts have polls; the rest use partisan lean and incumbency.`;
    if (s.p_uncommitted_decides >= 0.005)
      extra += ` ${fmtPct(s.p_uncommitted_decides)} chance an independent who joins neither party holds the balance.`;
    $("extra").textContent = extra;
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
      + `<span><i style="background:var(--none)"></i>No race</span>`
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
    svg.setAttribute("viewBox", vb.map((v) => v.toFixed(1)).join(" "));
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
    if (zoom) {
      const bar = document.createElement("div");
      bar.className = "zoombar";
      bar.innerHTML = `<strong>${NAMES[ST_ABBR[zoom]]}</strong><span>Tap a district for details</span><button id="unzoom">Whole map</button>`;
      $("map").appendChild(bar);
      bar.querySelector("#unzoom").addEventListener("click", () => { state.houseZoom = null; renderHouseMap(); });
    }
    $("map").appendChild(svg);
    $("key").innerHTML = RATINGS.map(([k, l]) => `<span><i style="background:var(--${k})"></i>${l}</span>`).join("")
      + `<span>${zoom ? "" : "Tap a state to zoom in. "}District lines: Census, 2026 maps.</span>`
      + (state.live ? `<span>Bright = called. Faded = not called yet, shown by forecast.</span>` : "");
  }

  const ordinal = (n) => { const t = ["th", "st", "nd", "rd"], v = n % 100; return n + (t[(v - 20) % 10] || t[v] || t[0]); };
  function raceLabel(r) {
    if (r.chamber === "house") {
      const atLarge = state.allRaces.filter((x) => x.chamber === "house" && x.state === r.state).length === 1;
      return `${NAMES[r.state]} ${atLarge ? "at-large" : ordinal(+r.district)} district`;
    }
    return `${NAMES[r.state]} Senate${r.race_id.endsWith("-S") ? " (special)" : ""}`;
  }
  const shortLabel = (r) => r.chamber === "house" ? `${r.state}-${r.district}${r.redrawn_2026 ? "*" : ""}` : r.state;

  // ---- list ----------------------------------------------------------------
  function renderList() {
    const house = state.chamber === "house";
    const list = house ? races().slice().sort((a, b) => Math.abs(a.p_a - 0.5) - Math.abs(b.p_a - 0.5)).slice(0, state.showAll ? 435 : 40) : races();
    $("list-title").textContent = house ? (state.showAll ? "All districts, closest first" : "40 closest districts") : "Races, closest first";
    $("races").innerHTML = list.map((r) => {
      const cat = category(r);
      const fav = r.p_a >= 0.5;
      const pFav = Math.max(r.p_a, 1 - r.p_a);
      const favName = fav ? r.side_a : r.side_b;
      const lr = liveRes(r);
      let right = `${fmtPct(pFav)}<small>${esc(favName.split(" ").slice(-1)[0])} · ${fmtMargin(r.margin, letter(r.side_a_party), letter(r.side_b_party))}</small>`;
      if (lr && lr.total > 0) {
        const [c1, c2] = lr.candidates;
        const m = c2 ? ((c1.pct || 0) - (c2.pct || 0)) : 100;
        const lead = `${esc(c1.name.split(" ").slice(-1)[0])} +${m.toFixed(1)}`;
        const counted = lr.expected ? `~${Math.min(99, Math.round(100 * lr.total / lr.expected))}% in` : `${(lr.total / 1000).toFixed(0)}k votes`;
        const tag = lr.called ? `<span class="won ${lr.winner_party === "DEM" ? "d" : lr.winner_party === "REP" ? "r" : "i"}">Won</span> ` : "";
        right = `${tag}${lead}<small>${lr.called ? "Called" : counted}</small>`;
      }
      return `<li><button data-race="${esc(r.race_id)}">
        <span class="chip" style="background:var(--${cat});color:${DARK_TEXT.has(cat) ? "#0f1526" : "#fff"}">${shortLabel(r)}</span>
        <span class="names"><span class="a">${esc(r.side_a)} (${letter(r.side_a_party)})</span><span class="b">${esc(r.side_b)} (${letter(r.side_b_party)})</span></span>
        <span class="odds">${right}</span>
      </button></li>`;
    }).join("");
    if (house && !state.showAll) $("races").innerHTML += `<li><button class="more" id="show-all">Show all 435 districts</button></li>`;
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
    const pollRows = (r.polls || []).slice(0, 25).map((p) => {
      const pol = state.pollsters[p.pollster_id];
      const name = p.name || (pol ? pol.name : p.pollster_id);
      const grade = p.sb_grade ? ` <span class="sbg" title="Silver Bulletin grade">(${esc(p.sb_grade)}${p.sb_banned ? ", banned" : ""})</span>` : "";
      const adj = Math.abs(p.bias_correction) >= 0.05 ? `<span class="pq">counted as ${fmtMargin(p.margin, A, B)}</span>` : "";
      return `<tr><td>${esc(name)}${grade}<span class="pq">${esc(pollsterLine(p.pollster_id))}</span></td>
        <td class="num">${fmtDate(p.end)}</td>
        <td class="num">${fmtMargin(p.margin_raw, A, B)}${adj}</td>
        <td class="num">${(p.weight_share * 100).toFixed(0)}%</td></tr>`;
    }).join("");
    const pa = r.p_a;
    const lr = liveRes(r);
    let liveBox = "";
    if (lr && lr.total > 0) {
      const share = lr.expected ? Math.min(100, 100 * lr.total / lr.expected) : null;
      liveBox = `<div class="livebox">
        <table>${lr.candidates.slice(0, 4).map((c) => `<tr><td>${esc(c.name)} (${letter(c.party)})${c.winner && lr.called ? ' <span class="won ' + (c.party === "DEM" ? "d" : c.party === "REP" ? "r" : "i") + '">Won</span>' : ""}</td>
          <td class="num">${c.votes.toLocaleString()}</td><td class="num">${c.pct != null ? c.pct.toFixed(1) + "%" : ""}</td></tr>`).join("")}</table>
        ${share != null ? `<div class="meter"><span style="width:${share.toFixed(0)}%"></span></div>` : ""}
        <div class="note">${lr.total.toLocaleString()} votes counted${share != null ? `, about ${share.toFixed(0)}% of the vote we expect (estimate from 2024 turnout)` : ""}.
        ${lr.called ? "Called, per Wikipedia." : "Not called yet."} Wikipedia last edited ${new Date(lr.edited).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}.</div>
      </div>`;
    }
    $("sheet-body").innerHTML = liveBox + `
      <div class="duel">
        <div><div class="n">${esc(r.side_a)} (${A})</div><div class="p" style="color:var(--${A === "D" ? "dem" : A === "R" ? "rep" : "ind"})">${fmtPct(pa)}</div></div>
        <div class="r"><div class="n">${esc(r.side_b)} (${B})</div><div class="p" style="color:var(--${B === "R" ? "rep" : "dem"})">${fmtPct(1 - pa)}</div></div>
      </div>
      <dl class="facts">
        <dt>Forecast margin</dt><dd>${fmtMargin(r.margin, A, B)} (typical miss ±${r.sd.toFixed(1)})</dd>
        ${r.poll_average != null ? `<dt>Polling average</dt><dd>${fmtMargin(r.poll_average, A, B)} from ${r.n_polls} poll${r.n_polls === 1 ? "" : "s"}, latest ${fmtDate(r.last_poll)}</dd>` : `<dt>Polls</dt><dd>None published. Forecast is from partisan lean only.</dd>`}
        ${r.lean_prior != null ? `<dt>Partisan lean</dt><dd>${fmtMargin(r.lean_prior, "D", "R")} ${r.chamber === "house" ? leanNote(r) : "(state's 2024 result moved by the national mood)"}</dd>` : ""}
        ${r.basis === "unopposed" ? `<dt>Note</dt><dd>No major-party opponent on the ballot.</dd>` : ""}
        ${r.redrawn_2026 ? `<dt>New map*</dt><dd>${esc(r.map_note)}</dd>` : ""}
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

  async function startLive(electionDate) {
    state.liveMode = liveModeFromURL(electionDate);
    if (!state.liveMode) return;
    const table = await getJSON("data/live.json");
    if (state.liveMode === "test") {
      for (const v of Object.values(table.races)) if (v.page) v.page = v.page.replace(/^2026 /, "2024 ");
    }
    state.liveTable = table;
    state.live = {};
    renderLiveBar();
    state.poller = Live.poller(table, ({ results, checked, error }) => {
      state.live = results; state.liveChecked = checked; state.liveError = error || null;
      renderLiveBar(); renderBoard(); renderMap(); renderList();
      if (state.selected && document.body.classList.contains("sheet-open")) openRace(state.selected);
    });
    state.poller.start();
  }

  // ---- boot ----------------------------------------------------------------
  async function boot() {
    $("close").addEventListener("click", closeRace);
    $("sheet-bg").addEventListener("click", closeRace);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeRace(); });
    const setTab = (which) => {
      $("tab-senate").setAttribute("aria-selected", String(which === "senate"));
      $("tab-house").setAttribute("aria-selected", String(which === "house"));
    };
    const show = (which) => {
      state.chamber = which; setTab(which); closeRace(); state.houseZoom = null;
      renderBoard(); renderMap(); renderList();
    };
    $("tab-house").addEventListener("click", () => show("house"));
    $("tab-senate").addEventListener("click", () => show("senate"));
    try {
      const [f, races, pollsters, topo] = await Promise.all([
        getJSON("data/forecast.json"), getJSON("data/races.json"), getJSON("data/pollsters.json"),
        getJSON("https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json"),
      ]);
      state.forecast = f;
      state.allRaces = races.races;
      pollsters.pollsters.forEach((p) => (state.pollsters[p.id] = p));
      state.topo = topo;
      const t = new Date(f.generated_utc);
      $("updated").textContent = `Updated ${t.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;
      renderBoard(); renderMap(); renderList();
      startLive(f.election_date).catch((e) => { state.liveError = e.message; renderLiveBar(); });
      if (location.hash.length > 1) {
        const id = decodeURIComponent(location.hash.slice(1));
        if (id.includes("-HOUSE-")) show("house");
        openRace(id);
      }
    } catch (e) {
      $("map").innerHTML = `<p class="note">Couldn't load the forecast (${esc(e.message)}). Reload the page to try again.</p>`;
    }
  }
  boot();
})();
