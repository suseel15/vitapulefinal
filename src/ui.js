import { summarizeMovementSamples } from "./rehab-movement.js";

const iconPaths = {
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  bell: '<path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  chevron: '<path d="m8 10 4 4 4-4"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  connect: '<path d="M8 12h8M12 8v8"/><circle cx="12" cy="12" r="9"/><path d="M5.6 5.6 8 8m8 8 2.4 2.4"/>',
  heart: '<path d="M20.5 8.8c0 5.3-8.5 10-8.5 10s-8.5-4.7-8.5-10A4.7 4.7 0 0 1 12 6.3a4.7 4.7 0 0 1 8.5 2.5Z"/>',
  home: '<path d="m3 10 9-7 9 7v10a1 1 0 0 1-1 1h-5v-7h-6v7H4a1 1 0 0 1-1-1V10Z"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8h.01"/>',
  lock: '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  moon: '<path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5a8.7 8.7 0 1 0 12 12Z"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  rehab: '<path d="M5 12h3l2-6 4 12 2-6h3"/><circle cx="12" cy="12" r="9"/>',
  search: '<circle cx="10.8" cy="10.8" r="6.3"/><path d="m16 16 4 4"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1a1.8 1.8 0 0 1-2.5 2.5l-.1-.1a1.8 1.8 0 0 0-3 .9v.2a1.8 1.8 0 0 1-3.6 0v-.2a1.8 1.8 0 0 0-3-.9l-.1.1a1.8 1.8 0 1 1-2.5-2.5l.1-.1a1.8 1.8 0 0 0-.9-3h-.2a1.8 1.8 0 0 1 0-3.6h.2a1.8 1.8 0 0 0 .9-3l-.1-.1a1.8 1.8 0 1 1 2.5-2.5l.1.1a1.8 1.8 0 0 0 3-.9v-.2a1.8 1.8 0 0 1 3.6 0v.2a1.8 1.8 0 0 0 3 .9l.1-.1a1.8 1.8 0 1 1 2.5 2.5l-.1.1a1.8 1.8 0 0 0 .9 3h.2a1.8 1.8 0 0 1 0 3.6h-.2a1.8 1.8 0 0 0-.9 3Z"/>',
  shield: '<path d="m12 3 8 3v5c0 5.2-3.3 8.2-8 10-4.7-1.8-8-4.8-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/>',
  sleep: '<path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5a8.7 8.7 0 1 0 12 12Z"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  water: '<path d="M12 3s7 7.3 7 12a7 7 0 0 1-14 0c0-4.7 7-12 7-12Z"/><path d="M9 16a3 3 0 0 0 3 3"/>',
  wellbeing: '<path d="M12 20s-7-4.1-7-9.2A4 4 0 0 1 12 8a4 4 0 0 1 7 2.8c0 5.1-7 9.2-7 9.2Z"/>',
};

export function icon(name, className = "") {
  const path = iconPaths[name] ?? iconPaths.info;
  return `<svg class="icon ${className}" viewBox="0 0 24 24" aria-hidden="true">${path}</svg>`;
}

export function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

const athleteNavigation = [
  ["home", "Home"],
  ["health", "Health"],
  ["rehab", "Rehab"],
  ["wellbeing", "Wellbeing"],
  ["connect", "Connect"],
];

const doctorNavigation = [
  ["doctor-dashboard", "Dashboard"],
  ["doctor-athletes", "Athletes"],
  ["doctor-health", "Health"],
  ["doctor-rehab", "Rehab"],
  ["doctor-reports", "Reports"],
];

const modules = {
  health: {
    eyebrow: "YOUR HEALTH",
    title: "Health",
    subtitle: "Keep the health details that support your sport in one place.",
    items: [
      ["Medical reports", "Securely upload and review your lab documents.", "health-reports"],
      ["Body map", "Add private, user-entered notes to body regions.", "health-body-map"],
      ["Biomarkers", "Review extracted measurements with their source context.", "health-biomarkers"],
      ["Health intelligence", "Evidence-linked health insights, when configured.", "health-intelligence"],
      ["Nutrition", "Record meals, hydration and your own goals.", "health-nutrition"],
      ["Medication", "Keep your medication list up to date.", "health-medication"],
      ["Anti-doping", "Review status and verified-source availability.", "health-anti-doping"],
      ["Skin screening", "Availability and limitations for skin screening.", "health-skin-screening"],
      ["Health reports", "View report drafts linked to your health data.", "health-history"],
    ],
  },
  rehab: {
    eyebrow: "YOUR REHABILITATION",
    title: "Rehab",
    subtitle: "A place for your plan, progress and return-to-sport journey.",
    items: [
      ["Today's rehab", "See the assigned exercises for today.", "rehab/today"],
      ["Program", "Review your assigned goal and configured stages.", "rehab/program"],
      ["Exercises", "Explore exercise instructions and prescriptions.", "rehab/exercises"],
      ["Movement analysis", "Review source-labelled movement signals.", "rehab/movement"],
      ["Progress", "Review completed sessions and assigned exercises.", "rehab/progress"],
      ["Functional tests", "Record supported timed tests.", "rehab/functional-tests"],
      ["Readiness", "Review a traceable rehabilitation readiness signal.", "rehab/readiness"],
      ["Return to sport", "Track progression requirements, not medical clearance.", "rehab/return-to-sport"],
      ["Recovery", "View rehab load and honest wearable availability.", "rehab/recovery"],
      ["History", "Review completed sessions.", "rehab/history"],
      ["Reports", "Review available report data contracts.", "rehab/reports"],
    ],
  },
  wellbeing: {
    eyebrow: "YOUR WELLBEING",
    title: "Wellbeing",
    subtitle: "Check in with yourself, at your own pace.",
    items: [
      ["Self check-in", "Record how you feel today.", "Check-in"],
      ["30-second camera check", "Native camera observations are planned for the Android app. No browser camera access is requested.", "Camera check"],
      ["Sleep", "Record sleep times and optional quality notes.", "Sleep"],
      ["Recovery", "Review context from recorded check-ins and sleep.", "Recovery"],
      ["History", "Review your saved wellbeing records.", "History"],
      ["Trends", "Explore patterns only when enough records exist.", "Trends"],
      ["Reports", "Create a summary from your recorded data.", "Wellbeing reports"],
    ],
  },
  connect: {
    eyebrow: "YOUR DEVICES",
    title: "Connect",
    subtitle: "Manage the sources that help tell your movement and recovery story.",
    items: [
      ["Movement device", "ESP32 · Not connected", "Movement device"],
      ["Smartwatch", "No watch connected", "Smartwatch"],
      ["Data sync", "There are no data sources to sync yet.", "Data sync"],
      ["Permissions", "Device permissions will be requested only when needed.", "Permissions"],
      ["Diagnostics", "Connection diagnostics will appear here.", "Diagnostics"],
    ],
  },
};

function brand() {
  return `<a class="brand" href="#home" data-route="home" aria-label="VitaPulse home">
    <span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32"><path d="M4 17h6l3-8 5 15 3-9h7"/></svg></span>
    <span>vita<span>pulse</span></span>
  </a>`;
}

function navLinks(current, role) {
  const links = role === "DOCTOR" ? doctorNavigation : athleteNavigation;
  const activeRoute = current.startsWith("health-") || current.startsWith("rehab/") ? current.startsWith("health-") ? "health" : "rehab" : current;
  return links.map(([route, label]) => `
    <a class="nav-link ${activeRoute === route ? "active" : ""}" href="#${route}" data-route="${route}" ${activeRoute === route ? 'aria-current="page"' : ""}>
      ${icon(route.startsWith("doctor") ? "activity" : route)}
      <span>${label}</span>
    </a>`).join("");
}

function pageName(route) {
  return ({
    home: "Home",
    health: "Health",
    rehab: "Rehab",
    wellbeing: "Wellbeing",
    connect: "Connect",
    profile: "Profile",
    settings: "Settings",
    "doctor-dashboard": "Dashboard",
    "doctor-athletes": "Athletes",
    "doctor-health": "Health",
    "doctor-rehab": "Rehab",
    "doctor-reports": "Reports",
    "health-reports": "Medical reports",
    "health-body-map": "Body map",
    "health-biomarkers": "Biomarkers",
    "health-intelligence": "Health intelligence",
    "health-nutrition": "Nutrition",
    "health-medication": "Medication",
    "health-anti-doping": "Anti-doping",
    "health-skin-screening": "Skin screening",
    "health-history": "Health reports",
    "rehab/today": "Today's rehab",
    "rehab/program": "Rehab program",
    "rehab/exercises": "Exercise library",
    "rehab/session": "Rehab session",
    "rehab/movement": "Movement analysis",
    "rehab/progress": "Rehab progress",
    "rehab/recovery": "Recovery",
    "rehab/functional-tests": "Functional tests",
    "rehab/readiness": "Rehab readiness",
    "rehab/return-to-sport": "Return to sport",
    "rehab/history": "Rehab history",
    "rehab/reports": "Rehab reports",
    detail: "Coming up",
  })[route] ?? (route.startsWith("rehab/session/") ? "Rehab session"
    : route.startsWith("rehab/exercises/") ? "Exercise details"
      : route.startsWith("rehab/functional-tests/") ? "Functional test"
        : "Home");
}

function emptyState(title, description, action = "") {
  return `<div class="empty-state">
    <span class="empty-icon">${icon("activity")}</span>
    <strong>${escapeHtml(title)}</strong>
    <p>${escapeHtml(description)}</p>
    ${action ? `<button class="text-button" type="button" data-action="${escapeHtml(action)}">Explore Home ${icon("arrow")}</button>` : ""}
  </div>`;
}

function homePage(session) {
  const name = escapeHtml(session.name.split(/\s+/)[0] || "Athlete");
  return `<section class="welcome-row">
    <div><p class="eyebrow">${new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(new Date()).toUpperCase()}</p>
      <h1>Good morning, ${name}<span class="wave" aria-hidden="true">✦</span></h1>
      <p class="welcome-subtitle">Train with awareness. Give your recovery room to work.</p>
    </div>
    <a class="profile-shortcut" href="#profile" data-route="profile" aria-label="Open profile"><span class="avatar">${escapeHtml(initials(session.name))}</span>${icon("chevron")}</a>
  </section>
  <section class="today-section" aria-labelledby="today-title">
    <div class="section-heading"><div><p class="eyebrow">YOUR DAILY CHECK-IN</p><h2 id="today-title">Today's status</h2></div><span class="quiet-tag">${icon("shield")} Athlete first</span></div>
    <article class="readiness-card">
      <div class="readiness-orbit">${icon("activity")}</div>
      <div class="readiness-copy"><span class="status-label">${icon("clock")} READY WHEN YOU ARE</span>
        <h3>Start with how you feel.</h3>
        <p>No readiness assessment is available yet. Take a moment to check in before your next session.</p>
        <button class="primary-button compact" type="button" data-route="wellbeing">Check in with yourself ${icon("arrow")}</button>
      </div>
      <div class="readiness-stamp">${icon("heart")}<span>Listen to<br />your body</span></div>
    </article>
    <div class="home-card-grid">
      <article class="home-card"><div class="home-card-top"><span class="small-icon rehab-tint">${icon("rehab")}</span><span class="soft-tag">REHAB</span></div><h3>Rehabilitation</h3><p>No program has been assigned yet. Your plan will appear here when it's ready.</p><a href="#rehab" data-route="rehab">Explore rehab ${icon("arrow")}</a></article>
      <article class="home-card"><div class="home-card-top"><span class="small-icon recovery-tint">${icon("wellbeing")}</span><span class="soft-tag">RECOVERY</span></div><h3>Make space to recover</h3><p>Recovery data isn't connected yet. Your rest deserves attention too.</p><a href="#wellbeing" data-route="wellbeing">Explore wellbeing ${icon("arrow")}</a></article>
      <article class="home-card"><div class="home-card-top"><span class="small-icon movement-tint">${icon("activity")}</span><span class="soft-tag">MOVEMENT</span></div><h3>Your movement story</h3><p>Connect a movement device when you're ready to start tracking.</p><a href="#connect" data-route="connect">Explore connections ${icon("arrow")}</a></article>
    </div>
  </section>
  <section class="quick-actions" aria-labelledby="quick-title"><div class="section-heading"><div><p class="eyebrow">A GOOD PLACE TO START</p><h2 id="quick-title">Your next step</h2></div></div>
    <div class="quick-grid">
      <button class="quick-action" data-route="health" type="button"><span class="small-icon health-tint">${icon("heart")}</span><span><strong>Keep health in context</strong><small>Your sports-health space</small></span>${icon("arrow")}</button>
      <button class="quick-action" data-route="rehab" type="button"><span class="small-icon rehab-tint">${icon("rehab")}</span><span><strong>Explore rehabilitation</strong><small>Your plan and progress</small></span>${icon("arrow")}</button>
      <button class="quick-action" data-route="connect" type="button"><span class="small-icon movement-tint">${icon("connect")}</span><span><strong>Connect a device</strong><small>Movement and wearable sources</small></span>${icon("arrow")}</button>
    </div>
  </section>`;
}

function modulePage(route) {
  const page = modules[route];
  if (!page) return "";
  return `<section class="page-intro"><p class="eyebrow">${page.eyebrow}</p><h1>${page.title}</h1><p>${page.subtitle}</p></section>
    <div class="module-grid">${page.items.map(([title, description, detail]) => `
      <button class="module-card" type="button" ${detail.startsWith("health-") ? `data-route="${escapeHtml(detail)}"` : `data-detail="${escapeHtml(detail)}"`} ${route === "connect" && title === "Movement device" ? 'aria-label="Movement device, ESP32 not connected"' : ""}>
        <span class="module-icon">${icon(route === "connect" ? "connect" : route === "wellbeing" ? "wellbeing" : route === "rehab" ? "rehab" : "heart")}</span>
        <span class="module-copy"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(description)}</small></span>
        <span class="module-arrow">${icon("arrow")}</span>
      </button>`).join("")}</div>
    <div class="honesty-note">${icon("info")} <span>Your health information is private. VitaPulse only shows data you've connected or shared.</span></div>`;
}

