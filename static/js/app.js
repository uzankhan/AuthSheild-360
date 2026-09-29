/* ============================================================
   AuthShield 360 – UI Controller (Complete with Profile Edit)
   ============================================================ */
(function () {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  let currentChallenge = null;
  let currentFactor = null;
  let otpCountdown = null;
  let devPanelTimer = null;
  let sessionTicker = null;
  let currentUser = null;

  // ============ Toast ============
  function toast(msg, type = "info") {
    const c = $("#toast-container");
    if (!c) return;
    const t = document.createElement("div");
    t.className = `toast ${type}`;
    t.textContent = msg;
    c.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // ============ Overlays ============
  function showAccessGranted() {
    showOverlay("Access Granted", "Signing you in…", 1400);
  }
  function showOtpVerified(label) {
    showOverlay(label || "OTP Verified", "Code accepted", 1000);
  }
  function showOverlay(title, subtitle, durationMs) {
    const existing = document.getElementById("status-overlay");
    if (existing) existing.remove();
    const msg = document.createElement("div");
    msg.id = "status-overlay";
    msg.className = "success-msg";
    msg.innerHTML = `
      <span class="success-icon">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 13l4 4L19 7"/>
        </svg>
      </span>
      <span><strong>${title}</strong> — ${subtitle}</span>
    `;
    document.body.appendChild(msg);
    setTimeout(() => {
      if (msg && msg.parentNode) {
        msg.style.transition = "opacity 0.3s ease, transform 0.3s ease";
        msg.style.opacity = "0";
        msg.style.transform = "translate(-50%, -50%) scale(0.95)";
        setTimeout(() => msg.remove(), 300);
      }
    }, durationMs);
  }

  // ============ Views ============
  function showView(id) {
    $$(".view").forEach((v) => v.classList.remove("active"));
    const el = $(`#${id}`);
    if (el) el.classList.add("active");
  }

  function showPage(id) {
    $$(".page").forEach((p) => p.classList.remove("active"));
    const el = $(`#page-${id}`);
    if (el) el.classList.add("active");
    $$(".nav-link").forEach((l) => l.classList.toggle("active", l.dataset.page === id));
    const sb = $("#sidebar");
    if (sb) sb.classList.remove("open");
    if (id !== "admin") stopSessionTicker();
  }

  // ============ OTP Inputs ============
  function setupOtpInputs(sel) {
    const inputs = $$(`${sel} .otp-digit`);
    inputs.forEach((inp, idx) => {
      inp.addEventListener("input", (e) => {
        const v = e.target.value.replace(/\D/g, "");
        e.target.value = v.slice(-1);
        if (v && idx < inputs.length - 1) inputs[idx + 1].focus();
      });
      inp.addEventListener("keydown", (e) => {
        if (e.key === "Backspace" && !e.target.value && idx > 0) inputs[idx - 1].focus();
      });
      inp.addEventListener("paste", (e) => {
        e.preventDefault();
        const p = (e.clipboardData || window.clipboardData)
          .getData("text").replace(/\D/g, "").slice(0, 6);
        p.split("").forEach((ch, i) => { if (inputs[i]) inputs[i].value = ch; });
        if (p.length) inputs[Math.min(p.length, 5)].focus();
      });
    });
  }
  function otpValue(sel) { return Array.from($$(sel)).map((i) => i.value).join(""); }
  function clearOtp(sel) { $$(sel).forEach((i) => (i.value = "")); }

  // ============ Login ============
  async function handleLogin(e) {
    e.preventDefault();
    const errEl = $("#error-msg");
    const lockEl = $("#lockout-msg");
    errEl.classList.add("hidden");
    lockEl.classList.add("hidden");

    const u = $("#username").value.trim();
    const p = $("#password").value;
    if (!u || !p) {
      errEl.textContent = "Please enter username and password";
      errEl.classList.remove("hidden");
      return;
    }
    const btn = $("#btn-login");
    btn.disabled = true;
    btn.textContent = "Verifying…";
    const r = await AuthClient.login(u, p);
    btn.disabled = false;
    btn.textContent = "Continue";

    if (r.data && r.data.locked) {
      lockEl.textContent = r.data.message || "Account locked";
      lockEl.classList.remove("hidden");
      return;
    }
    if (!r.ok || !r.data.ok) {
      errEl.textContent = (r.data && r.data.message) || "Access denied";
      errEl.classList.remove("hidden");
      return;
    }
    if (r.data.status === "authenticated") {
      showAccessGranted();
      setTimeout(() => enterApp(r.data.user, r.data.mode), 1400);
      return;
    }
    if (r.data.status === "otp_sent") {
      currentChallenge = r.data.challenge_token;
      currentFactor = r.data.factor;
      gotoOtpStep(r.data);
    }
  }

  function gotoOtpStep(info) {
    $("#login-form").classList.add("hidden");
    $("#otp-step").classList.toggle("hidden", info.factor !== "mobile");
    $("#email-step").classList.toggle("hidden", info.factor !== "email");
    $("#otp-error").classList.add("hidden");
    $("#email-error").classList.add("hidden");
    const sel = info.factor === "mobile" ? "#otp-inputs" : "#email-otp-inputs";
    clearOtp(sel);
    const digitSel = info.factor === "mobile" ? "#otp-inputs .otp-digit" : "#email-otp-inputs .otp-digit";
    const first = $$(digitSel)[0];
    if (first) first.focus();
    if (info.dev_otp) showDevOtpPanel(info.factor, info.dev_otp, info.destination);
    startCountdown(info.factor, info.expires_in || 300);
  }

  function startCountdown(factor, seconds) {
    if (otpCountdown) clearInterval(otpCountdown);
    const el = $(factor === "mobile" ? "#otp-timer" : "#email-timer");
    if (!el) return;
    let left = seconds;
    const tick = () => {
      el.innerHTML = `Code expires in <strong>${left}</strong>s`;
      if (left <= -30) {
        clearInterval(otpCountdown);
        el.innerHTML = `<strong style="color:var(--danger)">Expired</strong>`;
        return;
      }
      left--;
    };
    tick();
    otpCountdown = setInterval(tick, 1000);
  }

  async function handleVerifyOtp() {
    const isM = currentFactor === "mobile";
    const sel = isM ? "#otp-inputs .otp-digit" : "#email-otp-inputs .otp-digit";
    const errEl = isM ? "#otp-error" : "#email-error";
    const code = otpValue(sel);
    $(errEl).classList.add("hidden");
    if (code.length !== 6) {
      $(errEl).textContent = "Please enter the full 6-digit code";
      $(errEl).classList.remove("hidden");
      return;
    }
    const r = await AuthClient.verifyOtp(currentChallenge, code);
    if (!r.ok || !r.data.ok) {
      $(errEl).classList.add("hidden");
      toast("Verification failed. Please try again.", "error");
      clearOtp(sel);
      return;
    }
    hideDevOtpPanel();
    if (r.data.status === "otp_sent") {
      showOtpVerified("Mobile OTP Verified");
      currentChallenge = r.data.challenge_token;
      currentFactor = r.data.factor;
      setTimeout(() => gotoOtpStep(r.data), 1100);
      return;
    }
    if (r.data.status === "authenticated") {
      if (otpCountdown) clearInterval(otpCountdown);
      showOtpVerified(isM ? "Mobile OTP Verified" : "Email OTP Verified");
      setTimeout(() => {
        showAccessGranted();
        setTimeout(() => enterApp(r.data.user, r.data.mode), 1400);
      }, 1100);
    }
  }

  async function handleResend() {
    const r = await AuthClient.resendOtp();
    if (!r.ok || !r.data.ok) {
      toast((r.data && r.data.message) || "Resend failed", "error");
      return;
    }
    currentChallenge = r.data.challenge_token;
    currentFactor = r.data.factor;
    clearOtp(currentFactor === "mobile" ? "#otp-inputs" : "#email-otp-inputs");
    startCountdown(currentFactor, r.data.expires_in || 300);
    if (r.data.dev_otp) showDevOtpPanel(currentFactor, r.data.dev_otp, r.data.destination);
    toast(`New code sent to ${r.data.destination}`, "info");
  }

  function showDevOtpPanel(factor, otp, destination) {
    let panel = document.getElementById("dev-otp-panel");
    if (!panel) {
      panel = document.createElement("div");
      panel.id = "dev-otp-panel";
      document.body.appendChild(panel);
    }
    panel.innerHTML = `
      <div class="dev-otp-head">
        <span>⚡ DELIVERY FALLBACK</span>
        <button onclick="this.closest('#dev-otp-panel').remove()">×</button>
      </div>
      <div class="dev-otp-body">
        <div class="dev-otp-label">${factor.toUpperCase()} OTP → ${destination}</div>
        <div class="dev-otp-code">${otp}</div>
        <div class="dev-otp-note">SMS/Email delivery failed. Auto-hides in 5s.</div>
      </div>`;
    panel.classList.add("active");
    if (devPanelTimer) clearTimeout(devPanelTimer);
    devPanelTimer = setTimeout(() => hideDevOtpPanel(), 5000);
  }

  function hideDevOtpPanel() {
    const panel = document.getElementById("dev-otp-panel");
    if (!panel) return;
    panel.classList.remove("active");
    panel.style.transition = "opacity 0.3s ease, transform 0.3s ease";
    panel.style.opacity = "0";
    panel.style.transform = "translateY(-12px)";
    setTimeout(() => panel.remove(), 350);
    if (devPanelTimer) { clearTimeout(devPanelTimer); devPanelTimer = null; }
  }

  // ============ Enter App ============
  function enterApp(user, mode) {
    currentUser = user;
    showView("app-view");
    $("#user-display").textContent = user.display_name;
    $("#dash-name").textContent = user.display_name;
    buildNav(user.role);
    buildDashboard(user);
    loadPortalData();
    showPage("dashboard");
  }

  // ============ Navigation ============
  function buildNav(role) {
    const perms = {
      student: ["dashboard", "records", "assignments", "results", "profile", "matrix"],
      teacher: ["dashboard", "records", "assignments", "results", "students", "profile", "logs", "matrix"],
      admin:   ["dashboard", "records", "assignments", "results", "admin", "students", "profile", "logs", "matrix"],
    }[role] || [];

    const labels = {
      dashboard: "Dashboard",
      records: "Records",
      assignments: "Assignments",
      results: "Results",
      admin: "Admin",
      students: "Students",
      profile: "Profile",
      logs: "Monitoring",
      matrix: "Test Matrix",
    };

    const nav = $("#main-nav");
    nav.innerHTML = "";
    perms.forEach((id) => {
      const b = document.createElement("button");
      b.className = "nav-link" + (id === "dashboard" ? " active" : "");
      b.dataset.page = id;
      b.textContent = labels[id];
      b.addEventListener("click", () => {
        if (id === "logs") loadLogs();
        if (id === "admin") loadAdminPanel();
        if (id === "matrix") loadTestMatrix();
        if (id === "profile") loadProfile();
        if (id === "students") loadTeacherStudents();
        showPage(id);
      });
      nav.appendChild(b);
    });
  }

  // ============ Dashboard ============
  function buildDashboard(user) {
    $("#dash-cards").innerHTML = `
      <div class="card"><h3>Role</h3><p class="stat">${escapeHtml(user.role)}</p></div>
      <div class="card"><h3>Email</h3><p>${escapeHtml(user.email)}</p></div>
      <div class="card"><h3>Mobile</h3><p>${escapeHtml(user.mobile)}</p></div>
    `;
    const rows = buildProfileRows(user);
    $("#session-info").innerHTML = rows
      .map(([k, v]) => `<li><strong>${escapeHtml(k)}</strong> ${escapeHtml(String(v))}</li>`)
      .join("");
  }

  function buildProfileRows(user) {
    const rows = [
      ["Username", user.username],
      ["Full Name", user.display_name],
      ["Role", capitalize(user.role)],
    ];
    if (user.role === "student") {
      rows.push(["Class", user.class_name || "—"]);
      rows.push(["Course", "Science (Pre-Engineering)"]);
      rows.push(["School ID", `AS-${String(user.id || 0).padStart(4, "0")}`]);
      rows.push(["Enrollment", "2024"]);
      rows.push(["Section", "A"]);
    } else if (user.role === "teacher") {
      rows.push(["Department", "Computer Science"]);
      rows.push(["Employee ID", `T-${String(user.id || 0).padStart(4, "0")}`]);
      rows.push(["Designation", "Senior Instructor"]);
      rows.push(["Joined", "2022"]);
    } else if (user.role === "admin") {
      rows.push(["Designation", "Principal / Administrator"]);
      rows.push(["Employee ID", `A-${String(user.id || 0).padStart(4, "0")}`]);
      rows.push(["Department", "Administration"]);
      rows.push(["Access Level", "Full System Control"]);
    }
    rows.push(["Email", user.email]);
    rows.push(["Mobile", user.mobile]);
    return rows;
  }
  function capitalize(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ""; }

  // ============ Portal Data ============
  async function loadPortalData() {
    const [rec, asg, res] = await Promise.all([
      AuthClient.records(), AuthClient.assignments(), AuthClient.results(),
    ]);
    if (rec.ok && rec.data.ok) {
      $("#records-table tbody").innerHTML = rec.data.data.map((r) =>
        `<tr><td>${escapeHtml(r.id)}</td><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.class)}</td><td>${escapeHtml(r.attendance)}</td><td>${escapeHtml(r.status)}</td></tr>`
      ).join("");
    }
    if (asg.ok && asg.data.ok) {
      $("#assignments-list").innerHTML = asg.data.data.map((a) =>
        `<div class="card"><h3>${escapeHtml(a.title)}</h3><p>Due: ${escapeHtml(a.due)} · ${escapeHtml(a.for)}</p><p><strong>${escapeHtml(a.status)}</strong></p></div>`
      ).join("");
    }
    if (res.ok && res.data.ok) {
      $("#results-table tbody").innerHTML = res.data.data.map((r) =>
        `<tr><td>${escapeHtml(r.student)}</td><td>${escapeHtml(r.subject)}</td><td>${escapeHtml(String(r.score))}</td><td>${escapeHtml(r.grade)}</td></tr>`
      ).join("");
    }
  }

  // ============ Profile (self) ============
  async function loadProfile() {
    const r = await AuthClient.getProfile();
    if (!r.ok || !r.data.ok) {
      toast("Unable to load profile", "error");
      return;
    }
    const u = r.data.user;
    $("#pf-username").value = u.username || "";
    $("#pf-display-name").value = u.display_name || "";
    $("#pf-email").value = u.email || "";
    $("#pf-mobile").value = u.mobile || "";
    $("#pf-class").value = u.class_name || "";
    $("#pf-role").value = u.role || "";
    $("#pf-password").value = "";
    $("#profile-msg").classList.add("hidden");
  }

  async function handleProfileSubmit(e) {
    e.preventDefault();
    const msgEl = $("#profile-msg");
    msgEl.classList.add("hidden");

    const payload = {
      username: $("#pf-username").value.trim(),
      display_name: $("#pf-display-name").value.trim(),
      email: $("#pf-email").value.trim(),
      mobile: $("#pf-mobile").value.trim(),
    };

    const role = $("#pf-role").value;
    if (role === "student") {
      payload.class_name = $("#pf-class").value.trim() || null;
    }

    const pw = $("#pf-password").value;
    if (pw) payload.password = pw;

    const r = await AuthClient.updateProfile(payload);
    if (!r.ok || !r.data.ok) {
      msgEl.textContent = (r.data && r.data.message) || "Update failed";
      msgEl.classList.remove("hidden");
      return;
    }

    // Refresh current user
    currentUser = r.data.user;
    $("#user-display").textContent = currentUser.display_name;
    $("#dash-name").textContent = currentUser.display_name;
    buildDashboard(currentUser);
    toast("Profile updated successfully", "success");
    $("#pf-password").value = "";
  }

  // ============ Logs ============
  async function loadLogs() {
    const r = await AuthClient.adminLogs();
    const tb = $("#logs-table tbody");
    if (!r.ok || !r.data.ok) {
      tb.innerHTML = `<tr><td colspan="8" style="text-align:center">Access denied</td></tr>`;
      return;
    }
    if (!r.data.data.length) {
      tb.innerHTML = `<tr><td colspan="8" style="text-align:center">No events</td></tr>`;
      return;
    }
    tb.innerHTML = r.data.data.map((l) => {
      const cls = l.result === "SUCCESS" ? "log-success"
                : (l.result === "FAIL" || l.result === "LOCKED") ? "log-fail"
                : "log-info";
      return `
        <tr>
          <td>${new Date(l.time).toLocaleString()}</td>
          <td>${escapeHtml(l.user)}</td>
          <td>${escapeHtml(l.role)}</td>
          <td>${escapeHtml(l.action)}</td>
          <td>${escapeHtml(l.factor)}</td>
          <td><span class="ip-cell">${escapeHtml(l.ip || "—")}</span></td>
          <td><span class="log-result ${cls}">${escapeHtml(l.result)}</span></td>
          <td>${escapeHtml(l.details)}</td>
        </tr>`;
    }).join("");
  }

  // ============ Admin Panel ============
  function setupAdminTabs() {
    $$(".admin-tab").forEach((tab) => {
      tab.addEventListener("click", () => {
        $$(".admin-tab").forEach((t) => t.classList.remove("active"));
        $$(".admin-tab-content").forEach((c) => c.classList.remove("active"));
        tab.classList.add("active");
        const target = $(`#admin-tab-${tab.dataset.tab}`);
        if (target) target.classList.add("active");
      });
    });
  }

  async function loadAdminPanel() {
    await Promise.all([loadAdminStats(), loadUsers(), loadSessions()]);
  }

  async function loadAdminStats() {
    const r = await AuthClient.adminOverview();
    if (!r.ok || !r.data.ok) return;
    const d = r.data.data;
    $("#admin-stats").innerHTML = `
      <div class="card"><h3>Total Users</h3><p class="stat">${d.total_users}</p></div>
      <div class="card"><h3>Students</h3><p class="stat">${d.students}</p></div>
      <div class="card"><h3>Teachers</h3><p class="stat">${d.teachers}</p></div>
      <div class="card"><h3>Admins</h3><p class="stat">${d.admins}</p></div>
      <div class="card"><h3>Active Sessions</h3><p class="stat">${d.active_sessions}</p></div>
      <div class="card"><h3>System Status</h3><p>🟢 Operational</p></div>
    `;
  }

  async function loadUsers() {
    const r = await AuthClient.adminListUsers();
    const tb = $("#users-table tbody");
    if (!r.ok || !r.data.ok) {
      tb.innerHTML = `<tr><td colspan="7">Access denied</td></tr>`;
      return;
    }
    tb.innerHTML = r.data.data.map((u) => `
      <tr>
        <td>${escapeHtml(u.username)}</td>
        <td>${escapeHtml(u.display_name)}</td>
        <td>${escapeHtml(u.role)}</td>
        <td>${escapeHtml(u.class_name || "—")}</td>
        <td>${escapeHtml(u.email)}</td>
        <td>${u.last_login ? new Date(u.last_login).toLocaleString() : "—"}</td>
        <td class="action-cell">
          <button class="mini-btn" data-act="edit" data-id="${u.id}">Edit</button>
          <button class="mini-btn danger" data-act="logout" data-id="${u.id}">Force Logout</button>
          <button class="mini-btn danger" data-act="delete" data-id="${u.id}">Delete</button>
        </td>
      </tr>`).join("");

    // Cache all users for edit modal
    window.__usersCache = {};
    r.data.data.forEach((u) => { window.__usersCache[u.id] = u; });

    tb.querySelectorAll(".mini-btn").forEach((b) => {
      b.addEventListener("click", async () => {
        const id = b.dataset.id;
        const act = b.dataset.act;
        if (act === "delete") {
          if (!confirm("Delete this user?")) return;
          const res = await AuthClient.adminDeleteUser(id);
          if (res.ok && res.data.ok) {
            toast("User deleted", "success");
            loadUsers();
            loadAdminStats();
          } else {
            toast((res.data && res.data.message) || "Delete failed", "error");
          }
        } else if (act === "logout") {
          const res = await AuthClient.adminForceLogout(id);
          if (res.ok && res.data.ok) {
            toast("User logged out everywhere", "success");
            loadSessions();
          } else {
            toast("Force logout failed", "error");
          }
        } else if (act === "edit") {
          openEditUserModal(window.__usersCache[id]);
        }
      });
    });
  }

  // ============ Edit User Modal ============
  let editingUser = null;

  function openEditUserModal(user) {
    if (!user) return;
    editingUser = user;
    $("#eu-id").value = user.id;
    $("#eu-username").value = user.username || "";
    $("#eu-display").value = user.display_name || "";
    $("#eu-email").value = user.email || "";
    $("#eu-mobile").value = user.mobile || "";
    $("#eu-role").value = user.role || "student";
    $("#eu-class").value = user.class_name || "";
    $("#eu-password").value = "";
    $("#edit-user-msg").classList.add("hidden");
    $("#edit-user-modal").classList.remove("hidden");
  }

  function closeEditUserModal() {
    $("#edit-user-modal").classList.add("hidden");
    editingUser = null;
  }

  async function handleEditUserSubmit(e) {
    e.preventDefault();
    if (!editingUser) return;
    const msgEl = $("#edit-user-msg");
    msgEl.classList.add("hidden");

    const payload = {
      username: $("#eu-username").value.trim(),
      display_name: $("#eu-display").value.trim(),
      email: $("#eu-email").value.trim(),
      mobile: $("#eu-mobile").value.trim(),
      role: $("#eu-role").value,
      class_name: $("#eu-class").value.trim() || null,
    };
    const pw = $("#eu-password").value;
    if (pw) payload.password = pw;

    const r = await AuthClient.adminUpdateUser(editingUser.id, payload);
    if (!r.ok || !r.data.ok) {
      msgEl.textContent = (r.data && r.data.message) || "Update failed";
      msgEl.classList.remove("hidden");
      return;
    }
    toast("User updated successfully", "success");
    closeEditUserModal();
    loadUsers();
    loadAdminStats();
  }

  // ============ Live Duration Ticker ============
  function stopSessionTicker() {
    if (sessionTicker) { clearInterval(sessionTicker); sessionTicker = null; }
  }
  function formatDuration(totalSeconds) {
    const s = Math.max(0, totalSeconds);
    const hrs = Math.floor(s / 3600);
    const mins = Math.floor((s % 3600) / 60);
    const secs = s % 60;
    if (hrs > 0) return `${hrs}h ${mins}m ${secs}s`;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  }
  function startSessionTicker() {
    stopSessionTicker();
    sessionTicker = setInterval(() => {
      $$(".duration-live").forEach((el) => {
        const loginTime = new Date(el.dataset.login).getTime();
        if (isNaN(loginTime)) return;
        const seconds = Math.floor((Date.now() - loginTime) / 1000);
        el.textContent = formatDuration(seconds);
      });
    }, 1000);
  }

  async function loadSessions() {
    const r = await AuthClient.adminSessions();
    const tb = $("#sessions-table tbody");
    if (!r.ok || !r.data.ok) {
      tb.innerHTML = `<tr><td colspan="8" style="text-align:center">Access denied</td></tr>`;
      stopSessionTicker(); return;
    }
    if (!r.data.data.length) {
      tb.innerHTML = `<tr><td colspan="8" style="text-align:center">No active sessions</td></tr>`;
      stopSessionTicker(); return;
    }
    tb.innerHTML = r.data.data.map((s) => `
      <tr>
        <td>${escapeHtml(s.user)}</td>
        <td>${escapeHtml(s.role)}</td>
        <td><span class="ip-cell">${escapeHtml(s.ip)}</span></td>
        <td>${escapeHtml(s.mode || "—")}</td>
        <td>${new Date(s.login_time).toLocaleString()}</td>
        <td>${new Date(s.last_seen).toLocaleString()}</td>
        <td><span class="duration-live" data-login="${escapeHtml(s.login_time)}">${escapeHtml(s.duration || "0s")}</span></td>
        <td><button class="mini-btn danger" data-act="kill" data-session="${escapeHtml(s.session_id)}">Kill</button></td>
      </tr>`).join("");
    tb.querySelectorAll(".mini-btn").forEach((b) => {
      b.addEventListener("click", async () => {
        const res = await AuthClient.adminKillSession(b.dataset.session);
        if (res.ok && res.data.ok) {
          toast("Session killed", "success");
          loadSessions();
        } else { toast("Failed", "error"); }
      });
    });
    startSessionTicker();
  }

  // ============ Teacher: Manage Students ============
  async function loadTeacherStudents() {
    const r = await AuthClient.teacherListStudents();
    const tb = $("#teacher-students-table tbody");
    if (!r.ok || !r.data.ok) {
      tb.innerHTML = `<tr><td colspan="5" style="text-align:center">Access denied</td></tr>`;
      return;
    }
    if (!r.data.data.length) {
      tb.innerHTML = `<tr><td colspan="5" style="text-align:center">No students</td></tr>`;
      return;
    }
    tb.innerHTML = r.data.data.map((u) => `
      <tr>
        <td>${escapeHtml(u.username)}</td>
        <td>${escapeHtml(u.display_name)}</td>
        <td>${escapeHtml(u.class_name || "—")}</td>
        <td>${escapeHtml(u.email)}</td>
        <td class="action-cell">
          <button class="mini-btn" data-act="edit-student" data-id="${u.id}">Edit</button>
        </td>
      </tr>`).join("");

    window.__studentsCache = {};
    r.data.data.forEach((u) => { window.__studentsCache[u.id] = u; });

    tb.querySelectorAll(".mini-btn").forEach((b) => {
      b.addEventListener("click", () => {
        const user = window.__studentsCache[b.dataset.id];
        openTeacherStudentModal(user);
      });
    });
  }

  // Teacher modal reuses admin modal but only shows student fields
  let editingTeacherStudent = null;
  function openTeacherStudentModal(user) {
    if (!user) return;
    editingTeacherStudent = user;
    $("#eu-id").value = user.id;
    $("#eu-username").value = user.username || "";
    $("#eu-username").disabled = true;  // Teacher can't change username
    $("#eu-display").value = user.display_name || "";
    $("#eu-email").value = user.email || "";
    $("#eu-mobile").value = user.mobile || "";
    $("#eu-role").value = user.role || "student";
    $("#eu-role").disabled = true;  // Teacher can't change role
    $("#eu-class").value = user.class_name || "";
    $("#eu-password").value = "";
    $("#edit-user-msg").classList.add("hidden");
    $("#edit-user-modal").classList.remove("hidden");
  }

  async function handleTeacherStudentSubmit(e) {
    e.preventDefault();
    if (!editingTeacherStudent) return;
    const msgEl = $("#edit-user-msg");
    msgEl.classList.add("hidden");

    const payload = {
      display_name: $("#eu-display").value.trim(),
      email: $("#eu-email").value.trim(),
      mobile: $("#eu-mobile").value.trim(),
      class_name: $("#eu-class").value.trim() || null,
    };
    const pw = $("#eu-password").value;
    if (pw) payload.password = pw;

    const r = await AuthClient.teacherUpdateStudent(editingTeacherStudent.id, payload);
    if (!r.ok || !r.data.ok) {
      msgEl.textContent = (r.data && r.data.message) || "Update failed";
      msgEl.classList.remove("hidden");
      return;
    }
    toast("Student updated successfully", "success");
    closeEditUserModal();
    $("#eu-username").disabled = false;
    $("#eu-role").disabled = false;
    loadTeacherStudents();
  }

  async function handleAddUser() {
    const username = prompt("Username:");
    if (!username) return;
    const display_name = prompt("Full Name:", username) || username;
    const password = prompt("Password:", "Student@123") || "Student@123";
    const role = prompt("Role (student/teacher/admin):", "student") || "student";
    const class_name = role === "student"
      ? (prompt("Class (e.g., 10-A):", "10-A") || "10-A")
      : null;
    const r = await AuthClient.adminCreateUser({
      username, display_name, password, role, class_name,
    });
    if (r.ok && r.data.ok) {
      toast("User created", "success");
      loadUsers();
      loadAdminStats();
    } else {
      toast((r.data && r.data.message) || "Create failed", "error");
    }
  }

  // ============ Test Matrix ============
  async function loadTestMatrix() {
    const r = await AuthClient.adminTestMatrix();
    const tb = $("#matrix-table tbody");
    if (!r.ok || !r.data.ok) return;
    tb.innerHTML = r.data.data.map((t) => `
      <tr>
        <td>${escapeHtml(t.test_id)}</td>
        <td>${escapeHtml(t.user_role)}</td>
        <td>${escapeHtml(t.action)}</td>
        <td>${escapeHtml(t.expected)}</td>
        <td contenteditable data-test="${escapeHtml(t.test_id)}" data-field="actual">${escapeHtml(t.actual || "-")}</td>
        <td contenteditable data-test="${escapeHtml(t.test_id)}" data-field="status">${escapeHtml(t.status || "PENDING")}</td>
      </tr>`).join("");
    $$("#matrix-table [contenteditable]").forEach((cell) => {
      cell.addEventListener("blur", async () => {
        await AuthClient.updateTestMatrix(cell.dataset.test, {
          [cell.dataset.field]: cell.textContent.trim(),
        });
      });
    });
  }

  // ============ Utilities ============
  function escapeHtml(str) {
    if (str === null || str === undefined) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // ============ Splash ============
  function runSplash() {
    const splash = $("#splash-screen");
    if (!splash) { showView("login-view"); return; }
    splash.classList.add("active");
    setTimeout(() => {
      splash.classList.add("fade-out");
      setTimeout(() => {
        splash.classList.remove("active", "fade-out");
        showView("login-view");
      }, 700);
    }, 2600);
  }

  // ============ Init ============
  function init() {
    setupOtpInputs("#otp-inputs");
    setupOtpInputs("#email-otp-inputs");
    setupAdminTabs();

    $("#login-form").addEventListener("submit", handleLogin);
    $("#btn-verify-otp").addEventListener("click", handleVerifyOtp);
    $("#btn-verify-email").addEventListener("click", handleVerifyOtp);
    $("#resend-otp").addEventListener("click", handleResend);
    $("#resend-email-otp").addEventListener("click", handleResend);

    $("#btn-back-cred").addEventListener("click", () => {
      $("#otp-step").classList.add("hidden");
      $("#email-step").classList.add("hidden");
      $("#login-form").classList.remove("hidden");
    });
    $("#btn-back-otp").addEventListener("click", () => {
      $("#email-step").classList.add("hidden");
      $("#otp-step").classList.remove("hidden");
    });
    $("#toggle-pw").addEventListener("click", () => {
      const i = $("#password");
      i.type = i.type === "password" ? "text" : "password";
    });

    $("#btn-logout").addEventListener("click", async () => {
      stopSessionTicker();
      await AuthClient.logout();
      location.reload();
    });

    const btnAdd = $("#btn-add-user");
    if (btnAdd) btnAdd.addEventListener("click", handleAddUser);
    const btnRefU = $("#btn-refresh-users");
    if (btnRefU) btnRefU.addEventListener("click", loadUsers);
    const btnRefS = $("#btn-refresh-sessions");
    if (btnRefS) btnRefS.addEventListener("click", loadSessions);

    // Profile form
    const pfForm = $("#profile-form");
    if (pfForm) pfForm.addEventListener("submit", handleProfileSubmit);

    // Edit user modal
    const euForm = $("#edit-user-form");
    if (euForm) {
      euForm.addEventListener("submit", (e) => {
        // Route to correct handler based on context
        if (editingTeacherStudent) {
          handleTeacherStudentSubmit(e);
        } else {
          handleEditUserSubmit(e);
        }
      });
    }
    const mc = $("#modal-close-btn");
    if (mc) mc.addEventListener("click", () => {
      $("#eu-username").disabled = false;
      $("#eu-role").disabled = false;
      editingTeacherStudent = null;
      closeEditUserModal();
    });
    const mcan = $("#modal-cancel-btn");
    if (mcan) mcan.addEventListener("click", () => {
      $("#eu-username").disabled = false;
      $("#eu-role").disabled = false;
      editingTeacherStudent = null;
      closeEditUserModal();
    });
    // Close on outside click
    const modal = $("#edit-user-modal");
    if (modal) modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        $("#eu-username").disabled = false;
        $("#eu-role").disabled = false;
        editingTeacherStudent = null;
        closeEditUserModal();
      }
    });

    // Logs actions
    const cb = $("#btn-clear-logs");
    if (cb) cb.addEventListener("click", async () => {
      if (!confirm("Clear all logs?")) return;
      const r = await AuthClient.clearLogs();
      if (r.ok) { toast("Logs cleared", "info"); loadLogs(); }
    });

    const eb = $("#btn-export-logs");
    if (eb) eb.addEventListener("click", async () => {
      const r = await AuthClient.adminLogs();
      if (!r.ok || !r.data.ok) { toast("Export failed", "error"); return; }
      const blob = new Blob([JSON.stringify(r.data.data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "authshield360-logs.json";
      a.click();
      URL.revokeObjectURL(url);
    });

    AuthClient.session().then((r) => {
      if (r.ok && r.data && r.data.ok) {
        showView("app-view");
        enterApp(r.data.user, r.data.mode);
      } else {
        runSplash();
      }
    }).catch(() => runSplash());
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();