const state = {
  selectedDate: toDateKey(new Date()),
  calMonth: new Date().getMonth(),
  calYear: new Date().getFullYear(),
  monthSchedules: [],
  daySchedules: [],
  documents: [],
  profile: null,
};

const BULAN_ID = [
  "Januari", "Februari", "Maret", "April", "Mei", "Juni",
  "Juli", "Agustus", "September", "Oktober", "November", "Desember"
];
const HARI_ID = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const CATEGORY_LABEL = {
  meeting: "Meeting",
  deep_work: "Deep Work",
  deadline: "Deadline",
  personal: "Personal",
  reminder: "Reminder",
};
const PRIORITY_LABEL = { high: "Tinggi", medium: "Sedang", low: "Rendah" };
const STATUS_LABEL = { scheduled: "Terjadwal", done: "Selesai", cancelled: "Batal" };

// --- Helpers ---
function pad(n) { return String(n).padStart(2, "0"); }

function toDateKey(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function toLocalInputValue(dtStr) {
  if (!dtStr) return "";
  return dtStr.slice(0, 16);
}

function formatTime(dtStr) {
  if (!dtStr) return "";
  return dtStr.slice(11, 16);
}

function formatReadableDate(dateKey) {
  const [y, m, d] = dateKey.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return `${HARI_ID[dt.getDay()]}, ${d} ${BULAN_ID[m - 1]} ${y}`;
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdown(md) {
  const safe = escapeHtml(md);
  const lines = safe.split("\n");
  let html = "";
  let inList = false;

  for (const rawLine of lines) {
    let line = rawLine
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*(.+?)\*/g, "<em>$1</em>");

    if (/^\s*[-*•]\s+/.test(line)) {
      if (!inList) { html += "<ul>"; inList = true; }
      html += `<li>${line.replace(/^\s*[-*•]\s+/, "")}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (/^&gt;\s*/.test(line)) {
        html += `<blockquote>${line.replace(/^&gt;\s*/, "")}</blockquote>`;
      } else if (line.trim() === "---") {
        html += `<hr style="border:none;border-top:1px solid var(--border);margin:8px 0;" />`;
      } else if (line.trim() === "") {
        html += "<br/>";
      } else {
        html += `<p style="margin:3px 0;">${line}</p>`;
      }
    }
  }
  if (inList) html += "</ul>";
  return html;
}

function showToast(message, type = "info") {
  const box = document.getElementById("toast-container");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  box.appendChild(el);
  setTimeout(() => { el.remove(); }, 4500);
}

async function api(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return data;
}

// --- Navigation ---
const TAB_TITLES = {
  dashboard: "Dashboard & Penjadwalan Cerdas",
  chat: "AI Assistant Chat (Gemini)",
  knowledge: "Knowledge Base & Dokumen SOP",
  settings: "Profil Pribadi & Pengaturan",
};

function switchTab(tabName) {
  document.querySelectorAll(".nav-item").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${tabName}`);
  });
  document.getElementById("page-title").textContent = TAB_TITLES[tabName] || "KaryawanAI";

  if (tabName === "chat") loadChatHistory();
  if (tabName === "knowledge") loadDocuments();
  if (tabName === "settings") loadSettings();
}

// --- Health & Profile ---
async function loadHealth() {
  try {
    const h = await api("/api/health");
    const dotDb = document.getElementById("dot-db");
    const txtDb = document.getElementById("status-db-text");
    dotDb.className = `dot ${h.db_connected ? "ok" : "err"}`;
    txtDb.textContent = h.db_connected ? `MySQL: ${h.database}` : "MySQL terputus";

    const dotAi = document.getElementById("dot-ai");
    const txtAi = document.getElementById("status-ai-text");
    dotAi.className = `dot ${h.gemini_configured ? "ok" : "warn"}`;
    txtAi.textContent = h.gemini_configured ? `Gemini: ${h.gemini_model}` : "Mode Lokal (Isi API Key)";
  } catch {
    document.getElementById("status-db-text").textContent = "Server tidak terjangkau";
  }
}

