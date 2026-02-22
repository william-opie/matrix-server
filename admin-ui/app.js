const loginCard = document.getElementById("login-card");
const dashboard = document.getElementById("dashboard");
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
  dashboard.classList.remove("hidden");
}

function showLogin() {
  dashboard.classList.add("hidden");
  loginCard.classList.remove("hidden");
}

async function refreshTokens() {
  const payload = await api("/registration-tokens");
  document.getElementById("token-list").textContent = JSON.stringify(payload, null, 2);
}

async function refreshAudit() {
  const payload = await api("/audit-logs");
  document.getElementById("audit-list").textContent = JSON.stringify(payload, null, 2);
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
