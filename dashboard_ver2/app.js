const data = window.DASHBOARD_DATA;

const state = {
  authority: "all",
  search: "",
  selectedCode: null,
  scenario: [],
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
  detailOneLabel: document.getElementById("detailOneLabel"),
  detailTwoLabel: document.getElementById("detailTwoLabel"),
  areaPopulation: document.getElementById("areaPopulation"),
  areaRepeat: document.getElementById("areaRepeat"),
  contextProfile: document.getElementById("contextProfile"),
  areaReason: document.getElementById("areaReason"),
  rankingList: document.getElementById("rankingList"),
};

const mapState = {
  map: null,
  markers: new Map(),
  zoneLayer: null,
  layer: null,
  needsFit: true,
};

const tierText = {
  priority: "Priority review",
  reserve: "Reserve watch",
  routine: "Routine coverage",
};

const zonePalette = [
  "#806ab7",
  "#2f8d83",
  "#b07231",
  "#5c7faa",
  "#9a5b7c",
  "#697a3e",
  "#6f6f8f",
  "#b85c4b",
  "#4f8f5f",
  "#9b7a2f",
  "#587a8f",
  "#7e6a52",
  "#8b6fb0",
  "#537c75",
];

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

function mapZoom() {
  return mapState.map ? mapState.map.getZoom() : 11;
}

function markerZoomProfile() {
  const zoom = mapZoom();
  if (zoom <= 8) return { scale: 0.34, opacity: 0.58, stroke: 0.65 };
  if (zoom <= 9) return { scale: 0.42, opacity: 0.62, stroke: 0.75 };
  if (zoom <= 10) return { scale: 0.52, opacity: 0.68, stroke: 0.85 };
  if (zoom <= 11) return { scale: 0.72, opacity: 0.74, stroke: 0.95 };
  return { scale: 1, opacity: 0.78, stroke: 1 };
}

function zoneZoomProfile() {
  const zoom = mapZoom();
  if (zoom <= 8) return { weight: 3.6, opacity: 0.95, fill: 0.11 };
  if (zoom <= 9) return { weight: 3.1, opacity: 0.9, fill: 0.1 };
  if (zoom <= 10) return { weight: 2.6, opacity: 0.84, fill: 0.09 };
  if (zoom <= 11) return { weight: 2.1, opacity: 0.76, fill: 0.08 };
  return { weight: 1.6, opacity: 0.7, fill: 0.07 };
}

function contextPressure(area) {
  const deciles = [area.imdDecile, area.incomeDecile, area.educationDecile, area.employmentDecile].filter(Boolean);
  if (!deciles.length) return 0;
  const avgPressure = deciles.reduce((sum, decile) => sum + (11 - decile) / 10, 0) / deciles.length;
  return Math.max(0, Math.min(1, avgPressure));
}

function zoneColor(index) {
  return zonePalette[index % zonePalette.length];
}

const teammateClusteringCenters = [
  // Same structure as dataShort/input.csv: latitude, longitude, fake LSOA weight.
  // The fake LSOAs pull the final weighted centres toward selected logistical points.
  { lat: 51.5074, lon: -0.1278, weight: 100000000 },
  { lat: 52.4862, lon: -1.8904, weight: 100000000 },
  { lat: 53.4808, lon: -2.2426, weight: 100000000 },
];

function getTeammateClusteringCenters() {
  const supplied = data.meta?.clusteringCenters || [];
  const valid = supplied
    .map((center) => ({
      lat: Number(center.lat),
      lon: Number(center.lon),
      weight: Number(center.weight),
    }))
    .filter(
      (center) =>
        Number.isFinite(center.lat) &&
        Number.isFinite(center.lon) &&
        Number.isFinite(center.weight) &&
        center.weight > 0
    );
  return valid.length ? valid : teammateClusteringCenters;
}

function teammateCrimeWeight(area) {
  return Math.max(1, Math.round(Number(area.recent12Incidents || area.predictedDemand || 1)));
}