const wellbeingMetrics = [
  ["energy", "Energy"],
  ["stress", "Stress"],
  ["fatigue", "Fatigue"],
  ["soreness", "Soreness"],
  ["recovery_feeling", "Recovery feeling"],
  ["sleep_duration_minutes", "Sleep duration"],
];

function wellbeingDate(value) {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function wellbeingTrendLabel(metric) {
  return wellbeingMetrics.find(([key]) => key === metric)?.[1] ?? metric.replaceAll("_", " ");
}

function wellbeingTrendValue(metric, value) {
  if (metric === "sleep_duration_minutes" && Number.isFinite(Number(value))) {
    const minutes = Number(value);
    return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  }
  return `${value}/5`;
}

function wellbeingHistorySummary(item) {
  const record = item.record || {};
  if (item.type === "CHECK_IN") {
    return `Energy ${record.energy ?? "—"}/5 · fatigue ${record.fatigue ?? "—"}/5`;
  }
  if (item.type === "SLEEP") {
    return Number.isFinite(Number(record.duration_minutes))
      ? `${wellbeingTrendValue("sleep_duration_minutes", record.duration_minutes)} · ${record.source || "SELF_REPORTED"}`
      : "Sleep duration unavailable";
  }
  if (item.type === "CAMERA") return `Camera observation · ${record.capture_quality || "quality unavailable"}`;
  if (item.type === "RECOVERY") return `Calculated recovery · ${record.recovery_state || "INSUFFICIENT_DATA"}`;
  return record.report_type?.replaceAll("_", " ") || "Wellbeing summary";
}

function wellbeingPage(state) {
  const wellbeing = state.wellbeing || {};
  const overview = wellbeing.overview || {};
  const checkin = overview.checkin;
  const sleep = overview.sleep;
  const recovery = overview.recovery_context || overview.recovery;
  const trends = wellbeing.trends?.series || {};
  const history = wellbeing.history?.items || [];
  const reports = wellbeing.reports?.reports || [];
  const demo = Boolean(state.session?.demo);
  const unavailable = !demo && !state.healthApiConfigured;
  const error = wellbeing.error
    ? `<div class="health-notice health-notice-error" role="alert">${icon("info")}<span>${escapeHtml(wellbeing.error)}</span></div>`
    : "";
  const notice = demo
    ? `<div class="health-notice" role="status">${icon("info")}<span>Demo entries stay in memory for this browser tab and are cleared when you sign out or reload. They are not sent to the API.</span></div>`
    : unavailable
      ? `<div class="health-notice health-notice-warning" role="status">${icon("info")}<span>Configure the authenticated VitaPulse API to save private wellbeing records. Entries are not stored in this browser as a fallback.</span></div>`
      : "";
  const loading = wellbeing.loading
    ? `<div class="health-loading" role="status"><span class="loading-mark" aria-hidden="true"></span><span>Loading your private wellbeing records…</span></div>`
    : "";
  const busy = wellbeing.busy || unavailable ? "disabled" : "";
  const latestCheckin = checkin
    ? `${checkin.energy}/5 energy · ${checkin.fatigue}/5 fatigue`
    : "No check-in yet";
  const sleepLabel = sleep && Number.isFinite(Number(sleep.duration_minutes))
    ? wellbeingTrendValue("sleep_duration_minutes", sleep.duration_minutes)
    : "Not recorded";
  const recoveryLabel = recovery?.recovery_state || overview.context?.recovery_state || "INSUFFICIENT_DATA";
  const trendCards = wellbeingMetrics.map(([metric, label]) => {
    const series = trends[metric];
    if (!series) return "";
    const trend = series.trend || {};
    const values = Array.isArray(series.values) ? series.values : [];
    const recentValues = values.slice(-12);
    const bars = recentValues.map((value, index) => {
      const normalized = metric === "sleep_duration_minutes"
        ? Math.min(100, Math.max(4, Number(value) / 600 * 100))
        : Math.min(100, Math.max(4, Number(value) / 5 * 100));
      const height = Number.isFinite(normalized) ? normalized : 4;
      return `<rect x="${index * 10 + 1}" y="${100 - height}" width="7" height="${height}" rx="1"><title>${escapeHtml(wellbeingTrendValue(metric, value))}</title></rect>`;
    }).join("");
    const chart = recentValues.length
      ? `<svg class="wellbeing-trend-chart" viewBox="0 0 ${recentValues.length * 10} 100" preserveAspectRatio="none" aria-hidden="true">${bars}</svg>`
      : '<span class="empty-bar" aria-hidden="true"></span>';
    return `<article class="wellbeing-trend-card">
      <div><strong>${escapeHtml(label)}</strong><span>${escapeHtml(trend.classification || "INSUFFICIENT_DATA")}</span></div>
      <div class="wellbeing-trend-bars" role="img" aria-label="${escapeHtml(label)} recorded values">${chart}</div>
      <small>${Number(trend.observation_count || values.length)} recorded observations · ${escapeHtml(series.source || (series.sources || []).join(", ") || "RECORDED")}</small>
    </article>`;
  }).filter(Boolean).join("");
  const historyMarkup = history.slice(0, 8).map((item) => `
    <article class="health-record">
      <div class="health-record-top"><div><strong>${escapeHtml(String(item.type || "RECORD").replaceAll("_", " "))}</strong><small>${escapeHtml(wellbeingDate(item.created_at || item.record?.created_at || item.record?.start_time))}</small></div><span class="health-status">${escapeHtml(item.record?.source || item.type || "RECORDED")}</span></div>
      <p>${escapeHtml(wellbeingHistorySummary(item))}</p>
    </article>`).join("");
  const reportMarkup = reports.slice(0, 5).map((report) => `
    <article class="health-record"><div class="health-record-top"><div><strong>${escapeHtml(String(report.report_type || "WELLBEING REPORT").replaceAll("_", " "))}</strong><small>${escapeHtml(wellbeingDate(report.created_at))}</small></div></div>
      <p>Sources: ${escapeHtml((report.source_provenance || []).join(", ") || "Not listed")}</p>
      <p>${escapeHtml((report.limitations || []).join(" "))}</p></article>`).join("");
  const contextText = overview.context?.summary ||
    "Record a check-in or sleep entry to see a summary grounded in your own information.";
  const cameraTile = `<article class="health-panel wellbeing-camera-panel">
  <div class="health-section-title"><div><h2>30-second camera check</h2><p>Camera observations are planned for the native Android app, not enabled in this web experience.</p></div>${icon("shield")}</div>
    <p class="health-disclaimer">This website does not request camera permission, capture frames, or infer emotional or medical states. Self-reports and any future camera observations remain separate.</p>
  </article>`;

  return `<section class="page-intro"><p class="eyebrow">YOUR WELLBEING</p><h1>Wellbeing</h1><p>Check in with yourself, at your own pace. Nothing is inferred when you have not recorded it.</p></section>
    ${notice}${error}${loading}
    <section class="health-summary-grid wellbeing-summary" aria-label="Latest recorded wellbeing">
      <article class="health-summary-card"><span>Latest check-in</span><strong>${escapeHtml(latestCheckin)}</strong><small>${checkin ? escapeHtml(wellbeingDate(checkin.created_at)) : "No self-report recorded"}</small></article>
      <article class="health-summary-card"><span>Latest sleep</span><strong>${escapeHtml(sleepLabel)}</strong><small>${sleep ? escapeHtml(sleep.source || "SELF_REPORTED") : "No sleep record"}</small></article>
      <article class="health-summary-card"><span>Recovery context</span><strong>${escapeHtml(recoveryLabel.replaceAll("_", " "))}</strong><small>${recovery ? "Calculated from available records" : "No supporting records yet"}</small></article>
    </section>
    <section class="panel health-panel">
      <div class="health-section-title"><div><h2>Your wellbeing context</h2><p>Self-reported information and calculated context are labelled separately.</p></div>${icon("wellbeing")}</div>
      <p class="wellbeing-context-copy">${escapeHtml(contextText)}</p>
      <p class="health-disclaimer">This information is not a medical or mental-health diagnosis, treatment recommendation, or emergency service.</p>
    </section>
    <div class="wellbeing-entry-grid">
      <section class="panel health-panel">
        <div class="health-section-title"><div><h2>Self check-in</h2><p>Your answers are self-reported. Rate each from 1 (low) to 5 (high).</p></div>${icon("heart")}</div>
        <form class="health-form" data-form="wellbeing-checkin">
          ${[
            ["energy", "Energy", "How is your energy?"],
            ["stress", "Stress", "How is your stress level?"],
            ["fatigue", "Fatigue", "How fatigued do you feel?"],
            ["soreness", "Soreness", "How sore do you feel?"],
            ["recoveryFeeling", "Recovery feeling", "How recovered do you feel?"],
          ].map(([name, label, hint]) => `<label class="field"><span>${escapeHtml(label)} <small>· ${escapeHtml(hint)}</small></span><select name="${name}" required ${busy}><option value="">Choose 1–5</option>${[1, 2, 3, 4, 5].map((number) => `<option value="${number}">${number}</option>`).join("")}</select></label>`).join("")}
          <label class="field"><span>Mood (optional self-report)</span><select name="moodSelfReport" ${busy}><option value="">Prefer not to say</option>${[1, 2, 3, 4, 5].map((number) => `<option value="${number}">${number}</option>`).join("")}</select></label>
          <label class="field"><span>Reflection (optional, up to 500 characters)</span><textarea name="note" maxlength="500" rows="3" ${busy}></textarea></label>
          <button class="primary-button" type="submit" ${busy}>Save self check-in ${icon("check")}</button>
        </form>
      </section>
      <section class="panel health-panel">
        <div class="health-section-title"><div><h2>Record sleep</h2><p>Enter the times you remember. Sleep stages are not estimated.</p></div>${icon("moon")}</div>
        <form class="health-form" data-form="wellbeing-sleep">
          <label class="field"><span>Bedtime</span><input type="datetime-local" name="startTime" required ${busy} /></label>
          <label class="field"><span>Wake time</span><input type="datetime-local" name="endTime" required ${busy} /></label>
          <label class="field"><span>Sleep quality (optional, 1–5)</span><select name="qualityRating" ${busy}><option value="">Not recorded</option>${[1, 2, 3, 4, 5].map((number) => `<option value="${number}">${number}</option>`).join("")}</select></label>
          <label class="field"><span>Night interruptions (optional)</span><input type="number" name="interruptions" min="0" max="100" step="1" ${busy} /></label>
          <label class="field"><span>Notes (optional, up to 500 characters)</span><textarea name="notes" maxlength="500" rows="3" ${busy}></textarea></label>
          <button class="primary-button" type="submit" ${busy}>Save sleep entry ${icon("check")}</button>
        </form>
      </section>
    </div>
    ${cameraTile}
    <section class="panel health-panel wellbeing-trends-panel">
      <div class="health-section-title"><div><h2>Trends</h2><p>Patterns from your recorded values only. Three or more observations are needed for a trend classification.</p></div>${icon("activity")}</div>
      ${trendCards ? `<div class="wellbeing-trend-grid">${trendCards}</div>` : `<div class="health-empty"><strong>Not enough recorded data yet</strong><p>Save a few check-ins or sleep entries to see trends. Nothing is estimated for missing days.</p></div>`}
    </section>
    <section class="panel health-panel">
      <div class="health-section-title"><div><h2>Wellbeing History</h2><p>Self-reported, calculated, and camera-observed records are kept distinct.</p></div>${icon("clock")}</div>
      ${historyMarkup ? `<div class="health-record-list">${historyMarkup}</div>` : `<div class="health-empty"><strong>No wellbeing history yet</strong><p>Your saved check-ins and sleep records will appear here.</p></div>`}
    </section>
    <section class="panel health-panel">
      <div class="health-section-title"><div><h2>Reports &amp; summaries</h2><p>A summary uses only data already recorded for your account.</p></div>${icon("info")}</div>
      <button class="secondary-button" type="button" data-wellbeing-action="create-report" ${busy || demo || !history.length ? "disabled" : ""}>Create weekly summary</button>
      ${demo ? `<p class="health-disclaimer">Report storage is disabled for synthetic demo accounts.</p>` : ""}
      <div class="health-record-list wellbeing-reports">${reportMarkup || `<div class="health-empty"><strong>No summaries saved</strong><p>Create a weekly summary after recording wellbeing data.</p></div>`}</div>
    </section>
    <div class="honesty-note">${icon("shield")} <span>Your wellbeing entries are private to your athlete account. You choose whether and when to record them.</span></div>`;
}

const healthRoutes = [
  ["health-reports", "Medical reports"],
  ["health-biomarkers", "Biomarkers"],
  ["health-body-map", "Body map"],
  ["health-intelligence", "Intelligence"],
  ["health-nutrition", "Nutrition"],
  ["health-medication", "Medication"],
  ["health-anti-doping", "Anti-doping"],
  ["health-skin-screening", "Skin"],
  ["health-history", "Reports"],
];

function healthHeader(route, title, description, content, state) {
  const loading = state.healthLoading
    ? `<div class="health-loading"><span class="loading-mark" aria-hidden="true"></span><span>Loading your health data…</span></div>`
    : "";
  const demoNotice = state.session.demo
    ? `<div class="health-notice" role="status">${icon("info")}<span>Health records are not connected to synthetic demo accounts.</span></div>`
    : !state.healthApiConfigured
      ? `<div class="health-notice" role="status">${icon("info")}<span>Connect a secure VitaPulse API and an athlete account to use health records.</span></div>`
      : state.healthError
        ? `<div class="health-notice health-notice-error" role="alert">${icon("info")}<span>${escapeHtml(state.healthError)}</span></div>`
        : "";
  const tabs = healthRoutes.map(([path, label]) => `
    <a class="health-tab ${route === path ? "active" : ""}" href="#${path}" data-route="${path}" ${route === path ? 'aria-current="page"' : ""}>${escapeHtml(label)}</a>`).join("");
  return `<section class="health-heading">
      <a class="back-link" href="#health" data-route="health">${icon("arrow")} Health overview</a>
      <p class="eyebrow">YOUR HEALTH</p><h1>${escapeHtml(title)}</h1><p>${escapeHtml(description)}</p>
    </section>
    <nav class="health-tabs" aria-label="Health sections">${tabs}</nav>
    ${demoNotice}${loading}
    ${state.healthError || state.healthLoading ? "" : content}`;
}

function healthOverview(state) {
  const data = state.healthData?.["health"] ?? {};
  const count = Number.isFinite(data.tracked_biomarker_count) ? data.tracked_biomarker_count : null;
  const report = data.latest_report;
  const stats = `<section class="health-summary-grid" aria-label="Health summary">
    <article class="health-summary-card"><span>Reports</span><strong>${report ? "Available" : "None yet"}</strong><small>${report ? escapeHtml(report.processing_status || "Processing") : "Your uploads appear here."}</small></article>
    <article class="health-summary-card"><span>Biomarkers</span><strong>${count === null ? "—" : count}</strong><small>Extracted from your documents.</small></article>
    <article class="health-summary-card"><span>Medications</span><strong>${Number.isFinite(data.medication_count) ? data.medication_count : "—"}</strong><small>Your active list.</small></article>
  </section>`;
  return `<section class="page-intro"><p class="eyebrow">YOUR HEALTH</p><h1>Health</h1><p>Keep the health details that support your sport in one place.</p></section>
    ${state.healthLoading ? `<div class="health-loading"><span class="loading-mark" aria-hidden="true"></span><span>Loading your health data…</span></div>` : ""}
    ${state.healthError ? `<div class="health-notice health-notice-error" role="alert">${icon("info")}<span>${escapeHtml(state.healthError)}</span></div>` : ""}
    ${state.session.demo
      ? `<div class="health-notice" role="status">${icon("info")}<span>Health records are not connected to synthetic demo accounts.</span></div>`
      : !state.healthApiConfigured
        ? `<div class="health-notice" role="status">${icon("info")}<span>Connect a secure VitaPulse API and an athlete account to use health records.</span></div>`
        : ""}
    ${state.healthLoading || state.healthError ? "" : stats}
    <div class="module-grid">${modules.health.items.map(([title, description, route]) => `
      <a class="module-card" href="#${escapeHtml(route)}" data-route="${escapeHtml(route)}">
        <span class="module-icon">${icon("heart")}</span><span class="module-copy"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(description)}</small></span><span class="module-arrow">${icon("arrow")}</span>
      </a>`).join("")}</div>
    <div class="health-notice">${icon("shield")}<span>Uploaded reports are private. Extracted values remain linked to their source page and quoted text.</span></div>`;
}

