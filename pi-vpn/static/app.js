const loginScreen = document.getElementById("login-screen");
const appScreen = document.getElementById("app-screen");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const peersBody = document.getElementById("peers-body");
const qrDialog = document.getElementById("qr-dialog");

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

function fmtBytes(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}

function showQr(result) {
  document.getElementById("qr-title").textContent = `Scan with WireGuard — ${result.name}`;
  document.getElementById("qr-image").src = `data:image/png;base64,${result.qr_png_base64}`;
  document.getElementById("qr-config").textContent = result.config;
  qrDialog.showModal();
}

async function refreshStatus() {
  const data = await api("/api/status");
  const server = data.server;

  document.getElementById("stat-running").textContent = server.running ? "Online" : "Offline";
  document.getElementById("stat-port").textContent = server.listen_port ?? "—";
  document.getElementById("stat-endpoint").textContent = server.endpoint ?? "Not set";
  document.getElementById("stat-connected").textContent = data.peers.filter((p) => p.connected).length;

  peersBody.innerHTML = "";
  const names = new Set(data.peers.map((p) => p.name));

  for (const peer of data.peers) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${peer.name}</td>
      <td>${peer.allowed_ip ?? "—"}</td>
      <td><span class="badge ${peer.connected ? "ok" : "off"}">${peer.connected ? "Connected" : "Idle"}</span></td>
      <td>${peer.last_handshake ?? "Never"}</td>
      <td>↓ ${fmtBytes(peer.rx_bytes)} · ↑ ${fmtBytes(peer.tx_bytes)}</td>
      <td><button class="danger" data-delete="${peer.name}">Remove</button></td>
    `;
    peersBody.appendChild(tr);
  }

  for (const name of data.saved_clients) {
    if (names.has(name)) continue;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${name}</td>
      <td>—</td>
      <td><span class="badge off">Not connected yet</span></td>
      <td>—</td>
      <td>—</td>
      <td>
        <button class="ghost" data-qr="${name}">QR</button>
        <button class="danger" data-delete="${name}">Remove</button>
      </td>
    `;
    peersBody.appendChild(tr);
  }

  if (!data.peers.length && !data.saved_clients.length) {
    peersBody.innerHTML = `<tr><td colspan="6" class="muted">No clients yet — add your Pixel 5 above.</td></tr>`;
  }
}

async function loadSettings() {
  const settings = await api("/api/settings");
  document.getElementById("endpoint").value = settings.endpoint || "";
}

async function boot() {
  const me = await api("/api/me");
  if (me.authenticated) {
    loginScreen.classList.add("hidden");
    appScreen.classList.remove("hidden");
    await loadSettings();
    await refreshStatus();
    setInterval(refreshStatus, 10000);
  } else {
    appScreen.classList.add("hidden");
    loginScreen.classList.remove("hidden");
  }
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  try {
    await api("/api/login", {
      method: "POST",
      body: JSON.stringify({ password: document.getElementById("password").value }),
    });
    await boot();
  } catch (err) {
    loginError.textContent = err.message;
    loginError.classList.remove("hidden");
  }
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  await api("/api/logout", { method: "POST" });
  location.reload();
});

document.getElementById("refresh-btn").addEventListener("click", refreshStatus);

document.getElementById("add-client-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const errEl = document.getElementById("add-error");
  errEl.classList.add("hidden");
  try {
    const result = await api("/api/clients", {
      method: "POST",
      body: JSON.stringify({
        name: document.getElementById("client-name").value,
        dns: document.getElementById("client-dns").value,
      }),
    });
    showQr(result);
    document.getElementById("client-name").value = "";
    await refreshStatus();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  }
});

document.getElementById("settings-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("settings-msg");
  msg.classList.add("hidden");
  const payload = { endpoint: document.getElementById("endpoint").value };
  const pw = document.getElementById("new-password").value;
  if (pw) payload.dashboard_password = pw;
  await api("/api/settings", { method: "PUT", body: JSON.stringify(payload) });
  msg.textContent = "Settings saved.";
  msg.classList.remove("hidden");
  document.getElementById("new-password").value = "";
});

peersBody.addEventListener("click", async (e) => {
  const deleteName = e.target.dataset.delete;
  const qrName = e.target.dataset.qr;
  if (deleteName && confirm(`Remove client '${deleteName}'?`)) {
    await api(`/api/clients/${deleteName}`, { method: "DELETE" });
    await refreshStatus();
  }
  if (qrName) {
    const result = await api(`/api/clients/${qrName}/config`);
    showQr(result);
  }
});

document.getElementById("close-qr").addEventListener("click", () => qrDialog.close());

boot().catch(() => {
  loginScreen.classList.remove("hidden");
});