async function loadProfile() {
  try {
    const p = await api("/api/profile");
    state.profile = p;
    document.getElementById("sidebar-user-name").textContent = p.full_name;
    document.getElementById("sidebar-user-role").textContent = `${p.work_start} – ${p.work_end}`;
    document.getElementById("user-avatar").textContent = (p.full_name || "K").charAt(0).toUpperCase();

    document.getElementById("prof-name").value = p.full_name || "";
    document.getElementById("prof-role").value = p.role_title || "";
    document.getElementById("prof-dept").value = p.department || "";
    document.getElementById("prof-start").value = p.work_start || "08:30";
    document.getElementById("prof-end").value = p.work_end || "17:30";
    document.getElementById("prof-pref").value = p.preferences_note || "";
  } catch (err) {
    showToast(`Gagal memuat profil: ${err.message}`, "error");
  }
}

async function loadSettings() {
  await loadProfile();
  try {
    const s = await api("/api/settings/ai");
    document.getElementById("ai-key-status").value = s.gemini_configured
      ? `Terpasang (${s.gemini_key_masked})`
      : "Belum diisi — berjalan dalam Mode Lokal";
    document.getElementById("ai-model-select").value = s.gemini_model || "gemini-3.8-flash";
    document.getElementById("info-db-host").textContent = s.db_host;
    document.getElementById("info-db-name").textContent = s.db_name;
  } catch (err) {
    showToast(`Gagal memuat pengaturan AI: ${err.message}`, "error");
  }
}

// --- Dashboard, Calendar & Schedules ---
async function loadStats() {
  try {
    const st = await api(`/api/schedules/stats?target_date=${state.selectedDate}`);
    document.getElementById("stat-today-total").textContent = st.today_total;
    document.getElementById("stat-today-pending").textContent = st.today_pending;
    document.getElementById("stat-today-done").textContent = st.today_done;
    document.getElementById("stat-high").textContent = st.high_priority_pending;
    const hrs = Math.floor(st.free_minutes_today / 60);
    const mins = st.free_minutes_today % 60;
    document.getElementById("stat-free").textContent = mins ? `${hrs}j ${mins}m` : `${hrs}j`;
    document.getElementById("stat-docs").textContent = st.total_documents;
  } catch (err) {
    console.error(err);
  }
}

async function loadMonthSchedules() {
  const first = new Date(state.calYear, state.calMonth, 1);
  const last = new Date(state.calYear, state.calMonth + 1, 0);
  const fromStr = `${toDateKey(first)}T00:00:00`;
  const toStr = `${toDateKey(last)}T23:59:59`;
  try {
    state.monthSchedules = await api(`/api/schedules?date_from=${encodeURIComponent(fromStr)}&date_to=${encodeURIComponent(toStr)}`);
    renderCalendar();
  } catch (err) {
    console.error(err);
  }
}