function dateLabel(value) {
  if (!value) return "Date not provided";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? "Date not provided"
    : new Intl.DateTimeFormat(undefined, { year: "numeric", month: "short", day: "numeric" }).format(parsed);
}

function healthEmpty(title, description) {
  return `<div class="health-empty"><strong>${escapeHtml(title)}</strong><p>${escapeHtml(description)}</p></div>`;
}

const rehabSections = [
  ["rehab", "Overview"],
  ["rehab/today", "Today's rehab"],
  ["rehab/program", "Program"],
  ["rehab/exercises", "Exercises"],
  ["rehab/movement", "Movement analysis"],
  ["rehab/progress", "Progress"],
  ["rehab/recovery", "Recovery"],
  ["rehab/functional-tests", "Functional tests"],
  ["rehab/readiness", "Readiness"],
  ["rehab/return-to-sport", "Return to sport"],
  ["rehab/history", "History"],
  ["rehab/reports", "Reports"],
];

function rehabTag(value) {
  return escapeHtml(String(value || "INSUFFICIENT_DATA").replaceAll("_", " "));
}

function sourceBadge(source = "SIMULATION") {
  return `<span class="rehab-source-badge">${escapeHtml(String(source).replaceAll("_", " "))}</span>`;
}

function rehabPanel(title, content, subtitle = "") {
  return `<section class="panel rehab-panel"><div class="health-section-title"><div><h2>${escapeHtml(title)}</h2>${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ""}</div></div>${content}</section>`;
}

function rehabScreenShell(route, title, subtitle, content, state, backRoute = "rehab") {
  const data = state.rehabData?.[route] || {};
  const tabs = rehabSections.map(([path, label]) =>
    `<a href="#${path}" data-route="${path}" class="rehab-tab ${route === path ? "active" : ""}" ${route === path ? 'aria-current="page"' : ""}>${escapeHtml(label)}</a>`).join("");
  const status = state.rehabLoading
    ? `<div class="health-loading" role="status"><span class="loading-mark" aria-hidden="true"></span><span>Loading rehabilitation data…</span></div>`
    : state.rehabError
      ? `<div class="health-notice health-notice-error" role="alert">${icon("info")}<span>${escapeHtml(state.rehabError)}</span></div>`
      : data.unavailable
        ? `<div class="health-notice" role="status">${icon("info")}<span>Connect a secure VitaPulse API and athlete account to load assigned rehabilitation data.</span></div>`
        : state.session.demo
          ? `<div class="health-notice rehab-demo-note" role="note"><strong>DEMO DATA</strong><span>SIMULATION DATA · Synthetic development preview only, not an assigned clinical plan.</span></div>`
          : state.offline
            ? `<div class="health-notice" role="status">${icon("info")}<span>Offline. Locally saved session data remains on this device and may be waiting to sync.</span></div>`
            : "";
  return `<section class="rehab-heading"><a class="back-link" href="#${backRoute}" data-route="${backRoute}">${icon("arrow")} Back</a><p class="eyebrow">YOUR MOVEMENT · YOUR COMEBACK</p><h1>${escapeHtml(title)}</h1><p>${escapeHtml(subtitle)}</p></section>
    <nav class="rehab-tabs" aria-label="Rehabilitation sections">${tabs}</nav>${status}${content}`;
}

function exerciseCard(exercise, assignment = null) {
  const prescribed = assignment
    ? `${escapeHtml(assignment.sets)} sets${assignment.repetitions ? ` × ${escapeHtml(assignment.repetitions)} reps` : ""}${assignment.duration_seconds ? ` · ${escapeHtml(assignment.duration_seconds)} sec` : ""}`
    : `${exercise.default_sets ? `${escapeHtml(exercise.default_sets)} sets` : "Prescription varies"}${exercise.default_repetitions ? ` × ${escapeHtml(exercise.default_repetitions)} reps` : ""}${exercise.default_duration_seconds ? ` · ${escapeHtml(exercise.default_duration_seconds)} sec` : ""}`;
  return `<a class="rehab-exercise-card" href="#rehab/exercises/${encodeURIComponent(exercise.id)}" data-route="rehab/exercises/${encodeURIComponent(exercise.id)}">
    <span class="rehab-card-top"><span class="soft-tag">${escapeHtml(exercise.category || "EXERCISE")}</span><span>${escapeHtml(exercise.difficulty || "DIFFICULTY NOT SET")}</span></span>
    <strong>${escapeHtml(exercise.name)}</strong><span>${escapeHtml(exercise.target_region || "Target region not set")}</span>
    <small>${escapeHtml(exercise.goal || exercise.description || "Purpose not provided")}</small><span class="rehab-prescription">${prescribed}</span>
  </a>`;
}

function rehabHub(state, data) {
  const program = data.current_program;
  const today = data.today || {};
  const assignments = today.exercises || [];
  const next = assignments.find((item) => item.status !== "COMPLETED") || assignments[0];
  const nextExercise = next?.exercise;
  const sessions = data.recent_sessions || [];
  return `<section class="page-intro rehab-hub-intro"><p class="eyebrow">ASSESS · TRAIN · MEASURE · PROGRESS</p><h1>Rehabilitation</h1><p>Your movement. Your recovery. Your comeback.</p></section>
    <nav class="rehab-tabs" aria-label="Rehabilitation sections">${rehabSections.map(([path, label]) => `<a href="#${path}" data-route="${path}" class="rehab-tab">${escapeHtml(label)}</a>`).join("")}</nav>
    ${!program ? healthEmpty("No rehabilitation program assigned", "When your clinician assigns a program, your stage and exercises will appear here.") : `
      <section class="rehab-stage-banner"><p class="eyebrow">CURRENT STAGE</p><h2>${escapeHtml(program.stage || "Stage not assigned")}</h2><p>${escapeHtml(program.name)}</p>${program.stage_order !== null && program.stage_order !== undefined ? `<span>Stage ${escapeHtml(Number(program.stage_order) + 1)}</span>` : ""}</section>
      <section class="panel rehab-today-card"><div class="health-section-title"><div><p class="eyebrow">TODAY'S REHABILITATION</p><h2>${escapeHtml(program.name)}</h2></div>${sourceBadge(nextExercise?.requires_sensor ? "SIMULATION" : "ASSIGNED PROGRAM")}</div>
        <p>${Number(today.completed || 0)} completed · ${Number(today.remaining || 0)} remaining</p>
        ${nextExercise ? `<div class="rehab-next-exercise"><span class="eyebrow">NEXT EXERCISE</span><h3>${escapeHtml(nextExercise.name)}</h3><p>${escapeHtml(next?.sets || nextExercise.default_sets || "—")} sets${next?.repetitions || nextExercise.default_repetitions ? ` × ${escapeHtml(next?.repetitions || nextExercise.default_repetitions)} reps` : ""}</p>
          <button class="primary-button" type="button" data-rehab-action="start-session" data-exercise-id="${escapeHtml(nextExercise.id)}">Start simulation session ${icon("arrow")}</button></div>`
          : healthEmpty("No exercises assigned for today", "Your program does not currently include any exercises.")}</section>`}
    <section class="rehab-summary-grid" aria-label="Rehabilitation overview">
      <article class="health-summary-card"><span>Movement quality</span><strong>${rehabTag(data.movement_quality)}</strong><small>Latest stored session signal</small></article>
      <article class="health-summary-card"><span>Recovery</span><strong>${rehabTag(data.recovery?.status || "UNAVAILABLE")}</strong><small>Sleep and wearable data are not connected</small></article>
      <article class="health-summary-card"><span>Sessions completed</span><strong>${Number(data.progress?.sessions_completed || 0)}</strong><small>Recent completed sessions</small></article>
    </section>
    <div class="rehab-quick-grid">
    ${[["rehab/exercises", "Exercise library", "Instructions and prescriptions"], ["rehab/movement", "Movement analysis", "Source-labelled movement signals"], ["rehab/functional-tests", "Functional tests", "Supported timed attempts"], ["rehab/progress", "Progress", "Program and session history"]].map(([route, title, detail]) => `<a class="module-card" href="#${route}" data-route="${route}"><span class="module-icon">${icon("rehab")}</span><span class="module-copy"><strong>${title}</strong><small>${detail}</small></span>${icon("arrow")}</a>`).join("")}
    </div>
    ${rehabPanel("Return to sport", `<p>Progression requirements are reviewed against your assigned program and recorded tests.</p><p class="rehab-caution">VitaPulse does not provide medical clearance.</p><a class="text-button" href="#rehab/return-to-sport" data-route="rehab/return-to-sport">Review progression ${icon("arrow")}</a>`, program ? `Current stage: ${escapeHtml(program.stage || "not set")}` : "No active program")}
    ${rehabPanel("Recent sessions", sessions.length ? `<div class="health-record-list">${sessions.slice(0, 3).map(sessionCard).join("")}</div>` : healthEmpty("No sessions recorded", "Completed sessions will appear here with their source and recorded movement signals."))}`;
}

function sessionCard(session) {
  const duration = session.session_duration_seconds ?? session.duration_seconds ??
    (Number.isFinite(session.elapsed_ms) ? Math.floor(session.elapsed_ms / 1000) : null);
  return `<article class="health-record"><div class="health-record-top"><div><strong>${escapeHtml(session.exercise?.name || session.exercise_name || "Rehabilitation session")}</strong><small>${escapeHtml(dateLabel(session.ended_at || session.started_at || session.created_at))} · ${duration !== null ? `${escapeHtml(duration)} sec` : "Duration not recorded"}</small></div>${sourceBadge(session.source || "UNKNOWN")}</div>
    <p>${Number(session.completed_repetitions || 0)}${session.target_repetitions ? ` / ${escapeHtml(session.target_repetitions)}` : ""} repetitions · ${rehabTag(session.movement_quality)}</p>
    ${session.locally_saved ? `<small>Saved locally · waiting to sync</small>` : ""}<a class="text-button" href="#rehab/session/${encodeURIComponent(session.id)}/result" data-route="rehab/session/${encodeURIComponent(session.id)}/result">View result ${icon("arrow")}</a></article>`;
}

function rehabToday(state, data) {
  const exercises = data.exercises || [];
  return rehabScreenShell("rehab/today", "Today's Rehabilitation", "Follow the exercises in your assigned program; your clinician sets your prescription.", `
    ${!data.program ? healthEmpty("No rehab program", "Your daily rehabilitation plan will appear here after it is assigned.") : `<section class="rehab-stage-banner"><p class="eyebrow">PROGRAM · ${escapeHtml(data.program.name)}</p><h2>${escapeHtml(data.stage?.name || data.program.stage || "Stage not set")}</h2></section>
      <progress class="rehab-progress" aria-label="Today's exercise completion" max="${Math.max(exercises.length, 1)}" value="${Math.min(Number(data.completed || 0), exercises.length)}"></progress>
      <p>${Number(data.completed || 0)} completed · ${Number(data.remaining || exercises.length)} remaining</p>
      <div class="rehab-exercise-list">${exercises.length ? exercises.map((item) => {
        const exercise = item.exercise || {};
        const status = item.status || "NOT_STARTED";
        return `<article class="rehab-today-exercise"><div><span class="soft-tag">${rehabTag(status)}</span><h3>${escapeHtml(exercise.name || "Exercise")}</h3><p>${escapeHtml(item.sets || exercise.default_sets || "—")} sets${item.repetitions || exercise.default_repetitions ? ` × ${escapeHtml(item.repetitions || exercise.default_repetitions)} reps` : ""} · ${escapeHtml(exercise.target_region || "Target region not set")}</p><small>${item.duration_seconds ? `${escapeHtml(item.duration_seconds)} sec` : "Duration not specified"}</small></div><button class="primary-button compact" type="button" data-rehab-action="start-session" data-exercise-id="${escapeHtml(exercise.id)}">Start</button></article>`;
      }).join("") : healthEmpty("No exercises assigned", "There are no exercises in this program.")}</div>`}`, state);
}

