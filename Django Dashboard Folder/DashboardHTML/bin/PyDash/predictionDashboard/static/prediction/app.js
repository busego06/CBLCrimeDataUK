const data = window.DASHBOARD_DATA;

const state = {
  authority: "all",
  search: "",
  selectedCode: null,
  areas: [],
  authoritySummaries: [],
};

const els = {
  forceName: document.getElementById("forceName"),
  forecastMonth: document.getElementById("forecastMonth"),
  authoritySelect: document.getElementById("authoritySelect"),
  searchInput: document.getElementById("searchInput"),
  downloadButton: document.getElementById("downloadButton"),
  priorityCount: document.getElementById("priorityCount"),
  reserveCount: document.getElementById("reserveCount"),
  routineCount: document.getElementById("routineCount"),
  zoneCount: document.getElementById("zoneCount"),
  shownCount: document.getElementById("shownCount"),
  shownLabel: document.getElementById("shownLabel"),
  allocationMap: document.getElementById("allocationMap"),
  mapTitle: document.getElementById("mapTitle"),
  mapDescription: document.getElementById("mapDescription"),
  panelEyebrow: document.getElementById("panelEyebrow"),
  areaName: document.getElementById("areaName"),
  areaMeta: document.getElementById("areaMeta"),
  areaTier: document.getElementById("areaTier"),
  metricOneLabel: document.getElementById("metricOneLabel"),
  metricTwoLabel: document.getElementById("metricTwoLabel"),
  metricThreeLabel: document.getElementById("metricThreeLabel"),
  metricFourLabel: document.getElementById("metricFourLabel"),
  areaDemand: document.getElementById("areaDemand"),
  areaUplift: document.getElementById("areaUplift"),
  areaHarm: document.getElementById("areaHarm"),
  areaContext: document.getElementById("areaContext"),
  contextTitle: document.getElementById("contextTitle"),
  contextHint: document.getElementById("contextHint"),
  contextProfile: document.getElementById("contextProfile"),
  detailOneLabel: document.getElementById("detailOneLabel"),
  detailTwoLabel: document.getElementById("detailTwoLabel"),
  areaPopulation: document.getElementById("areaPopulation"),
  areaRepeat: document.getElementById("areaRepeat"),
  areaReason: document.getElementById("areaReason"),
  rankingList: document.getElementById("rankingList"),
};

const mapState = {
  map: null,
  layer: null,
  needsFit: true,
};

const tierText = {
  priority: "Priority review",
  reserve: "Reserve watch",
  routine: "Routine coverage",
};

function fmt(value, decimals = 0) {
  return Number(value || 0).toLocaleString("en-GB", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  });
}

function pct(value, decimals = 1) {
  return `${(Number(value || 0) * 100).toLocaleString("en-GB", {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  })}%`;
}

function sum(items, getter) {
  return items.reduce((total, item) => total + Number(getter(item) || 0), 0);
}

function weightedAverage(items, valueGetter, weightGetter) {
  let weightedTotal = 0;
  let totalWeight = 0;

  items.forEach((item) => {
    const value = Number(valueGetter(item));
    const weight = Math.max(0, Number(weightGetter(item) || 0));

    if (Number.isFinite(value) && weight > 0) {
      weightedTotal += value * weight;
      totalWeight += weight;
    }
  });

  return totalWeight ? weightedTotal / totalWeight : 0;
}

function tierColor(tier) {
  if (tier === "priority") return "#c94b43";
  if (tier === "reserve") return "#c98522";
  return "#5b83a8";
}

function tierClass(tier) {
  if (tier === "priority") return "tier-priority";
  if (tier === "reserve") return "tier-reserve";
  return "tier-routine";
}

function tierFromModel(area) {
  const tier = String(area.originalTier || "").toLowerCase();

  if (tier.includes("priority")) return "priority";
  if (tier.includes("reserve")) return "reserve";
  return "routine";
}

