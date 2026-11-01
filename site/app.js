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
  const letter = (party) => ({ DEM: "D", REP: "R", IND: "I", LIB: "L", GRN: "G" }[party] || party[0]);

  const state = { forecast: null, races: [], pollsters: {}, topo: null, selected: null, chamber: "senate" };

  function category(r) {
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
  function renderBoard() {
    const f = state.forecast, s = f.senate;
    $("pd").textContent = fmtPct(s.p_dem_control);
    $("pr").textContent = fmtPct(s.p_rep_control);
    $("wd").textContent = "Democrats win control";
    $("wr").textContent = "Republicans win control";
    $("mid").innerHTML = `<strong>${s.dem_needs}</strong>seats for a<br>Democratic majority`;

    const counts = Object.fromEntries(RATINGS.map(([k]) => [k, 0]));
    state.races.forEach((r) => counts[category(r)]++);
    const segs = [["safe-d", s.not_up.dem, "Not up (D)"],
      ...RATINGS.filter(([k]) => k !== "ind").map(([k, l]) => [k, counts[k], l]),
      ["ind", counts.ind, "Independent"], ["safe-r", s.not_up.rep, "Not up (R)"]];
    const bar = $("bar");
    bar.innerHTML = "";
    segs.forEach(([k, n, label], i) => {
      if (!n) return;
      const sp = document.createElement("span");
      sp.style.width = n + "%";
      sp.style.background = `var(--${k})`;
      if (i === 0 || i === segs.length - 1) sp.style.opacity = ".55";
      sp.title = `${label}: ${n}`;
      bar.appendChild(sp);
    });
    const mark = document.createElement("i");
    mark.className = "mark";
    mark.style.left = "calc(50% - 1px)";
    bar.appendChild(mark);
    const dFav = s.not_up.dem + counts["safe-d"] + counts["likely-d"] + counts["lean-d"];
    const rFav = s.not_up.rep + counts["safe-r"] + counts["likely-r"] + counts["lean-r"];
    $("bl").textContent = `D ${dFav} incl. lean`;
    $("bm").textContent = `${counts.toss} toss-up${counts.toss === 1 ? "" : "s"}`;
    $("br").textContent = `R ${rFav} incl. lean`;
    bar.setAttribute("aria-label", `Democrats ${dFav} seats including leaning races, Republicans ${rFav}, ${counts.toss} toss-ups`);
    let extra = `Most likely Democratic seats: ${s.dem_seats_median} (80% range ${s.dem_seats_p10}–${s.dem_seats_p90}).`;
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
    const byState = {};
    state.races.forEach((r) => (byState[r.state] = byState[r.state] || []).push(r));
    const geo = topojson.feature(state.topo, state.topo.objects.states);
    const NS = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "0 0 1000 610");
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
      if (races && pt && area > 700 && !CALLOUTS.includes(st)) labels.push([st, pt, cat]);
    }
    for (const [st, pt, cat] of labels) {
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", pt[0]); t.setAttribute("y", pt[1] + 5); t.setAttribute("text-anchor", "middle");
      if (!DARK_TEXT.has(cat)) t.classList.add("light");
      t.textContent = st;
      svg.appendChild(t);
    }
    CALLOUTS.forEach((st, i) => {
      const races = byState[st];
      const y = 200 + i * 34;
      const g = document.createElementNS(NS, "g");
      const rect = document.createElementNS(NS, "path");
      rect.setAttribute("d", `M935 ${y}h46v26h-46z`);
      const cat = races ? category(races[0]) : "none";
      rect.setAttribute("fill", `var(--${cat})`);
      if (!races) rect.classList.add("none");
      else {
        rect.setAttribute("tabindex", "0");
        rect.setAttribute("role", "button");
        rect.setAttribute("aria-label", `${NAMES[st]}: ${RATINGS.find(([k]) => k === cat)[1]}`);
        rect.addEventListener("click", () => openRace(races[0].race_id));
      }
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", 958); t.setAttribute("y", y + 18); t.setAttribute("text-anchor", "middle");
      if (!DARK_TEXT.has(cat)) t.classList.add("light");
      t.textContent = st;
      g.append(rect, t);
      svg.appendChild(g);
    });
    $("map").innerHTML = "";
    $("map").appendChild(svg);
    $("key").innerHTML = RATINGS.map(([k, l]) => `<span><i style="background:var(--${k})"></i>${l}</span>`).join("")
      + `<span><i style="background:var(--none)"></i>No race</span>`;
  }

  // ---- list ----------------------------------------------------------------
  function renderList() {
    $("races").innerHTML = state.races.map((r) => {
      const cat = category(r);
      const fav = r.p_a >= 0.5;
      const pFav = Math.max(r.p_a, 1 - r.p_a);
      const favName = fav ? r.side_a : r.side_b;
      return `<li><button data-race="${esc(r.race_id)}">
        <span class="chip" style="background:var(--${cat});color:${DARK_TEXT.has(cat) ? "#0f1526" : "#fff"}">${r.state}</span>
        <span class="names"><span class="a">${esc(r.side_a)} (${letter(r.side_a_party)})</span><span class="b">${esc(r.side_b)} (${letter(r.side_b_party)})</span></span>
        <span class="odds">${fmtPct(pFav)}<small>${esc(favName.split(" ").slice(-1)[0])} · ${fmtMargin(r.margin, letter(r.side_a_party), letter(r.side_b_party))}</small></span>
      </button></li>`;
    }).join("");
    $("races").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => openRace(b.dataset.race)));
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
    const r = state.races.find((x) => x.race_id === id);
    if (!r) return;
    state.selected = id;
    document.querySelectorAll(".map path.sel").forEach((p) => p.classList.remove("sel"));
    document.querySelectorAll(`.map path[data-state="${r.state}"]`).forEach((p) => p.classList.add("sel"));
    const special = r.race_id.endsWith("-S") ? " (special)" : "";
    $("sheet-title").textContent = `${NAMES[r.state]} Senate${special}`;
    const A = letter(r.side_a_party), B = letter(r.side_b_party);
    const pollRows = (r.polls || []).slice(0, 25).map((p) => {
      const pol = state.pollsters[p.pollster_id];
      const name = pol ? pol.name : p.pollster_id;
      const adj = Math.abs(p.bias_correction) >= 0.05 ? `<span class="pq">adjusted ${p.bias_correction > 0 ? "−" : "+"}${Math.abs(p.bias_correction).toFixed(1)} for lean</span>` : "";
      return `<tr><td>${esc(name)}<span class="pq">${esc(pollsterLine(p.pollster_id))}</span></td>
        <td class="num">${p.end.slice(5).replace("-", "/")}</td>
        <td class="num">${fmtMargin(p.margin_raw, A, B)}${adj}</td>
        <td class="num">${(p.weight_share * 100).toFixed(0)}%</td></tr>`;
    }).join("");
    const pa = r.p_a;
    $("sheet-body").innerHTML = `
      <div class="duel">
        <div><div class="n">${esc(r.side_a)} (${A})</div><div class="p" style="color:var(--${A === "D" ? "dem" : A === "R" ? "rep" : "ind"})">${fmtPct(pa)}</div></div>
        <div class="r"><div class="n">${esc(r.side_b)} (${B})</div><div class="p" style="color:var(--${B === "R" ? "rep" : "dem"})">${fmtPct(1 - pa)}</div></div>
      </div>
      <dl class="facts">
        <dt>Forecast margin</dt><dd>${fmtMargin(r.margin, A, B)} (typical miss ±${r.sd.toFixed(1)})</dd>
        ${r.poll_average != null ? `<dt>Polling average</dt><dd>${fmtMargin(r.poll_average, A, B)} from ${r.n_polls} poll${r.n_polls === 1 ? "" : "s"}, last ${r.last_poll}</dd>` : `<dt>Polls</dt><dd>None published. Forecast is from partisan lean only.</dd>`}
        ${r.lean_prior != null ? `<dt>Partisan lean</dt><dd>${fmtMargin(r.lean_prior, "D", "R")} (state's 2024 result moved by the national mood)</dd>` : ""}
        ${r.uncommitted ? `<dt>Note</dt><dd>${esc(r.side_a)} says he will join neither party's caucus.</dd>` : ""}
      </dl>
      ${pollRows ? `<table class="polls"><thead><tr><th>Pollster</th><th class="num">Ended</th><th class="num">Result</th><th class="num">Weight</th></tr></thead><tbody>${pollRows}</tbody></table>
      <p class="note">Weight is each poll's share of the average: newer, larger, likely-voter polls from pollsters with better records count more. Polls from firms that historically lean one way are adjusted by that lean.</p>` : ""}`;
    document.body.classList.add("sheet-open");
    history.replaceState(null, "", "#" + id);
    $("close").focus();
  }
  function closeRace() {
    document.body.classList.remove("sheet-open");
    document.querySelectorAll(".map path.sel").forEach((p) => p.classList.remove("sel"));
    history.replaceState(null, "", location.pathname);
  }

  // ---- boot ----------------------------------------------------------------
  async function boot() {
    $("close").addEventListener("click", closeRace);
    $("sheet-bg").addEventListener("click", closeRace);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeRace(); });
    $("tab-house").addEventListener("click", () => {
      $("map").innerHTML = `<p class="note">House forecast and district map are being added before Election Day.</p>`;
    });
    $("tab-senate").addEventListener("click", () => { renderMap(); });
    try {
      const [f, races, pollsters, topo] = await Promise.all([
        getJSON("data/forecast.json"), getJSON("data/races.json"), getJSON("data/pollsters.json"),
        getJSON("https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json"),
      ]);
      state.forecast = f;
      state.races = races.races.filter((r) => r.chamber === "senate");
      pollsters.pollsters.forEach((p) => (state.pollsters[p.id] = p));
      state.topo = topo;
      const t = new Date(f.generated_utc);
      $("updated").textContent = `Updated ${t.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;
      renderBoard(); renderMap(); renderList();
      if (location.hash.length > 1) openRace(decodeURIComponent(location.hash.slice(1)));
    } catch (e) {
      $("map").innerHTML = `<p class="note">Couldn't load the forecast (${esc(e.message)}). Reload the page to try again.</p>`;
    }
  }
  boot();
})();
