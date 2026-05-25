const data = window.DASHBOARD_DATA;

const state = {
  authority: "all",
  search: "",
  selectedCode: null,
  scenario: [],
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
  shownCount: document.getElementById("shownCount"),
  shownLabel: document.getElementById("shownLabel"),
  allocationMap: document.getElementById("allocationMap"),
  areaName: document.getElementById("areaName"),
  areaMeta: document.getElementById("areaMeta"),
  areaTier: document.getElementById("areaTier"),
  areaDemand: document.getElementById("areaDemand"),
  areaUplift: document.getElementById("areaUplift"),
  areaHarm: document.getElementById("areaHarm"),
  areaContext: document.getElementById("areaContext"),
  areaPopulation: document.getElementById("areaPopulation"),
  areaRepeat: document.getElementById("areaRepeat"),
  contextProfile: document.getElementById("contextProfile"),
  areaReason: document.getElementById("areaReason"),
  rankingList: document.getElementById("rankingList"),
};

const mapState = {
  map: null,
  markers: new Map(),
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

function contextPressure(area) {
  const deciles = [area.imdDecile, area.incomeDecile, area.educationDecile, area.employmentDecile].filter(Boolean);
  if (!deciles.length) return 0;
  const avgPressure = deciles.reduce((sum, decile) => sum + (11 - decile) / 10, 0) / deciles.length;
  return Math.max(0, Math.min(1, avgPressure));
}

function baseAreas() {
  return data.areas.filter(
    (area) => state.authority === "all" || area.localAuthority === state.authority
  );
}

function visibleAreas() {
  const q = state.search.trim().toLowerCase();
  const areas = state.scenario.length ? state.scenario : baseAreas();
  if (!q) return areas;
  return areas.filter((area) =>
    `${area.name} ${area.shortName} ${area.code} ${area.localAuthority}`.toLowerCase().includes(q)
  );
}

function hasContextFlag(area) {
  return (
    area.imdDecile <= 2 ||
    area.incomeDecile <= 2 ||
    area.educationDecile <= 2 ||
    area.employmentDecile <= 2 ||
    area.repeatAttentionRisk === "High"
  );
}

function computeScenario() {
  const areas = baseAreas()
    .map((area) => ({ ...area, tier: "routine" }))
    .sort((a, b) => b.balancedScore - a.balancedScore);

  const priorityCount = Math.max(1, Math.round(areas.length * 0.1));
  const reserveCount = Math.max(1, Math.round(areas.length * 0.03));
  areas.slice(0, priorityCount).forEach((area) => {
    area.tier = "priority";
  });

  const reserveCandidates = areas
    .filter((area) => area.tier !== "priority")
    .sort((a, b) => b.spikeZ + b.uplift * 3 - (a.spikeZ + a.uplift * 3));
  reserveCandidates.slice(0, reserveCount).forEach((area) => {
    area.tier = "reserve";
  });

  state.scenario = areas;
  if (!state.scenario.find((area) => area.code === state.selectedCode)) {
    state.selectedCode = state.scenario[0]?.code || null;
  }
}

function updateSummary() {
  const visible = visibleAreas();
  const priority = state.scenario.filter((area) => area.tier === "priority");
  const reserve = state.scenario.filter((area) => area.tier === "reserve");
  const routine = state.scenario.filter((area) => area.tier === "routine");
  els.priorityCount.textContent = fmt(priority.length);
  els.reserveCount.textContent = fmt(reserve.length);
  els.routineCount.textContent = fmt(routine.length);
  els.shownCount.textContent = fmt(visible.length);
  els.shownLabel.textContent = state.authority === "all" ? "Available pilot areas" : state.authority;
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

function markerStyle(area) {
  const selected = area.code === state.selectedCode;
  const radius = 4 + Math.sqrt(Math.max(0, area.demandRank)) * 9;
  return {
    radius: selected ? radius + 3 : radius,
    color: selected ? "#102025" : "#ffffff",
    weight: selected ? 3 : 1,
    opacity: 1,
    fillColor: tierColor(area.tier),
    fillOpacity: selected ? 0.95 : 0.78,
  };
}

function fitMapToAreas(areas) {
  if (!mapState.map || !areas.length) return;
  const points = areas
    .filter((area) => Number.isFinite(area.latitude) && Number.isFinite(area.longitude))
    .map((area) => [area.latitude, area.longitude]);
  if (!points.length) return;
  const bounds = L.latLngBounds(points);
  mapState.map.fitBounds(bounds.pad(0.12), { maxZoom: state.authority === "all" ? 10 : 12 });
}

function focusSelectedArea() {
  if (!mapState.map) return;
  const area = selectedArea();
  if (!area || !Number.isFinite(area.latitude) || !Number.isFinite(area.longitude)) return;
  mapState.map.flyTo([area.latitude, area.longitude], Math.max(mapState.map.getZoom(), 13), {
    duration: 0.55,
  });
}

function renderMap() {
  const areas = visibleAreas();
  const projectionAreas = areas.length ? areas : state.scenario;
  if (!mapState.map || !mapState.layer) return;
  mapState.layer.clearLayers();
  mapState.markers.clear();

  projectionAreas
    .filter((area) => Number.isFinite(area.latitude) && Number.isFinite(area.longitude))
    .slice()
    .sort((a, b) => a.balancedScore - b.balancedScore)
    .forEach((area) => {
      const marker = L.circleMarker([area.latitude, area.longitude], markerStyle(area));
      marker.bindTooltip(
        `<strong>${area.name}</strong><br>${tierText[area.tier]}<br>Forecasted demand: ${fmt(area.predictedDemand, 1)}`,
        { sticky: true }
      );
      marker.on("click", () => {
        state.selectedCode = area.code;
        mapState.needsFit = false;
        renderMap();
        renderSelectedArea();
      });
      marker.addTo(mapState.layer);
      mapState.markers.set(area.code, marker);
    });

  if (mapState.needsFit) {
    fitMapToAreas(projectionAreas);
    mapState.needsFit = false;
  }
}

function selectedArea() {
  return state.scenario.find((area) => area.code === state.selectedCode) || state.scenario[0];
}

function mainReasons(area) {
  const reasons = [];
  if (area.tier === "priority") reasons.push("high combined review score");
  if (area.demandRank >= 0.9) reasons.push("high forecasted demand");
  if (area.uplift >= 0.15 || area.spikeZ >= 1.5) reasons.push("recent increase");
  if (area.highHarmShare >= 0.4) reasons.push("higher serious-crime share");
  if (area.educationDecile <= 2) reasons.push("education pressure");
  if (area.incomeDecile <= 2 || area.employmentDecile <= 2) reasons.push("economic pressure");
  if (area.repeatAttentionRisk === "High") reasons.push("repeated high-demand pattern");
  return reasons;
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

function renderSelectedArea() {
  const area = selectedArea();
  if (!area) return;
  const pressure = contextPressure(area);
  const pressureText = pressure >= 0.65 ? "High" : pressure >= 0.4 ? "Medium" : "Lower";
  const reasons = mainReasons(area);
  els.areaName.textContent = area.name;
  els.areaMeta.textContent = `${area.localAuthority} - ${area.code}`;
  els.areaTier.textContent = tierText[area.tier];
  els.areaTier.className = `tier-badge ${tierClass(area.tier)}`;
  els.areaDemand.textContent = fmt(area.predictedDemand, 1);
  els.areaUplift.textContent = pct(area.uplift);
  els.areaHarm.textContent = pct(area.highHarmShare);
  els.areaContext.textContent = pressureText;
  els.areaPopulation.textContent = area.population ? fmt(area.population) : "No match";
  els.areaRepeat.textContent = `${fmt(area.recentTopDecileMonths)} of last 12`;
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
  const rows = visibleAreas().filter((area) => area.tier !== "routine").slice(0, 14);
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
      renderMap();
      renderSelectedArea();
      focusSelectedArea();
      document.querySelector(".area-panel").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function downloadList() {
  const rows = state.scenario.map((area) => [
    area.code,
    area.name,
    area.localAuthority,
    tierText[area.tier],
    area.predictedDemand,
    area.uplift,
    area.highHarmShare,
    area.imdDecile,
    area.incomeDecile,
    area.educationDecile,
    mainReasons(area).join("; "),
  ]);
  const header = [
    "LSOA code",
    "LSOA name",
    "Local authority",
    "Review tier",
    "Forecasted demand",
    "Recent change",
    "Serious-crime share",
    "IMD decile",
    "Income decile",
    "Education decile",
    "Main reasons",
  ];
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `police-demand-review-${state.authority}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function renderAll() {
  computeScenario();
  updateSummary();
  renderMap();
  renderSelectedArea();
  renderRanking();
}

function init() {
  els.forceName.textContent = data.meta.force;
  els.forecastMonth.textContent = `Forecast: ${data.meta.forecastMonth}`;
  els.authoritySelect.innerHTML = [
    '<option value="all">All available pilot areas</option>',
    ...data.localAuthorities.map((name) => `<option value="${name}">${name}</option>`),
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
    if (matches.length) state.selectedCode = matches[0].code;
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
