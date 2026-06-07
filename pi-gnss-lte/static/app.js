let map;
let marker = null;
let trackLine;
let routeLine;
let destMarker;
let baseTileLayer = null;

const layerOn = {
  tiles: true,
  route: true,
  track: true,
  pointer: true,
  destination: true,
};

let liveMode = true;
let pollTimer = null;
let navigating = false;
let destination = null;
let activeRoute = null;
let lastLiveFix = null;
let lastRerouteAt = 0;
let appConfig = { map_provider: "osm" };

const statusLine = document.getElementById("status-line");
const liveBtn = document.getElementById("live-toggle");
const navBanner = document.getElementById("nav-banner");
const searchResults = document.getElementById("search-results");

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

function makePointerIcon(heading = 0) {
  return L.divIcon({
    className: "vehicle-pointer-wrap",
    html: `<img class="vehicle-pointer" src="/static/pointer.svg" style="transform: rotate(${heading}deg)" alt="you" />`,
    iconSize: [48, 48],
    iconAnchor: [24, 24],
  });
}

function setPointer(lat, lon, trackDeg = 0) {
  const heading = trackDeg ?? 0;
  if (!marker) {
    marker = L.marker([lat, lon], { icon: makePointerIcon(heading), zIndexOffset: 1000 });
    if (layerOn.pointer) marker.addTo(map);
    return;
  }
  marker.setLatLng([lat, lon]);
  marker.setIcon(makePointerIcon(heading));
  if (layerOn.pointer && !map.hasLayer(marker)) marker.addTo(map);
}

function applyLayers() {
  const mapEl = document.getElementById("map");
  mapEl.classList.toggle("map-no-tiles", !layerOn.tiles);

  if (baseTileLayer) {
    if (layerOn.tiles && !map.hasLayer(baseTileLayer)) baseTileLayer.addTo(map);
    if (!layerOn.tiles && map.hasLayer(baseTileLayer)) map.removeLayer(baseTileLayer);
  }

  if (routeLine) routeLine.setStyle({ opacity: layerOn.route ? 0.85 : 0 });
  if (trackLine) trackLine.setStyle({ opacity: layerOn.track ? 0.7 : 0 });

  if (marker) {
    if (layerOn.pointer && !map.hasLayer(marker)) marker.addTo(map);
    if (!layerOn.pointer && map.hasLayer(marker)) map.removeLayer(marker);
  }

  if (destMarker) {
    destMarker.setOpacity(layerOn.destination && navigating ? 1 : 0);
  }
}

function setupLayerToggles() {
  document.querySelectorAll(".layer-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.layer;
      layerOn[key] = !layerOn[key];
      btn.classList.toggle("on", layerOn[key]);
      applyLayers();
    });
  });
}

function updateRawPanel(data) {
  document.getElementById("raw-nav").textContent = JSON.stringify(
    { mode: data.mode, polled_at: data.polled_at, gps: data.gps, sky: data.sky },
    null,
    2
  );
  document.getElementById("raw-lte").textContent = JSON.stringify(data.lte ?? {}, null, 2);
  document.getElementById("raw-gpsd").textContent = JSON.stringify(data.gpsd_raw ?? [], null, 2);
}

async function initMap() {
  appConfig = await fetchJson("/api/config");
  map = L.map("map", { zoomControl: true }).setView([51.5074, -0.1278], 14);

  if (appConfig.map_provider === "google" && appConfig.google_maps_api_key) {
    try {
      await loadScript(
        `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(appConfig.google_maps_api_key)}`
      );
      await loadScript(
        "https://unpkg.com/leaflet.gridlayer.googlemutant@0.14.0/dist/Leaflet.GoogleMutant.js"
      );
      baseTileLayer = L.gridLayer.googleMutant({ type: "roadmap", maxZoom: 21 }).addTo(map);
      statusLine.textContent = "Google Maps · custom GPS pointer";
    } catch (err) {
      console.warn(err);
      baseTileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: "&copy; OpenStreetMap",
        maxZoom: 19,
      }).addTo(map);
      statusLine.textContent = "Google Maps failed — using OpenStreetMap";
    }
  } else {
    baseTileLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap",
      maxZoom: 19,
    }).addTo(map);
    statusLine.textContent = "OpenStreetMap · add GOOGLE_MAPS_API_KEY for Google tiles";
  }

  trackLine = L.polyline([], { color: "#94a3b8", weight: 3, opacity: 0.7 }).addTo(map);
  routeLine = L.polyline([], { color: "#3b82f6", weight: 6, opacity: 0.85 }).addTo(map);
  destMarker = L.marker([51.5074, -0.1278], { opacity: 0, zIndexOffset: 500 }).addTo(map);
  setPointer(51.5074, -0.1278, 0);
  setupLayerToggles();
}