function stableHash(value) {
  let hash = 2166136261;
  String(value).split("").forEach((char) => {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  });
  return hash >>> 0;
}

function deterministicTeammateOrder(areas) {
  return areas
    .slice()
    .sort((a, b) => stableHash(a.code) - stableHash(b.code));
}

function teammateWeightingFunction(crimeCount) {
  return Number(crimeCount || 0);
}

function teammateDistance(a, b) {
  return Math.sqrt((Number(a.lat) - Number(b.lat)) ** 2 + (Number(a.lon) - Number(b.lon)) ** 2);
}

function teammateTotalDistance(center, group) {
  return group.reduce((total, lsoa) => {
    const distance = teammateDistance(center, lsoa);
    return total + distance * teammateWeightingFunction(lsoa.cC);
  }, 0);
}

function teammateGradient(center, group) {
  return group.reduce(
    (gradient, lsoa) => {
      const distance = teammateDistance(center, lsoa);
      let coefficient = 0;
      if (distance >= 0.0000000001) {
        coefficient = teammateWeightingFunction(lsoa.cC) / distance;
      }
      gradient.lat += coefficient * (2 * center.lat - 2 * lsoa.lat);
      gradient.lon += coefficient * (2 * center.lon - 2 * lsoa.lon);
      return gradient;
    },
    { lat: 0, lon: 0 }
  );
}

function teammateNormalizeGradient(gradient) {
  const length = Math.sqrt(gradient.lat ** 2 + gradient.lon ** 2);
  if (!length || !Number.isFinite(length)) return { lat: 0, lon: 0 };
  return { lat: gradient.lat / length, lon: gradient.lon / length };
}

function teammateLogBase(base, value) {
  return Math.log(value) / Math.log(base);
}

function teammateGradientDescentHalfDecay(center, newLSOA, group, totalWeight) {
  const targetPrecision = 0.00001;
  let currLat = center.lat;
  let currLon = center.lon;
  const estShift =
    teammateDistance(center, newLSOA) * teammateWeightingFunction(newLSOA.cC) /
    (Number(totalWeight || 0) + teammateWeightingFunction(newLSOA.cC));
  let currStep = estShift / 1.5;
  const steps = Math.max(0, Math.ceil(teammateLogBase(1.5, currStep / targetPrecision)));

  for (let i = 0; i < steps; i++) {
    // This mirrors the C++ half-decay implementation, where the gradient is
    // evaluated from the original centre coordinates during the update.
    const gradient = teammateGradient(center, group);
    const normalGradient = teammateNormalizeGradient(gradient);
    currLat -= currStep * normalGradient.lat;
    currLon -= currStep * normalGradient.lon;
    currStep /= 1.5;
  }
  return { lat: currLat, lon: currLon };
}

function teammateProbeAddition(groupState, newLSOA) {
  const currentDistance = groupState.distance;
  groupState.group.push(newLSOA);
  const newCenter = teammateGradientDescentHalfDecay(
    groupState.center,
    newLSOA,
    groupState.group,
    groupState.totalWeight
  );
  const additionCost = teammateTotalDistance(newCenter, groupState.group) - currentDistance;
  groupState.group.pop();
  return { center: newCenter, additionCost };
}

function teammateDistributeToBestFit(groups, newLSOA) {
  let bestIndex = 0;
  let bestFit = { center: groups[0].center, additionCost: Infinity };

  groups.forEach((groupState, index) => {
    const fit = teammateProbeAddition(groupState, newLSOA);
    if (fit.additionCost < bestFit.additionCost) {
      bestFit = fit;
      bestIndex = index;
    }
  });

  const bestGroup = groups[bestIndex];
  bestGroup.center = bestFit.center;
  bestGroup.group.push(newLSOA);
  bestGroup.members.push(newLSOA.area);
  bestGroup.totalWeight += teammateWeightingFunction(newLSOA.cC);
  bestGroup.distance += bestFit.additionCost;
}