function rehabProgram(state, data) {
  const program = data.program;
  if (!program) return rehabScreenShell("rehab/program", "Your program", "Clinician-assigned stages and exercises.", healthEmpty("No rehabilitation program assigned", "Program details will appear here when a program is assigned."), state);
  const stages = Array.isArray(program.stages) ? program.stages : [];
  return rehabScreenShell("rehab/program", "Your program", "Clinician-assigned goal, current stage and configurable progression.", `
    ${rehabPanel(program.name, `<p>${escapeHtml(program.description || "No program description provided.")}</p><dl class="rehab-facts"><div><dt>Goal</dt><dd>${escapeHtml(program.goal || "Not specified")}</dd></div><div><dt>Current stage</dt><dd>${escapeHtml(program.stage || "Not specified")}</dd></div><div><dt>Start date</dt><dd>${escapeHtml(dateLabel(program.start_date))}</dd></div><div><dt>Target progression</dt><dd>${escapeHtml(dateLabel(program.target_end_date))}</dd></div><div><dt>Status</dt><dd>${rehabTag(program.status)}</dd></div></dl>`, "Assignment details")}
    ${rehabPanel("Configured stages", stages.length ? `<ol class="rehab-stage-list">${stages.map((stage, index) => `<li class="${stage.name === program.stage ? "current" : ""}"><span>${escapeHtml(stage.name || "Stage")}</span><small>${stage.order !== undefined ? `Stage ${Number(stage.order) + 1}` : `Stage ${index + 1}`}</small></li>`).join("")}</ol>` : healthEmpty("No stage sequence provided", "Your assigned program does not define a universal stage sequence."))}
    ${rehabPanel("Program exercises", data.exercises?.length ? `<div class="rehab-exercise-list">${data.exercises.map((item) => exerciseCard(item.exercise || {}, item)).join("")}</div>` : healthEmpty("No exercises assigned", "Your program currently has no exercise prescriptions."))}`, state);
}

function rehabExercises(state, data) {
  const exercises = data.exercises || [];
  const detailRoute = state.route.startsWith("rehab/exercises/") ? state.route : null;
  if (detailRoute) {
    const exercise = data.exercise;
    if (!exercise) return rehabScreenShell(detailRoute, "Exercise details", "Instructions and prescription.", healthEmpty("Exercise not available", "This exercise may have been removed from the library."), state, "rehab/exercises");
    const instructions = exercise.instructions || {};
    return rehabScreenShell(detailRoute, exercise.name, exercise.description || "Exercise details and assigned prescription.", `
      ${rehabPanel("Exercise overview", `<dl class="rehab-facts"><div><dt>Target region</dt><dd>${escapeHtml(exercise.target_region || "Not specified")}</dd></div><div><dt>Target muscles</dt><dd>${escapeHtml((exercise.target_muscles || []).join(", ") || "Not specified")}</dd></div><div><dt>Category</dt><dd>${escapeHtml(exercise.category || "Not specified")}</dd></div><div><dt>Difficulty</dt><dd>${escapeHtml(exercise.difficulty || "Not specified")}</dd></div><div><dt>Goal</dt><dd>${escapeHtml(exercise.goal || "Not specified")}</dd></div></dl>`)}
      ${rehabPanel("How to perform", `<p><strong>Starting position</strong><br>${escapeHtml(instructions.starting_position || "Not provided")}</p><p><strong>Execution</strong><br>${escapeHtml(instructions.execution || "Not provided")}</p><p><strong>Breathing</strong><br>${escapeHtml(instructions.breathing || "Breathe steadily.")}</p><p><strong>Common mistakes</strong></p><ul>${(exercise.common_mistakes || []).map((mistake) => `<li>${escapeHtml(mistake)}</li>`).join("") || "<li>No common mistakes provided.</li>"}</ul>`)}
      ${rehabPanel("Prescription and sensor", `<p>Default prescription: ${escapeHtml(exercise.default_sets || "—")} sets${exercise.default_repetitions ? ` × ${escapeHtml(exercise.default_repetitions)} reps` : ""}${exercise.default_duration_seconds ? ` · ${escapeHtml(exercise.default_duration_seconds)} sec` : ""} · rest ${escapeHtml(exercise.rest_seconds ?? "—")} sec</p><p>${exercise.requires_sensor ? `Sensor placement: ${escapeHtml(exercise.default_sensor_placement || "Choose with your clinician")}. Movement here uses an explicit simulation source; live sensor connection is Phase 4.` : "No sensor is required for this exercise."}</p><p>Previous performance: ${data.previous_performance?.length ? `${data.previous_performance.length} recorded session(s)` : "No completed session recorded."}</p>
        <label class="field"><span>Simulation scenario · synthetic test signal</span><select data-rehab-scenario>${["NORMAL", "GOOD_FORM", "POOR_FORM", "FATIGUE", "ABNORMAL_MOVEMENT", "CONNECTION_DROP"].map((scenario) => `<option value="${scenario}" ${state.rehabScenario === scenario ? "selected" : ""}>${scenario.replaceAll("_", " ")}</option>`).join("")}</select></label>
        <button class="primary-button" type="button" data-rehab-action="start-session" data-exercise-id="${escapeHtml(exercise.id)}">Start simulation session ${icon("arrow")}</button>
        <button class="secondary-button" type="button" data-rehab-action="start-session" data-source="MANUAL" data-exercise-id="${escapeHtml(exercise.id)}">Record a manual session</button>
        <a class="text-button" href="#rehab/history" data-route="rehab/history">View history</a>`)}
    `, state, "rehab/exercises");
  }
  return rehabScreenShell("rehab/exercises", "Exercise library", "Exercise content is managed as data, with extensible categories and clinician-assigned prescriptions.", `
    ${exercises.length ? `<div class="rehab-exercise-list">${exercises.map((exercise) => exerciseCard(exercise)).join("")}</div>` : healthEmpty(state.session.demo ? "No demo exercises available" : "Exercise library unavailable", state.session.demo ? "Synthetic exercise cards are not configured." : "The exercise library is loaded from the Rehab API.")}`, state);
}

function chartPoints(samples) {
  const points = samples.slice(-20).map((sample, index) => {
    const x = samples.length <= 1 ? 0 : index / (Math.min(samples.length, 20) - 1) * 300;
    const magnitude = Math.hypot(sample.ax, sample.ay, sample.az);
    return `${x},${Math.max(4, Math.min(76, 40 - (magnitude - 1) * 45))}`;
  });
  return points.join(" ");
}

function liveRehabSession(state, route) {
  const session = state.rehabSession;
  const isResult = route.endsWith("/result");
  if (!session) return rehabScreenShell(route, isResult ? "Session result" : "Rehab session", "Session data is source-labelled.", healthEmpty("Session not available", "Start an exercise from your assigned program or library."), state, "rehab/today");
  if (isResult || session.status === "COMPLETED") {
    const summary = summarizeMovementSamples(session.samples || [], session.repetitions || []);
    const quality = session.movement_quality || summary.movement_quality;
    const duration = Math.floor((session.elapsed_ms || 0) / 1000);
    return rehabScreenShell(route, "Session complete", session.exercise?.name || "Rehabilitation exercise", `
      <div class="rehab-session-hero"><span class="eyebrow">SESSION COMPLETE</span><h2>${escapeHtml(session.exercise?.name || "Exercise")}</h2>${sourceBadge(session.source)}</div>
      <section class="rehab-summary-grid" aria-label="Recorded session results">
        <article class="health-summary-card"><span>Completed</span><strong>${Number(session.completed_repetitions || 0)}${session.target_repetitions ? ` / ${escapeHtml(session.target_repetitions)}` : ""}</strong><small>Repetitions recorded</small></article>
        <article class="health-summary-card"><span>Movement quality</span><strong>${rehabTag(quality)}</strong><small>Source-labelled signal</small></article>
        <article class="health-summary-card"><span>Stability</span><strong>${rehabTag(session.stability || summary.stability)}</strong><small>Not a clinical assessment</small></article>
        <article class="health-summary-card"><span>Smoothness</span><strong>${rehabTag(session.smoothness || summary.smoothness)}</strong><small>Sensor movement signal</small></article>
        <article class="health-summary-card"><span>Fatigue signal</span><strong>${rehabTag(session.fatigue_signal || summary.fatigue_signal)}</strong><small>Movement-based only</small></article>
        <article class="health-summary-card"><span>Duration</span><strong>${Math.floor(duration / 60)}:${String(duration % 60).padStart(2, "0")}</strong><small>Session elapsed time</small></article>
      </section>
      ${session.locally_saved ? `<div class="health-notice" role="status">${icon("info")}<span>Saved locally · Waiting to sync when your connection returns.</span></div>` : ""}
      ${session.locally_saved && !session.demo && state.healthApiConfigured ? `<button class="secondary-button" type="button" data-rehab-action="sync-session">Sync saved session</button>` : ""}
      <p class="rehab-caution">One movement sensor does not measure full-body biomechanics, exact joint angles or injury.</p>
      <div class="rehab-quick-grid"><a class="module-card" href="#rehab/progress" data-route="rehab/progress"><span class="module-copy"><strong>View progress</strong><small>Recorded sessions and assigned work</small></span>${icon("arrow")}</a><a class="module-card" href="#rehab/history" data-route="rehab/history"><span class="module-copy"><strong>View history</strong><small>Your completed session record</small></span>${icon("arrow")}</a><a class="module-card" href="#rehab" data-route="rehab"><span class="module-copy"><strong>Back to Rehab</strong><small>Return to your overview</small></span>${icon("arrow")}</a></div>`, state, "rehab/history");
  }
  const elapsed = Math.floor((session.elapsed_ms || 0) / 1000);
  const summary = summarizeMovementSamples(session.samples || [], session.repetitions || []);
  const liveQuality = summary.movement_quality;
  const placement = session.sensor_placement ? String(session.sensor_placement).replaceAll("_", " ") : "Not recorded";
  return rehabScreenShell(route, session.exercise?.name || "Rehabilitation session", "Follow your assigned movement at a comfortable pace. Stop if you feel pain or unsafe.", `
    <section class="rehab-session-hero"><span class="eyebrow">${session.status === "CALIBRATING" ? "CALIBRATION" : "LIVE SESSION"}</span><div class="rehab-live-label"><strong>${session.source === "SIMULATION" ? "SIMULATION MODE" : "MANUAL SESSION"}</strong>${sourceBadge(session.source)}</div><p>Sensor placement: ${escapeHtml(placement)}${session.source === "SIMULATION" ? " · synthetic signal, not connected hardware" : ""}</p></section>
    ${session.status === "CALIBRATING" || session.status === "PLANNED" ? rehabPanel(session.source === "SIMULATION" ? "Simulation calibration" : "Manual session", `<p>${session.source === "SIMULATION" ? "Keep the simulated sensor still at the selected placement while a development baseline is prepared." : "This session records manually timed activity without sensor measurements."}</p>${session.source === "SIMULATION" ? `<ol class="rehab-calibration-count" aria-label="Simulation calibration countdown"><li>5</li><li>4</li><li>3</li><li>2</li><li>1</li></ol><p>Simulation baseline ready. A physical sensor is not connected in Phase 3.</p>` : ""}<button class="primary-button" type="button" data-rehab-action="begin-session">Start session ${icon("arrow")}</button><button class="text-button" type="button" data-rehab-action="cancel-session">Cancel session</button>`) : ""}
    ${session.status === "ACTIVE" || session.status === "PAUSED" ? `<section class="rehab-live-grid" aria-label="Current session">
      <article class="health-summary-card"><span>Repetitions</span><strong>${Number(session.completed_repetitions || 0)}${session.target_repetitions ? ` / ${escapeHtml(session.target_repetitions)}` : ""}</strong><small>Signal-derived, approximate rep detection</small></article>
      <article class="health-summary-card"><span>Movement quality</span><strong>${rehabTag(liveQuality)}</strong><small>Qualitative signal; not an injury assessment</small></article>
      <article class="health-summary-card"><span>Stability</span><strong>${rehabTag(summary.stability)}</strong></article>
      <article class="health-summary-card"><span>Smoothness</span><strong>${rehabTag(summary.smoothness)}</strong></article>
      <article class="health-summary-card"><span>Session time</span><strong>${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, "0")}</strong><small>${session.status === "PAUSED" ? "Paused" : "Active"}</small></article>
      <article class="health-summary-card"><span>Fatigue signal</span><strong>${rehabTag(summary.fatigue_signal)}</strong><small>Movement-based, non-medical signal</small></article>
    </section>
    ${session.safety_events?.length ? `<div class="health-notice health-notice-warning" role="alert">${icon("info")}<span>A movement signal needs attention. Check sensor placement and stop if you feel pain or unsafe.</span></div>` : ""}
    ${session.source === "SIMULATION" ? rehabPanel("Movement signal · rolling 5-second window", `<svg class="rehab-signal-chart" viewBox="0 0 300 80" role="img" aria-label="Rolling simulated acceleration magnitude signal for the last five seconds"><line x1="0" y1="40" x2="300" y2="40"></line><polyline points="${chartPoints(session.samples || [])}"></polyline></svg><p>Aggregated visualisation · ${Number(session.samples?.slice(-20).length || 0)} recent samples · source ${escapeHtml(session.source)}</p>${session.connection_status === "RECONNECTING" ? `<div class="health-notice health-notice-warning" role="status">${icon("info")}<span>Simulation connection interruption · waiting to resume synthetic samples.</span></div>` : ""}`) : rehabPanel("Movement signal", "<p>No sensor signal was captured for this manual session.</p>")}
    ${session.status === "PAUSED" ? `<button class="primary-button" type="button" data-rehab-action="resume-session">Resume</button>` : `<button class="secondary-button" type="button" data-rehab-action="pause-session">Pause</button>`}
    <button class="primary-button" type="button" data-rehab-action="stop-session">Stop and save</button>
    <button class="text-button" type="button" data-rehab-action="cancel-session">Cancel session</button>
    ${state.rehabConfirmStop ? `<div class="rehab-confirm" role="alertdialog" aria-labelledby="rehab-stop-title" aria-describedby="rehab-stop-desc"><h2 id="rehab-stop-title">End session?</h2><p id="rehab-stop-desc">Completed repetitions and movement results will be saved.</p><button class="secondary-button" type="button" data-rehab-action="continue-session">Continue session</button><button class="primary-button" type="button" data-rehab-action="confirm-stop">End session</button></div>` : ""}` : ""}`, state, "rehab/today");
}