function contextPressure(area) {
  const deciles = [
    area.imdDecile,
    area.incomeDecile,
    area.employmentDecile,
    area.educationDecile,
  ].filter((value) => Number(value) > 0);

  if (!deciles.length) return 0;

  const pressure =
    deciles.reduce((total, decile) => total + (11 - Number(decile)) / 10, 0) /
    deciles.length;

  return Math.max(0, Math.min(1, pressure));
}

function pressureLabel(decile) {
  if (!decile) return "No match";
  if (decile <= 2) return "Very high";
  if (decile <= 4) return "High";
  if (decile <= 7) return "Medium";
  return "Lower";
}

function contextRow(label, decile) {
  const cleanDecile = Number(decile || 0);
  const pressure = cleanDecile ? 11 - cleanDecile : 0;
  const width = `${Math.max(8, pressure * 10)}%`;

  return `
    <div class="context-row">
      <div>
        <b>${label}</b>
        <span>${pressureLabel(cleanDecile)} pressure</span>
      </div>
      <div class="context-meter" aria-hidden="true">
        <i style="width: ${width}"></i>
      </div>
      <strong>${cleanDecile ? `${cleanDecile}/10` : "-"}</strong>
    </div>
  `;
}

function baseAreas() {
  return state.areas.filter(
    (area) => state.authority === "all" || area.localAuthority === state.authority
  );
}

function visibleAreas() {
  const query = state.search.trim().toLowerCase();
  const areas = baseAreas();

  if (!query) return areas;

  return areas.filter((area) =>
    `${area.name} ${area.shortName} ${area.code} ${area.localAuthority} ${area.ladCode}`
      .toLowerCase()
      .includes(query)
  );
}

function isNationalOverview() {
  return state.authority === "all" && !state.search.trim();
}

function selectedArea() {
  if (!state.selectedCode) return null;
  return state.areas.find((area) => area.code === state.selectedCode) || null;
}

function selectedAuthoritySummary() {
  if (state.authority === "all") return null;
  return state.authoritySummaries.find((summary) => summary.name === state.authority) || null;
}

function buildAuthoritySummaries(areas) {
  const groups = new Map();

  areas.forEach((area) => {
    const authority = area.localAuthority || "Unknown area";
    if (!groups.has(authority)) groups.set(authority, []);
    groups.get(authority).push(area);
  });

  return Array.from(groups.entries())
    .map(([name, members]) => {
      const demand = sum(members, (area) => area.predictedDemand);
      const population = sum(members, (area) => area.population);
      const priorityCount = members.filter((area) => area.tier === "priority").length;
      const reserveCount = members.filter((area) => area.tier === "reserve").length;
      const routineCount = members.length - priorityCount - reserveCount;
      const weight = (area) => Math.max(1, Number(area.predictedDemand || 1));

      const tier =
        priorityCount > 0
          ? "priority"
          : reserveCount > 0
            ? "reserve"
            : "routine";

      return {
        name,
        members,
        demand,
        population,
        priorityCount,
        reserveCount,
        routineCount,
        tier,
        latitude: weightedAverage(members, (area) => area.latitude, weight),
        longitude: weightedAverage(members, (area) => area.longitude, weight),
        imdDecile: weightedAverage(members, (area) => area.imdDecile, weight),
        incomeDecile: weightedAverage(members, (area) => area.incomeDecile, weight),
        employmentDecile: weightedAverage(members, (area) => area.employmentDecile, weight),
        educationDecile: weightedAverage(members, (area) => area.educationDecile, weight),
      };
    })
    .sort((a, b) => b.demand - a.demand);
}

function prepareData() {
  state.areas = data.areas
    .map((area) => ({
      ...area,
      tier: tierFromModel(area),
    }))
    .sort((a, b) => b.predictedDemand - a.predictedDemand);

  state.authoritySummaries = buildAuthoritySummaries(state.areas);
}