function weightedAverage(values, getValue, getWeight) {
  let weightedTotal = 0;
  let totalWeight = 0;
  values.forEach((value) => {
    const raw = getValue(value);
    if (raw === null || raw === undefined || raw === "") return;
    const number = Number(raw);
    const weight = Math.max(0, Number(getWeight(value) || 0));
    if (Number.isFinite(number) && weight > 0) {
      weightedTotal += number * weight;
      totalWeight += weight;
    }
  });
  return totalWeight ? weightedTotal / totalWeight : 0;
}

function sum(values, getValue) {
  return values.reduce((total, value) => total + Number(getValue(value) || 0), 0);
}

function percentileRank(sortedValues, value) {
  if (!sortedValues.length) return 0;
  let index = 0;
  while (index < sortedValues.length && sortedValues[index] <= value) index += 1;
  return index / sortedValues.length;
}

function authorityReviewTier(summary) {
  if (summary.pressureRank >= 0.78 || summary.priorityShare >= 0.14) return "priority";
  if (summary.pressureRank >= 0.52 || summary.reserveShare >= 0.05) return "reserve";
  return "routine";
}

function buildAuthoritySummaries(areas) {
  const groups = new Map();
  areas.forEach((area) => {
    const name = area.localAuthority || "Unknown area";
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name).push(area);
  });

  const summaries = Array.from(groups.entries()).map(([name, members]) => {
    const demand = sum(members, (area) => area.predictedDemand);
    const recentDemand = sum(members, (area) => area.recent12Demand);
    const incidents = sum(members, (area) => area.recent12Incidents);
    const highHarm = sum(members, (area) => area.recent12HighHarm);
    const population = sum(members, (area) => area.population);
    const priorityCount = members.filter((area) => area.tier === "priority").length;
    const reserveCount = members.filter((area) => area.tier === "reserve").length;
    const weightedDemand = (area) => Math.max(1, Number(area.predictedDemand || area.recent12Incidents || 1));
    return {
      name,
      members,
      areaCount: members.length,
      priorityCount,
      reserveCount,
      routineCount: members.length - priorityCount - reserveCount,
      demand,
      recentDemand,
      population,
      priorityShare: members.length ? priorityCount / members.length : 0,
      reserveShare: members.length ? reserveCount / members.length : 0,
      highHarmShare: incidents ? highHarm / incidents : 0,
      contextText: (() => {
        const pressure = weightedAverage(members, contextPressure, weightedDemand);
        if (pressure >= 0.65) return "High";
        if (pressure >= 0.4) return "Medium";
        return "Lower";
      })(),
      imdDecile: weightedAverage(members, (area) => area.imdDecile, weightedDemand),
      incomeDecile: weightedAverage(members, (area) => area.incomeDecile, weightedDemand),
      employmentDecile: weightedAverage(members, (area) => area.employmentDecile, weightedDemand),
      educationDecile: weightedAverage(members, (area) => area.educationDecile, weightedDemand),
      latitude: weightedAverage(members, (area) => area.latitude, weightedDemand),
      longitude: weightedAverage(members, (area) => area.longitude, weightedDemand),
      topAreas: members
        .slice()
        .sort((a, b) => b.balancedScore - a.balancedScore)
        .slice(0, 5),
    };
  });

  const pressureValues = summaries
    .map((summary) => summary.priorityCount * 3 + summary.reserveCount + summary.priorityShare * 60)
    .sort((a, b) => a - b);
  summaries.forEach((summary) => {
    summary.reviewPressure = summary.priorityCount * 3 + summary.reserveCount + summary.priorityShare * 60;
    summary.pressureRank = percentileRank(pressureValues, summary.reviewPressure);
    summary.tier = authorityReviewTier(summary);
  });

  return summaries.sort((a, b) =>
    b.reviewPressure === a.reviewPressure ? b.demand - a.demand : b.reviewPressure - a.reviewPressure
  );
}