function fmtSpeed(mps) {
  if (mps == null) return "—";
  return `${(mps * 3.6).toFixed(1)} km/h`;
}

function fmtDist(m) {
  if (m == null) return "—";
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m / 1000).toFixed(1)} km`;
}

function fmtDuration(s) {
  if (s == null) return "—";
  const mins = Math.round(s / 60);
  if (mins < 60) return `${mins} min`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

function haversineM(lat1, lon1, lat2, lon2) {
  const R = 6371000;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function minDistToRouteM(lat, lon, geometry) {
  if (!geometry?.length) return Infinity;
  return Math.min(...geometry.map(([gLat, gLon]) => haversineM(lat, lon, gLat, gLon)));
}

function setMetrics(point, sky, lteData) {
  document.getElementById("lat").textContent = point?.lat?.toFixed(6) ?? "—";
  document.getElementById("lon").textContent = point?.lon?.toFixed(6) ?? "—";
  document.getElementById("speed").textContent = fmtSpeed(point?.speed_mps);
  document.getElementById("sats").textContent = sky?.satellites_used ?? point?.satellites_used ?? "—";
  document.getElementById("rsrp").textContent =
    lteData?.rsrp_dbm != null ? `${lteData.rsrp_dbm} dBm` : lteData?.available === false ? "No modem" : "—";
}

function updateNavUi(fix) {
  if (!navigating || !destination || !activeRoute) {
    document.getElementById("dest-dist").textContent = "—";
    return;
  }

  const distToDest = haversineM(fix.lat, fix.lon, destination.lat, destination.lon);
  document.getElementById("dest-dist").textContent = fmtDist(distToDest);

  let step = activeRoute.steps[0];
  for (const s of activeRoute.steps) {
    if (haversineM(fix.lat, fix.lon, s.lat, s.lon) > 35) {
      step = s;
      break;
    }
    step = s;
  }

  document.getElementById("nav-instruction").textContent = step.instruction;
  document.getElementById("nav-meta").textContent =
    `${fmtDist(distToDest)} to destination · ${fmtDist(step.distance_m)} to next step`;

  const offRoute = minDistToRouteM(fix.lat, fix.lon, activeRoute.geometry) > 80;
  const now = Date.now();
  if (offRoute && now - lastRerouteAt > 15000 && lastLiveFix) {
    lastRerouteAt = now;
    statusLine.textContent = "Off route — recalculating…";
    requestRoute(fix.lat, fix.lon, destination.lat, destination.lon, document.getElementById("profile").value, false);
  }
}

function drawTrack(points, follow = false) {
  if (!points.length) return;
  trackLine.setLatLngs(points.map((p) => [p.lat, p.lon]));
  const last = points[points.length - 1];
  setPointer(last.lat, last.lon, last.track_deg ?? lastLiveFix?.track_deg ?? 0);
  if (follow || navigating) {
    map.setView([last.lat, last.lon], Math.max(map.getZoom(), 16), { animate: true });
  } else if (points.length > 1 && !navigating) {
    map.fitBounds(trackLine.getBounds(), { padding: [30, 30], maxZoom: 17 });
  } else {
    map.setView([last.lat, last.lon], 16);
  }
}

function drawRoute(route) {
  routeLine.setLatLngs(route.geometry);
  destMarker.setLatLng([route.end.lat, route.end.lon]);
  applyLayers();
  map.fitBounds(routeLine.getBounds(), { padding: [40, 40], maxZoom: 16 });
}

async function fetchJson(url, options) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

async function requestRoute(fromLat, fromLon, toLat, toLon, profile, showBanner = true) {
  const route = await fetchJson("/api/route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      from_lat: fromLat,
      from_lon: fromLon,
      to_lat: toLat,
      to_lon: toLon,
      profile: profile,
    }),
  });
  activeRoute = route;
  drawRoute(route);
  if (showBanner) {
    navigating = true;
    navBanner.classList.remove("hidden");
    document.getElementById("nav-instruction").textContent = route.steps[0]?.instruction ?? "Follow the blue route";
    document.getElementById("nav-meta").textContent =
      `${fmtDist(route.distance_m)} · about ${fmtDuration(route.duration_s)}`;
    statusLine.textContent = "Navigation active — your pointer follows Pi GPS";
  }
}

async function pollLive() {
  try {
    const data = await fetchJson("/api/raw");
    updateRawPanel(data);
    const track = await fetchJson("/api/track");
    const points = track.points ?? [];

    if (data.mode === "live" && data.gps?.lat != null) {
      lastLiveFix = data.gps;
      setPointer(data.gps.lat, data.gps.lon, data.gps.track_deg ?? 0);
      if (navigating) {
        statusLine.textContent = "Navigation active — live GPS pointer";
        setMetrics(data.gps, data.sky, data.lte);
        map.setView([data.gps.lat, data.gps.lon], Math.max(map.getZoom(), 16), { animate: true });
        updateNavUi(data.gps);
      } else {
        statusLine.textContent = `Live fix · ${points.length} logged points`;
        setMetrics(data.gps, data.sky, data.lte);
        if (points.length) drawTrack(points);
        else map.setView([data.gps.lat, data.gps.lon], Math.max(map.getZoom(), 16), { animate: true });
      }
    } else if (points.length) {
      statusLine.textContent = navigating ? "Waiting for GPS fix…" : `Waiting for GPS · ${track.mode} track`;
      drawTrack(points);
    } else {
      statusLine.textContent = "No GPS fix — move GPS near a window or go outside";
    }
  } catch (err) {
    statusLine.textContent = `Offline — ${err.message}`;
  }
}

document.getElementById("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = document.getElementById("search-input").value.trim();
  if (!q) return;
  searchResults.classList.add("hidden");
  try {
    const { results } = await fetchJson(`/api/geocode?q=${encodeURIComponent(q)}`);
    if (!results.length) {
      statusLine.textContent = "No places found — try a simpler search";
      return;
    }
    if (results.length === 1) {
      await pickDestination(results[0]);
      return;
    }
    searchResults.innerHTML = "";
    results.forEach((place) => {
      const li = document.createElement("li");
      li.textContent = place.label;
      li.addEventListener("click", () => pickDestination(place));
      searchResults.appendChild(li);
    });
    searchResults.classList.remove("hidden");
  } catch (err) {
    statusLine.textContent = err.message;
  }
});

async function pickDestination(place) {
  searchResults.classList.add("hidden");
  destination = place;
  document.getElementById("search-input").value = place.label;
  const profile = document.getElementById("profile").value;
  if (!lastLiveFix) {
    statusLine.textContent = "Waiting for GPS fix to route from your position…";
    const waitForFix = setInterval(async () => {
      await pollLive();
      if (lastLiveFix) {
        clearInterval(waitForFix);
        await requestRoute(lastLiveFix.lat, lastLiveFix.lon, place.lat, place.lon, profile);
      }
    }, 2000);
    return;
  }
  await requestRoute(lastLiveFix.lat, lastLiveFix.lon, place.lat, place.lon, profile);
}

document.getElementById("stop-nav").addEventListener("click", () => {
  navigating = false;
  destination = null;
  activeRoute = null;
  navBanner.classList.add("hidden");
  routeLine.setLatLngs([]);
  applyLayers();
  document.getElementById("dest-dist").textContent = "—";
  statusLine.textContent = "Navigation stopped";
});

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollLive();
  pollTimer = setInterval(pollLive, 2000);
}

liveBtn.addEventListener("click", async () => {
  liveMode = !liveMode;
  liveBtn.textContent = liveMode ? "Live" : "Demo";
  liveBtn.classList.toggle("off", !liveMode);
  if (liveMode) startPolling();
  else {
    clearInterval(pollTimer);
    const track = await fetchJson("/api/demo");
    statusLine.textContent = "Demo mode — custom pointer on sample track";
    drawTrack(track.points ?? []);
  }
});

initMap()
  .then(startPolling)
  .catch((err) => {
    statusLine.textContent = `Map init failed — ${err.message}`;
  });