function updateSummary() {
  const areas = visibleAreas();
  const priority = areas.filter((area) => area.tier === "priority").length;
  const reserve = areas.filter((area) => area.tier === "reserve").length;
  const routine = areas.filter((area) => area.tier === "routine").length;
  const authorities = new Set(areas.map((area) => area.localAuthority).filter(Boolean));

  els.priorityCount.textContent = fmt(priority);
  els.reserveCount.textContent = fmt(reserve);
  els.routineCount.textContent = fmt(routine);

  if (isNationalOverview()) {
    els.zoneCount.textContent = fmt(state.authoritySummaries.length);
    els.shownCount.textContent = fmt(state.authoritySummaries.length);
    els.shownLabel.textContent = "Local authority overview";
  } else {
    els.zoneCount.textContent = fmt(authorities.size);
    els.shownCount.textContent = fmt(areas.length);
    els.shownLabel.textContent = state.authority === "all" ? "Matched LSOAs" : state.authority;
  }
}

function initMap() {
  if (!window.L) {
    els.allocationMap.innerHTML =
      '<div class="map-fallback">Interactive map tiles need an internet connection. The data and review list still load below.</div>';
    return;
  }

  mapState.map = L.map(els.allocationMap, {
    preferCanvas: true,
    zoomControl: true,
    scrollWheelZoom: true,
  });

  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  }).addTo(mapState.map);

  L.control.scale({ imperial: false, position: "bottomleft" }).addTo(mapState.map);

  mapState.layer = L.layerGroup().addTo(mapState.map);
}

function markerStyle(tier, selected = false, score = 1) {
  const radius = 6 + Math.sqrt(Math.max(0, score)) * 1.8;

  return {
    radius: selected ? Math.min(radius + 3, 28) : Math.min(radius, 24),
    color: selected ? "#102025" : "#ffffff",
    weight: selected ? 3 : 1,
    opacity: 1,
    fillColor: tierColor(tier),
    fillOpacity: selected ? 0.95 : 0.65,
  };
}

function fitMap(points, maxZoom) {
  if (!mapState.map || !points.length) return;

  const validPoints = points.filter(
    (point) => Number.isFinite(point[0]) && Number.isFinite(point[1])
  );

  if (!validPoints.length) return;

  mapState.map.fitBounds(L.latLngBounds(validPoints).pad(0.15), { maxZoom });
}

function renderNationalMap() {
  if (!mapState.map || !mapState.layer) return;

  els.mapTitle.textContent = "UK review overview";
  els.mapDescription.textContent =
    "Each circle is a local authority. Size and colour are based on the SSA7 LSOA predictions inside that authority.";

  mapState.layer.clearLayers();

  state.authoritySummaries.forEach((summary) => {
    if (!Number.isFinite(summary.latitude) || !Number.isFinite(summary.longitude)) return;

    const selected = state.authority === summary.name;
    const score = Math.max(1, summary.priorityCount + summary.reserveCount);

    const marker = L.circleMarker(
      [summary.latitude, summary.longitude],
      markerStyle(summary.tier, selected, score)
    );

    marker.bindTooltip(
      `<strong>${summary.name}</strong><br>
       Predicted crime: ${fmt(summary.demand, 0)}<br>
       Priority LSOAs: ${fmt(summary.priorityCount)}<br>
       Reserve LSOAs: ${fmt(summary.reserveCount)}`,
      { sticky: true }
    );

    marker.on("click", () => {
      state.authority = summary.name;
      state.selectedCode = null;
      els.authoritySelect.value = summary.name;
      mapState.needsFit = true;
      renderAll();
    });

    marker.addTo(mapState.layer);
  });

  if (mapState.needsFit) {
    fitMap(
      state.authoritySummaries.map((summary) => [summary.latitude, summary.longitude]),
      6
    );
    mapState.needsFit = false;
  }
}