function rehabPage(route, state) {
  const data = state.rehabData?.[route] || {};
  if (route === "rehab") return rehabHub(state, data);
  if (route === "rehab/today") return rehabToday(state, data);
  if (route === "rehab/program" || route.startsWith("rehab/program/")) return rehabProgram(state, data);
  if (route === "rehab/exercises" || route.startsWith("rehab/exercises/")) return rehabExercises(state, data);
  if (route === "rehab/session") return liveRehabSession(state, route);
  if (route.startsWith("rehab/session/")) return liveRehabSession(state, route);
  if (route.startsWith("rehab/movement")) {
    if (route !== "rehab/movement") {
      const quality = data.quality || {};
      return rehabScreenShell(route, "Movement session", "Stored repetition and metric summaries; no raw sensor stream is retained.", `
        ${rehabPanel("Movement quality", `<p>Movement quality: ${rehabTag(quality.movement_quality)}</p><p>Stability: ${rehabTag(quality.stability)}</p><p>Smoothness: ${rehabTag(quality.smoothness)}</p><p>Fatigue signal: ${rehabTag(quality.fatigue_signal)}</p>${sourceBadge(quality.source || "UNKNOWN")}`)}
        ${rehabPanel("Recorded repetitions", data.repetitions?.length ? `<ol>${data.repetitions.map((rep) => `<li>Rep ${escapeHtml(rep.rep_number)} · ${escapeHtml(rep.duration_ms)} ms · ${rehabTag(rep.quality)} · ${escapeHtml(rep.source || "UNKNOWN")}</li>`).join("")}</ol>` : healthEmpty("No repetition records", "This session has no stored repetition detail."))}
        ${rehabPanel("Movement metrics", data.metrics?.length ? `<ul>${data.metrics.map((metric) => `<li>${escapeHtml(metric.metric_name)}: ${escapeHtml(metric.metric_value)} ${escapeHtml(metric.unit || "")} · ${escapeHtml(metric.source)}</li>`).join("")}</ul>` : healthEmpty("No metrics recorded", "The session summary has no metric details."))}
      `, state, "rehab/movement");
    }
    const sessions = data.sessions || [];
    return rehabScreenShell("rehab/movement", "Movement analysis", "Review recorded movement signals with their source. This is not full-body biomechanics.", `
      ${rehabPanel("Movement overview", `<div class="rehab-summary-grid"><article class="health-summary-card"><span>Movement quality</span><strong>${rehabTag(data.movement_quality)}</strong></article><article class="health-summary-card"><span>Sessions</span><strong>${Number(data.session_count || sessions.length)}</strong></article><article class="health-summary-card"><span>Movement-based fatigue</span><strong>${rehabTag(data.fatigue_signal)}</strong></article><article class="health-summary-card"><span>Trend</span><strong>${rehabTag(data.trend)}</strong></article></div><p>${escapeHtml(data.notice || "Complete at least three sessions before interpreting a movement trend.")}</p>`)}
      ${rehabPanel("Recent movement sessions", sessions.length ? `<div class="health-record-list">${sessions.map(sessionCard).join("")}</div>` : healthEmpty("Not enough data", "Complete source-labelled rehab sessions before a movement trend can be shown."))}
    `, state);
  }
  if (route === "rehab/progress") {
    return rehabScreenShell(route, "Rehabilitation progress", "Progress is based on persisted program and session records, not a weighted score.", `
      <section class="rehab-summary-grid"><article class="health-summary-card"><span>Current stage</span><strong>${escapeHtml(data.program?.stage || "Not assigned")}</strong></article><article class="health-summary-card"><span>Sessions completed</span><strong>${Number(data.sessions_completed || 0)}</strong></article><article class="health-summary-card"><span>Exercises completed</span><strong>${Number(data.exercises_completed || 0)} / ${Number(data.assigned_exercises || 0)}</strong></article><article class="health-summary-card"><span>Functional tests</span><strong>${Number(data.functional_tests_completed || 0)}</strong></article><article class="health-summary-card"><span>Movement trend</span><strong>${rehabTag(data.movement_trend)}</strong></article><article class="health-summary-card"><span>Return-to-sport</span><strong>${rehabTag(data.return_to_sport_status)}</strong></article></section>
      ${data.movement_trend === "INSUFFICIENT_DATA" ? `<p class="health-disclaimer">Not enough sessions for a meaningful trend.</p>` : ""}`, state);
  }
  if (route === "rehab/recovery") {
    return rehabScreenShell(route, "Recovery", "Recovery context alongside your assigned rehabilitation.", `
      <section class="rehab-summary-grid"><article class="health-summary-card"><span>Recent rehab load</span><strong>${data.recent_rehab_load === null || data.recent_rehab_load === undefined ? "Not available" : `${escapeHtml(data.recent_rehab_load)} sec`}</strong></article><article class="health-summary-card"><span>Recent sessions</span><strong>${Number(data.recent_session_count || 0)}</strong></article><article class="health-summary-card"><span>Movement fatigue signal</span><strong>${rehabTag(data.fatigue_signal)}</strong></article></section>
      ${rehabPanel("Sleep and wearable context", `<p>Recovery data unavailable. Connect a supported device in Connect.</p><p>Sleep: ${rehabTag(data.sleep?.status || "NOT_CONNECTED")}</p><p>Soreness: ${data.soreness ? rehabTag(data.soreness) : "Not recorded"}</p>`)}
    `, state);
  }
  if (route.startsWith("rehab/functional-tests")) {
    const resultRoute = route.endsWith("/result");
    const testId = route.split("/")[2];
    const activeRun = state.functionalTestRun;
    const result = data.result || data.history?.[0];
    if (resultRoute) {
      const duration = activeRun ? (Date.now() - activeRun.started_at) / 1000 : result?.duration_seconds;
      return rehabScreenShell(route, activeRun ? "Functional test in progress" : "Functional test result", activeRun?.test?.name || result?.functional_test?.name || "Timed test", `
        ${activeRun ? `<div class="rehab-session-hero"><p>Elapsed time</p><strong class="rehab-test-timer">${(duration || 0).toFixed(1)} sec</strong>${sourceBadge(activeRun.source)}<p>This timed attempt does not include sensor-based stability measurement.</p><button class="primary-button" type="button" data-rehab-action="finish-functional-test">Stop and save test</button></div>`
          : result ? `<section class="rehab-summary-grid"><article class="health-summary-card"><span>Duration</span><strong>${Number(result.duration_seconds).toFixed(1)} sec</strong></article><article class="health-summary-card"><span>Stability signal</span><strong>${rehabTag(result.stability)}</strong></article><article class="health-summary-card"><span>Movement quality</span><strong>${rehabTag(result.movement_quality)}</strong></article></section><p>Recorded result only. No clinical norms or clearance are inferred.</p>`
            : healthEmpty("No test result", "Start an available functional test to record an elapsed attempt.")}`, state, "rehab/functional-tests");
    }
    const tests = data.tests || [];
    const selectedTest = tests.find((item) => item.id === testId);
    if (testId) {
      return rehabScreenShell(route, selectedTest?.name || "Functional test details", "Purpose, preparation and measurement method for this supported test.", selectedTest
        ? `${rehabPanel("Purpose", `<p>${escapeHtml(selectedTest.purpose)}</p>`)}
          ${rehabPanel("Preparation", `<p>${escapeHtml(selectedTest.preparation)}</p>`)}
          ${rehabPanel("Instructions", `<ol>${(selectedTest.instructions || []).map((instruction) => `<li>${escapeHtml(instruction)}</li>`).join("")}</ol><p><strong>Measurement</strong><br>${escapeHtml(selectedTest.measurement_method || "Timed attempt only; movement quality unavailable.")}</p><p>Result records time and source; no clinical norms are inferred.</p><button class="primary-button" type="button" data-rehab-action="start-functional-test" data-test-id="${escapeHtml(selectedTest.id)}">Start test</button>`)}` 
        : healthEmpty("Functional test not available", "This test has no configured, validated measurement method."), state, "rehab/functional-tests");
    }
    return rehabScreenShell("rehab/functional-tests", "Functional tests", "Only tests with an explicitly available measurement method are offered.", tests.length ? `<div class="rehab-exercise-list">${tests.map((test) => `<article class="rehab-exercise-card"><span class="soft-tag">TIMED ATTEMPT</span><strong>${escapeHtml(test.name)}</strong><small>${escapeHtml(test.purpose)}</small><p>${escapeHtml(test.preparation || "Use a stable support and clear space.")}</p><p>Target duration: ${test.target_duration_seconds ? `${escapeHtml(test.target_duration_seconds)} sec` : "No timed target"}</p><button class="primary-button compact" type="button" data-rehab-action="start-functional-test" data-test-id="${escapeHtml(test.id)}">Start test</button></article>`).join("")}</div>` : healthEmpty("No tests available", "Functional tests load from your Rehab API."), state, testId ? "rehab/functional-tests" : "rehab");
  }
  if (route === "rehab/readiness") {
    const assessment = data.assessment;
    return rehabScreenShell(route, "Today's rehab readiness", "A traceable rehabilitation signal, not medical clearance.", `
      ${assessment ? rehabPanel(rehabTag(assessment.status), `<p>${escapeHtml(assessment.recommendation || "")}</p><h3>Recorded factors</h3><ul>${(assessment.factors || []).map((factor) => `<li>${escapeHtml(factor.factor)}: ${escapeHtml(factor.value)}</li>`).join("")}</ul>`) : healthEmpty("No readiness assessment yet", "Complete the check-in below to create an explanation tied to your reported status and recent recorded sessions.")}
      <form class="health-form" data-form="rehab-readiness"><label class="field"><span>How are you feeling?</span><select name="selfReportedStatus"><option value="">Prefer not to say</option><option value="FEELING_OK">Feeling okay</option><option value="SORE">Sore</option><option value="FATIGUED">Fatigued</option><option value="PAIN_OR_CONCERN">Pain or concern</option></select></label><label class="field"><span>Soreness</span><select name="soreness"><option value="">Not recorded</option><option value="NONE">None</option><option value="MILD">Mild</option><option value="MODERATE">Moderate</option><option value="SEVERE">Severe</option></select></label><button class="primary-button" type="submit">Evaluate readiness</button></form>
      <p class="rehab-caution">This signal cannot diagnose, medically clear or replace advice from your clinician.</p>`, state);
  }
  if (route === "rehab/return-to-sport") {
    const assessment = data.assessment;
    return rehabScreenShell(route, "Return-to-sport progression", "Progression requirements are not medical clearance.", `
      ${assessment ? rehabPanel(rehabTag(assessment.status), `<p>Clinician review: ${rehabTag(assessment.clinician_review_status)}</p><h3>Outstanding</h3><pre class="rehab-json">${escapeHtml(JSON.stringify(assessment.outstanding_requirements || [], null, 2))}</pre>`) : healthEmpty("No progression assessment", "An assessment uses your active program, required exercises, tests and self-reported status.") }
      <form class="health-form" data-form="rehab-return"><label class="field"><span>Your reported progress</span><select name="athleteReportedStatus"><option value="">Not recorded</option><option value="NOT_READY">Not ready</option><option value="PROGRESSING">Progressing</option><option value="READY_FOR_REVIEW">Ready for review</option></select></label><button class="primary-button" type="submit">Evaluate progression</button></form>
      <p class="rehab-caution">VitaPulse does not mark you medically cleared. Any ready state means ready for clinician review only.</p>`, state);
  }
  if (route === "rehab/history") {
    const sessions = [...(data.sessions || [])].sort((left, right) => new Date(right.started_at || right.created_at || 0) - new Date(left.started_at || left.created_at || 0));
    return rehabScreenShell(route, "Rehabilitation history", "Completed sessions with recorded time, source and qualitative movement results.", sessions.length ? `<div class="health-record-list">${sessions.map(sessionCard).join("")}</div>` : healthEmpty("No sessions recorded", "Session history appears after a rehabilitation session is completed."), state);
  }
  if (route === "rehab/reports") {
    return rehabScreenShell(route, "Rehabilitation reports", "Structured report data contracts; rendered PDFs and generated narratives are not enabled.", `
      ${rehabPanel("Available report types", `<ul class="rehab-report-types">${(data.available_types || []).map((type) => `<li>${escapeHtml(type.replaceAll("_", " "))}</li>`).join("")}</ul><p>${escapeHtml(data.note || "No reports are available yet.")}</p>`)}
      ${data.reports?.length ? `<div class="health-record-list">${data.reports.map((report) => `<article class="health-record"><strong>${escapeHtml(report.report_type)}</strong><p>${escapeHtml(report.status)}</p></article>`).join("")}</div>` : healthEmpty("No rehabilitation reports", "Validated report data will appear here when a shared report workflow is connected.")}`, state);
  }
  return rehabHub(state, data);
}

