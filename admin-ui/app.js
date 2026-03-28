const loginCard = document.getElementById("login-card");
const dashboard = document.getElementById("dashboard");
const auditLogPage = document.getElementById("audit-log-page");
const statusEl = document.getElementById("status");

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#b42318" : "#166534";
}

function token() {
  return localStorage.getItem("adminToken") || "";
}

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (token()) {
    headers.Authorization = `Bearer ${token()}`;
  }
  headers["Content-Type"] = "application/json";

  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

function showDashboard() {
  loginCard.classList.add("hidden");
  auditLogPage.classList.add("hidden");
  dashboard.classList.remove("hidden");
}

function showLogin() {
  dashboard.classList.add("hidden");
  auditLogPage.classList.add("hidden");
  loginCard.classList.remove("hidden");
}

function showAuditLog() {
  loginCard.classList.add("hidden");
  dashboard.classList.add("hidden");
  auditLogPage.classList.remove("hidden");
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatDateTime(isoString) {
  const date = new Date(isoString.endsWith("Z") ? isoString : isoString + "Z");
  return date.toLocaleString();
}

function sinceFromWindow(windowValue) {
  if (!windowValue) return null;
  const offsets = { "1h": 60, "24h": 1440, "7d": 10080, "30d": 43200 };
  const minutes = offsets[windowValue];
  if (!minutes) return null;
  const since = new Date(Date.now() - minutes * 60 * 1000);
  return since.toISOString().split(".")[0];
}

function renderAuditRows(tbodyId, logs) {
  const tbody = document.getElementById(tbodyId);
  tbody.innerHTML = "";
  if (logs.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="4" class="audit-empty">No entries found.</td>`;
    tbody.appendChild(tr);
    return;
  }
  for (const log of logs) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${formatDateTime(log.created_at)}</td>
      <td>${escapeHtml(log.actor_email)}</td>
      <td>${escapeHtml(log.action)}</td>
      <td>${escapeHtml(log.target || "")}</td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshTokens() {
  const payload = await api("/registration-tokens");
  document.getElementById("token-list").textContent = JSON.stringify(payload, null, 2);
}

async function refreshAudit() {
  const payload = await api("/audit-logs?limit=10");
  renderAuditRows("audit-preview-body", payload.logs);
}

async function refreshFullAudit() {
  const since = sinceFromWindow(document.getElementById("audit-time-filter").value);
  const qs = since ? `?since=${encodeURIComponent(since)}` : "";
  const payload = await api(`/audit-logs${qs}`);
  renderAuditRows("audit-full-body", payload.logs);
}

async function refreshSelfHostingHealth() {
  const payload = await api("/self-hosting/health");
  document.getElementById("self-hosting-report").textContent = JSON.stringify(payload, null, 2);
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const payload = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: document.getElementById("email").value,
        password: document.getElementById("password").value,
      }),
    });
    localStorage.setItem("adminToken", payload.access_token);
    showDashboard();
    await refreshTokens();
    await refreshAudit();
    await refreshSelfHostingHealth();
    setStatus("Signed in");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("logout").addEventListener("click", () => {
  localStorage.removeItem("adminToken");
  showLogin();
  setStatus("Signed out");
});

document.getElementById("token-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/registration-tokens", {
      method: "POST",
      body: JSON.stringify({
        token: document.getElementById("invite-token").value || null,
        uses_allowed: Number(document.getElementById("invite-uses").value),
      }),
    });
    await refreshTokens();
    setStatus("Registration token created");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("deactivate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/users/deactivate", {
      method: "POST",
      body: JSON.stringify({ user_id: document.getElementById("deactivate-user").value }),
    });
    await refreshAudit();
    setStatus("User deactivated");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("reactivate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/users/reactivate", {
      method: "POST",
      body: JSON.stringify({ user_id: document.getElementById("reactivate-user").value }),
    });
    await refreshAudit();
    setStatus("User reactivated");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("reset-password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/users/reset-password", {
      method: "POST",
      body: JSON.stringify({
        user_id: document.getElementById("reset-user").value,
        new_password: document.getElementById("reset-password").value,
      }),
    });
    await refreshAudit();
    setStatus("Password reset completed");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("shutdown-room-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await api("/rooms/shutdown", {
      method: "POST",
      body: JSON.stringify({
        room_id: document.getElementById("room-id").value,
        message: document.getElementById("room-message").value,
      }),
    });
    await refreshAudit();
    setStatus("Room/space shutdown submitted");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("refresh-tokens").addEventListener("click", async () => {
  try {
    await refreshTokens();
    setStatus("Tokens refreshed");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("refresh-audit").addEventListener("click", async () => {
  try {
    await refreshAudit();
    setStatus("Audit log refreshed");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("refresh-self-hosting").addEventListener("click", async () => {
  try {
    await refreshSelfHostingHealth();
    setStatus("Self-hosting report refreshed");
  } catch (error) {
    setStatus(error.message, true);
  }
});

document.getElementById("view-full-audit").addEventListener("click", async () => {
  showAuditLog();
  try {
    await refreshFullAudit();
  } catch (error) {
    document.getElementById("audit-full-status").textContent = error.message;
  }
});

document.getElementById("back-to-dashboard").addEventListener("click", () => {
  showDashboard();
});

document.getElementById("refresh-full-audit").addEventListener("click", async () => {
  try {
    await refreshFullAudit();
    document.getElementById("audit-full-status").textContent = "Refreshed";
  } catch (error) {
    document.getElementById("audit-full-status").textContent = error.message;
  }
});

document.getElementById("audit-time-filter").addEventListener("change", async () => {
  try {
    await refreshFullAudit();
  } catch (error) {
    document.getElementById("audit-full-status").textContent = error.message;
  }
});

(async () => {
  if (!token()) {
    showLogin();
    return;
  }

  try {
    await api("/auth/me");
    showDashboard();
    await refreshTokens();
    await refreshAudit();
    await refreshSelfHostingHealth();
    setStatus("Session restored");
  } catch {
    localStorage.removeItem("adminToken");
    showLogin();
  }
})();