function renderLsoaMap() {
  if (!mapState.map || !mapState.layer) return;

  const areas = visibleAreas();

  els.mapTitle.textContent =
    state.authority === "all"
      ? "LSOA review results"
      : `${state.authority} LSOA review`;

  els.mapDescription.textContent =
    "Each point is an LSOA. Red, yellow and blue are based on the SSA7 predicted crime count.";

  mapState.layer.clearLayers();

  areas.forEach((area) => {
    if (!Number.isFinite(area.latitude) || !Number.isFinite(area.longitude)) return;

    const selected = area.code === state.selectedCode;
    const marker = L.circleMarker(
      [area.latitude, area.longitude],
      markerStyle(area.tier, selected, area.demandRank)
    );

    marker.bindTooltip(
      `<strong>${area.name}</strong><br>
       ${tierText[area.tier]}<br>
       Predicted crime count: ${fmt(area.predictedDemand, 1)}<br>
       LSOA share of LAD: ${pct(area.lsoaShare, 2)}`,
      { sticky: true }
    );

    marker.on("click", () => {
      state.selectedCode = area.code;
      renderMap();
      renderSelectedArea();
    });

    marker.addTo(mapState.layer);
  });

  if (mapState.needsFit) {
    fitMap(
      areas.map((area) => [area.latitude, area.longitude]),
      state.authority === "all" ? 7 : 12
    );
    mapState.needsFit = false;
  }
}

function renderMap() {
  if (isNationalOverview()) {
    renderNationalMap();
  } else {
    renderLsoaMap();
  }
}

function mainReasons(area) {
  const reasons = [];

  if (area.tier === "priority") reasons.push("high SSA7 predicted crime count");
  if (area.tier === "reserve") reasons.push("above-average SSA7 predicted crime count");
  if (area.lsoaShare > 0.01) reasons.push("larger share of predicted LAD crime");
  if (area.highHarmShare >= 0.4) reasons.push("higher recent serious-crime share");

  if (Number(area.educationDecile) > 0 && Number(area.educationDecile) <= 2) {
    reasons.push("education pressure shown in IoD context");
  }

  if (
    (Number(area.incomeDecile) > 0 && Number(area.incomeDecile) <= 2) ||
    (Number(area.employmentDecile) > 0 && Number(area.employmentDecile) <= 2)
  ) {
    reasons.push("economic pressure shown in IoD context");
  }

  return reasons;
}

function renderNationalPanel() {
  const topAuthorities = state.authoritySummaries
    .slice(0, 3)
    .map((summary) => summary.name)
    .join(", ");

  els.panelEyebrow.textContent = "National overview";
  els.areaName.textContent = "Start with the UK pattern";
  els.areaMeta.textContent = `${fmt(state.authoritySummaries.length)} local authorities, ${fmt(state.areas.length)} LSOAs`;
  els.areaTier.textContent = "Overview";
  els.areaTier.className = "tier-badge tier-zone";

  els.metricOneLabel.textContent = "Total predicted crime";
  els.metricTwoLabel.textContent = "Priority LSOAs";
  els.metricThreeLabel.textContent = "Reserve LSOAs";
  els.metricFourLabel.textContent = "Areas shown";

  els.areaDemand.textContent = fmt(sum(state.areas, (area) => area.predictedDemand), 0);
  els.areaUplift.textContent = fmt(state.areas.filter((area) => area.tier === "priority").length);
  els.areaHarm.textContent = fmt(state.areas.filter((area) => area.tier === "reserve").length);
  els.areaContext.textContent = fmt(state.authoritySummaries.length);

  els.contextTitle.textContent = "How to read this view";
  els.contextHint.textContent =
    "The national view groups LSOAs by local authority so the map is not overcrowded.";

  els.detailOneLabel.textContent = "Top predicted areas";
  els.detailTwoLabel.textContent = "Map level";
  els.areaPopulation.textContent = topAuthorities || "-";
  els.areaRepeat.textContent = "Local authority";

  els.contextProfile.innerHTML = [
    `<div class="read-step"><b>1. LAD model</b><span>The regression estimates crime at LAD level.</span></div>`,
    `<div class="read-step"><b>2. LSOA allocation</b><span>The LAD prediction is split using LSOA share weights.</span></div>`,
    `<div class="read-step"><b>3. IoD context</b><span>IoD is shown for interpretation, not used to change the ranking.</span></div>`,
  ].join("");

  els.areaReason.textContent =
    "This overview shows where the SSA7 model predicts the highest crime counts. Click a local authority to inspect its LSOA-level results.";
}