function medicalReportsContent(state) {
  const reports = state.healthData?.["health-reports"]?.reports ?? [];
  const busy = state.healthBusy;
  return `<section class="panel health-panel">
      <div class="health-section-title"><div><h2>Upload a medical report</h2><p>PDF, JPEG or PNG · up to 25 MB</p></div>${icon("lock")}</div>
      <form class="health-form" data-form="health-upload">
        <label class="field"><span>Select a file</span><input type="file" name="report" accept="application/pdf,image/jpeg,image/png" required ${busy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <label class="health-consent"><input type="checkbox" name="consent" value="true" required ${busy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}><span>I agree to upload this report and have it processed to extract health information. I understand it is not a diagnosis.</span></label>
        ${state.healthFormError ? `<p class="form-error" role="alert">${escapeHtml(state.healthFormError)}</p>` : ""}
        <button class="primary-button" type="submit" ${busy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>${busy ? "Uploading…" : "Upload report"} ${icon("arrow")}</button>
      </form>
      <p class="health-disclaimer">Uploads are stored privately. OCR is asynchronous; extracted values are not diagnoses and must be checked against the source.</p>
    </section>
    <section class="health-list-section"><div class="health-section-title"><div><h2>Your reports</h2><p>Latest uploads and processing status</p></div></div>
      ${reports.length ? `<div class="health-record-list">${reports.map((report) => `
        <article class="health-record">
          <div class="health-record-top"><div><strong>${escapeHtml(report.original_filename || "Medical report")}</strong><small>${escapeHtml(dateLabel(report.report_date || report.uploaded_at))} · ${Number(report.file_size || 0) ? `${(report.file_size / 1024 / 1024).toFixed(1)} MB` : "File size unavailable"}</small></div>
          <span class="health-status">${escapeHtml((report.processing_status || "UNKNOWN").replaceAll("_", " "))}</span></div>
          ${report.error_code ? `<p class="health-disclaimer">Processing could not finish (${escapeHtml(report.error_code)}). The source remains available.</p>` : ""}
          ${report.data_quality_warnings?.length ? `<p class="health-disclaimer">${escapeHtml(report.data_quality_warnings.join(", ").replaceAll("_", " ").toLowerCase())}</p>` : ""}
          <div class="health-record-actions"><button class="secondary-button" type="button" data-health-action="source" data-report-id="${escapeHtml(report.id)}">Create private source link</button>
          ${state.healthSourceLink?.id === report.id ? `<a class="text-button" href="${escapeHtml(state.healthSourceLink.url)}" target="_blank" rel="noopener noreferrer">Open source report</a>` : ""}</div>
          <button class="text-button health-delete-action" type="button" data-health-action="delete-report" data-report-id="${escapeHtml(report.id)}" ${state.healthBusy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>Delete report</button>
        </article>`).join("")}</div>` : healthEmpty("No medical reports yet", "Upload a document to create a private, traceable record.")}</section>`;
}

function biomarkersContent(state) {
  const markers = state.healthData?.["health-biomarkers"]?.biomarkers ?? [];
  return `<section class="health-list-section"><div class="health-section-title"><div><h2>Your measurements</h2><p>Extracted values with page-level source context</p></div></div>
    ${markers.length ? `<div class="health-record-list">${markers.map((marker) => `
      <article class="health-record"><div class="health-record-top"><div><strong>${escapeHtml(marker.canonical_name || marker.biomarker_name)}</strong><small>${escapeHtml(dateLabel(marker.latest?.collection_date))} · ${Number(marker.measurement_count)} record${Number(marker.measurement_count) === 1 ? "" : "s"}</small></div>
        <span class="health-value">${marker.latest?.value_numeric === null || marker.latest?.value_numeric === undefined ? escapeHtml(marker.latest?.value_text || "Not extracted") : `${escapeHtml(marker.latest.value_numeric)} ${escapeHtml(marker.latest.unit || "")}`}</span></div>
        <p class="health-disclaimer">Trend: ${escapeHtml(String(marker.trend || "INSUFFICIENT_DATA").replaceAll("_", " ").toLowerCase())}. Descriptive only; not an interpretation.</p>
        ${marker.latest?.reference_low !== null || marker.latest?.reference_high !== null ? `<p class="health-source">Source reference: ${escapeHtml(marker.latest.reference_low ?? "—")} – ${escapeHtml(marker.latest.reference_high ?? "—")} ${escapeHtml(marker.latest.unit || "")}</p>` : `<p class="health-source">No source reference range was available.</p>`}
        <blockquote class="health-source">${escapeHtml(marker.latest?.source_text || "Source text unavailable")}${marker.latest?.source_page ? ` <span>· page ${escapeHtml(marker.latest.source_page)}</span>` : ""}</blockquote>
      </article>`).join("")}</div>` : healthEmpty("No extracted biomarkers", "Measurements appear after a report has been processed. Every value is tied to its source text.")}</section>
    <div class="health-notice">${icon("info")}<span>${escapeHtml(state.healthData?.["health-biomarkers"]?.note || "Reference ranges and trend direction are shown only when present in the source data.")}</span></div>`;
}

function bodyMapContent(state) {
  const regions = state.healthData?.["health-body-map"]?.regions ?? [];
  const regionPositions = {
    head: [50, 8],
    neck: [50, 20],
    "chest-front": [50, 32],
    heart: [44, 33],
    lungs: [56, 33],
    "abdomen-front": [50, 46],
    liver: [58, 44],
    "kidneys-back": [50, 56],
    pelvis: [50, 62],
    "left-shoulder": [32, 28],
    "right-shoulder": [68, 28],
    "left-arm": [24, 48],
    "right-arm": [76, 48],
    back: [50, 50],
    "left-hip": [44, 66],
    "right-hip": [56, 66],
    "left-leg": [43, 84],
    "right-leg": [57, 84],
    skin: [50, 74],
  };
  return `<section class="health-panel panel"><div class="health-section-title"><div><h2>Body regions</h2><p>Personal notes only. This map does not assess or diagnose.</p></div></div>
    <div class="body-map-layout">
      <div class="body-map-visual" aria-label="Body map, select a marked region">
        <svg viewBox="0 0 100 100" role="img" aria-label="Neutral front-facing body silhouette">
          <circle cx="50" cy="10" r="7"></circle>
          <path d="M42 20 Q50 17 58 20 L65 27 L62 46 L59 60 L41 60 L38 46 L35 27 Z"></path>
          <path d="M36 26 L25 31 L18 48 L22 50 L31 39 M64 26 L75 31 L82 48 L78 50 L69 39"></path>
          <path d="M42 60 L39 69 L37 90 L43 91 L49 69 L51 69 L57 91 L63 90 L61 69 L58 60"></path>
        </svg>
        ${regions.map((region) => {
          const identifier = region.anatomical_identifier;
          const position = Object.hasOwn(regionPositions, identifier)
            ? ` body-map-pin--${identifier}`
            : " body-map-pin--center";
          return `<button class="body-map-pin${position} ${state.selectedBodyRegion === region.id ? "selected" : ""}" type="button" data-body-region="${escapeHtml(region.id)}" aria-label="Select ${escapeHtml(region.name)}" title="${escapeHtml(region.name)}"></button>`;
        }).join("")}
      </div>
      <p class="health-disclaimer">Select a region on the map or in the list. The illustration is a navigation aid, not an anatomical assessment.</p>
    </div>
    ${regions.length ? `<div class="body-region-grid">${regions.map((region) => `
      <button class="body-region-card ${state.selectedBodyRegion === region.id ? "selected" : ""}" type="button" data-body-region="${escapeHtml(region.id)}">
        <span><strong>${escapeHtml(region.name)}</strong><small>${escapeHtml(region.system)}</small></span><span class="health-status">${escapeHtml(String(region.state || "NO_DATA").replaceAll("_", " "))}</span>
        ${region.findings?.length ? `<small>${escapeHtml(region.findings.length)} note${region.findings.length === 1 ? "" : "s"} · ${escapeHtml(region.findings[0].description)}</small>` : `<small>No notes recorded</small>`}
      </button>`).join("")}</div>` : healthEmpty("Body map is empty", "Connect the Health API to load body regions and private notes.")}</section>
    <section class="health-panel panel"><div class="health-section-title"><div><h2>Add a personal note</h2><p>Not a diagnosis or medical assessment</p></div></div>
      <form class="health-form" data-form="health-body-note">
        <label class="field"><span>Body region</span><select name="bodyRegion" required ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}><option value="">Choose a region</option>${regions.map((region) => `<option value="${escapeHtml(region.id)}" ${state.selectedBodyRegion === region.id ? "selected" : ""}>${escapeHtml(region.name)}</option>`).join("")}</select></label>
        <label class="field"><span>Note title</span><input name="findingType" maxlength="80" required ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <label class="field"><span>Note</span><textarea name="description" maxlength="1000" rows="3" required ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></textarea></label>
        <button class="primary-button" type="submit" ${state.healthBusy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>Save note</button>
      </form>
    </section>`;
}

function intelligenceContent(state) {
  const data = state.healthData?.["health-intelligence"] ?? {};
  const items = data.items ?? [];
  return `<div class="health-notice">${icon("info")}<span>${escapeHtml(data.notice || "Health intelligence is unavailable until an evidence-linked engine is configured. No predictions are shown.")}</span></div>
    ${items.length ? `<div class="health-record-list">${items.map((item) => `<article class="health-record"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.explanation)}</p><small>${escapeHtml(item.status)} · ${escapeHtml(dateLabel(item.observed_at || item.created_at))}</small></article>`).join("")}</div>` : healthEmpty("No health intelligence available", "This feature will only display validated information with source evidence.")}`;
}

function nutritionContent(state) {
  const data = state.healthData?.["health-nutrition"] ?? {};
  const profile = data.profile ?? {};
  const entries = data.entries ?? [];
  return `<section class="health-panel panel"><div class="health-section-title"><div><h2>Your nutrition goal</h2><p>Personal tracking, not a prescribed diet</p></div></div>
    <form class="health-form health-form-grid" data-form="health-nutrition-profile">
      <label class="field"><span>Goal</span><select name="goal" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>${[["GENERAL_SPORTS_NUTRITION", "General sports nutrition"], ["RECOVERY", "Recovery"], ["PERFORMANCE", "Performance"], ["STRENGTH", "Strength"], ["ENDURANCE", "Endurance"], ["BODY_COMPOSITION", "Body composition"]].map(([value, label]) => `<option value="${value}" ${profile.goal === value ? "selected" : ""}>${label}</option>`).join("")}</select></label>
      <label class="field"><span>Hydration goal (mL/day, optional)</span><input type="number" min="0" max="15000" step="1" name="hydrationGoal" value="${escapeHtml(profile.hydration_goal_ml ?? "")}" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <button class="primary-button" type="submit" ${state.healthBusy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>Save goal</button>
    </form></section>
    <section class="health-panel panel"><div class="health-section-title"><div><h2>Log an entry</h2><p>Only information you choose to record</p></div></div>
      <form class="health-form health-form-grid" data-form="health-nutrition-entry">
        <label class="field"><span>Date</span><input type="date" name="entryDate" value="${new Date().toISOString().slice(0, 10)}" required ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <label class="field"><span>Entry type</span><select name="entryType"><option value="MEAL">Meal</option><option value="HYDRATION">Hydration</option><option value="MICRONUTRIENT">Micronutrient</option></select></label>
        <label class="field"><span>Name</span><input name="name" maxlength="160" required ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <label class="field"><span>Hydration (mL)</span><input type="number" min="0" max="15000" name="hydrationMl" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <label class="field"><span>Calories (optional)</span><input type="number" min="0" max="10000" name="calories" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <label class="field"><span>Protein (g, optional)</span><input type="number" min="0" max="1000" name="proteinG" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
        <button class="primary-button" type="submit" ${state.healthBusy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>Save entry</button>
      </form></section>
    <section class="health-list-section"><div class="health-section-title"><div><h2>Recent entries</h2></div></div>
      ${entries.length ? `<div class="health-record-list">${entries.map((entry) => `<article class="health-record"><div class="health-record-top"><strong>${escapeHtml(entry.name)}</strong><span>${escapeHtml(dateLabel(entry.entry_date))}</span></div><small>${escapeHtml(entry.entry_type)}${entry.hydration_ml !== null ? ` · ${escapeHtml(entry.hydration_ml)} mL` : ""}${entry.calories !== null ? ` · ${escapeHtml(entry.calories)} kcal` : ""}</small></article>`).join("")}</div>` : healthEmpty("No nutrition entries yet", "Your logged meals and hydration will appear here.")}</section>`;
}

function medicationContent(state) {
  const medications = state.healthData?.["health-medication"]?.medications ?? [];
  return `<section class="health-panel panel"><div class="health-section-title"><div><h2>Add medication</h2><p>Medication logging is not a prescribing service.</p></div></div>
    <form class="health-form health-form-grid" data-form="health-medication">
      <label class="field"><span>Name</span><input name="name" maxlength="200" required ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <label class="field"><span>Dose (optional)</span><input name="dose" maxlength="120" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <label class="field"><span>Frequency (optional)</span><input name="frequency" maxlength="160" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <label class="field"><span>Start date</span><input type="date" name="startDate" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <label class="field"><span>End date</span><input type="date" name="endDate" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <label class="field"><span>Reason (optional)</span><input name="reason" maxlength="1000" ${state.session.demo || !state.healthApiConfigured ? "disabled" : ""}></label>
      <button class="primary-button" type="submit" ${state.healthBusy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>Add medication</button>
    </form></section>
    <section class="health-list-section"><div class="health-section-title"><div><h2>Your medications</h2></div></div>
      ${medications.length ? `<div class="health-record-list">${medications.map((medication) => `<article class="health-record"><div class="health-record-top"><strong>${escapeHtml(medication.name)}</strong><span class="health-status">${escapeHtml(medication.status)}</span></div><p>${escapeHtml(medication.dose || "Dose not recorded")}${medication.frequency ? ` · ${escapeHtml(medication.frequency)}` : ""}</p><small>${escapeHtml(medication.reason || "Reason not recorded")}</small>
        ${medication.status === "ACTIVE" ? `<button class="text-button" type="button" data-health-action="complete-medication" data-resource-id="${escapeHtml(medication.id)}" ${state.healthBusy ? "disabled" : ""}>Mark completed</button>` : ""}</article>`).join("")}</div>` : healthEmpty("No medications recorded", "Items you add will appear here. Nothing is inferred from reports.")}</section>`;
}

function antiDopingContent(state) {
  const data = state.healthData?.["health-anti-doping"] ?? {};
  return `<section class="health-panel panel"><div class="health-section-title"><div><h2>Current review status</h2><p>${escapeHtml(String(data.status || "INSUFFICIENT_INFORMATION").replaceAll("_", " "))}</p></div><span class="health-status">${escapeHtml(data.source_status || "NOT_CONFIGURED")}</span></div>
    <div class="health-notice health-notice-warning">${icon("info")}<span>${escapeHtml(data.notice || "No current verified prohibited-list source is connected. This is not anti-doping clearance.")}</span></div>
    <p class="health-disclaimer">Rules depend on sport, event and effective date. Check current official guidance and consult a qualified anti-doping professional.</p>
    ${data.reviews?.length ? `<div class="health-record-list">${data.reviews.map((review) => `<article class="health-record"><strong>${escapeHtml(review.substance_name || "Review")}</strong><small>${escapeHtml(review.status)} · ${escapeHtml(dateLabel(review.created_at))}</small></article>`).join("")}</div>` : ""}</section>`;
}