function renderCalendar() {
  document.getElementById("cal-month-label").textContent = `${BULAN_ID[state.calMonth]} ${state.calYear}`;
  const grid = document.getElementById("cal-grid");
  grid.innerHTML = "";

  const firstDay = new Date(state.calYear, state.calMonth, 1);
  const startOffset = (firstDay.getDay() + 6) % 7; // Senin = 0
  const daysInMonth = new Date(state.calYear, state.calMonth + 1, 0).getDate();
  const prevMonthDays = new Date(state.calYear, state.calMonth, 0).getDate();
  const todayKey = toDateKey(new Date());

  const byDate = {};
  for (const s of state.monthSchedules) {
    if (s.status === "cancelled") continue;
    const key = s.start_time.slice(0, 10);
    if (!byDate[key]) byDate[key] = [];
    byDate[key].push(s);
  }

  for (let i = 0; i < 42; i++) {
    let dayNum, m = state.calMonth, y = state.calYear, isOther = false;
    if (i < startOffset) {
      dayNum = prevMonthDays - startOffset + i + 1;
      m -= 1;
      if (m < 0) { m = 11; y -= 1; }
      isOther = true;
    } else if (i >= startOffset + daysInMonth) {
      dayNum = i - (startOffset + daysInMonth) + 1;
      m += 1;
      if (m > 11) { m = 0; y += 1; }
      isOther = true;
    } else {
      dayNum = i - startOffset + 1;
    }

    const key = `${y}-${pad(m + 1)}-${pad(dayNum)}`;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "cal-day";
    if (isOther) btn.classList.add("other-month");
    if (key === todayKey) btn.classList.add("today");
    if (key === state.selectedDate) btn.classList.add("selected");

    const items = byDate[key] || [];
    const dotsHtml = items
      .slice(0, 3)
      .map((x) => `<span class="cal-dot ${x.priority === "high" ? "high" : ""}"></span>`)
      .join("");

    btn.innerHTML = `<span>${dayNum}</span><div class="cal-dots">${dotsHtml}</div>`;
    btn.addEventListener("click", () => {
      state.selectedDate = key;
      if (isOther) {
        state.calMonth = m;
        state.calYear = y;
        loadMonthSchedules();
      } else {
        renderCalendar();
      }
      loadDayAgenda();
      loadFreeSlots();
      loadStats();
    });
    grid.appendChild(btn);
  }
}

async function loadFreeSlots() {
  const dur = document.getElementById("free-slot-duration").value;
  const list = document.getElementById("free-slots-list");
  try {
    const slots = await api(`/api/schedules/free-slots?target_date=${state.selectedDate}&duration_minutes=${dur}`);
    if (!slots.length) {
      list.innerHTML = `<div class="muted-text">Tidak ada slot kosong ≥ ${dur} menit di tanggal ini.</div>`;
      return;
    }
    list.innerHTML = "";
    for (const s of slots) {
      const div = document.createElement("div");
      div.className = "slot-pill";
      div.title = "Klik untuk langsung buat jadwal di slot ini";
      div.innerHTML = `
        <span class="slot-time">${formatTime(s.start_time)} – ${formatTime(s.end_time)}</span>
        <span class="slot-dur">${s.duration_minutes} menit · + Isi</span>
      `;
      div.addEventListener("click", () => {
        openScheduleModal(null, s.start_time, s.end_time);
      });
      list.appendChild(div);
    }
  } catch (err) {
    list.innerHTML = `<div class="muted-text">Gagal memuat slot kosong.</div>`;
  }
}