function renderAuthorityPanel(summary) {
  if (!summary) {
    renderNationalPanel();
    return;
  }

  els.panelEyebrow.textContent = "Selected local authority";
  els.areaName.textContent = summary.name;
  els.areaMeta.textContent = `${fmt(summary.members.length)} LSOAs`;
  els.areaTier.textContent = tierText[summary.tier];
  els.areaTier.className = `tier-badge ${tierClass(summary.tier)}`;

  els.metricOneLabel.textContent = "Predicted crime";
  els.metricTwoLabel.textContent = "Priority LSOAs";
  els.metricThreeLabel.textContent = "Reserve LSOAs";
  els.metricFourLabel.textContent = "Population";

  els.areaDemand.textContent = fmt(summary.demand, 0);
  els.areaUplift.textContent = fmt(summary.priorityCount);
  els.areaHarm.textContent = fmt(summary.reserveCount);
  els.areaContext.textContent = summary.population ? fmt(summary.population) : "No match";

  els.contextTitle.textContent = "IoD context profile";
  els.contextHint.textContent = "Demand-weighted average deciles. Lower values mean stronger pressure.";

  els.detailOneLabel.textContent = "Map level";
  els.detailTwoLabel.textContent = "Routine LSOAs";
  els.areaPopulation.textContent = "LSOA detail";
  els.areaRepeat.textContent = fmt(summary.routineCount);

  els.contextProfile.innerHTML = [
    contextRow("Overall deprivation", Math.round(summary.imdDecile)),
    contextRow("Income", Math.round(summary.incomeDecile)),
    contextRow("Employment", Math.round(summary.employmentDecile)),
    contextRow("Education", Math.round(summary.educationDecile)),
  ].join("");

  els.areaReason.textContent =
    `${summary.name} contains ${fmt(summary.priorityCount)} priority LSOAs and ${fmt(summary.reserveCount)} reserve-watch LSOAs according to the SSA7 prediction output.`;
}

function renderSelectedArea() {
  const area = selectedArea();

  if (!area) {
    if (state.authority !== "all") {
      renderAuthorityPanel(selectedAuthoritySummary());
    } else {
      renderNationalPanel();
    }
    return;
  }

  const pressure = contextPressure(area);
  const pressureText = pressure >= 0.65 ? "High" : pressure >= 0.4 ? "Medium" : "Lower";
  const reasons = mainReasons(area);

  els.panelEyebrow.textContent = "Selected LSOA";
  els.areaName.textContent = area.name;
  els.areaMeta.textContent = `${area.localAuthority} - ${area.code}`;
  els.areaTier.textContent = tierText[area.tier];
  els.areaTier.className = `tier-badge ${tierClass(area.tier)}`;

  els.metricOneLabel.textContent = "Predicted crime count";
  els.metricTwoLabel.textContent = "LSOA share of LAD";
  els.metricThreeLabel.textContent = "Recent serious-crime share";
  els.metricFourLabel.textContent = "IoD context";

  els.areaDemand.textContent = fmt(area.predictedDemand, 1);
  els.areaUplift.textContent = pct(area.lsoaShare, 2);
  els.areaHarm.textContent = pct(area.highHarmShare);
  els.areaContext.textContent = pressureText;

  els.contextTitle.textContent = "IoD context profile";
  els.contextHint.textContent =
    "These values are shown for interpretation only. They do not change the SSA7 ranking.";

  els.detailOneLabel.textContent = "Population";
  els.detailTwoLabel.textContent = "Recent demand";
  els.areaPopulation.textContent = area.population ? fmt(area.population) : "No match";
  els.areaRepeat.textContent = fmt(area.recent12Demand, 0);

  els.contextProfile.innerHTML = [
    contextRow("Overall deprivation", area.imdDecile),
    contextRow("Income", area.incomeDecile),
    contextRow("Employment", area.employmentDecile),
    contextRow("Education", area.educationDecile),
  ].join("");

  els.areaReason.textContent = reasons.length
    ? `This area is marked because of ${reasons.join(", ")}. It should be reviewed with local knowledge before any operational decision.`
    : "This area is not currently highlighted for extra review. It still requires routine policing coverage.";
}

