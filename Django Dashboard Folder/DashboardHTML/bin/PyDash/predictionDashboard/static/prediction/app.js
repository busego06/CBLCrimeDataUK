const dashboardData = window.DASHBOARDDATA;

const state = {
  ladSelected: "all",
  search: "",
  selectedCode: null,
  areas: [],
  authoritySummaries: [],
};

const els = {
  dataFrom: document.getElementById("dataFrom"),
  forecastMonth: document.getElementById("forecastMonth"),
  authoritySelect: document.getElementById("authoritySelect"),
  searchInput: document.getElementById("searchInput"),
  downloadButton: document.getElementById("downloadButton"),

  priorityCount: document.getElementById("priorityCount"),
  riskyCount: document.getElementById("reserveCount"),
  standardCount: document.getElementById("routineCount"),
  shownCount: document.getElementById("shownCount"),
  shownLabel: document.getElementById("shownLabel"),

  allocationMap: document.getElementById("allocationMap"),
  mapDescription: document.getElementById("mapDescription"),
  mapSelectedArea: document.getElementById("mapSelectedArea"),
  mapLevel: document.getElementById("mapLevel"),
  mapPopulation: document.getElementById("mapPopulation"),

  contextTitle: document.getElementById("contextTitle"),
  contextHint: document.getElementById("contextHint"),
  contextProfile: document.getElementById("contextProfile"),

  rankingList: document.getElementById("rankingList"),
};

const mapState = {
  map: null,
  layer: null,
  needsFit: true,
};

const tierText = {
  priority: "Priority Patrol",
  reserve: "Risk Addressing Patrol",
  routine: "Standard Patrol",
};