async function loadDayAgenda() {
  const cat = document.getElementById("filter-category").value;
  const status = document.getElementById("filter-status").value;
  document.getElementById("selected-date-title").textContent = `Agenda — ${formatReadableDate(state.selectedDate)}`;

  const params = new URLSearchParams({
    date_from: `${state.selectedDate}T00:00:00`,
    date_to: `${state.selectedDate}T23:59:59`,
  });
  if (cat) params.append("category", cat);
  if (status) params.append("status", status);

  const list = document.getElementById("agenda-list");
  try {
    const items = await api(`/api/schedules?${params.toString()}`);
    state.daySchedules = items;
    document.getElementById("selected-date-count").textContent = `${items.length} jadwal tercatat`;

    if (!items.length) {
      list.innerHTML = `
        <div class="empty-state">
          <p>Belum ada jadwal di tanggal ini.</p>
          <p style="margin-top:6px;font-size:0.8rem;">Klik <strong>+ Tambah Jadwal</strong> atau minta langsung lewat <strong>AI Assistant</strong>!</p>
        </div>`;
      return;
    }

    list.innerHTML = "";
    for (const item of items) {
      const card = document.createElement("div");
      card.className = `agenda-item priority-${item.priority} status-${item.status}`;
      card.innerHTML = `
        <div class="agenda-time">
          ${formatTime(item.start_time)}
          <small>s/d ${formatTime(item.end_time)}</small>
        </div>
        <div>
          <div class="agenda-title">${escapeHtml(item.title)}</div>
          <div class="agenda-meta">
            <span class="badge">${CATEGORY_LABEL[item.category] || item.category}</span>
            <span class="badge badge-${item.priority}">Prioritas ${PRIORITY_LABEL[item.priority] || item.priority}</span>
            <span class="badge badge-${item.status}">${STATUS_LABEL[item.status] || item.status}</span>
            ${item.location ? `<span>📍 ${escapeHtml(item.location)}</span>` : ""}
          </div>
          ${item.description ? `<div class="agenda-desc">${escapeHtml(item.description)}</div>` : ""}
        </div>
        <div class="agenda-actions">
          ${item.status !== "done" ? `<button class="btn btn-secondary btn-xs" data-act="done" title="Tandai Selesai">✓</button>` : ""}
          <button class="btn btn-secondary btn-xs" data-act="edit" title="Edit">✎</button>
          <button class="btn btn-danger-soft btn-xs" data-act="delete" title="Hapus">🗑</button>
        </div>
      `;

      const btnDone = card.querySelector('[data-act="done"]');
      if (btnDone) {
        btnDone.addEventListener("click", async () => {
          await api(`/api/schedules/${item.id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: "done" }),
          });
          showToast(`"${item.title}" ditandai selesai!`, "success");
          refreshDashboardData();
        });
      }
      card.querySelector('[data-act="edit"]').addEventListener("click", () => openScheduleModal(item));
      card.querySelector('[data-act="delete"]').addEventListener("click", async () => {
        if (!confirm(`Hapus jadwal "${item.title}"?`)) return;
        await api(`/api/schedules/${item.id}`, { method: "DELETE" });
        showToast("Jadwal dihapus.", "info");
        refreshDashboardData();
      });
      list.appendChild(card);
    }
  } catch (err) {
    list.innerHTML = `<div class="empty-state">Gagal memuat agenda: ${escapeHtml(err.message)}</div>`;
  }
}

async function refreshDashboardData() {
  await Promise.all([loadStats(), loadMonthSchedules(), loadDayAgenda(), loadFreeSlots()]);
}

// --- Schedule Modal ---
function openScheduleModal(item = null, presetStart = null, presetEnd = null) {
  const modal = document.getElementById("schedule-modal");
  document.getElementById("modal-title").textContent = item ? "Edit Jadwal" : "Tambah Jadwal Baru";
  document.getElementById("sched-id").value = item ? item.id : "";
  document.getElementById("sched-title").value = item ? item.title : "";
  document.getElementById("sched-category").value = item ? item.category : "meeting";
  document.getElementById("sched-priority").value = item ? item.priority : "medium";
  document.getElementById("sched-status").value = item ? item.status : "scheduled";
  document.getElementById("sched-location").value = item ? (item.location || "") : "";
  document.getElementById("sched-reminder").value = item ? item.reminder_minutes : 15;
  document.getElementById("sched-desc").value = item ? (item.description || "") : "";

  if (item) {
    document.getElementById("sched-start").value = toLocalInputValue(item.start_time);
    document.getElementById("sched-end").value = toLocalInputValue(item.end_time);
  } else if (presetStart && presetEnd) {
    document.getElementById("sched-start").value = toLocalInputValue(presetStart);
    document.getElementById("sched-end").value = toLocalInputValue(presetEnd);
  } else {
    document.getElementById("sched-start").value = `${state.selectedDate}T09:00`;
    document.getElementById("sched-end").value = `${state.selectedDate}T10:00`;
  }
  modal.classList.remove("hidden");
}

function closeScheduleModal() {
  document.getElementById("schedule-modal").classList.add("hidden");
}

// --- AI Daily Briefing ---
async function triggerDailyBriefing() {
  const card = document.getElementById("briefing-card");
  const body = document.getElementById("briefing-content");
  card.classList.remove("hidden");
  body.innerHTML = "<em>Sedang menyusun ringkasan jadwal harian Anda...</em>";
  try {
    const res = await api("/api/chat/briefing");
    body.innerHTML = renderMarkdown(res.briefing || "Tidak ada ringkasan.");
  } catch (err) {
    body.textContent = `Gagal memuat briefing: ${err.message}`;
  }
}

// --- AI Chat ---
function appendChatBubble(role, content, toolActions = []) {
  const box = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;

  let toolsHtml = "";
  if (toolActions && toolActions.length) {
    toolsHtml = `<div class="tool-badges">${toolActions
      .map((t) => `<span class="tool-badge">⚙ ${escapeHtml(t.summary)}</span>`)
      .join("")}</div>`;
  }

  row.innerHTML = `
    ${toolsHtml}
    <div class="msg-bubble markdown-body">${role === "assistant" ? renderMarkdown(content) : escapeHtml(content).replace(/\n/g, "<br/>")}</div>
  `;
  box.appendChild(row);
  box.scrollTop = box.scrollHeight;
  return row;
}

async function loadChatHistory() {
  const box = document.getElementById("chat-messages");
  try {
    const rows = await api("/api/chat/history");
    box.innerHTML = "";
    if (!rows.length) {
      appendChatBubble(
        "assistant",
        "Halo! Saya **KaryawanAI**, asisten pribadi penjadwalan & SOP Anda.\n\nCoba ketik perintah seperti:\n- *\"Jadwalkan meeting evaluasi besok jam 10:00 sampai 11:00 prioritas tinggi\"*\n- *\"Cari jam kosong hari ini untuk deep work\"*\n- *\"Bagaimana SOP pengajuan cuti tahunan?\"*"
      );
      return;
    }
    for (const r of rows) {
      appendChatBubble(r.role, r.content, r.tool_actions || []);
    }
  } catch (err) {
    showToast(`Gagal memuat riwayat chat: ${err.message}`, "error");
  }
}

async function sendChatMessage(text) {
  const clean = text.trim();
  if (!clean) return;

  appendChatBubble("user", clean);
  const thinking = appendChatBubble("assistant", "*Sedang berpikir & mengecek data Anda...*");

  try {
    const res = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: clean, session_id: "default" }),
    });
    thinking.remove();
    appendChatBubble("assistant", res.reply, res.tool_actions || []);
    if (res.schedules_modified) {
      showToast("Jadwal Anda diperbarui otomatis oleh AI!", "success");
      refreshDashboardData();
    }
  } catch (err) {
    thinking.remove();
    appendChatBubble("assistant", `Maaf, terjadi kesalahan: \`${err.message}\``);
  }
}

// --- Knowledge Base ---
async function loadDocuments(q = "") {
  const list = document.getElementById("kb-list");
  try {
    const url = q ? `/api/knowledge?q=${encodeURIComponent(q)}` : "/api/knowledge";
    const docs = await api(url);
    state.documents = docs;

    if (!docs.length) {
      list.innerHTML = `<div class="empty-state">Belum ada dokumen SOP atau catatan tersimpan.</div>`;
      return;
    }
    list.innerHTML = "";
    for (const d of docs) {
      const el = document.createElement("div");
      el.className = "kb-item";
      const snippet = d.content.length > 180 ? `${d.content.slice(0, 180)}...` : d.content;
      el.innerHTML = `
        <div>
          <div class="kb-item-title">${escapeHtml(d.title)}</div>
          <div class="agenda-meta">
            <span class="badge">${escapeHtml(d.category)}</span>
            ${d.filename ? `<span>📎 ${escapeHtml(d.filename)}</span>` : ""}
          </div>
          <div class="kb-item-snippet">${escapeHtml(snippet)}</div>
        </div>
        <div class="kb-item-actions">
          <button class="btn btn-secondary btn-xs" data-act="view">Lihat</button>
          <button class="btn btn-danger-soft btn-xs" data-act="delete">Hapus</button>
        </div>
      `;
      el.querySelector('[data-act="view"]').addEventListener("click", () => {
        document.getElementById("doc-modal-title").textContent = d.title;
        document.getElementById("doc-modal-cat").textContent = d.category;
        document.getElementById("doc-modal-content").textContent = d.content;
        document.getElementById("doc-modal").classList.remove("hidden");
      });
      el.querySelector('[data-act="delete"]').addEventListener("click", async () => {
        if (!confirm(`Hapus dokumen "${d.title}"?`)) return;
        await api(`/api/knowledge/${d.id}`, { method: "DELETE" });
        showToast("Dokumen dihapus.", "info");
        loadDocuments(document.getElementById("kb-search").value);
        loadStats();
      });
      list.appendChild(el);
    }
  } catch (err) {
    list.innerHTML = `<div class="empty-state">Gagal memuat dokumen: ${escapeHtml(err.message)}</div>`;
  }
}

// --- Event Listeners ---
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("page-date-label").textContent = formatReadableDate(state.selectedDate);

  // Nav tabs
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });

  // Calendar nav
  document.getElementById("cal-prev").addEventListener("click", () => {
    state.calMonth -= 1;
    if (state.calMonth < 0) { state.calMonth = 11; state.calYear -= 1; }
    loadMonthSchedules();
  });
  document.getElementById("cal-next").addEventListener("click", () => {
    state.calMonth += 1;
    if (state.calMonth > 11) { state.calMonth = 0; state.calYear += 1; }
    loadMonthSchedules();
  });
  document.getElementById("cal-today").addEventListener("click", () => {
    const now = new Date();
    state.selectedDate = toDateKey(now);
    state.calMonth = now.getMonth();
    state.calYear = now.getFullYear();
    refreshDashboardData();
  });

  // Filters & Free slots duration
  document.getElementById("filter-category").addEventListener("change", loadDayAgenda);
  document.getElementById("filter-status").addEventListener("change", loadDayAgenda);
  document.getElementById("free-slot-duration").addEventListener("change", loadFreeSlots);

  // Briefing
  document.getElementById("btn-briefing").addEventListener("click", () => {
    switchTab("dashboard");
    triggerDailyBriefing();
  });
  document.getElementById("btn-close-briefing").addEventListener("click", () => {
    document.getElementById("briefing-card").classList.add("hidden");
  });

  // Quick AI Bar on Dashboard
  document.getElementById("quick-ai-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("quick-ai-input");
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    switchTab("chat");
    await loadChatHistory();
    await sendChatMessage(msg);
  });

  // Schedule Modal
  document.getElementById("btn-open-new-schedule").addEventListener("click", () => openScheduleModal(null));
  document.getElementById("btn-close-modal").addEventListener("click", closeScheduleModal);
  document.getElementById("btn-cancel-modal").addEventListener("click", closeScheduleModal);

  document.getElementById("schedule-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("sched-id").value;
    const payload = {
      title: document.getElementById("sched-title").value.trim(),
      start_time: document.getElementById("sched-start").value,
      end_time: document.getElementById("sched-end").value,
      category: document.getElementById("sched-category").value,
      priority: document.getElementById("sched-priority").value,
      status: document.getElementById("sched-status").value,
      location: document.getElementById("sched-location").value.trim(),
      reminder_minutes: Number(document.getElementById("sched-reminder").value || 15),
      description: document.getElementById("sched-desc").value.trim(),
    };
    try {
      const res = await api(id ? `/api/schedules/${id}` : "/api/schedules", {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      closeScheduleModal();
      if (res.has_conflict) {
        const names = res.conflicts.map((c) => c.title).join(", ");
        showToast(`Jadwal disimpan, tapi BENTROK dengan: ${names}`, "warn");
      } else {
        showToast(id ? "Jadwal berhasil diperbarui!" : "Jadwal baru berhasil disimpan!", "success");
      }
      state.selectedDate = payload.start_time.slice(0, 10);
      refreshDashboardData();
    } catch (err) {
      showToast(`Gagal menyimpan jadwal: ${err.message}`, "error");
    }
  });

  // Chat Form & Quick Prompts
  const chatInput = document.getElementById("chat-input");
  document.getElementById("chat-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const val = chatInput.value;
    chatInput.value = "";
    await sendChatMessage(val);
  });
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      document.getElementById("chat-form").requestSubmit();
    }
  });
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => sendChatMessage(chip.dataset.prompt));
  });
  document.getElementById("btn-clear-chat").addEventListener("click", async () => {
    if (!confirm("Hapus semua riwayat percakapan chat?")) return;
    await api("/api/chat/history", { method: "DELETE" });
    loadChatHistory();
    showToast("Riwayat chat dibersihkan.", "info");
  });

  // Knowledge Base Sub-tabs & Forms
  document.querySelectorAll(".sub-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".sub-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const mode = btn.dataset.kbMode;
      document.getElementById("kb-upload-form").classList.toggle("hidden", mode !== "upload");
      document.getElementById("kb-manual-form").classList.toggle("hidden", mode !== "manual");
    });
  });

  document.getElementById("kb-upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("kb-upload-file");
    if (!fileInput.files.length) return;
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    fd.append("title", document.getElementById("kb-upload-title").value.trim());
    fd.append("category", document.getElementById("kb-upload-category").value.trim());
    try {
      await api("/api/knowledge/upload", { method: "POST", body: fd });
      e.target.reset();
      document.getElementById("kb-upload-category").value = "SOP & Kebijakan";
      showToast("File SOP berhasil diunggah & disimpan!", "success");
      loadDocuments();
      loadStats();
    } catch (err) {
      showToast(`Upload gagal: ${err.message}`, "error");
    }
  });

  document.getElementById("kb-manual-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: document.getElementById("kb-manual-title").value.trim(),
          category: document.getElementById("kb-manual-category").value.trim(),
          content: document.getElementById("kb-manual-content").value.trim(),
        }),
      });
      e.target.reset();
      document.getElementById("kb-manual-category").value = "SOP Kerja";
      showToast("Catatan SOP berhasil disimpan!", "success");
      loadDocuments();
      loadStats();
    } catch (err) {
      showToast(`Gagal menyimpan: ${err.message}`, "error");
    }
  });

  document.getElementById("kb-search").addEventListener("input", (e) => {
    loadDocuments(e.target.value);
  });

  document.getElementById("btn-close-doc-modal").addEventListener("click", () => {
    document.getElementById("doc-modal").classList.add("hidden");
  });

  // Profile & AI Settings Forms
  document.getElementById("profile-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: document.getElementById("prof-name").value.trim(),
          role_title: document.getElementById("prof-role").value.trim(),
          department: document.getElementById("prof-dept").value.trim(),
          work_start: document.getElementById("prof-start").value,
          work_end: document.getElementById("prof-end").value,
          preferences_note: document.getElementById("prof-pref").value.trim(),
        }),
      });
      showToast("Profil pribadi berhasil diperbarui!", "success");
      loadProfile();
      loadFreeSlots();
    } catch (err) {
      showToast(`Gagal menyimpan profil: ${err.message}`, "error");
    }
  });

  document.getElementById("ai-settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const keyVal = document.getElementById("ai-key-input").value.trim();
    const modelVal = document.getElementById("ai-model-select").value;
    const payload = { gemini_model: modelVal };
    if (keyVal) payload.gemini_api_key = keyVal;
    try {
      await api("/api/settings/ai", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      document.getElementById("ai-key-input").value = "";
      showToast("Konfigurasi Gemini AI berhasil disimpan ke .env!", "success");
      loadSettings();
      loadHealth();
    } catch (err) {
      showToast(`Gagal menyimpan konfigurasi AI: ${err.message}`, "error");
    }
  });

  // Initial Load
  loadHealth();
  loadProfile();
  refreshDashboardData();
});
