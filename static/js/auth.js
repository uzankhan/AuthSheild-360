/* ============================================================
   AuthShield 360 – API Client
   Complete file with auth flow + portal + admin endpoints
   ============================================================ */
(function () {
  "use strict";

  const API_BASE = "/api/auth";

  // ---------- Helpers ----------
  async function getJson(url) {
    try {
      const r = await fetch(url, { credentials: "same-origin" });
      const data = await r.json().catch(() => ({}));
      return { status: r.status, ok: r.ok, data };
    } catch (e) {
      return { status: 0, ok: false, data: { ok: false, message: "Network error" } };
    }
  }

  async function postJson(path, body) {
    try {
      const r = await fetch(API_BASE + path, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      const data = await r.json().catch(() => ({}));
      return { status: r.status, ok: r.ok, data };
    } catch (e) {
      return { status: 0, ok: false, data: { ok: false, message: "Network error" } };
    }
  }

  async function postAdminJson(path, body) {
    try {
      const r = await fetch("/api/admin" + path, {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      const data = await r.json().catch(() => ({}));
      return { status: r.status, ok: r.ok, data };
    } catch (e) {
      return { status: 0, ok: false, data: { ok: false, message: "Network error" } };
    }
  }

  async function postAdminPut(path, body) {
    try {
      const r = await fetch("/api/admin" + path, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      const data = await r.json().catch(() => ({}));
      return { status: r.status, ok: r.ok, data };
    } catch (e) {
      return { status: 0, ok: false, data: { ok: false, message: "Network error" } };
    }
  }

  async function adminDelete(path) {
    try {
      const r = await fetch("/api/admin" + path, {
        method: "DELETE",
        credentials: "same-origin",
      });
      const data = await r.json().catch(() => ({}));
      return { status: r.status, ok: r.ok, data };
    } catch (e) {
      return { status: 0, ok: false, data: { ok: false, message: "Network error" } };
    }
  }

  // ============================================================
  // Public API
  // ============================================================
  window.AuthClient = {
        // ---- Self profile ----
    getProfile: () => getJson("/api/auth/profile"),
    updateProfile: (payload) => fetch("/api/auth/profile", {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(async (r) => ({ status: r.status, ok: r.ok, data: await r.json().catch(() => ({})) })),

    // ---- Teacher: students ----
    teacherListStudents: () => getJson("/api/admin/students"),
    teacherUpdateStudent: (id, payload) => fetch(`/api/admin/students/${id}`, {
      method: "PUT",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(async (r) => ({ status: r.status, ok: r.ok, data: await r.json().catch(() => ({})) })),
    
    // ---- Auth flow ----
    login: (u, p) => postJson("/login", { username: u, password: p }),
    verifyOtp: (t, o) => postJson("/verify-otp", { challenge_token: t, otp: o }),
    resendOtp: () => postJson("/resend-otp", {}),
    logout: () => postJson("/logout", {}),
    session: () => getJson("/api/auth/session"),

    // ---- Portal data ----
    records: () => getJson("/api/portal/records"),
    assignments: () => getJson("/api/portal/assignments"),
    results: () => getJson("/api/portal/results"),

        // ---- Self profile ----
    getProfile: () => getJson("/api/auth/profile"),
    updateProfile: (payload) => {
      return fetch("/api/auth/profile", {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(async (r) => ({ status: r.status, ok: r.ok, data: await r.json().catch(() => ({})) }));
    },

    // ---- Teacher: students ----
    teacherListStudents: () => getJson("/api/admin/students"),
    teacherUpdateStudent: (id, payload) => {
      return fetch(`/api/admin/students/${id}`, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(async (r) => ({ status: r.status, ok: r.ok, data: await r.json().catch(() => ({})) }));
    },

    // ---- Admin: overview & logs ----
    adminOverview: () => getJson("/api/admin/overview"),
    adminLogs: () => getJson("/api/admin/logs"),
    clearLogs: () => postAdminJson("/logs/clear", {}),

    // ---- Admin: users CRUD ----
    adminListUsers: () => getJson("/api/admin/users"),
    adminCreateUser: (payload) => postAdminJson("/users", payload),
    adminUpdateUser: (id, payload) => postAdminPut(`/users/${id}`, payload),
    adminDeleteUser: (id) => adminDelete(`/users/${id}`),
    adminForceLogout: (id) => postAdminJson(`/users/${id}/force-logout`, {}),

    // ---- Admin: sessions ----
    adminSessions: () => getJson("/api/admin/sessions"),
    adminKillSession: (sid) => postAdminJson(`/sessions/${sid}/kill`, {}),

    // ---- Admin: records CRUD ----
    adminListRecords: () => getJson("/api/admin/records"),
    adminUpdateRecord: (id, payload) => postAdminPut(`/records/${id}`, payload),
    adminDeleteRecord: (id) => adminDelete(`/records/${id}`),

    // ---- Test matrix ----
    adminTestMatrix: () => getJson("/api/admin/test-matrix"),
    updateTestMatrix: (id, payload) => postAdminJson(`/test-matrix/${id}`, payload),
  };

  console.log("[AuthShield] AuthClient loaded");
})();