function convexHull(points) {
  const unique = Array.from(
    new Map(
      points
        .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
        .map((p) => [`${p.lon.toFixed(6)},${p.lat.toFixed(6)}`, p])
    ).values()
  ).sort((a, b) => (a.lon === b.lon ? a.lat - b.lat : a.lon - b.lon));

  if (unique.length < 3) return unique.map((p) => [p.lat, p.lon]);

  const cross = (origin, a, b) =>
    (a.lon - origin.lon) * (b.lat - origin.lat) - (a.lat - origin.lat) * (b.lon - origin.lon);
  const lower = [];
  unique.forEach((point) => {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], point) <= 0) {
      lower.pop();
    }
    lower.push(point);
  });
  const upper = [];
  unique
    .slice()
    .reverse()
    .forEach((point) => {
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], point) <= 0) {
        upper.pop();
      }
      upper.push(point);
    });
  return lower
    .slice(0, -1)
    .concat(upper.slice(0, -1))
    .map((p) => [p.lat, p.lon]);
}

function baseAreas() {
  return state.scenario.filter(
    (area) => state.authority === "all" || area.localAuthority === state.authority
  );
}

function isNationalOverview() {
  return state.authority === "all" && !state.search.trim();
}

function visibleAreas() {
  const q = state.search.trim().toLowerCase();
  const areas = baseAreas();
  if (!q) return areas;
  return areas.filter((area) =>
    `${area.name} ${area.shortName} ${area.code} ${area.localAuthority}`.toLowerCase().includes(q)
  );
}

function visibleAuthoritySummaries() {
  const q = state.search.trim().toLowerCase();
  if (!q) return state.authoritySummaries;
  return state.authoritySummaries.filter((summary) => summary.name.toLowerCase().includes(q));
}

function selectedAuthoritySummary() {
  if (state.authority === "all") return null;
  return state.authoritySummaries.find((summary) => summary.name === state.authority) || null;
}

function hasContextFlag(area) {
  const highPressure = (decile) => Number(decile) > 0 && Number(decile) <= 2;
  return (
    highPressure(area.imdDecile) ||
    highPressure(area.incomeDecile) ||
    highPressure(area.educationDecile) ||
    highPressure(area.employmentDecile) ||
    area.repeatAttentionRisk === "High"
  );
}

function computeScenario() {
  const areas = data.areas
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
  state.authoritySummaries = buildAuthoritySummaries(state.scenario);
  if (state.selectedCode && !baseAreas().find((area) => area.code === state.selectedCode)) {
    state.selectedCode = null;
  }
}

function updateSummary() {
  const visible = visibleAreas();
  const priority = visible.filter((area) => area.tier === "priority");
  const reserve = visible.filter((area) => area.tier === "reserve");
  const routine = visible.filter((area) => area.tier === "routine");
  const localAuthorities = new Set(visible.map((area) => area.localAuthority).filter(Boolean));
  els.priorityCount.textContent = fmt(priority.length);
  els.reserveCount.textContent = fmt(reserve.length);
  els.routineCount.textContent = fmt(routine.length);
  els.zoneCount.textContent = fmt(isNationalOverview() ? visibleAuthoritySummaries().length : localAuthorities.size);
  els.shownCount.textContent = fmt(isNationalOverview() ? visibleAuthoritySummaries().length : visible.length);
  els.shownLabel.textContent = isNationalOverview()
    ? "Local authority overview"
    : state.authority === "all"
      ? "Matched LSOA areas"
      : state.authority;
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
  mapState.zoneLayer = L.layerGroup().addTo(mapState.map);
  mapState.layer = L.layerGroup().addTo(mapState.map);
  mapState.map.on("zoomend", () => {
    mapState.needsFit = false;
    renderMap();
  });
}

