const dashboardData = window.DASHBOARDDATA;

// Dashboard state
const state = {
  ladSelected: "all",
  search: "",
  selectedCode: null,
  reserveCutoff: 0.75,
  priorityCutoff: 0.90,
  areas: [],
  authoritySummaries: [],
};

// HTML Elements
const elements = {
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
  tierSlider: document.getElementById("tierSlider"),
  reserveValue: document.getElementById("reserveValue"),
  priorityValue: document.getElementById("priorityValue"),
  rankingList: document.getElementById("rankingList"),
};

// State of Leaflet Map
const mapState = {
  map: null,
  layer: null,
  needsFit: true,
};

// Tiers of patrol for addressing what police should do in LSOA/LAD's
const tierText = {
  priority: "Priority Patrol",
  reserve: "Risk Addressing Patrol",
  routine: "Standard Patrol",
};

// Formats numbers for ease of reading (12495 -> 12,495)
function formatFloat(value, decimals = 0) {
  return Number(value || 0).toLocaleString("en-GB", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

// Converts decimals to percentage (0.25 -> 25%)
function formatPercent(value, decimals = 1) {
  return `${formatFloat(Number(value || 0) * 100, decimals)}%`;
}

// Weighted average for classifyingLAD demand summary
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

// Sets color of nodes on the map
function tierColor(tier) {
  if (tier === "priority") return "#b71c1c";
  if (tier === "reserve") return "#ef6c00";
  return "#1565c0";
}

// Gets the tier of the node from the model output
function tierFromDemandRank(area) {
  if (area.demandRank >= state.priorityCutoff) {
    return "priority";
  }

  if (area.demandRank >= state.reserveCutoff) {
    return "reserve";
  }

  return "routine";
}

// Creates a row for deprivation
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

// Returns the nodes matching the selected overview (national or LAD)
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

// Checks if the overview is national (or of a specific LAD)
function isNationalOverview() {
  return state.ladSelected === "all" && !state.search.trim();
}

// Returns selected LSOA
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

// Creates LAD summary from individual LSOAs
function buildAuthoritySummaries(areas) {
  // Group LSOAs by LAD name
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

    if ((priorityCount / members.length) > 0.15) {
      if (priorityCount * 1.5 > reserveCount){
        tier = "priority";
      } else {
        tier = "reserve"
      }
    } else if ((reserveCount / members.length) > 0.15) {
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
      // Calculating LAD point through average of LSOA coordinates
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

// Converts data into UI friendly visualizations
function prepareData() {
  state.areas = dashboardData.areas
    .map((area) => ({
      ...area,
      tier: tierFromDemandRank(area),
    }))
    .sort((a, b) => b.predictedDemand - a.predictedDemand);

  state.authoritySummaries = buildAuthoritySummaries(state.areas);
}

// Updates the numbers that are above the map
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

  elements.priorityCount.textContent = formatFloat(priority);
  elements.riskyCount.textContent = formatFloat(reserve);
  elements.standardCount.textContent = formatFloat(routine);

  if (isNationalOverview()) {
    elements.shownCount.textContent = formatFloat(state.authoritySummaries.length);
    elements.shownLabel.textContent = "Local Authority Overview";
  } else {
    elements.shownCount.textContent = formatFloat(areas.length);
    elements.shownLabel.textContent = state.ladSelected;
  }
}

// Updates the numbers right above the map (population etc.)
function updateMapHeader() {
  const area = selectedArea();
  const areas = visibleAreas();

  let population = 0;

  if (area) {
    population = Number(area.population || 0);
    elements.mapSelectedArea.textContent = area.name;
    elements.mapLevel.textContent = "LSOA";
  } else {
    for (const item of areas) {
      population += Number(item.population || 0);
    }

    if (isNationalOverview()) {
      elements.mapSelectedArea.textContent = "UK Overview";
      elements.mapLevel.textContent = "Local Authority";
    } else {
      elements.mapSelectedArea.textContent = state.ladSelected;
      elements.mapLevel.textContent = "LSOA";
    }
  }

  elements.mapPopulation.textContent = formatFloat(population, 0);
}

// Updates deprivation data below the map
function updateContextProfile() {
  let areas = visibleAreas();
  const selected = selectedArea();

  if (selected) {
    areas = [selected];
  }

  elements.contextTitle.textContent = "Deprivation Context";
  elements.contextHint.textContent = "Higher values mean stronger pressure.";

  elements.contextProfile.innerHTML = [
    contextRow("Overall deprivation", Math.round(weightedAverageByDemand(areas, "imdDecile"))),
    contextRow("Income", Math.round(weightedAverageByDemand(areas, "incomeDecile"))),
    contextRow("Employment", Math.round(weightedAverageByDemand(areas, "employmentDecile"))),
    contextRow("Education", Math.round(weightedAverageByDemand(areas, "educationDecile"))),
  ].join("");
}

// Creates Leaflet Map
function initMap() {
  if (!window.L) {
    elements.allocationMap.innerHTML =
      '<div class="map-fallback">Interactive map needs an internet connection. The data still loads below.</div>';
    return;
  }

  mapState.map = L.map(elements.allocationMap, {
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

// Sets the node styling based on the crime model
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

// Fits map according to the node placements
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

// Renders nodes of LADs into the map
function renderLADMap() {
  if (!mapState.map || !mapState.layer) {
    return;
  }

  elements.mapDescription.textContent =
    "Select a local authority to inspect LSOA level review points.";

  mapState.layer.clearLayers();

  for (const summary of state.authoritySummaries) {
    if (!Number.isFinite(summary.latitude) || !Number.isFinite(summary.longitude)) {
      continue;
    }

    const selected = state.ladSelected === summary.name;
    const score = Math.max(1, summary.priorityCount + summary.reserveCount);
    // Bases marker size according to the number of priority and risky nodes
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
      elements.authoritySelect.value = summary.name;
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

// Renders nodes of LSOAs into the map (of the specific LAD)
function renderLSOAMap() {
  if (!mapState.map || !mapState.layer) {
    return;
  }

  const areas = visibleAreas();

  elements.mapDescription.textContent =
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

// Check which map is visualized
function renderMap() {
  if (isNationalOverview()) {
    renderLADMap();
  } else {
    renderLSOAMap();
  }
}

// Render the review list 
function renderRanking() {
  if (isNationalOverview()) {
    const rows = state.authoritySummaries.slice(0, 14);

    elements.rankingList.innerHTML = rows
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

    elements.rankingList.querySelectorAll("button").forEach((button) => {
      button.addEventListener("click", () => {
        state.ladSelected = button.dataset.authority;
        elements.authoritySelect.value = state.ladSelected;
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

  elements.rankingList.innerHTML = rows
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

  elements.rankingList.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedCode = button.dataset.code;
      mapState.needsFit = false;
      renderAll();
    });
  });
}

// Export current area info as a csv
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
    Math.round(area.predictedDemand / 10) * 10,
    area.lsoaShare,
    area.highHarmShare,
    area.population,
    area.imdDecile,
    area.incomeDecile,
    area.employmentDecile,
    area.educationDecile,
  ]);

  // Converts data into csv format
  const csv = [header, ...rows].map((row) => row.join(",")).join("\n");

  const blob = new Blob([csv], {type: "text/csv;charset=utf-8",});

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = `police-dashboard-review-${state.ladSelected}.csv`;
  link.click();

  URL.revokeObjectURL(url);
}

// Refresh all dashboard data
function renderAll() {
  updateSummary();
  updateMapHeader();
  renderMap();
  updateContextProfile();
  renderRanking();
}

// Start dashboard
function init() {
  prepareData();

  elements.dataFrom.textContent = dashboardData.meta.dataFrom;
  elements.forecastMonth.textContent = `Forecast: ${dashboardData.meta.forecastMonth}`;

  elements.authoritySelect.innerHTML = [
    '<option value="all">All Local Authorities</option>',
    ...state.authoritySummaries
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(
        (summary) =>
          `<option value="${summary.name}">${summary.name}</option>`
      ),
  ].join("");

  // Dropdown Menu
  elements.authoritySelect.addEventListener("change", (event) => {
    state.ladSelected = event.target.value;
    state.selectedCode = null;
    mapState.needsFit = true;
    renderAll();
  });

  // Search Bar
  elements.searchInput.addEventListener("input", (event) => {
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

  // Download Button
  elements.downloadButton.addEventListener("click", downloadList);

  // Tier Threshold Slider
  noUiSlider.create(elements.tierSlider, {
    start: [75, 90],
    connect: [false, true, false],
    margin: 5,
    step: 1,
    range: {
      min: 0,
      max: 100,
    },
  });

  elements.tierSlider.noUiSlider.on("update", (values) => {
    state.reserveCutoff = Number(values[0]) / 100;
    state.priorityCutoff = Number(values[1]) / 100;

    elements.reserveValue.textContent = `${Math.round(values[0])}%`;
    elements.priorityValue.textContent = `${Math.round(values[1])}%`;

    elements.tierSlider.style.setProperty("--reserve-stop", `${Math.round(values[0])}%`);

    elements.tierSlider.style.setProperty("--priority-stop", `${Math.round(values[1])}%`);

    prepareData();
    renderAll();
  });

  window.addEventListener("resize", () => {
    if (mapState.map) {
      mapState.map.invalidateSize();
    }
  });

  initMap();
  renderAll();
}

init();
