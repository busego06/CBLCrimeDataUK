// Function for grabbig a certain cookie. Mostly meant for the CSRF cookie needed to post to Django
function getCookie(name) {
  return document.cookie.split("; ").find((row) => row.startsWith(name + "="))?.split("=")[1];
}

const centers = [];

// Initialize the map
const map = L.map("allocationMap", {preferCanvas: true}).setView([54.5, -3.0], 6);
// Initialize a layer for showing resulting LSOAs
const resultLayer = L.layerGroup().addTo(map);

// Grab the status span
const runStatus = document.getElementById("runStatus");

// Makes sure the standard LMB action only places markers
map.dragging.disable();

// Set source of images
L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
}).addTo(map);


// When user clicks on the map
map.on("click", (e) => {
  // Record the coordinates of the center
  const center = { lat: e.latlng.lat, lon: e.latlng.lng, weight: 1000 };
  // Push to list of centers
  centers.push(center);
  // Adds marker to the map
  const marker = L.marker(e.latlng).addTo(map);

  // Adds a slider to the marker
  const slider = Object.assign(document.createElement("input"), { type: "range", min: 0, max: 6, step: 0.01, value: 3 });
  const popup = document.createElement("div");
  const label = document.createElement("div");
  popup.append(label, slider);
  marker.bindPopup(popup);

  // Point popup refresh function
  function refresh() {
    center.weight = Math.pow(10, Number(slider.value));
    label.textContent = Math.round(Number(center.weight.toPrecision(2)));
  }
  slider.addEventListener("input", refresh);
  refresh();

  // Handle RMB clicks
  marker.on("contextmenu", (i) => {

    // Disable default functionality
    L.DomEvent.preventDefault(i.originalEvent);
    // Remove marker under the click
    map.removeLayer(marker);
    // Remove entry from centers list
    centers.splice(centers.indexOf(center), 1);
  });
});

// Function for getting colors for a group of points easily
function groupColor(group, total) {
  return `hsl(${(group * 360) / total}, 70%, 50%)`;
}

async function runClustering() {

  let response, data;

  let success = false;
  runButton.disabled = true;
  runStatus.textContent = "Clustering...";

  try {
    // Call the fetch command to the Django backend
    response = await fetch("/clusterDashboard/run/", {
      method: "POST",
      // Include content and CSRF headers
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      // Push center data into the body
      body: JSON.stringify(centers),
    });

    // Get data from the call
    data = await response.json();
    success = true;
  } catch (err) {
    runStatus.textContent = "Request Failed";

  } finally {
    runButton.disabled = false;
  }
  if(success){

    // If something goes wrong log the error
    if (!response.ok) {
      console.error(data.error, data.detail);
      runStatus.textContent = String(data.error);
      return;
    }

    // Clear past result
    resultLayer.clearLayers();
    // For each LSOA
    data.LSOAs.forEach((lsoa) => {
      // Add circular marker
      L.circleMarker([lsoa.lat, lsoa.lon], {
        // Set size and color
        radius: 4, stroke: false,
        fillColor: groupColor(lsoa.group, centers.length), fillOpacity: 0.8,
        bubblingMouseEvents: false,
      // Add to the result layer
      }).bindPopup(lsoa.code).addTo(resultLayer);
    });

    data.centers.forEach((center) => {
      L.circleMarker([center.lat, center.lon], {
        radius: 10, color: "#000", weight: 2,
        fillColor: groupColor(center.group, data.centers.length), fillOpacity: 1,
      }).bindPopup("Group center " + center.group).addTo(resultLayer);
    });


    runStatus.textContent = "Clustering Successful!";
  } else {
    runStatus.textContent = "Clustering failed";
  }
}

// Grab the button that triggers clustering
const runButton = document.getElementById("runButton");
// Bind the event to runClustering function
runButton.addEventListener("click", runClustering);

// Panning with MMB
let panning = false, lastX = 0, lastY = 0;

// Add listened for mouse down
map.getContainer().addEventListener("mousedown", (e) => {
  // Return if the button isnt MMB
  if (e.button !== 1) return;
  // If MMB, prevent default behavior
  e.preventDefault();
  // Start panning
  panning = true;
  // Record last known pos
  lastX = e.clientX; lastY = e.clientY;
});

// Panning listener
document.addEventListener("mousemove", (e) => {
  // Return if not currently panning
  if (!panning) return;
  // If mouse moved and actively panning, pan the map
  map.panBy([lastX - e.clientX, lastY - e.clientY], { animate: false });
  // Record last known positions
  lastX = e.clientX; lastY = e.clientY;
});

// Listener that stops panning on MMB release
document.addEventListener("mouseup", (e) => {
  if (e.button === 1) panning = false;
});