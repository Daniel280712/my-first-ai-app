const map = L.map("map", { zoomControl: true }).setView([51.5074, -0.1278], 14);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

const trackLine = L.polyline([], { color: "#22c55e", weight: 4 }).addTo(map);
const marker = L.circleMarker([51.5074, -0.1278], {
  radius: 8,
  color: "#22c55e",
  fillColor: "#22c55e",
  fillOpacity: 0.9,
}).addTo(map);

let liveMode = true;
let pollTimer = null;

const statusLine = document.getElementById("status-line");
const liveBtn = document.getElementById("live-toggle");

function fmtSpeed(mps) {
  if (mps == null) return "—";
  const kmh = mps * 3.6;
  return `${kmh.toFixed(1)} km/h`;
}

function setMetrics(point, sky, lteData) {
  document.getElementById("lat").textContent = point?.lat?.toFixed(6) ?? "—";
  document.getElementById("lon").textContent = point?.lon?.toFixed(6) ?? "—";
  document.getElementById("speed").textContent = fmtSpeed(point?.speed_mps);
  document.getElementById("sats").textContent = sky?.satellites_used ?? point?.satellites_used ?? "—";
  document.getElementById("hdop").textContent = sky?.hdop ?? point?.hdop ?? "—";
  document.getElementById("rsrp").textContent =
    lteData?.rsrp_dbm != null ? `${lteData.rsrp_dbm} dBm` : lteData?.available === false ? "No modem" : "—";
}

function drawTrack(points) {
  if (!points.length) return;
  const latlngs = points.map((p) => [p.lat, p.lon]);
  trackLine.setLatLngs(latlngs);
  const last = points[points.length - 1];
  marker.setLatLng([last.lat, last.lon]);
  if (points.length > 1) {
    map.fitBounds(trackLine.getBounds(), { padding: [30, 30], maxZoom: 17 });
  } else {
    map.setView([last.lat, last.lon], 16);
  }
  setMetrics(last, null, last.lte);
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function pollLive() {
  try {
    const data = await fetchJson("/api/live");
    const track = await fetchJson("/api/track");
    const points = track.points ?? [];

    if (data.mode === "live" && data.gps?.lat != null) {
      statusLine.textContent = `Live fix · ${data.gps.source} · ${points.length} logged points`;
      setMetrics(data.gps, data.sky, data.lte);
      drawTrack(points);
    } else if (points.length) {
      statusLine.textContent = `Waiting for GPS fix · showing ${track.mode} track`;
      drawTrack(points);
    } else {
      statusLine.textContent = "No GPS fix yet — plug in USB GPS and check gpsd";
    }
  } catch (err) {
    statusLine.textContent = `Offline — ${err.message}`;
  }
}

async function loadDemo() {
  const track = await fetchJson("/api/demo");
  statusLine.textContent = "Demo mode — sample track (no Pi GPS yet)";
  drawTrack(track.points ?? []);
}

function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollLive();
  pollTimer = setInterval(pollLive, 3000);
}

liveBtn.addEventListener("click", () => {
  liveMode = !liveMode;
  liveBtn.textContent = liveMode ? "Live" : "Demo";
  liveBtn.classList.toggle("off", !liveMode);
  if (liveMode) startPolling();
  else {
    clearInterval(pollTimer);
    loadDemo();
  }
});

startPolling();