function authorityMarkerStyle(summary) {
  const selected = state.authority === summary.name;
  const radius = 5 + Math.sqrt(Math.max(0, summary.priorityCount + summary.reserveCount * 0.7)) * 1.25;
  return {
    radius: Math.max(6, Math.min(selected ? radius + 3 : radius, 22)),
    color: selected ? "#102025" : "#ffffff",
    weight: selected ? 3 : 1.5,
    opacity: 1,
    fillColor: tierColor(summary.tier),
    fillOpacity: selected ? 0.9 : 0.66,
  };
}

function markerStyle(area) {
  const selected = area.code === state.selectedCode;
  const profile = markerZoomProfile();
  const radius = (4 + Math.sqrt(Math.max(0, area.demandRank)) * 9) * profile.scale;
  return {
    radius: selected ? Math.max(radius + 3, 8) : Math.max(radius, 2.6),
    color: selected ? "#102025" : "#ffffff",
    weight: selected ? 3 : profile.stroke,
    opacity: 1,
    fillColor: tierColor(area.tier),
    fillOpacity: selected ? 0.95 : profile.opacity,
  };
}

function fitMapToAreas(areas) {
  if (!mapState.map || !areas.length) return;
  const points = areas
    .filter((area) => Number.isFinite(area.latitude) && Number.isFinite(area.longitude))
    .map((area) => [area.latitude, area.longitude]);
  if (!points.length) return;
  const bounds = L.latLngBounds(points);
  mapState.map.fitBounds(bounds.pad(0.12), { maxZoom: state.authority === "all" ? 7 : 12 });
}

function fitMapToSummaries(summaries) {
  if (!mapState.map || !summaries.length) return;
  const points = summaries
    .filter((summary) => Number.isFinite(summary.latitude) && Number.isFinite(summary.longitude))
    .map((summary) => [summary.latitude, summary.longitude]);
  if (!points.length) return;
  mapState.map.fitBounds(L.latLngBounds(points).pad(0.18), { maxZoom: 6 });
}

function focusSelectedArea() {
  if (!mapState.map) return;
  const area = selectedArea();
  if (!area || !Number.isFinite(area.latitude) || !Number.isFinite(area.longitude)) return;
  mapState.map.flyTo([area.latitude, area.longitude], Math.max(mapState.map.getZoom(), 13), {
    duration: 0.55,
  });
}

function renderNationalOverviewMap() {
  const summaries = visibleAuthoritySummaries();
  if (!mapState.map || !mapState.layer || !mapState.zoneLayer) return;
  els.mapTitle.textContent = "UK review overview";
  els.mapDescription.textContent =
    "Each circle is a local authority. Size shows how many areas need review; colour shows relative review pressure.";
  mapState.zoneLayer.clearLayers();
  mapState.layer.clearLayers();
  mapState.markers.clear();

  summaries
    .filter((summary) => Number.isFinite(summary.latitude) && Number.isFinite(summary.longitude))
    .slice()
    .sort((a, b) => a.reviewPressure - b.reviewPressure)
    .forEach((summary) => {
      const marker = L.circleMarker([summary.latitude, summary.longitude], authorityMarkerStyle(summary));
      marker.bindTooltip(
        `<strong>${summary.name}</strong><br>${fmt(summary.priorityCount)} priority LSOAs<br>${fmt(summary.reserveCount)} reserve-watch LSOAs<br>Total forecast: ${fmt(summary.demand, 0)}`,
        { sticky: true }
      );
      marker.on("click", () => {
        state.authority = summary.name;
        els.authoritySelect.value = summary.name;
        state.selectedCode = null;
        mapState.needsFit = true;
        renderAll();
      });
      marker.addTo(mapState.layer);
      mapState.markers.set(`authority:${summary.name}`, marker);
    });

  if (mapState.needsFit) {
    fitMapToSummaries(summaries);
    mapState.needsFit = false;
  }
}