function renderRanking() {
  if (isNationalOverview()) {
    const rows = state.authoritySummaries.slice(0, 14);

    els.rankingList.innerHTML = rows
      .map(
        (summary, index) => `
        <button type="button" class="rank-row" data-authority="${summary.name}">
          <span class="rank-number">${index + 1}</span>
          <span class="rank-main">
            <strong>${summary.name}</strong>
            <small>${fmt(summary.priorityCount)} priority, ${fmt(summary.reserveCount)} reserve</small>
          </span>
          <span class="rank-score">${fmt(summary.demand, 0)}</span>
        </button>
      `
      )
      .join("");

    els.rankingList.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.authority = button.dataset.authority;
        els.authoritySelect.value = state.authority;
        state.selectedCode = null;
        mapState.needsFit = true;
        renderAll();
      });
    });

    return;
  }

  const rows = visibleAreas()
    .filter((area) => area.tier !== "routine")
    .sort((a, b) => b.predictedDemand - a.predictedDemand)
    .slice(0, 14);

  els.rankingList.innerHTML = rows
    .map(
      (area, index) => `
      <button type="button" class="rank-row" data-code="${area.code}">
        <span class="rank-number">${index + 1}</span>
        <span class="rank-main">
          <strong>${area.name}</strong>
          <small>${area.localAuthority} - ${tierText[area.tier]}</small>
        </span>
        <span class="rank-score">${fmt(area.predictedDemand, 0)}</span>
      </button>
    `
    )
    .join("");

  els.rankingList.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCode = button.dataset.code;
      mapState.needsFit = false;
      renderAll();
    });
  });
}

function downloadList() {
  const header = [
    "LSOA code",
    "LSOA name",
    "Local authority",
    "LAD code",
    "Review tier",
    "Predicted crime count",
    "LSOA share of LAD",
    "Recent serious-crime share",
    "Population",
    "IMD decile",
    "Income decile",
    "Employment decile",
    "Education decile",
    "Main reasons",
  ];

  const rows = state.areas.map((area) => [
    area.code,
    area.name,
    area.localAuthority,
    area.ladCode,
    tierText[area.tier],
    area.predictedDemand,
    area.lsoaShare,
    area.highHarmShare,
    area.population,
    area.imdDecile,
    area.incomeDecile,
    area.employmentDecile,
    area.educationDecile,
    mainReasons(area).join("; "),
  ]);

  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `ssa7-police-review-${state.authority}.csv`;
  link.click();

  URL.revokeObjectURL(url);
}

function renderAll() {
  updateSummary();
  renderMap();
  renderSelectedArea();
  renderRanking();
}

function init() {
  prepareData();

  els.forceName.textContent = data.meta.force;
  els.forecastMonth.textContent = `Forecast: ${data.meta.forecastMonth}`;

  els.authoritySelect.innerHTML = [
    '<option value="all">All local authorities</option>',
    ...state.authoritySummaries.map((summary) => `<option value="${summary.name}">${summary.name}</option>`),
  ].join("");

  els.authoritySelect.addEventListener("change", (event) => {
    state.authority = event.target.value;
    state.selectedCode = null;
    mapState.needsFit = true;
    renderAll();
  });

  els.searchInput.addEventListener("input", (event) => {
    state.search = event.target.value;
    const matches = visibleAreas();
    state.selectedCode = state.search.trim() && matches.length ? matches[0].code : null;
    mapState.needsFit = true;
    renderAll();
  });

  els.downloadButton.addEventListener("click", downloadList);

  window.addEventListener("resize", () => {
    if (mapState.map) mapState.map.invalidateSize();
  });

  initMap();
  renderAll();
}

init();