function formatFloat(value, decimals = 0) {
  return Number(value || 0).toLocaleString("en-GB", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatPercent(value, decimals = 1) {
  return `${formatFloat(Number(value || 0) * 100, decimals)}%`;
}

function weightedAverageByDemand(items, columnName) {
  let weightedTotal = 0;
  let totalWeight = 0;

  for (const item of items) {
    const value = Number(item[columnName]);
    const weight = Number(item.predictedDemand || 0);

    if (Number.isFinite(value) && weight > 0) {
      weightedTotal += value * weight;
      totalWeight += weight;
    }
  }

  if (totalWeight === 0) {
    return 0;
  }

  return weightedTotal / totalWeight;
}

function tierColor(tier) {
  if (tier === "priority") return "#b71c1c";
  if (tier === "reserve") return "#ef6c00";
  return "#1565c0";
}

function tierFromModel(area) {
  const tier = String(area.originalTier || "").toLowerCase();

  if (tier.includes("priority")) return "priority";
  if (tier.includes("reserve")) return "reserve";
  return "routine";
}

function contextRow(label, decile) {
  const cleanDecile = Number(decile || 0);
  const pressure = cleanDecile ? 11 - cleanDecile : 0;
  const width = `${Math.max(8, pressure * 10)}%`;

  return `
    <div class="context-row">
      <div>
        <b>${label}</b>
      </div>
      <div class="context-meter" aria-hidden="true">
        <i style="width: ${width}"></i>
      </div>
      <strong>${pressure ? `${pressure}/10` : "-"}</strong>
    </div>
  `;
}

function visibleAreas() {
  let areas = [];

  for (const area of state.areas) {
    if (state.ladSelected === "all" || area.ladName === state.ladSelected) {
      areas.push(area);
    }
  }

  const query = state.search.trim().toLowerCase();

  if (!query) {
    return areas;
  }

  let searchedAreas = [];

  for (const area of areas) {
    const searchableText = `${area.name} ${area.lsoaName} ${area.lsoaCode} ${area.ladName} ${area.ladCode}`;

    if (searchableText.toLowerCase().includes(query)) {
      searchedAreas.push(area);
    }
  }

  return searchedAreas;
}

function isNationalOverview() {
  return state.ladSelected === "all" && !state.search.trim();
}

function selectedArea() {
  if (!state.selectedCode) {
    return null;
  }

  for (const area of state.areas) {
    if (area.lsoaCode === state.selectedCode) {
      return area;
    }
  }

  return null;
}

function buildAuthoritySummaries(areas) {
  const groups = new Map();

  for (const area of areas) {
    const ladName = area.ladName || "Unknown area";

    if (!groups.has(ladName)) {
      groups.set(ladName, []);
    }

    groups.get(ladName).push(area);
  }

  const summaries = [];

  for (const [name, members] of groups.entries()) {
    let demand = 0;
    let population = 0;
    let priorityCount = 0;
    let reserveCount = 0;

    for (const area of members) {
      demand += Number(area.predictedDemand || 0);
      population += Number(area.population || 0);

      if (area.tier === "priority") {
        priorityCount++;
      }

      if (area.tier === "reserve") {
        reserveCount++;
      }
    }

    const routineCount = members.length - priorityCount - reserveCount;

    let tier = "routine";

    if (priorityCount > 3) {
      tier = "priority";
    } else if (reserveCount > 3) {
      tier = "reserve";
    }

    summaries.push({
      name,
      members,
      demand,
      population,
      priorityCount,
      reserveCount,
      routineCount,
      tier,
      latitude: weightedAverageByDemand(members, "latitude"),
      longitude: weightedAverageByDemand(members, "longitude"),
      imdDecile: weightedAverageByDemand(members, "imdDecile"),
      incomeDecile: weightedAverageByDemand(members, "incomeDecile"),
      employmentDecile: weightedAverageByDemand(members, "employmentDecile"),
      educationDecile: weightedAverageByDemand(members, "educationDecile"),
    });
  }

  return summaries.sort((a, b) => b.demand - a.demand);
}

function prepareData() {
  state.areas = dashboardData.areas
    .map((area) => ({
      ...area,
      tier: tierFromModel(area),
    }))
    .sort((a, b) => b.predictedDemand - a.predictedDemand);

  state.authoritySummaries = buildAuthoritySummaries(state.areas);
}

function updateSummary() {
  const areas = visibleAreas();

  let priority = 0;
  let reserve = 0;
  let routine = 0;

  for (const area of areas) {
    if (area.tier === "priority") {
      priority++;
    } else if (area.tier === "reserve") {
      reserve++;
    } else {
      routine++;
    }
  }

  els.priorityCount.textContent = formatFloat(priority);
  els.riskyCount.textContent = formatFloat(reserve);
  els.standardCount.textContent = formatFloat(routine);

  if (isNationalOverview()) {
    els.shownCount.textContent = formatFloat(state.authoritySummaries.length);
    els.shownLabel.textContent = "Local Authority Overview";
  } else {
    els.shownCount.textContent = formatFloat(areas.length);
    els.shownLabel.textContent = state.ladSelected;
  }
}

function updateMapHeader() {
  const area = selectedArea();
  const areas = visibleAreas();

  let population = 0;

  if (area) {
    population = Number(area.population || 0);
    els.mapSelectedArea.textContent = area.name;
    els.mapLevel.textContent = "LSOA";
  } else {
    for (const item of areas) {
      population += Number(item.population || 0);
    }

    if (isNationalOverview()) {
      els.mapSelectedArea.textContent = "UK Overview";
      els.mapLevel.textContent = "Local Authority";
    } else {
      els.mapSelectedArea.textContent = state.ladSelected;
      els.mapLevel.textContent = "LSOA";
    }
  }

  els.mapPopulation.textContent = formatFloat(population, 0);
}

function updateContextProfile() {
  let areas = visibleAreas();
  const selected = selectedArea();

  if (selected) {
    areas = [selected];
  }

  els.contextTitle.textContent = "Deprivation Context";
  els.contextHint.textContent = "Higher values mean stronger pressure.";

  els.contextProfile.innerHTML = [
    contextRow("Overall deprivation", Math.round(weightedAverageByDemand(areas, "imdDecile"))),
    contextRow("Income", Math.round(weightedAverageByDemand(areas, "incomeDecile"))),
    contextRow("Employment", Math.round(weightedAverageByDemand(areas, "employmentDecile"))),
    contextRow("Education", Math.round(weightedAverageByDemand(areas, "educationDecile"))),
  ].join("");
}

function initMap() {
  if (!window.L) {
    els.allocationMap.innerHTML =
      '<div class="map-fallback">Interactive map needs an internet connection. The data still loads below.</div>';
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

  L.control.scale({
    imperial: false,
    position: "bottomleft",
  }).addTo(mapState.map);

  mapState.layer = L.layerGroup().addTo(mapState.map);
}

function markerStyle(tier, selected = false, score = 1) {
  let radius = 8 + Math.sqrt(Math.max(0, score)) * 1.5;

  if (selected) {
    radius = Math.min(radius + 2, 28);
  } else {
    radius = Math.min(radius, 24);
  }

  let borderColor = "#ffffff";
  let borderWidth = 1;
  let fillOpacity = 0.65;

  if (selected) {
    borderColor = "#102025";
    borderWidth = 3;
    fillOpacity = 0.95;
  }

  return {
    radius,
    color: borderColor,
    weight: borderWidth,
    opacity: 1,
    fillColor: tierColor(tier),
    fillOpacity,
  };
}

function fitMap(points, maxZoom) {
  if (!mapState.map || points.length === 0) {
    return;
  }

  const validPoints = points.filter((point) => {
    return Number.isFinite(point[0]) && Number.isFinite(point[1]);
  });

  if (validPoints.length === 0) {
    return;
  }

  mapState.map.fitBounds(L.latLngBounds(validPoints).pad(0.15), {
    maxZoom,
  });
}

function renderLADMap() {
  if (!mapState.map || !mapState.layer) {
    return;
  }

  els.mapDescription.textContent =
    "Select a local authority to inspect LSOA level review points.";

  mapState.layer.clearLayers();

  for (const summary of state.authoritySummaries) {
    if (!Number.isFinite(summary.latitude) || !Number.isFinite(summary.longitude)) {
      continue;
    }

    const selected = state.ladSelected === summary.name;
    const score = Math.max(1, summary.priorityCount + summary.reserveCount);

    const marker = L.circleMarker(
      [summary.latitude, summary.longitude],
      markerStyle(summary.tier, selected, score)
    );

    marker.bindTooltip(
      `<strong>${summary.name}</strong><br>
       Predicted Crime: ${formatFloat(Math.round(summary.demand / 100) * 100, 0)}<br>
       Priority LSOAs: ${formatFloat(summary.priorityCount)}<br>
       Reserve LSOAs: ${formatFloat(summary.reserveCount)}`,
      { sticky: true }
    );

    marker.on("click", () => {
      state.ladSelected = summary.name;
      state.selectedCode = null;
      els.authoritySelect.value = summary.name;
      mapState.needsFit = true;
      renderAll();
    });

    marker.addTo(mapState.layer);
  }

  if (mapState.needsFit) {
    const coordinates = [];

    for (const summary of state.authoritySummaries) {
      coordinates.push([summary.latitude, summary.longitude]);
    }

    fitMap(coordinates, 6);
    mapState.needsFit = false;
  }
}

function renderLSOAMap() {
  if (!mapState.map || !mapState.layer) {
    return;
  }

  const areas = visibleAreas();

  els.mapDescription.textContent =
    "Each point is an LSOA. Colours are based on the predicted crime count.";

  mapState.layer.clearLayers();

  for (const area of areas) {
    if (!Number.isFinite(area.latitude) || !Number.isFinite(area.longitude)) {
      continue;
    }

    const selected = area.lsoaCode === state.selectedCode;

    const marker = L.circleMarker(
      [area.latitude, area.longitude],
      markerStyle(area.tier, selected, area.demandRank)
    );

    marker.bindTooltip(
      `<strong>${area.name}</strong><br>
      ${tierText[area.tier]}<br>
      Predicted crime count: ${formatFloat(area.predictedDemand, 1)}<br>
      LSOA share of LAD: ${formatPercent(area.lsoaShare, 2)}<br>
      Recent serious crime share: ${formatPercent(area.highHarmShare, 1)}`,
      { sticky: true }
    );

    marker.on("click", () => {
      state.selectedCode = area.lsoaCode;
      mapState.needsFit = false;
      renderAll();
    });

    marker.addTo(mapState.layer);
  }

  if (mapState.needsFit) {
    const coordinates = [];

    for (const area of areas) {
      coordinates.push([area.latitude, area.longitude]);
    }

    let maxZoom = 12;

    if (state.ladSelected === "all") {
      maxZoom = 7;
    }

    fitMap(coordinates, maxZoom);

    mapState.needsFit = false;
  }
}

function renderMap() {
  if (isNationalOverview()) {
    renderLADMap();
  } else {
    renderLSOAMap();
  }
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
            <small>${formatFloat(summary.priorityCount)} priority, ${formatFloat(summary.reserveCount)} reserve</small>
          </span>
        </button>
      `
      )
      .join("");

    els.rankingList.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.ladSelected = button.dataset.authority;
        els.authoritySelect.value = state.ladSelected;
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
      <button type="button" class="rank-row" data-code="${area.lsoaCode}">
        <span class="rank-number">${index + 1}</span>
        <span class="rank-main">
          <strong>${area.name}</strong>
          <small>${area.ladName} - ${tierText[area.tier]}</small>
        </span>
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
    "LAD name",
    "LAD code",
    "Review tier",
    "Predicted crime count",
    "LSOA share of LAD",
    "Recent serious crime share",
    "Population",
    "IMD decile",
    "Income decile",
    "Employment decile",
    "Education decile",
  ];

  const rows = state.areas.map((area) => [
    area.lsoaCode,
    area.name,
    area.ladName,
    area.ladCode,
    tierText[area.tier],
    Math.round(area.predictedDemand / 10) * 10,,
    area.lsoaShare,
    area.highHarmShare,
    area.population,
    area.imdDecile,
    area.incomeDecile,
    area.employmentDecile,
    area.educationDecile,
  ]);

  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(","))
    .join("\n");

  const blob = new Blob([csv], {
    type: "text/csv;charset=utf-8",
  });

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `police-dashboard-review-${state.ladSelected}.csv`;
  link.click();

  URL.revokeObjectURL(url);
}

function renderAll() {
  updateSummary();
  updateMapHeader();
  renderMap();
  updateContextProfile();
  renderRanking();
}

function init() {
  prepareData();

  els.dataFrom.textContent = dashboardData.meta.dataFrom;
  els.forecastMonth.textContent = `Forecast: ${dashboardData.meta.forecastMonth}`;

  els.authoritySelect.innerHTML = [
    '<option value="all">All Local Authorities</option>',
    ...state.authoritySummaries
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(
        (summary) =>
          `<option value="${summary.name}">${summary.name}</option>`
      ),
  ].join("");

  els.authoritySelect.addEventListener("change", (event) => {
    state.ladSelected = event.target.value;
    state.selectedCode = null;
    mapState.needsFit = true;
    renderAll();
  });

  els.searchInput.addEventListener("input", (event) => {
    state.search = event.target.value;
    const matches = visibleAreas();

    if (state.search.trim() && matches.length > 0) {
      state.selectedCode = matches[0].lsoaCode;
    } else {
      state.selectedCode = null;
    }

    mapState.needsFit = true;
    renderAll();
  });

  els.downloadButton.addEventListener("click", downloadList);

  window.addEventListener("resize", () => {
    if (mapState.map) {
      mapState.map.invalidateSize();
    }
  });

  initMap();
  renderAll();
}

init();