function renderLsoaMap() {
  const areas = visibleAreas();
  const projectionAreas = areas.length ? areas : baseAreas();
  if (!mapState.map || !mapState.layer || !mapState.zoneLayer) return;
  els.mapTitle.textContent = state.authority === "all" ? "Matched LSOA review results" : `${state.authority} LSOA review`;
  els.mapDescription.textContent =
    "Red, yellow and blue points are individual LSOA-level review results. Select a point to see the reason in plain language.";
  mapState.zoneLayer.clearLayers();
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

function renderMap() {
  if (isNationalOverview()) {
    renderNationalOverviewMap();
  } else {
    renderLsoaMap();
  }
}

function selectedArea() {
  if (!state.selectedCode) return null;
  return state.scenario.find((area) => area.code === state.selectedCode) || null;
}

function mainReasons(area) {
  const reasons = [];
  if (area.tier === "priority") reasons.push("high combined review score");
  if (area.demandRank >= 0.9) reasons.push("high forecasted demand");
  if (area.uplift >= 0.15 || area.spikeZ >= 1.5) reasons.push("recent increase");
  if (area.highHarmShare >= 0.4) reasons.push("higher serious-crime share");
  if (Number(area.educationDecile) > 0 && Number(area.educationDecile) <= 2) reasons.push("education pressure");
  if (
    (Number(area.incomeDecile) > 0 && Number(area.incomeDecile) <= 2) ||
    (Number(area.employmentDecile) > 0 && Number(area.employmentDecile) <= 2)
  ) {
    reasons.push("economic pressure");
  }
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

function renderNationalOverviewPanel() {
  const topAuthorities = state.authoritySummaries.slice(0, 3).map((summary) => summary.name).join(", ");
  els.panelEyebrow.textContent = "National overview";
  els.areaName.textContent = "Start with the UK pattern";
  els.areaMeta.textContent = `${fmt(state.authoritySummaries.length)} local authorities, ${fmt(state.scenario.length)} police.uk areas`;
  els.areaTier.textContent = "Overview";
  els.areaTier.className = "tier-badge tier-zone";
  els.metricOneLabel.textContent = "Total forecasted demand";
  els.metricTwoLabel.textContent = "Priority LSOAs";
  els.metricThreeLabel.textContent = "Reserve watch";
  els.metricFourLabel.textContent = "Areas shown";
  els.areaDemand.textContent = fmt(sum(state.scenario, (area) => area.predictedDemand), 0);
  els.areaUplift.textContent = fmt(state.scenario.filter((area) => area.tier === "priority").length);
  els.areaHarm.textContent = fmt(state.scenario.filter((area) => area.tier === "reserve").length);
  els.areaContext.textContent = fmt(state.authoritySummaries.length);
  els.contextTitle.textContent = "How to read this view";
  els.contextHint.textContent = "The national view aggregates LSOAs so planners do not have to inspect thousands of points first.";
  els.detailOneLabel.textContent = "Top pressure areas";
  els.detailTwoLabel.textContent = "Map level";
  els.areaPopulation.textContent = topAuthorities || "-";
  els.areaRepeat.textContent = "Local authority";
  els.contextProfile.innerHTML = [
    `<div class="read-step"><b>1. National overview</b><span>Find local authorities with concentrated review pressure.</span></div>`,
    `<div class="read-step"><b>2. Local drill-down</b><span>Click a circle or use the dropdown to inspect LSOA-level results.</span></div>`,
    `<div class="read-step"><b>3. LSOA detail</b><span>Open a local view only when planners need to inspect individual review points.</span></div>`,
  ].join("");
  els.areaReason.textContent =
    "This view deliberately hides individual LSOA points at national scale. It is meant to show where planners should zoom in, not to make street-level deployment decisions.";
}

function renderSelectedAuthority(summary) {
  if (!summary) {
    renderNationalOverviewPanel();
    return;
  }
  const pressureText = summary.tier === "priority" ? "High pressure" : summary.tier === "reserve" ? "Medium pressure" : "Lower pressure";
  els.panelEyebrow.textContent = "Selected local authority";
  els.areaName.textContent = summary.name;
  els.areaMeta.textContent = `${fmt(summary.areaCount)} LSOA-level areas in this view`;
  els.areaTier.textContent = pressureText;
  els.areaTier.className = `tier-badge ${tierClass(summary.tier)}`;
  els.metricOneLabel.textContent = "Total forecasted demand";
  els.metricTwoLabel.textContent = "Priority LSOAs";
  els.metricThreeLabel.textContent = "Reserve watch";
  els.metricFourLabel.textContent = "Main context";
  els.areaDemand.textContent = fmt(summary.demand, 0);
  els.areaUplift.textContent = fmt(summary.priorityCount);
  els.areaHarm.textContent = fmt(summary.reserveCount);
  els.areaContext.textContent = summary.contextText;
  els.contextTitle.textContent = "Local context profile";
  els.contextHint.textContent = "Demand-weighted average deciles. Lower values mean stronger pressure.";
  els.detailOneLabel.textContent = "Population";
  els.detailTwoLabel.textContent = "Map level";
  els.areaPopulation.textContent = summary.population ? fmt(summary.population) : "No match";
  els.areaRepeat.textContent = "LSOA detail";
  els.contextProfile.innerHTML = [
    contextRow("Overall deprivation", Math.round(summary.imdDecile)),
    contextRow("Income", Math.round(summary.incomeDecile)),
    contextRow("Employment", Math.round(summary.employmentDecile)),
    contextRow("Education", Math.round(summary.educationDecile)),
  ].join("");
  els.areaReason.textContent = `${summary.name} contains ${fmt(
    summary.priorityCount
  )} priority review LSOAs and ${fmt(
    summary.reserveCount
  )} reserve-watch LSOAs. The map now shows the detailed LSOA layer for this local authority; click a point for the plain-language reason.`;
}

function renderSelectedArea() {
  const area = selectedArea();
  if (!area) {
    if (state.authority !== "all") {
      renderSelectedAuthority(selectedAuthoritySummary());
    } else {
      renderNationalOverviewPanel();
    }
    return;
  }
  const pressure = contextPressure(area);
  const pressureText = pressure >= 0.65 ? "High" : pressure >= 0.4 ? "Medium" : "Lower";
  const reasons = mainReasons(area);
  els.panelEyebrow.textContent = "Selected area";
  els.areaName.textContent = area.name;
  els.areaMeta.textContent = `${area.localAuthority} - ${area.code}`;
  els.areaTier.textContent = tierText[area.tier];
  els.areaTier.className = `tier-badge ${tierClass(area.tier)}`;
  els.metricOneLabel.textContent = "Forecasted demand";
  els.metricTwoLabel.textContent = "Recent change";
  els.metricThreeLabel.textContent = "Serious-crime share";
  els.metricFourLabel.textContent = "Social context";
  els.areaDemand.textContent = fmt(area.predictedDemand, 1);
  els.areaUplift.textContent = pct(area.uplift);
  els.areaHarm.textContent = pct(area.highHarmShare);
  els.areaContext.textContent = pressureText;
  els.contextTitle.textContent = "Local context profile";
  els.contextHint.textContent = "Lower deciles mean stronger social or economic pressure.";
  els.detailOneLabel.textContent = "Population";
  els.detailTwoLabel.textContent = "Repeated high-demand months";
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
  if (isNationalOverview()) {
    const rows = visibleAuthoritySummaries().slice(0, 14);
    els.rankingList.innerHTML = rows
      .map(
        (summary, index) => `
        <button type="button" class="rank-row" data-authority="${summary.name}">
          <span class="rank-number">${index + 1}</span>
          <span class="rank-main">
            <strong>${summary.name}</strong>
            <small>${fmt(summary.priorityCount)} priority, ${fmt(summary.reserveCount)} reserve-watch LSOAs</small>
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
        document.querySelector(".map-card").scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
    return;
  }

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
    '<option value="all">All police.uk areas</option>',
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