function skinContent(state) {
  const data = state.healthData?.["health-skin-screening"] ?? {};
  const records = data.records ?? [];
  return `<section class="health-panel panel"><div class="health-section-title"><div><h2>Skin screening</h2><p>Visual screening is not diagnosis.</p></div><span class="health-status">${escapeHtml(data.status || "NOT_CONFIGURED")}</span></div>
    <div class="health-notice health-notice-warning">${icon("info")}<span>${data.feature_enabled ? "The feature is enabled in configuration, but no validated assessment model is connected." : "This feature is not enabled. No image is uploaded or analyzed."}</span></div>
    <p class="health-disclaimer">A clinician should assess any concerning or changing skin lesion. A screening tool cannot rule out disease.</p>
    ${records.length ? `<div class="health-record-list">${records.map((item) => `<article class="health-record"><strong>${escapeHtml(item.result)}</strong><small>${escapeHtml(item.quality_status)} · ${escapeHtml(dateLabel(item.created_at))}</small></article>`).join("")}</div>` : healthEmpty("No screening records", "No camera or gallery access is requested while screening is unavailable.")}</section>`;
}

function healthHistoryContent(state) {
  const reports = state.healthData?.["health-history"]?.reports ?? [];
  const medicalReports = state.healthData?.["health-reports"]?.reports ?? [];
  return `<section class="health-list-section"><div class="health-section-title"><div><h2>Health report drafts</h2><p>Drafts reference data you selected; they do not contain a clinical interpretation.</p></div></div>
    ${reports.length ? `<div class="health-record-list">${reports.map((report) => `<article class="health-record"><div class="health-record-top"><strong>${escapeHtml(report.report_type.replaceAll("_", " "))}</strong><span class="health-status">${escapeHtml(report.status)}</span></div><small>Created ${escapeHtml(dateLabel(report.created_at))} · ${Number(report.source_ids?.length || 0)} source(s)</small><p>${escapeHtml(report.summary || "Draft only — no interpretation or PDF has been generated.")}</p></article>`).join("")}</div>` : healthEmpty("No health report drafts yet", "Create a draft from one of your uploaded reports.")}
    ${medicalReports.length ? `<div class="health-record-list">${medicalReports.filter((item) => item.processing_status === "COMPLETED").map((report) => `<article class="health-record"><div class="health-record-top"><strong>${escapeHtml(report.original_filename || "Medical report")}</strong><span>${escapeHtml(dateLabel(report.report_date || report.uploaded_at))}</span></div><button class="secondary-button" type="button" data-health-action="create-report-draft" data-report-id="${escapeHtml(report.id)}" ${state.healthBusy || state.session.demo || !state.healthApiConfigured ? "disabled" : ""}>Create analysis draft</button></article>`).join("")}</div>` : ""}</section>`;
}

function healthPage(route, state) {
  if (route === "health") return healthOverview(state);
  const contentByRoute = {
    "health-reports": ["Medical reports", "Upload private health documents and follow OCR processing.", medicalReportsContent],
    "health-biomarkers": ["Biomarkers", "Review source-linked measurements without turning them into a diagnosis.", biomarkersContent],
    "health-body-map": ["Body map", "Organize personal notes by body region. This is not an assessment.", bodyMapContent],
    "health-intelligence": ["Health intelligence", "Evidence-linked insights are shown only when a validated engine is connected.", intelligenceContent],
    "health-nutrition": ["Nutrition", "Keep a personal record of nutrition and hydration.", nutritionContent],
    "health-medication": ["Medication", "Maintain your own medication record and its source.", medicationContent],
    "health-anti-doping": ["Anti-doping", "Check source availability; an unavailable list never means clearance.", antiDopingContent],
    "health-skin-screening": ["Skin screening", "See feature availability and limitations before sharing an image.", skinContent],
    "health-history": ["Health reports", "Review drafts linked to your selected health records.", healthHistoryContent],
  };
  const [title, description, renderContent] = contentByRoute[route] ?? contentByRoute["health-reports"];
  const content = state.healthLoading || state.healthError ? "" : renderContent(state);
  return healthHeader(route, title, description, content, state);
}

function detailPage(state) {
  const detail = state.detail;
  if (!detail) return modulePage(state.lastModule || "health");
  return `<section class="page-intro"><button class="back-link" type="button" data-action="back">${icon("arrow")} Back</button><p class="eyebrow">VITAPULSE MODULE</p><h1>${escapeHtml(detail)}</h1><p>A dedicated space for this part of your sports-health journey.</p></section>
    <section class="panel large-empty">${emptyState("Nothing here yet", "This feature is being prepared. When it is available, your information will appear here.", "home")}</section>`;
}

function profilePage(session, state) {
  const fullName = escapeHtml(session.name || "Athlete");
  const email = escapeHtml(session.email || "Email unavailable");
  const doctor = session.role === "DOCTOR" || session.role === "ADMIN";
  const role = doctor ? "Doctor" : "Athlete";
  const athlete = state.athleteProfile ?? {};
  const profileValue = (value) => state.profileLoading
    ? "Loading…"
    : escapeHtml(value || "Not added yet");
  const editing = state.profileEditing && session.role === "ATHLETE";
  if (editing) {
    return `<section class="page-intro"><p class="eyebrow">YOUR ACCOUNT</p><h1>Edit profile</h1><p>Update your personal and sports details.</p></section>
      <section class="panel profile-editor"><form class="auth-form" data-form="profile">
        ${authField({ id: "displayName", label: "Full name", autocomplete: "name", value: session.name })}
        <div class="field-grid">
          ${authField({ id: "dateOfBirth", label: "Date of birth", type: "date", autocomplete: "bday", required: false, value: athlete.date_of_birth, max: new Date().toISOString().slice(0, 10) })}
          ${authField({ id: "sport", label: "Sport", required: false, value: athlete.sport })}
          ${authField({ id: "position", label: "Position", required: false, value: athlete.position })}
          ${authField({ id: "heightCm", label: "Height (cm)", type: "number", min: "50", max: "260", step: "0.1", required: false, value: athlete.height_cm })}
          ${authField({ id: "weightKg", label: "Weight (kg)", type: "number", min: "20", max: "350", step: "0.1", required: false, value: athlete.weight_kg })}
          ${selectField({ id: "dominantSide", label: "Dominant side", value: athlete.dominant_side, options: [["LEFT", "Left"], ["RIGHT", "Right"], ["AMBIDEXTROUS", "Ambidextrous"]] })}
          ${authField({ id: "injuryRegion", label: "Current injury region", required: false, value: athlete.injury_region })}
        </div>
        <label class="field" for="rehabilitationGoal"><span>Rehabilitation goal <small>(optional)</small></span><textarea id="rehabilitationGoal" name="rehabilitationGoal" rows="3">${escapeHtml(athlete.rehabilitation_goal || "")}</textarea></label>
        ${state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : ""}
        <div class="editor-actions"><button class="secondary-button" type="button" data-action="cancel-profile-edit">Cancel</button><button class="primary-button" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? "Saving…" : "Save changes"} ${icon("check")}</button></div>
      </form></section>`;
  }
  return `<section class="page-intro"><p class="eyebrow">YOUR ACCOUNT</p><h1>Profile</h1><p>Your personal details and sports profile.</p></section>
    <section class="panel profile-hero"><span class="avatar avatar-large">${escapeHtml(initials(session.name))}</span><div><h2>${fullName}</h2><p>${email}</p><span class="role-badge">${icon("shield")}${role} account</span></div>${doctor ? "" : '<button class="secondary-button" type="button" data-action="edit-profile">Edit profile</button>'}</section>
    <div class="profile-section-grid">
      <section class="panel profile-section"><h2>Personal information</h2><dl><div><dt>Full name</dt><dd>${fullName}</dd></div><div><dt>Email</dt><dd>${email}</dd></div></dl></section>
      ${doctor
        ? `<section class="panel profile-section"><h2>Professional information</h2><p class="subtle-copy">Verified professional details are managed by your VitaPulse administrator.</p></section>`
        : `<section class="panel profile-section"><h2>Sports information</h2><dl><div><dt>Date of birth</dt><dd>${profileValue(athlete.date_of_birth)}</dd></div><div><dt>Sport</dt><dd>${profileValue(athlete.sport)}</dd></div><div><dt>Position</dt><dd>${profileValue(athlete.position)}</dd></div><div><dt>Height</dt><dd>${athlete.height_cm ? `${escapeHtml(athlete.height_cm)} cm` : profileValue(null)}</dd></div><div><dt>Weight</dt><dd>${athlete.weight_kg ? `${escapeHtml(athlete.weight_kg)} kg` : profileValue(null)}</dd></div><div><dt>Dominant side</dt><dd>${profileValue(athlete.dominant_side)}</dd></div><div><dt>Injury region</dt><dd>${profileValue(athlete.injury_region)}</dd></div></dl><button class="text-button" type="button" data-action="edit-profile">Edit sports information ${icon("arrow")}</button></section>
          <section class="panel profile-section"><h2>Rehabilitation</h2><dl><div><dt>Rehab stage</dt><dd>${profileValue(athlete.rehab_stage)}</dd></div></dl><p class="subtle-copy">Clinician-assigned details appear only when shared with you.</p></section>
          <section class="panel profile-section"><h2>Goals</h2><p class="subtle-copy">${athlete.rehabilitation_goal ? escapeHtml(athlete.rehabilitation_goal) : "Your rehabilitation goal will appear here when you add it."}</p><button class="text-button" type="button" data-action="edit-profile">Edit goals ${icon("arrow")}</button></section>`}
    </div>`;
}

function settingsPage(state) {
  const dark = state.theme === "dark";
  return `<section class="page-intro"><p class="eyebrow">YOUR PREFERENCES</p><h1>Settings</h1><p>Make VitaPulse feel comfortable, clear and secure.</p></section>
    <div class="settings-list">
      <section class="panel settings-group"><div class="settings-title">${icon("moon")}<div><h2>Appearance</h2><p>Light is the default. You can switch themes at any time.</p></div></div>
        <div class="setting-row"><div><strong>Color theme</strong><small>Choose how VitaPulse looks</small></div><div class="segmented"><button type="button" data-theme-choice="light" class="${dark ? "" : "selected"}" aria-pressed="${!dark}">Light</button><button type="button" data-theme-choice="dark" class="${dark ? "selected" : ""}" aria-pressed="${dark}">Dark</button></div></div>
      </section>
      <section class="panel settings-group"><div class="settings-title">${icon("bell")}<div><h2>Notifications</h2><p>Notifications are not connected yet.</p></div></div></section>
      <section class="panel settings-group"><div class="settings-title">${icon("lock")}<div><h2>Privacy</h2><p>Your health information is visible only to you and people you authorize.</p></div></div></section>
      <section class="panel settings-group"><div class="settings-title">${icon("shield")}<div><h2>Permissions</h2><p>No camera or health permissions are requested until a feature needs them.</p></div></div></section>
      <section class="panel settings-group"><div class="settings-title">${icon("connect")}<div><h2>Connected devices</h2><p>No devices connected.</p></div><button class="secondary-button" type="button" data-route="connect">Manage</button></div></section>
      <section class="panel settings-group"><div class="settings-title">${icon("user")}<div><h2>Account</h2><p>${escapeHtml(state.session?.email || "Email unavailable")} · ${state.session?.role === "DOCTOR" ? "Doctor" : "Athlete"}</p></div><button class="secondary-button" type="button" data-route="profile">Profile</button></div></section>
      <section class="panel settings-group"><div class="settings-title">${icon("info")}<div><h2>About VitaPulse</h2><p>Sports health, rehabilitation and recovery — built around you.</p></div></div></section>
      <section class="panel settings-group danger-row"><div><h2>Sign out</h2><p>Sign out of your VitaPulse account on this browser.</p></div><button class="secondary-button danger-button" type="button" data-action="logout">Sign out</button></section>
    </div>`;
}

function doctorPage(route) {
  const content = {
    "doctor-dashboard": ["Your clinical workspace", "An overview of your authorized athlete relationships."],
    "doctor-athletes": ["Athletes", "Athletes who have shared access with you will appear here."],
    "doctor-health": ["Health", "Health information shared by your authorized athletes will appear here."],
    "doctor-rehab": ["Rehabilitation", "Rehabilitation programs shared with you will appear here."],
    "doctor-reports": ["Reports", "Reports shared with your clinical account will appear here."],
  }[route] ?? ["Doctor workspace", "Clinical workspace content will appear here."];
  const cards = route === "doctor-dashboard"
    ? [
      ["Authorized athletes", "user", "No athletes linked yet", "When an athlete shares access, their profile will appear here."],
      ["Pending reviews", "clock", "No pending reviews", "Reviews will appear here when an athlete shares information."],
      ["Recent reports", "heart", "No shared reports", "Reports shared with your account will appear here."],
      ["Rehabilitation alerts", "rehab", "No rehabilitation alerts", "Authorized rehabilitation updates will appear here."],
    ]
    : route === "doctor-athletes"
      ? [["Authorized athletes", "user", "No athletes linked yet", "When an athlete shares access, their profile will appear here."]]
      : route === "doctor-health"
        ? [["Shared health information", "heart", "No shared health information", "Health information shared with your account will appear here."]]
        : route === "doctor-rehab"
          ? [["Rehabilitation reviews", "rehab", "No reviews to show", "Rehabilitation reviews will appear here when shared."]]
          : [["Shared reports", "info", "No shared reports", "Reports shared with your account will appear here."]];
  return `<section class="page-intro doctor-intro"><p class="eyebrow">CLINICAL WORKSPACE</p><h1>${content[0]}</h1><p>Only information shared with your account is shown.</p></section>
    <section class="doctor-welcome"><span class="small-icon health-tint">${icon("shield")}</span><div><strong>Welcome to VitaPulse</strong><p>${content[1]}</p></div><span class="permission-badge">${icon("lock")} Authorized only</span></section>
    <div class="doctor-cards">${cards.map(([title, iconName, emptyTitle, description]) => `
      <article class="panel doctor-card"><span class="small-icon movement-tint">${icon(iconName)}</span><h2>${title}</h2>${emptyState(emptyTitle, description)}</article>`).join("")}
    </div>`;
}

function authLayout(content, message = "") {
  return `<main class="auth-layout">
    <aside class="auth-aside"><div class="auth-aside-inner">${brand()}<div class="aside-copy"><span class="auth-kicker">${icon("activity")} MADE FOR THE WAY YOU MOVE</span>
      <h1>Your health.<br /><span>Your sport.</span><br />Your rhythm.</h1>
      <p>A calmer space for sports health, rehabilitation and recovery — built around the athlete.</p>
      <div class="aside-promise">${icon("shield")} Athlete-first. Private by design. Built to grow with you.</div></div><span class="aside-footer">Your journey, at your pace.</span></div></aside>
    <section class="auth-main"><div class="auth-content">${message ? `<div class="inline-notice" role="status">${icon("info")}<span>${escapeHtml(message)}</span></div>` : ""}${content}<footer>VitaPulse helps you stay curious about your health. It doesn't replace professional medical advice.</footer></div></section>
  </main>`;
}

function authField({
  id,
  label,
  type = "text",
  autocomplete,
  required = true,
  hint = "",
  value = "",
  min = "",
  max = "",
  step = "",
}) {
  return `<label class="field" for="${id}"><span>${label}${required ? "" : ' <small>(optional)</small>'}</span>
    <input id="${id}" name="${id}" type="${type}" ${autocomplete ? `autocomplete="${autocomplete}"` : ""} ${required ? "required" : ""} ${min ? `min="${min}"` : ""} ${max ? `max="${max}"` : ""} ${step ? `step="${step}"` : ""} ${value ? `value="${escapeHtml(value)}"` : ""} ${hint ? `aria-describedby="${id}-hint"` : ""} />
    ${hint ? `<small class="field-hint" id="${id}-hint">${hint}</small>` : ""}</label>`;
}

function selectField({ id, label, value = "", options, required = false }) {
  return `<label class="field" for="${id}"><span>${label}${required ? "" : ' <small>(optional)</small>'}</span>
    <select id="${id}" name="${id}" ${required ? "required" : ""}>
      <option value="">Choose an option</option>
      ${options.map(([optionValue, optionLabel]) => `<option value="${optionValue}" ${value === optionValue ? "selected" : ""}>${optionLabel}</option>`).join("")}
    </select></label>`;
}

function demoNotice() {
  return `<aside class="demo-banner" role="note" aria-label="Development demo mode">
    <strong>DEMO MODE</strong>
    <span>Local-only sample accounts. No real athlete or patient records are included.</span>
    <details><summary>View development demo accounts</summary>
      <div><span>Athlete</span><code>demo@vitapulse.app</code><code>Demo@12345!</code><button class="text-button" type="button" data-demo-sign-in="ATHLETE">Use athlete demo</button></div>
      <div><span>Doctor</span><code>doctor.demo@vitapulse.app</code><code>DemoDoctor@12345!</code><button class="text-button" type="button" data-demo-sign-in="DOCTOR">Use doctor demo</button></div>
    </details>
  </aside>`;
}

function loginPage(state) {
  return authLayout(`${state.demoMode ? demoNotice() : ""}${state.notice ? `<div class="success-notice" role="status">${icon("info")} ${escapeHtml(state.notice)}</div>` : ""}<span class="eyebrow">WELCOME BACK</span><h2 class="auth-title">Let's get you back in.</h2><p class="auth-subtitle">Sign in to continue your VitaPulse journey.</p>
    <form class="auth-form" data-form="login">
      ${authField({ id: "email", label: "Email address", type: "email", autocomplete: "email" })}
      ${authField({ id: "password", label: "Password", type: "password", autocomplete: "current-password" })}
      <div class="form-options"><span>Secure sign-in</span><button type="button" class="text-button" data-auth-mode="forgot">Forgot password?</button></div>
      ${state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : ""}
      <button class="primary-button submit-button" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? "Signing in…" : "Sign in"} ${icon("arrow")}</button>
    </form><div class="auth-divider"><span>NEW TO VITAPULSE?</span></div>
    <p class="auth-switch">Start your journey <button class="text-button" type="button" data-auth-mode="register">Create an account ${icon("arrow")}</button></p>
    <p class="config-hint">${state.configured ? "Your account is protected with Supabase Auth." : "Connect a Supabase project to enable sign-in. See README.md for setup."}</p>`);
}

function registerPage(state) {
  return authLayout(`${state.demoMode ? demoNotice() : ""}<button type="button" class="back-link" data-auth-mode="login">${icon("arrow")} Back to sign in</button><span class="eyebrow">GET STARTED</span><h2 class="auth-title">Make room for your next chapter.</h2><p class="auth-subtitle">Create an account to bring your sports-health journey together.</p>
    <div class="account-tabs" role="group" aria-label="Account type">
      <button type="button" data-account-type="ATHLETE" class="${state.accountType === "ATHLETE" ? "selected" : ""}" aria-pressed="${state.accountType === "ATHLETE"}">I'm an athlete</button>
      <button type="button" data-account-type="DOCTOR" class="${state.accountType === "DOCTOR" ? "selected" : ""}" aria-pressed="${state.accountType === "DOCTOR"}">I'm a doctor</button>
    </div>
    ${state.accountType === "DOCTOR" ? `<div class="approval-note">${icon("shield")}<span>Doctor accounts require verification before clinical access is granted. Registration never grants access to athlete records.</span></div>` : ""}
    <form class="auth-form" data-form="register">
      ${authField({ id: "fullName", label: "Full name", autocomplete: "name" })}
      ${authField({ id: "email", label: "Email address", type: "email", autocomplete: "email" })}
      ${state.accountType === "ATHLETE"
        ? `<p class="form-section-label">Sports profile <small>Optional — you can add these details later.</small></p>
          <div class="field-grid">
            ${authField({ id: "dateOfBirth", label: "Date of birth", type: "date", autocomplete: "bday", required: false, max: new Date().toISOString().slice(0, 10) })}
            ${authField({ id: "sport", label: "Sport", required: false, autocomplete: "off" })}
            ${authField({ id: "position", label: "Position", required: false })}
            ${authField({ id: "heightCm", label: "Height (cm)", type: "number", min: "50", max: "260", step: "0.1", required: false })}
            ${authField({ id: "weightKg", label: "Weight (kg)", type: "number", min: "20", max: "350", step: "0.1", required: false })}
            ${selectField({ id: "dominantSide", label: "Dominant side", options: [["LEFT", "Left"], ["RIGHT", "Right"], ["AMBIDEXTROUS", "Ambidextrous"]] })}
            ${authField({ id: "injuryRegion", label: "Current injury region", required: false })}
          </div>
          <label class="field" for="rehabilitationGoal"><span>Rehabilitation goal <small>(optional)</small></span><textarea id="rehabilitationGoal" name="rehabilitationGoal" rows="3"></textarea></label>`
        : `${authField({ id: "licenseId", label: "License / professional ID" })}${authField({ id: "specialization", label: "Specialization" })}${authField({ id: "organization", label: "Clinic / organization", required: false })}${authField({ id: "phone", label: "Phone number", type: "tel", autocomplete: "tel", required: false })}`}
      ${authField({ id: "password", label: "Password", type: "password", autocomplete: "new-password", hint: "Use at least 8 characters." })}
      ${authField({ id: "confirmPassword", label: "Confirm password", type: "password", autocomplete: "new-password" })}
      ${state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : ""}
      <button class="primary-button submit-button" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? "Creating account…" : state.accountType === "DOCTOR" ? "Request doctor access" : "Create athlete account"} ${icon("arrow")}</button>
    </form><p class="auth-switch">Already have an account? <button class="text-button" type="button" data-auth-mode="login">Sign in</button></p>
    <p class="config-hint">${state.configured ? "Account verification is handled by your secure auth provider." : "Authentication is not connected. Add your Supabase settings to enable account creation."}</p>`);
}

function forgotPage(state) {
  return authLayout(`${state.demoMode ? demoNotice() : ""}<button type="button" class="back-link" data-auth-mode="login">${icon("arrow")} Back to sign in</button><span class="eyebrow">ACCOUNT RECOVERY</span><h2 class="auth-title">Let's get you back on track.</h2><p class="auth-subtitle">Enter the email linked to your account. We'll send a password reset link if it exists.</p>
    ${state.notice ? `<div class="success-notice" role="status">${icon("check")} ${escapeHtml(state.notice)}</div>` : ""}
    <form class="auth-form" data-form="forgot">${authField({ id: "email", label: "Email address", type: "email", autocomplete: "email" })}
      ${state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : ""}
      <button class="primary-button submit-button" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? "Sending…" : "Send reset link"} ${icon("arrow")}</button>
    </form><p class="config-hint">For your security, we don't reveal whether an email address is registered.</p>`);
}

function resetPage(state) {
  return authLayout(`${state.demoMode ? demoNotice() : ""}<button type="button" class="back-link" data-auth-mode="login">${icon("arrow")} Back to sign in</button><span class="eyebrow">RESET PASSWORD</span><h2 class="auth-title">Choose a new password.</h2><p class="auth-subtitle">Create a new password for your VitaPulse account.</p>
    <form class="auth-form" data-form="reset">${authField({ id: "password", label: "New password", type: "password", autocomplete: "new-password", hint: "Use at least 8 characters." })}${authField({ id: "confirmPassword", label: "Confirm new password", type: "password", autocomplete: "new-password" })}
      ${state.error ? `<p class="form-error" role="alert">${escapeHtml(state.error)}</p>` : ""}
      <button class="primary-button submit-button" type="submit" ${state.loading ? "disabled" : ""}>${state.loading ? "Updating…" : "Update password"} ${icon("arrow")}</button>
    </form><p class="config-hint">If this link has expired, request a fresh reset link from the sign-in screen.</p>`);
}

function initials(name) {
  return name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("") || "VP";
}

export function renderAuth(state) {
  if (state.authMode === "register") return registerPage(state);
  if (state.authMode === "forgot") return forgotPage(state);
  if (state.authMode === "reset") return resetPage(state);
  return loginPage(state);
}

export function renderApp(state) {
  const doctor = state.session.role === "DOCTOR" || state.session.role === "ADMIN";
  const route = state.route;
  let content;
  if (route === "home") content = homePage(state.session);
  else if (route === "health" || route.startsWith("health-")) content = healthPage(route, state);
  else if (route === "rehab" || route.startsWith("rehab/")) content = rehabPage(route, state);
  else if (route === "wellbeing") content = wellbeingPage(state);
  else if (modules[route]) content = modulePage(route);
  else if (route === "profile") content = profilePage(state.session, state);
  else if (route === "settings") content = settingsPage(state);
  else if (route === "detail") content = detailPage(state);
  else if (doctor && route.startsWith("doctor-")) content = doctorPage(route);
  else content = homePage(state.session);

  const offline = state.offline ? `<div class="offline-banner" role="status">${icon("info")}<span><strong>You're offline.</strong> Some information may be unavailable.</span></div>` : "";
  const roleLabel = doctor ? "Clinical workspace" : "Athlete space";
  const demo = state.session.demo
    ? `<div class="demo-mode-banner" role="status"><strong>DEMO MODE</strong><span>Development-only synthetic account. No real athlete or patient data is used.</span></div>`
    : "";
  return `<div class="app-shell ${doctor ? "doctor-shell" : ""}">
    <aside class="sidebar" aria-label="Main navigation">
      ${brand()}<p class="nav-label">${roleLabel.toUpperCase()}</p><nav class="main-nav">${navLinks(route, state.session.role)}</nav>
      <div class="sidebar-bottom"><div class="support-card">${icon("shield")}<strong>Built around your wellbeing</strong><p>Small, considered steps — at your pace.</p><span>Private by design</span></div>
      <button class="account-button" type="button" data-route="profile"><span class="avatar">${escapeHtml(initials(state.session.name))}</span><span><strong>${escapeHtml(state.session.name || "Your profile")}</strong><small>${escapeHtml(state.session.email)}</small></span>${icon("more")}</button></div>
    </aside>
    <main class="main-content">
      <header class="topbar">${brand()}<div class="breadcrumb"><span>Pages</span><span>/</span><strong>${pageName(route)}</strong></div>
        <div class="topbar-actions"><div class="network-label ${state.offline ? "is-offline" : ""}">${state.offline ? "Offline" : "Online"}</div>
          <button class="header-icon" type="button" aria-label="Open settings" data-route="settings">${icon("settings")}</button>
          <button class="header-avatar" type="button" aria-label="Open profile" data-route="profile">${escapeHtml(initials(state.session.name))}</button></div>
      </header>
      ${demo}
      ${offline}
      <div class="page-content">${content}<footer class="page-footer"><span>Made for your wellbeing, one day at a time.</span><span>Your data, your pace <i></i></span></footer></div>
    </main>
    <nav class="bottom-nav ${doctor ? "doctor-bottom-nav" : ""}" aria-label="${doctor ? "Clinical navigation" : "Main navigation"}">${navLinks(route, state.session.role)}</nav>
  </div>`;
}

export function renderLoading(message = "Checking your VitaPulse session…") {
  return `<main class="boot-screen" aria-live="polite"><span class="brand-mark">V</span><span class="loading-mark" aria-hidden="true"></span><p>${escapeHtml(message)}</p></main>`;
}

export function renderDoctorApproval() {
  return authLayout(`<span class="status-icon">${icon("shield")}</span><span class="eyebrow">DOCTOR ACCESS</span><h2 class="auth-title">Your request is on its way.</h2><p class="auth-subtitle">A doctor account requires verification. Clinical tools stay locked until your access is approved.</p>
    <div class="approval-note">${icon("lock")}<span>You won't see athlete records until an administrator verifies your professional details and grants access.</span></div>
    <button class="primary-button submit-button" type="button" data-action="doctor-request-done">Return to sign in ${icon("arrow")}</button>`);
}

export { initials };
