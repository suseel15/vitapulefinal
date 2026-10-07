import { AuthError, SupabaseAuth } from "./src/auth.js";
import { authIsConfigured, demoModeEnabled, healthApiIsConfigured } from "./src/config.js";
import {
  escapeHtml,
  renderApp,
  renderAuth,
  renderDoctorApproval,
  renderLoading,
} from "./src/ui.js";
import {
  SimulationMovementDataSource,
  RehabSafetyMonitor,
  SquatRepetitionDetector,
  summarizeMovementSamples,
} from "./src/rehab-movement.js";

function getRecoveryToken(hash) {
  const recoveryParams = new URLSearchParams(hash.slice(1));
  return recoveryParams.get("type") === "recovery"
    ? recoveryParams.get("access_token") || ""
    : "";
}

let recoveryToken = getRecoveryToken(location.hash);
if (recoveryToken) history.replaceState({}, "", `${location.pathname}${location.search}`);
const requestedAuthMode = new URLSearchParams(location.search).get("auth");

const appRoot = document.querySelector("#app");
const toastRoot = document.querySelector("#toast-region");
const preferenceStore = window.localStorage;
const auth = new SupabaseAuth();
const initialTheme = preferenceStore.getItem("vitapulse.theme") === "dark" ? "dark" : "light";
const state = {
  authMode: recoveryToken ? "reset" : requestedAuthMode === "register" ? "register" : "login",
  accountType: "ATHLETE",
  approvalScreen: false,
  booting: true,
  configured: authIsConfigured,
  healthApiConfigured: healthApiIsConfigured,
  healthBusy: false,
  healthData: {},
  connectContext: {
    activityRecords: [],
    error: "",
    heartRateRecords: [],
    lastLoadedAt: 0,
    loading: false,
    sleepRecords: [],
    status: null,
  },
  wellbeing: {
    overview: null,
    checkins: [],
    sleepRecords: [],
    recoveryRecords: [],
    history: [],
    trends: null,
    reports: [],
    loading: false,
    busy: false,
    error: "",
  },
  reporting: {
    reports: [],
    detail: null,
    selectedId: "",
    status: {},
    loading: false,
    busy: false,
    error: "",
  },
  rehabData: {},
  rehabLoading: false,
  rehabError: "",
  rehabBusy: false,
  rehabSession: null,
  rehabScenario: "NORMAL",
  rehabConfirmStop: false,
  functionalTestRun: null,
  healthError: "",
  healthFormError: "",
  healthLoading: false,
  healthSourceLink: null,
  selectedBodyRegion: "",
  demoMode: demoModeEnabled,
  detail: "",
  error: "",
  lastModule: "health",
  loading: false,
  notice: "",
  offline: !navigator.onLine,
  athleteProfile: null,
  profileLoading: false,
  profileEditing: false,
  route: "home",
  session: null,
  theme: initialTheme,
};
let toastTimer;
const healthRoutes = new Set([
  "health",
  "health-reports",
  "health-body-map",
  "health-biomarkers",
  "health-intelligence",
  "health-nutrition",
  "health-medication",
  "health-anti-doping",
  "health-skin-screening",
  "health-history",
]);
const REHAB_STORAGE_KEY = "vitapulse.rehab.sessions.v1";
const rehabTimer = { interval: null, testInterval: null, lastRenderAt: 0 };
let reportPollTimer = null;

function isRehabRoute(route) {
  return new Set([
    "rehab", "rehab/today", "rehab/program", "rehab/exercises", "rehab/session",
    "rehab/movement", "rehab/progress", "rehab/recovery", "rehab/functional-tests",
    "rehab/readiness", "rehab/return-to-sport", "rehab/history", "rehab/reports",
  ]).has(route) || /^rehab\/(?:program|exercises|session|movement|functional-tests)\/[^/]+(?:\/result)?$/.test(route);
}

function rehabStorageKey() {
  return `${REHAB_STORAGE_KEY}.${state.session?.userId || "anonymous"}`;
}
function showToast(message) {
  toastRoot.innerHTML = `<div class="toast">${escapeHtml(message)}</div>`;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toastRoot.replaceChildren();
  }, 3000);
}

function render() {
  document.documentElement.dataset.theme = state.theme;
  document.documentElement.style.colorScheme = state.theme;
  if (state.booting) {
    appRoot.innerHTML = renderLoading();
  } else if (state.approvalScreen) {
    appRoot.innerHTML = renderDoctorApproval();
  } else if (state.session) {
    appRoot.innerHTML = renderApp(state);
  } else {
    appRoot.innerHTML = renderAuth(state);
  }
}

function navigate(route, { replace = false } = {}) {
  const doctor = state.session?.role === "DOCTOR" || state.session?.role === "ADMIN";
  const validDoctorRoute = route.startsWith("doctor-");
  const validAthleteRoute = ["home", "wellbeing", "connect", "profile", "settings", "detail"].includes(route) ||
    route === "reports" ||
    isRehabRoute(route) ||
    healthRoutes.has(route);
  if (!state.session || (doctor ? !validDoctorRoute && !["profile", "settings"].includes(route) : !validAthleteRoute)) {
    return;
  }
  if (route === "detail") state.detail = state.detail || "VitaPulse feature";
  if (healthRoutes.has(route)) state.lastModule = "health";
  else if (isRehabRoute(route)) state.lastModule = "rehab";
  else if (["wellbeing", "connect"].includes(route)) state.lastModule = route;
  state.route = route;
  const url = `#${route}`;
  if (replace) history.replaceState({ route }, "", url);
  else if (location.hash !== url) history.pushState({ route }, "", url);
  render();
  if (route !== "reports") stopReportPolling();
  if (route === "profile" && state.session.role === "ATHLETE" && !state.athleteProfile) {
    void loadAthleteProfile();
  }
  if (route === "home" || route === "wellbeing" || route === "rehab" || route === "rehab/recovery") {
    void loadConnectContext();
  }
  if (healthRoutes.has(route)) void loadHealthRoute(route);
  if (route === "wellbeing") void loadWellbeingRoute();
  if (route === "reports") void loadReports();
  if (isRehabRoute(route)) void loadRehabRoute(route);
  if (!isRehabRoute(route)) {
    stopFunctionalTestTimer();
    if (state.rehabSession?.status === "ACTIVE") {
      stopRehabTimer();
      void updateRehabSessionStatus("PAUSED");
    }
    else stopRehabTimer();
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function loadConnectContext() {
  const context = state.connectContext;
  const userId = state.session?.userId;
  if (context.loading || (context.lastLoadedAt && Date.now() - context.lastLoadedAt < 60_000)) return;
  if (state.session?.role !== "ATHLETE" || state.session?.demo || !state.healthApiConfigured) {
    state.connectContext = { ...context, lastLoadedAt: Date.now() };
    render();
    return;
  }
  state.connectContext = { ...context, loading: true, error: "" };
  render();
  try {
    const [status, sleep, heartRate, activity] = await Promise.all([
      auth.apiRequest(state.session, "/connect/status"),
      auth.apiRequest(state.session, "/health-data/sleep?limit=100"),
      auth.apiRequest(state.session, "/health-data/heart-rate?limit=100"),
      auth.apiRequest(state.session, "/health-data/activity?limit=100"),
    ]);
    if (state.session?.userId !== userId) return;
    state.connectContext = {
      activityRecords: activity?.activity_records || [],
      error: "",
      heartRateRecords: heartRate?.heart_rate_records || [],
      lastLoadedAt: Date.now(),
      loading: false,
      sleepRecords: sleep?.sleep_records || [],
      status: status?.health_connect || null,
    };
  } catch (error) {
    if (state.session?.userId !== userId) return;
    state.connectContext = {
      ...state.connectContext,
      error: friendlyError(error),
      lastLoadedAt: Date.now(),
      loading: false,
    };
  }
  render();
}

function clearConnectContext() {
  state.connectContext = {
    activityRecords: [],
    error: "",
    heartRateRecords: [],
    lastLoadedAt: 0,
    loading: false,
    sleepRecords: [],
    status: null,
  };
}

async function loadHealthRoute(route) {
  state.healthError = "";
  state.healthFormError = "";
  if (state.session?.demo || !state.healthApiConfigured) {
    state.healthLoading = false;
    render();
    return;
  }
  state.healthLoading = true;
  render();
  try {
    let data;
    if (route === "health") {
      data = await auth.healthRequest(state.session, "/overview");
    } else if (route === "health-reports") {
      data = await auth.healthRequest(state.session, "/medical-reports");
    } else if (route === "health-biomarkers") {
      data = await auth.healthRequest(state.session, "/biomarkers");
    } else if (route === "health-body-map") {
      data = await auth.healthRequest(state.session, "/body-map");
    } else if (route === "health-intelligence") {
      data = await auth.healthRequest(state.session, "/health-intelligence");
    } else if (route === "health-nutrition") {
      const [profile, entries] = await Promise.all([
        auth.healthRequest(state.session, "/nutrition/profile"),
        auth.healthRequest(state.session, "/nutrition/entries"),
      ]);
      data = { ...profile, ...entries };
    } else if (route === "health-medication") {
      data = await auth.healthRequest(state.session, "/medications");
    } else if (route === "health-anti-doping") {
      data = await auth.healthRequest(state.session, "/anti-doping");
    } else if (route === "health-skin-screening") {
      data = await auth.healthRequest(state.session, "/skin-screening");
    } else if (route === "health-history") {
      const [reports, medicalReports] = await Promise.all([
        auth.healthRequest(state.session, "/reports"),
        auth.healthRequest(state.session, "/medical-reports"),
      ]);
      data = { ...reports, medical_reports: medicalReports.reports };
      state.healthData["health-reports"] = medicalReports;
    }
    state.healthData[route] = data ?? {};
  } catch (error) {
    state.healthError = friendlyError(error);
  } finally {
    state.healthLoading = false;
    render();
  }
}

async function loadReports({ silent = false } = {}) {
  const reportState = state.reporting;
  if (reportState.loading) return;
  if (state.session?.demo || !state.healthApiConfigured) {
    state.reporting = { ...reportState, loading: false };
    if (!silent) render();
    return;
  }
  const userId = state.session?.userId;
  state.reporting = { ...reportState, loading: true, error: "" };
  if (!silent) render();
  try {
    const response = await auth.apiRequest(state.session, "/reports");
    if (state.session?.userId !== userId) return;
    const reports = response?.reports || [];
    state.reporting = { ...state.reporting, reports, loading: false, error: "" };
    if (reports.some((item) => ["QUEUED", "COLLECTING_DATA", "VALIDATING_INPUT", "GENERATING_AI", "VALIDATING_AI", "BUILDING_REPORT", "RENDERING_HTML", "RENDERING_PDF", "UPLOADING"].includes(item.status))) {
      startReportPolling();
    } else {
      stopReportPolling();
    }
  } catch (error) {
    if (state.session?.userId !== userId) return;
    state.reporting = { ...state.reporting, loading: false, error: friendlyError(error) };
  }
  if (!silent) render();
}

async function loadReportDetails(reportId) {
  if (!reportId || state.reporting.busy) return;
  const userId = state.session?.userId;
  state.reporting = { ...state.reporting, loading: true, error: "" };
  render();
  try {
    const [detail, status] = await Promise.all([
      auth.apiRequest(state.session, `/reports/${encodeURIComponent(reportId)}`),
      auth.apiRequest(state.session, `/reports/${encodeURIComponent(reportId)}/status`),
    ]);
    if (state.session?.userId !== userId) return;
    state.reporting = {
      ...state.reporting,
      selectedId: reportId,
      detail: detail?.report || null,
      status: status || {},
      loading: false,
      error: "",
    };
    if (["QUEUED", "COLLECTING_DATA", "VALIDATING_INPUT", "GENERATING_AI", "VALIDATING_AI", "BUILDING_REPORT", "RENDERING_HTML", "RENDERING_PDF", "UPLOADING"].includes(status?.status)) {
      startReportPolling();
    }
  } catch (error) {
    if (state.session?.userId !== userId) return;
    state.reporting = { ...state.reporting, loading: false, error: friendlyError(error) };
  }
  render();
}

function startReportPolling() {
  if (reportPollTimer) return;
  reportPollTimer = window.setInterval(() => {
    if (state.route !== "reports") {
      stopReportPolling();
      return;
    }
    if (state.reporting.loading || state.reporting.busy) return;
    void loadReports({ silent: true }).then(() => {
      if (state.reporting.selectedId) void loadReportDetails(state.reporting.selectedId);
    });
  }, 5000);
}

function stopReportPolling() {
  if (!reportPollTimer) return;
  window.clearInterval(reportPollTimer);
  reportPollTimer = null;
}

function clearReportState() {
  stopReportPolling();
  state.reporting = {
    reports: [],
    detail: null,
    selectedId: "",
    status: {},
    loading: false,
    busy: false,
    error: "",
  };
}

async function submitReportRequest(form) {
  const data = new FormData(form);
  const startDate = String(data.get("dateRangeStart") || "");
  const endDate = String(data.get("dateRangeEnd") || "");
  if (startDate && endDate && endDate < startDate) {
    state.reporting = { ...state.reporting, error: "The end date must be on or after the start date." };
    render();
    return;
  }
  state.reporting = { ...state.reporting, busy: true, error: "" };
  render();
  try {
    const dateRangeStart = startDate ? new Date(`${startDate}T00:00:00`).toISOString() : null;
    const dateRangeEnd = endDate ? new Date(`${endDate}T23:59:59.999`).toISOString() : null;
    const created = await auth.apiRequest(state.session, "/reports", {
      method: "POST",
      body: {
        reportType: String(data.get("reportType")),
        ...(dateRangeStart ? { dateRangeStart } : {}),
        ...(dateRangeEnd ? { dateRangeEnd } : {}),
        includeAi: data.has("includeAi"),
        includePdf: data.has("includePdf"),
        idempotencyKey: crypto.randomUUID(),
      },
    });
    state.reporting = { ...state.reporting, selectedId: created.reportId, detail: null, busy: false };
    showToast("Your report has been queued.");
    await loadReports();
    startReportPolling();
  } catch (error) {
    state.reporting = { ...state.reporting, busy: false, error: friendlyError(error) };
    render();
  }
}

async function performReportAction(action, reportId = state.reporting.selectedId) {
  const reportState = state.reporting;
  if (action === "back") {
    state.reporting = { ...reportState, detail: null, selectedId: "", status: {}, error: "" };
    render();
  } else if (action === "refresh") {
    await loadReports();
  } else if (action === "view") {
    await loadReportDetails(reportId);
  } else if (action === "download-pdf" || action === "download-html") {
    try {
      const format = action.endsWith("pdf") ? "pdf" : "html";
      const result = await auth.apiRequest(state.session, `/reports/${encodeURIComponent(reportId)}/download?format=${format}`);
      window.location.assign(result.url);
    } catch (error) {
      state.reporting = { ...state.reporting, error: friendlyError(error) };
      render();
    }
  }
}

async function submitReportEmail(form) {
  const recipient = fieldValue(form, "recipient");
  state.reporting = { ...state.reporting, busy: true, error: "" };
  render();
  try {
    await auth.apiRequest(state.session, `/reports/${encodeURIComponent(state.reporting.selectedId)}/email`, {
      method: "POST",
      body: { recipient },
    });
    state.reporting = { ...state.reporting, busy: false };
    showToast("Secure report link queued for email.");
    await loadReports();
    await loadReportDetails(state.reporting.selectedId);
  } catch (error) {
    state.reporting = { ...state.reporting, busy: false, error: friendlyError(error) };
    render();
  }
}

async function loadWellbeingRoute() {
  const current = state.wellbeing;
  state.wellbeing = { ...current, error: "" };
  if (state.session?.demo || !state.healthApiConfigured) {
    state.wellbeing = { ...state.wellbeing, loading: false };
    render();
    return;
  }
  state.wellbeing = { ...state.wellbeing, loading: true };
  render();
  try {
    const [overview, checkins, sleep, recovery, history, trends, reports] = await Promise.all([
      auth.healthRequest(state.session, "/wellbeing/overview"),
      auth.healthRequest(state.session, "/wellbeing/checkins"),
      auth.healthRequest(state.session, "/wellbeing/sleep"),
      auth.healthRequest(state.session, "/wellbeing/recovery"),
      auth.healthRequest(state.session, "/wellbeing/history"),
      auth.healthRequest(state.session, "/wellbeing/trends"),
      auth.healthRequest(state.session, "/wellbeing/reports"),
    ]);
    state.wellbeing = {
      ...state.wellbeing,
      overview,
      checkins: checkins?.checkins || [],
      sleepRecords: sleep?.sleep_records || [],
      recoveryRecords: recovery?.recovery_records || [],
      history: history?.items || [],
      trends,
      reports: reports?.reports || [],
      error: "",
    };
  } catch (error) {
    state.wellbeing = { ...state.wellbeing, error: friendlyError(error) };
  } finally {
    state.wellbeing = { ...state.wellbeing, loading: false };
    render();
  }
}

function addDemoWellbeingRecord(type, record) {
  const createdAt = record.created_at || new Date().toISOString();
  const withDate = { ...record, created_at: createdAt };
  const historyItem = { type, record: withDate, created_at: createdAt };
  const history = [historyItem, ...state.wellbeing.history].slice(0, 100);
  const wellbeing = { ...state.wellbeing, history };
  if (type === "CHECK_IN") {
    const checkins = [withDate, ...wellbeing.checkins].slice(0, 90);
    wellbeing.checkins = checkins;
    wellbeing.overview = { ...(wellbeing.overview || {}), checkin: withDate };
  } else if (type === "SLEEP") {
    const sleepRecords = [withDate, ...wellbeing.sleepRecords].slice(0, 90);
    wellbeing.sleepRecords = sleepRecords;
    wellbeing.overview = { ...(wellbeing.overview || {}), sleep: withDate };
  }
  state.wellbeing = wellbeing;
  refreshDemoWellbeing();
}

function refreshDemoWellbeing() {
  const { checkins, sleepRecords } = state.wellbeing;
  const latestCheckin = checkins[0] || null;
  const latestSleep = sleepRecords[0] || null;
  const factors = {};
  const normalized = [];
  if (latestCheckin) {
    for (const field of ["recovery_feeling", "fatigue", "soreness", "stress"]) {
      factors[field] = { value: latestCheckin[field], source: "SELF_REPORTED" };
      normalized.push(field === "recovery_feeling" ? latestCheckin[field] : 6 - latestCheckin[field]);
    }
  }
  if (latestSleep) {
    factors.sleep_duration_minutes = {
      value: latestSleep.duration_minutes,
      source: latestSleep.source,
    };
  }
  const score = normalized.length ? normalized.reduce((total, value) => total + value, 0) / normalized.length : null;
  const recoveryState = score === null ? "INSUFFICIENT_DATA" : score >= 4 ? "GOOD" : score >= 3 ? "MODERATE" : "LOW";
  const recoveryContext = Object.keys(factors).length
    ? { recovery_state: recoveryState, supporting_factors: factors, source: "CALCULATED" }
    : null;
  const observations = latestCheckin
    ? ["energy", "stress", "fatigue", "soreness", "recovery_feeling"]
      .map((name) => ({ name, value: latestCheckin[name], source: "SELF_REPORTED" }))
    : [];
  if (latestSleep) {
    observations.push({
      name: "sleep_duration_minutes",
      value: latestSleep.duration_minutes,
      source: latestSleep.source,
    });
  }
  state.wellbeing.overview = {
    ...(state.wellbeing.overview || {}),
    checkin: latestCheckin,
    sleep: latestSleep,
    recovery_context: recoveryContext,
    context: {
      recovery_state: recoveryState,
      recovery_source: recoveryContext ? "CALCULATED" : null,
      observations,
      summary: observations.length
        ? "Your recorded self-reported wellbeing and available observations are shown separately. The available information does not establish a medical or psychological diagnosis."
        : "There is not enough recorded information to summarize wellbeing yet.",
    },
  };
  const series = {};
  for (const field of ["energy", "stress", "fatigue", "soreness", "recovery_feeling"]) {
    const values = checkins.slice().reverse().map((entry) => Number(entry[field]));
    const highIsGood = !["stress", "fatigue", "soreness"].includes(field);
    series[field] = { values, source: "SELF_REPORTED", higher_is_better: highIsGood, trend: classifyDemoTrend(values, highIsGood) };
  }
  const sleepValues = sleepRecords.slice().reverse().map((entry) => Number(entry.duration_minutes));
  series.sleep_duration_minutes = {
    values: sleepValues,
    sources: [...new Set(sleepRecords.map((entry) => entry.source))],
    higher_is_better: true,
    trend: classifyDemoTrend(sleepValues, true),
  };
  state.wellbeing.trends = { series };
}

function classifyDemoTrend(values, higherIsBetter) {
  if (values.length < 3) return { classification: "INSUFFICIENT_DATA", observation_count: values.length, direction: null };
  const ordered = higherIsBetter ? values : values.map((value) => -value);
  const chunk = Math.max(1, Math.floor(ordered.length / 3));
  const first = ordered.slice(0, chunk).reduce((sum, value) => sum + value, 0) / chunk;
  const last = ordered.slice(-chunk).reduce((sum, value) => sum + value, 0) / chunk;
  const mean = ordered.reduce((sum, value) => sum + value, 0) / ordered.length;
  const deviation = Math.sqrt(ordered.reduce((sum, value) => sum + (value - mean) ** 2, 0) / ordered.length);
  const delta = last - first;
  const classification = deviation >= 1
    ? "VARIABLE"
    : Math.abs(delta) < 0.5
      ? "STABLE"
      : delta > 0
        ? "IMPROVING"
        : "DECLINING";
  return {
    classification,
    observation_count: values.length,
    direction: delta > 0 ? "UP" : delta < 0 ? "DOWN" : "UNCHANGED",
  };
}

function localDateTimeToIso(value) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) {
    const error = new Error("Enter valid bedtime and wake times.");
    error.name = "WellbeingInputError";
    throw error;
  }
  return date.toISOString();
}

async function submitWellbeingForm(form) {
  const formType = form.dataset.form;
  const data = new FormData(form);
  state.wellbeing = { ...state.wellbeing, busy: true, error: "" };
  render();
  try {
    if (formType === "wellbeing-checkin") {
      const body = {
        energy: Number(data.get("energy")),
        stress: Number(data.get("stress")),
        fatigue: Number(data.get("fatigue")),
        soreness: Number(data.get("soreness")),
        recovery_feeling: Number(data.get("recoveryFeeling")),
        mood_self_report: data.get("moodSelfReport") ? Number(data.get("moodSelfReport")) : null,
        note: String(data.get("note") || "").trim() || null,
        source: "SELF_REPORTED",
      };
      if (state.session.demo) {
        addDemoWellbeingRecord("CHECK_IN", body);
      } else {
        await auth.healthRequest(state.session, "/wellbeing/checkins", { method: "POST", body });
      }
      showToast("Your self-reported check-in was saved.");
    } else if (formType === "wellbeing-sleep") {
      const startTime = localDateTimeToIso(String(data.get("startTime") || ""));
      const endTime = localDateTimeToIso(String(data.get("endTime") || ""));
      if (new Date(endTime) <= new Date(startTime)) {
        const error = new Error("Wake time must be after bedtime and within 24 hours.");
        error.name = "WellbeingInputError";
        throw error;
      }
      const durationMinutes = Math.round((new Date(endTime) - new Date(startTime)) / 60_000);
      if (durationMinutes > 1440) {
        const error = new Error("A sleep entry cannot exceed 24 hours.");
        error.name = "WellbeingInputError";
        throw error;
      }
      const body = {
        start_time: startTime,
        end_time: endTime,
        quality_rating: data.get("qualityRating") ? Number(data.get("qualityRating")) : null,
        interruptions: data.get("interruptions") ? Number(data.get("interruptions")) : null,
        notes: String(data.get("notes") || "").trim() || null,
        source: "SELF_REPORTED",
      };
      if (state.session.demo) {
        addDemoWellbeingRecord("SLEEP", { ...body, duration_minutes: durationMinutes });
      } else {
        await auth.healthRequest(state.session, "/wellbeing/sleep", { method: "POST", body });
      }
      showToast("Your sleep entry was saved.");
    }
    await loadWellbeingRoute();
  } catch (error) {
    state.wellbeing = {
      ...state.wellbeing,
      error: error?.name === "WellbeingInputError" ? error.message : friendlyError(error),
    };
  } finally {
    state.wellbeing = { ...state.wellbeing, busy: false };
    render();
  }
}

async function createWellbeingReport() {
  if (state.wellbeing.busy || state.session?.demo || !state.healthApiConfigured) return;
  const history = state.wellbeing.history;
  if (!history.length) {
    state.wellbeing = { ...state.wellbeing, error: "Record a check-in or sleep entry before creating a summary." };
    render();
    return;
  }
  const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
  const recent = history.filter((item) => new Date(item.created_at).getTime() >= cutoff);
  if (!recent.length) {
    state.wellbeing = { ...state.wellbeing, error: "There are no wellbeing records from the past seven days to summarize." };
    render();
    return;
  }
  const sourceProvenance = [...new Set(recent.map((item) => {
    if (item.type === "CAMERA") return "CAMERA_OBSERVED";
    if (item.type === "RECOVERY") return "CALCULATED";
    return item.record?.source || "SELF_REPORTED";
  }))];
  const reportData = {
    period_start: new Date(cutoff).toISOString(),
    period_end: new Date().toISOString(),
    record_count: recent.length,
    records: recent.map((item) => ({
      type: item.type,
      created_at: item.created_at,
      source: item.record?.source || (item.type === "RECOVERY" ? "CALCULATED" : null),
      values: item.type === "CHECK_IN"
        ? Object.fromEntries(["energy", "stress", "fatigue", "soreness", "recovery_feeling", "mood_self_report"]
          .filter((key) => Number.isInteger(item.record?.[key]))
          .map((key) => [key, item.record[key]]))
        : item.type === "SLEEP"
          ? Object.fromEntries(["start_time", "end_time", "duration_minutes", "quality_rating", "interruptions"]
            .filter((key) => item.record?.[key] !== null && item.record?.[key] !== undefined)
            .map((key) => [key, item.record[key]]))
          : item.type === "RECOVERY"
            ? { recovery_state: item.record?.recovery_state, supporting_factors: item.record?.supporting_factors || {} }
            : item.type === "CAMERA"
              ? { capture_quality: item.record?.capture_quality, duration_seconds: item.record?.duration_seconds }
              : { report_type: item.record?.report_type },
    })),
    context: state.wellbeing.overview?.context || null,
  };
  state.wellbeing = { ...state.wellbeing, busy: true, error: "" };
  render();
  try {
    await auth.healthRequest(state.session, "/wellbeing/reports", {
      method: "POST",
      body: {
        report_type: "WEEKLY_WELLBEING",
        report_data: reportData,
        source_provenance: sourceProvenance,
        limitations: [
          "This summary reflects only records entered in the selected period.",
          "Wellbeing records do not establish a medical or psychological diagnosis.",
        ],
      },
    });
    showToast("Your weekly summary was saved.");
    await loadWellbeingRoute();
  } catch (error) {
    state.wellbeing = { ...state.wellbeing, error: friendlyError(error) };
  } finally {
    state.wellbeing = { ...state.wellbeing, busy: false };
    render();
  }
}

function readRehabSessions() {
  return JSON.parse(preferenceStore.getItem(rehabStorageKey()) || "[]");
}

function saveRehabSession(session) {
  const storedSession = { ...session, samples: [] };
  const sessions = readRehabSessions();
  const existingIndex = sessions.findIndex((item) => item.id === storedSession.id);
  if (existingIndex < 0) sessions.unshift(storedSession);
  else sessions[existingIndex] = storedSession;
  preferenceStore.setItem(rehabStorageKey(), JSON.stringify(sessions.slice(0, 100)));
}

function demoExercises() {
  return [
    {
      id: "demo-single-leg-squat",
      slug: "single-leg-squat",
      name: "Single-Leg Squat",
      category: "STRENGTH",
      target_region: "Lower body",
      target_muscles: ["quadriceps", "gluteals"],
      goal: "Practice controlled single-leg strength.",
      difficulty: "INTERMEDIATE",
      default_sets: 3,
      default_repetitions: 8,
      rest_seconds: 60,
      requires_sensor: true,
      default_sensor_placement: "THIGH",
      instructions: {
        starting_position: "Stand near a stable support.",
        execution: "Shift weight to one leg and bend through a comfortable range, then return with control.",
      },
      common_mistakes: ["Moving beyond a comfortable range", "Losing balance"],
    },
    {
      id: "demo-supported-calf-raise",
      slug: "calf-raise",
      name: "Supported Calf Raise",
      category: "STRENGTH",
      target_region: "Lower leg",
      target_muscles: ["calf"],
      goal: "Practice controlled ankle movement.",
      difficulty: "BEGINNER",
      default_sets: 2,
      default_repetitions: 10,
      rest_seconds: 45,
      requires_sensor: false,
      instructions: {
        starting_position: "Stand near a stable support.",
        execution: "Rise onto the balls of your feet, then lower slowly.",
      },
      common_mistakes: ["Bouncing through the movement"],
    },
  ];
}

function demoRehabData(route) {
  const exercises = demoExercises();
  const now = Date.now();
  const history = readRehabSessions().filter((session) => session.demo);
  const syntheticProgram = {
    id: "demo-program",
    name: "Strength & Stability",
    description: "Synthetic development-only program preview. It is not assigned clinical care.",
    goal: "Build controlled lower-body movement.",
    stage: "Strength & Stability",
    stage_order: 2,
    stages: [
      { order: 0, name: "Mobility" },
      { order: 1, name: "Control" },
      { order: 2, name: "Strength & Stability" },
      { order: 3, name: "Sport-Specific Movement" },
    ],
    start_date: new Date(now - 21 * 86400000).toISOString().slice(0, 10),
    target_end_date: null,
    status: "ACTIVE",
  };
  const assignments = exercises.map((exercise, index) => ({
    id: `demo-assignment-${index}`,
    exercise_id: exercise.id,
    order_index: index,
    sets: exercise.default_sets,
    repetitions: exercise.default_repetitions,
    duration_seconds: null,
    rest_seconds: exercise.rest_seconds,
    required: true,
    exercise,
  }));
  if (route === "rehab") {
    return {
      current_program: syntheticProgram,
      current_stage: { name: syntheticProgram.stage, order: syntheticProgram.stage_order },
      today: { exercises: assignments, completed: history.length, remaining: Math.max(0, assignments.length - history.length) },
      readiness: null,
      movement_quality: history[0]?.movement_quality || null,
      recovery: { status: "UNAVAILABLE", sleep: null },
      progress: { sessions_completed: history.length, functional_tests_completed: 0 },
      recent_sessions: history.slice(0, 5),
      program_assigned: true,
      demo_data: true,
    };
  }
  if (route === "rehab/today") return { program: syntheticProgram, stage: { name: syntheticProgram.stage }, exercises: assignments, completed: history.length, remaining: Math.max(0, assignments.length - history.length), demo_data: true };
  if (route === "rehab/program") return { program: syntheticProgram, exercises: assignments, programs: [syntheticProgram], demo_data: true };
  if (route === "rehab/exercises") return { exercises, demo_data: true };
  if (route === "rehab/session") return { session: state.rehabSession, demo_data: true };
  if (route === "rehab/movement") return { sessions: history, session_count: history.length, movement_quality: history[0]?.movement_quality || "INSUFFICIENT_DATA", trend: history.length < 3 ? "INSUFFICIENT_DATA" : "STABLE", fatigue_signal: history[0]?.fatigue_signal || "INSUFFICIENT_DATA", demo_data: true };
  if (route === "rehab/progress") return { program: syntheticProgram, sessions_completed: history.length, exercises_completed: history.length, assigned_exercises: assignments.length, functional_tests_completed: 0, movement_trend: "INSUFFICIENT_DATA", return_to_sport_status: "IN_PROGRESS", demo_data: true };
  if (route === "rehab/recovery") return { recent_rehab_load: null, recent_session_count: history.length, fatigue_signal: "INSUFFICIENT_DATA", sleep: { status: "NOT_CONNECTED" }, recovery_data_available: false, demo_data: true };
  if (route === "rehab/functional-tests") return { tests: [{ id: "demo-balance-test", name: "Balance Test", purpose: "Record a timed balance attempt.", preparation: "Stand beside a stable support.", instructions: ["Stand on one leg for a comfortable time.", "Stop if unsafe."], target_duration_seconds: 30 }], history: [], demo_data: true };
  if (route === "rehab/readiness") return { assessment: null, demo_data: true };
  if (route === "rehab/return-to-sport") return { assessment: null, medical_clearance: false, demo_data: true };
  if (route === "rehab/history") return { sessions: history, demo_data: true };
  if (route === "rehab/reports") return { reports: [], available_types: ["REHAB_SESSION", "MOVEMENT_ANALYSIS", "EXERCISE_PROGRESS", "FUNCTIONAL_TEST", "READINESS", "RETURN_TO_SPORT", "WEEKLY_REHAB", "MONTHLY_REHAB"], note: "Synthetic demo data only; report rendering is not enabled.", demo_data: true };
  if (route.startsWith("rehab/exercises/")) {
    const exercise = exercises.find((item) => item.id === route.split("/").at(-1));
    return { exercise: exercise || null, previous_performance: history.filter((item) => item.exercise_id === exercise?.id), demo_data: true };
  }
  if (route.startsWith("rehab/functional-tests/")) {
    return { tests: [{ id: "demo-balance-test", name: "Balance Test", purpose: "Record a timed balance attempt.", preparation: "Stand beside a stable support.", instructions: ["Stand on one leg for a comfortable time.", "Stop if unsafe."], target_duration_seconds: 30 }], history: [], demo_data: true };
  }
  if (route.startsWith("rehab/session/")) {
    const session = history.find((item) => item.id === route.split("/")[2]) || state.rehabSession;
    return { session, repetitions: session?.repetitions || [], demo_data: true };
  }
  return { demo_data: true };
}

async function loadRehabRoute(route) {
  state.rehabError = "";
  if (state.session?.demo) {
    state.rehabData[route] = demoRehabData(route);
    if (route.startsWith("rehab/session/")) {
      state.rehabSession = state.rehabData[route].session || state.rehabSession;
    }
    state.rehabLoading = false;
    if (route.endsWith("/result") && state.functionalTestRun) startFunctionalTestTimer();
    render();
    return;
  }
  if (!state.healthApiConfigured) {
    state.rehabData[route] = { unavailable: true };
    state.rehabLoading = false;
    render();
    return;
  }
  state.rehabLoading = true;
  render();
  try {
    const subroute = route.slice("rehab/".length);
    let endpoint;
    if (route === "rehab") endpoint = "/dashboard";
    else if (subroute === "today") endpoint = "/today";
    else if (subroute === "program" || subroute.startsWith("program/")) endpoint = `/program${subroute === "program" ? "" : `/${encodeURIComponent(subroute.split("/").at(-1))}`}`;
    else if (subroute === "exercises" || subroute.startsWith("exercises/")) endpoint = `/exercises${subroute === "exercises" ? "" : `/${encodeURIComponent(subroute.split("/").at(-1))}`}`;
    else if (subroute === "session") endpoint = "/sessions";
    else if (subroute.startsWith("session/")) endpoint = `/sessions/${encodeURIComponent(subroute.split("/")[1])}`;
    else if (subroute === "movement") endpoint = "/movement/summary";
    else if (subroute.startsWith("movement/")) endpoint = `/sessions/${encodeURIComponent(subroute.split("/").at(-1))}/movement`;
    else if (subroute === "progress") endpoint = "/progress";
    else if (subroute === "recovery") endpoint = "/recovery";
    else if (subroute === "functional-tests" || subroute.startsWith("functional-tests/")) endpoint = "/functional-tests";
    else if (subroute === "readiness") endpoint = "/readiness/current";
    else if (subroute === "return-to-sport") endpoint = "/return-to-sport";
    else if (subroute === "history") endpoint = "/history";
    else if (subroute === "reports") endpoint = "/reports";
    else endpoint = "/dashboard";
    state.rehabData[route] = await auth.healthRequest(state.session, endpoint) ?? {};
    if (subroute === "session") {
      const activeSession = (state.rehabData[route].sessions || []).find((item) => item.status === "ACTIVE" || item.status === "PAUSED");
      state.rehabData[route].session = activeSession;
      if (activeSession) state.rehabSession = { ...(state.rehabSession || {}), ...activeSession };
    }
    if (route === "rehab/history" || route === "rehab") {
      const pending = readRehabSessions().filter((item) => item.locally_saved && !item.demo);
      if (route === "rehab/history") {
        const remote = state.rehabData[route].sessions || [];
        state.rehabData[route].sessions = [...pending, ...remote.filter((item) => !pending.some((saved) => saved.id === item.id))];
      } else {
        const remote = state.rehabData[route].recent_sessions || [];
        state.rehabData[route].recent_sessions = [...pending, ...remote.filter((item) => !pending.some((saved) => saved.id === item.id))].slice(0, 5);
      }
    }
    if (route.startsWith("rehab/session/")) {
      const serverSession = state.rehabData[route].session;
      if (serverSession) {
        state.rehabSession = {
          ...(state.rehabSession || {}),
          ...serverSession,
          id: serverSession.id,
          exercise: state.rehabSession?.exercise || serverSession.exercise,
          samples: state.rehabSession?.samples || [],
          repetitions: state.rehabSession?.repetitions || state.rehabData[route].repetitions || [],
          elapsed_ms: state.rehabSession?.elapsed_ms || 0,
        };
      }
    }
  } catch (error) {
    state.rehabError = friendlyError(error);
  } finally {
    state.rehabLoading = false;
    if (route.endsWith("/result") && state.functionalTestRun) startFunctionalTestTimer();
    render();
  }
}

function stopRehabTimer() {
  if (rehabTimer.interval !== null) window.clearInterval(rehabTimer.interval);
  rehabTimer.interval = null;
}

function stopFunctionalTestTimer() {
  if (rehabTimer.testInterval !== null) window.clearInterval(rehabTimer.testInterval);
  rehabTimer.testInterval = null;
}

function startFunctionalTestTimer() {
  stopFunctionalTestTimer();
  rehabTimer.testInterval = window.setInterval(() => {
    if (!state.functionalTestRun) {
      stopFunctionalTestTimer();
      return;
    }
    const timer = appRoot.querySelector(".rehab-test-timer");
    if (timer) timer.textContent = `${((Date.now() - state.functionalTestRun.started_at) / 1000).toFixed(1)} sec`;
  }, 250);
}

function persistActiveRehabSession() {
  if (state.rehabSession) saveRehabSession(state.rehabSession);
}

function sessionSummary(session) {
  const calculated = summarizeMovementSamples(session.samples || [], session.repetitions || []);
  if (calculated.sample_count < 10 && session.movement_quality) {
    return {
      ...calculated,
      movement_quality: session.movement_quality,
      stability: session.stability || calculated.stability,
      smoothness: session.smoothness || calculated.smoothness,
      fatigue_signal: session.fatigue_signal || calculated.fatigue_signal,
      metrics: session.metrics || calculated.metrics,
    };
  }
  return calculated;
}

function startRehabSampleTimer() {
  stopRehabTimer();
  if (state.rehabSession?.source !== "SIMULATION") {
    rehabTimer.interval = window.setInterval(() => {
      const session = state.rehabSession;
      if (!session || session.status !== "ACTIVE") {
        stopRehabTimer();
        return;
      }
      session.elapsed_ms = (session.elapsed_ms || 0) + 1000;
      persistActiveRehabSession();
      render();
    }, 1000);
    return;
  }
  const source = new SimulationMovementDataSource({ scenario: state.rehabSession?.scenario || "NORMAL" });
  const detector = new SquatRepetitionDetector();
  const safetyMonitor = new RehabSafetyMonitor();
  for (const repetition of state.rehabSession?.repetitions || []) detector.repetitions += 1;
  rehabTimer.interval = window.setInterval(() => {
    const session = state.rehabSession;
    if (!session || session.status !== "ACTIVE") {
      stopRehabTimer();
      return;
    }
    const timestamp = Date.now();
    const sample = source.nextSample(timestamp);
    if (!sample) {
      session.connection_status = "RECONNECTING";
      session.elapsed_ms = (session.elapsed_ms || 0) + 250;
      persistActiveRehabSession();
      if (timestamp - rehabTimer.lastRenderAt >= 1000) {
        rehabTimer.lastRenderAt = timestamp;
        render();
      }
      return;
    }
    session.connection_status = "CONNECTED";
    const safetySignal = safetyMonitor.evaluate(sample);
    if (safetySignal !== "NORMAL") {
      const event = safetySignal === "REVIEW_REQUIRED" ? "REVIEW_REQUIRED" : "CAUTION_MOVEMENT_SIGNAL";
      session.safety_events = [...new Set([...(session.safety_events || []), event])];
    }
    session.samples = [...(session.samples || []), sample].slice(-200);
    session.sample_count = (session.sample_count || 0) + 1;
    session.elapsed_ms = (session.elapsed_ms || 0) + 250;
    const repetition = detector.feed(sample);
    if (repetition) {
      repetition.quality = "MODERATE";
      repetition.stability = "MODERATE";
      repetition.smoothness = "MODERATE";
      repetition.movement_phase = "COMPLETE";
      session.repetitions = [...(session.repetitions || []), repetition];
      session.completed_repetitions = session.repetitions.length;
    }
    persistActiveRehabSession();
    if (timestamp - rehabTimer.lastRenderAt >= 1000) {
      rehabTimer.lastRenderAt = timestamp;
      render();
    }
  }, 250);
}

async function startRehabSession(exerciseId, source = "SIMULATION") {
  const currentData = state.rehabData[state.route] || {};
  const exercise = currentData.exercise ||
    (currentData.exercises || []).find((item) => item.id === exerciseId) ||
    (currentData.today?.exercises || []).find((item) => item.exercise_id === exerciseId)?.exercise ||
    (currentData.exercises || []).find((item) => item.exercise?.id === exerciseId)?.exercise;
  if (!exercise) {
    state.rehabError = "The selected exercise is no longer available. Reload the exercise list and try again.";
    render();
    return;
  }
  state.rehabBusy = true;
  render();
  try {
    const targetRepetitions = Number(exercise.default_repetitions || 8);
    const session = {
      id: crypto.randomUUID(),
      exercise_id: exercise.id,
      exercise,
      program_id: currentData.program?.id || currentData.current_program?.id || null,
      source,
      sensor_placement: source === "SIMULATION" ? exercise.default_sensor_placement || "THIGH" : null,
      status: source === "SIMULATION" ? "CALIBRATING" : "PLANNED",
      sample_count: 0,
      target_repetitions: targetRepetitions,
      completed_repetitions: 0,
      elapsed_ms: 0,
      repetitions: [],
      samples: [],
      demo: Boolean(state.session.demo),
      locally_saved: !state.session.demo && !state.healthApiConfigured,
      started_at: null,
      scenario: source === "SIMULATION" ? state.rehabScenario : "NORMAL",
      connection_status: "CONNECTED",
    };
    if (!session.demo && state.healthApiConfigured) {
      try {
        const created = await auth.healthRequest(state.session, "/sessions", {
          method: "POST",
          body: {
            exercise_id: session.exercise_id,
            program_id: session.program_id,
            source: session.source,
            sensor_placement: session.sensor_placement,
            target_repetitions: session.target_repetitions,
          },
        });
        session.server_id = created.session.id;
        await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(session.server_id)}`, {
          method: "PATCH",
          body: { status: "CALIBRATING" },
        });
        session.id = session.server_id;
      } catch (error) {
        if (!state.offline && !["NETWORK_ERROR", "TIMEOUT"].includes(error.code)) throw error;
        session.locally_saved = true;
      }
    }
    state.rehabSession = session;
    saveRehabSession(session);
    showToast(session.demo ? "Demo session ready. This is simulation data." : session.locally_saved ? "Session saved locally; it will wait to sync." : "Calibration is ready.");
    navigate(`rehab/session/${session.id}`);
  } catch (error) {
    state.rehabError = friendlyError(error);
  } finally {
    state.rehabBusy = false;
    render();
  }
}

async function updateRehabSessionStatus(status) {
  const session = state.rehabSession;
  if (!session) return;
  if (!session.demo && !session.locally_saved && state.healthApiConfigured) {
    try {
      await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(session.id)}`, {
        method: "PATCH",
        body: { status },
      });
    } catch (error) {
      if (!state.offline && !["NETWORK_ERROR", "TIMEOUT"].includes(error.code)) {
        state.rehabError = friendlyError(error);
        render();
        return;
      }
      session.locally_saved = true;
    }
  }
  if (status === "ACTIVE") {
    if (!session.started_at) session.started_at = new Date().toISOString();
    session.status = "ACTIVE";
    startRehabSampleTimer();
  } else {
    if (session.status === "ACTIVE" && status === "PAUSED") session.status = status;
    else session.status = status;
    if (status !== "ACTIVE") stopRehabTimer();
  }
  persistActiveRehabSession();
  render();
}

async function syncCompletedRehabSession(session) {
  let serverId = session.server_id || null;
  if (!serverId) {
    const created = await auth.healthRequest(state.session, "/sessions", {
      method: "POST",
      body: {
        exercise_id: session.exercise_id,
        program_id: session.program_id,
        source: session.source,
        sensor_placement: session.sensor_placement,
        target_repetitions: session.target_repetitions,
      },
    });
    serverId = created.session.id;
    await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(serverId)}`, {
      method: "PATCH",
      body: { status: "ACTIVE" },
    });
  } else {
    const current = await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(serverId)}`);
    if (current.session.status === "COMPLETED") {
      session.id = serverId;
      session.server_id = serverId;
      session.locally_saved = false;
      return session;
    }
    if (current.session.status !== "ACTIVE" && current.session.status !== "PAUSED") {
      await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(serverId)}`, {
        method: "PATCH",
        body: { status: "ACTIVE" },
      });
    }
  }
  const summary = sessionSummary(session);
  await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(serverId)}/complete`, {
    method: "POST",
    body: {
      source: session.source,
      sensor_placement: session.sensor_placement,
      sample_count: session.sample_count || 0,
      target_repetitions: session.target_repetitions,
      completed_repetitions: session.completed_repetitions || 0,
      movement_quality: summary.movement_quality,
      stability: summary.stability,
      smoothness: summary.smoothness,
      fatigue_signal: summary.fatigue_signal,
      session_duration_seconds: Math.floor((session.elapsed_ms || 0) / 1000),
      abnormal_events: session.safety_events || [],
      repetitions: (session.repetitions || []).map((rep, index) => ({
        rep_number: index + 1,
        started_at: rep.started_at,
        ended_at: rep.ended_at,
        duration_ms: rep.duration_ms,
        movement_phase: rep.movement_phase || "COMPLETE",
        quality: rep.quality || summary.movement_quality,
        stability: rep.stability || summary.stability,
        smoothness: rep.smoothness || summary.smoothness,
        source: session.source,
      })),
      metrics: summary.metrics,
    },
  });
  session.id = serverId;
  session.server_id = serverId;
  session.locally_saved = false;
  return session;
}

async function syncPendingRehabSessions() {
  if (!state.session || state.session.demo || !state.healthApiConfigured || state.offline) return;
  const pending = readRehabSessions().filter((item) => item.locally_saved && !item.demo && item.status === "COMPLETED");
  for (const session of pending) {
    try {
      await syncCompletedRehabSession(session);
      saveRehabSession(session);
    } catch (error) {
      state.rehabError = friendlyError(error);
      break;
    }
  }
  if (isRehabRoute(state.route)) await loadRehabRoute(state.route);
}

async function completeRehabSession() {
  const session = state.rehabSession;
  if (!session) return;
  stopRehabTimer();
  session.status = "COMPLETED";
  session.ended_at = new Date().toISOString();
  const summary = sessionSummary(session);
  session.movement_quality = summary.movement_quality;
  session.stability = summary.stability;
  session.smoothness = summary.smoothness;
  session.fatigue_signal = summary.fatigue_signal;
  session.metrics = summary.metrics;
  try {
    if (!session.demo && !session.locally_saved && state.healthApiConfigured) {
      try {
        await syncCompletedRehabSession(session);
      } catch (error) {
        if (!state.offline && !["NETWORK_ERROR", "TIMEOUT"].includes(error.code)) throw error;
        session.locally_saved = true;
      }
    }
    saveRehabSession(session);
    state.rehabConfirmStop = false;
    showToast(session.locally_saved ? "Completed locally. Waiting to sync." : "Session results saved.");
    navigate(`rehab/session/${session.id}/result`);
    if (state.healthApiConfigured && !session.demo && !session.locally_saved) {
      void loadRehabRoute("rehab/history");
    }
  } catch (error) {
    state.rehabError = friendlyError(error);
    session.status = "ACTIVE";
    startRehabSampleTimer();
    render();
  }
}

async function startFunctionalTest(testId) {
  const tests = state.rehabData[state.route]?.tests || [];
  const test = tests.find((item) => item.id === testId);
  if (!test) {
    state.rehabError = "This functional test is unavailable.";
    render();
    return;
  }
  state.functionalTestRun = { test, started_at: Date.now(), source: state.session.demo ? "SIMULATION" : "MANUAL" };
  navigate(`rehab/functional-tests/${encodeURIComponent(testId)}/result`);
}

async function finishFunctionalTest() {
  const run = state.functionalTestRun;
  if (!run) return;
  const result = {
    duration_seconds: Math.max(0.1, (Date.now() - run.started_at) / 1000),
    stability: "INSUFFICIENT_DATA",
    movement_quality: "INSUFFICIENT_DATA",
    source: run.source,
    notes: "Timed attempt only; no sensor-based movement quality was recorded.",
  };
  try {
    if (!state.session.demo && state.healthApiConfigured) {
      await auth.healthRequest(state.session, `/functional-tests/${encodeURIComponent(run.test.id)}/results`, {
        method: "POST",
        body: result,
      });
    }
    state.rehabData[state.route] = {
      ...(state.rehabData[state.route] || {}),
      result,
      test: run.test,
    };
    state.functionalTestRun = null;
    stopFunctionalTestTimer();
    showToast("Timed test result saved with its source.");
    render();
  } catch (error) {
    state.rehabError = friendlyError(error);
    render();
  }
}

async function performRehabAction(action, button) {
  const session = state.rehabSession;
  if (action === "start-session") {
    await startRehabSession(button.dataset.exerciseId, button.dataset.source || "SIMULATION");
  } else if (action === "begin-session") {
    await updateRehabSessionStatus("ACTIVE");
  } else if (action === "pause-session") {
    await updateRehabSessionStatus("PAUSED");
  } else if (action === "resume-session") {
    await updateRehabSessionStatus("ACTIVE");
  } else if (action === "stop-session") {
    state.rehabConfirmStop = true;
    render();
  } else if (action === "continue-session") {
    state.rehabConfirmStop = false;
    render();
  } else if (action === "confirm-stop") {
    await completeRehabSession();
  } else if (action === "cancel-session" && session) {
    if (!window.confirm("Cancel this session? Any results already recorded will remain in your history.")) return;
    stopRehabTimer();
    if (!session.demo && !session.locally_saved && state.healthApiConfigured) {
      try {
        await auth.healthRequest(state.session, `/sessions/${encodeURIComponent(session.id)}/cancel`, { method: "POST" });
      } catch (error) {
        if (!state.offline && !["NETWORK_ERROR", "TIMEOUT"].includes(error.code)) {
          state.rehabError = friendlyError(error);
          render();
          return;
        }
        session.locally_saved = true;
      }
    }
    session.status = "CANCELLED";
    saveRehabSession(session);
    navigate("rehab/today");
  } else if (action === "start-functional-test") {
    await startFunctionalTest(button.dataset.testId);
  } else if (action === "finish-functional-test") {
    await finishFunctionalTest();
  } else if (action === "sync-session" && session && state.healthApiConfigured) {
    try {
      state.rehabBusy = true;
      await syncCompletedRehabSession(session);
      saveRehabSession(session);
      showToast("Offline session synced.");
      await loadRehabRoute("rehab/history");
    } catch (error) {
      state.rehabError = friendlyError(error);
    } finally {
      state.rehabBusy = false;
      render();
    }
  }
}

async function submitRehabForm(form) {
  const data = new FormData(form);
  try {
    if (form.dataset.form === "rehab-readiness" && state.session.demo) {
      const selfReportedStatus = String(data.get("selfReportedStatus") || "") || null;
      const soreness = String(data.get("soreness") || "") || null;
      const status = selfReportedStatus === "PAIN_OR_CONCERN" ? "REVIEW_REQUIRED"
        : soreness === "SEVERE" ? "REST_RECOMMENDED"
          : selfReportedStatus === "FATIGUED" || selfReportedStatus === "SORE" || soreness === "MODERATE" ? "READY_WITH_CAUTION"
            : "INSUFFICIENT_DATA";
      state.rehabData["rehab/readiness"] = {
        assessment: {
          status,
          recommendation: "Demo-only rule result based only on this synthetic athlete's self-report. Not medical advice.",
          source: "SIMULATION",
          factors: [
            ...(selfReportedStatus ? [{ factor: "athlete_report", value: selfReportedStatus }] : []),
            ...(soreness ? [{ factor: "soreness", value: soreness }] : []),
          ],
        },
      };
    } else if (form.dataset.form === "rehab-readiness") {
      const result = await auth.healthRequest(state.session, "/readiness/evaluate", {
        method: "POST",
        body: {
          self_reported_status: String(data.get("selfReportedStatus") || "") || null,
          soreness: String(data.get("soreness") || "") || null,
        },
      });
      state.rehabData["rehab/readiness"] = result;
    } else if (state.session.demo) {
      state.rehabData["rehab/return-to-sport"] = {
        medical_clearance: false,
        assessment: {
          status: "IN_PROGRESS",
          clinician_review_status: "PENDING",
          outstanding_requirements: [{ type: "DEMO_ONLY" }],
        },
      };
    } else {
      const result = await auth.healthRequest(state.session, "/return-to-sport/evaluate", {
        method: "POST",
        body: { athlete_reported_status: String(data.get("athleteReportedStatus") || "") || null },
      });
      state.rehabData["rehab/return-to-sport"] = result;
    }
    showToast("Your rehabilitation assessment was recorded.");
  } catch (error) {
    state.rehabError = friendlyError(error);
  }
  render();
}

async function performHealthAction(action, reportId) {
  if (action === "delete-report" && !window.confirm("Permanently delete this report and its stored source file?")) return;
  state.healthBusy = true;
  state.healthFormError = "";
  render();
  try {
    if (action === "source") {
      const result = await auth.healthRequest(state.session, `/medical-reports/${encodeURIComponent(reportId)}/source`, { method: "POST" });
      state.healthSourceLink = { id: reportId, url: result.url, expiresAt: result.expires_at };
      showToast("Private source link created. It expires shortly.");
    } else if (action === "create-report-draft") {
      await auth.healthRequest(state.session, "/reports", {
        method: "POST",
        body: { report_type: "MEDICAL_REPORT_ANALYSIS", source_ids: [reportId] },
      });
      showToast("Health report draft created.");
      await loadHealthRoute("health-history");
    } else if (action === "delete-report") {
      await auth.healthRequest(state.session, `/medical-reports/${encodeURIComponent(reportId)}`, { method: "DELETE" });
      state.healthSourceLink = null;
      showToast("Report and source file deleted.");
      await loadHealthRoute("health-reports");
    } else if (action === "complete-medication") {
      await auth.healthRequest(state.session, `/medications/${encodeURIComponent(reportId)}`, {
        method: "PATCH",
        body: { status: "COMPLETED" },
      });
      showToast("Medication marked completed.");
      await loadHealthRoute("health-medication");
    }
  } catch (error) {
    state.healthFormError = friendlyError(error);
    state.healthError = state.healthFormError;
  } finally {
    state.healthBusy = false;
    render();
  }
}

function optionalNumber(value) {
  if (value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

async function submitHealthForm(form) {
  const data = new FormData(form);
  const formType = form.dataset.form;
  state.healthBusy = true;
  state.healthFormError = "";
  render();
  try {
    if (formType === "health-upload") {
      const file = data.get("report");
      if (!(file instanceof File) || !file.size) throw new Error("Choose a report file before uploading.");
      if (data.get("consent") !== "true") throw new Error("Consent is required before a report can be processed.");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("consent", "true");
      await auth.healthRequest(state.session, "/medical-reports", { method: "POST", body: formData });
      showToast("Report uploaded. Processing will continue in the background.");
    } else if (formType === "health-body-note") {
      await auth.healthRequest(state.session, "/body-map/findings", {
        method: "POST",
        body: {
          body_region_id: String(data.get("bodyRegion") || ""),
          finding_type: String(data.get("findingType") || "").trim(),
          description: String(data.get("description") || "").trim(),
        },
      });
      showToast("Your personal note was saved.");
    } else if (formType === "health-nutrition-profile") {
      await auth.healthRequest(state.session, "/nutrition/profile", {
        method: "PUT",
        body: {
          goal: String(data.get("goal") || "GENERAL_SPORTS_NUTRITION"),
          hydration_goal_ml: optionalNumber(String(data.get("hydrationGoal") || "")),
        },
      });
      showToast("Your nutrition goal was saved.");
    } else if (formType === "health-nutrition-entry") {
      await auth.healthRequest(state.session, "/nutrition/entries", {
        method: "POST",
        body: {
          entry_date: String(data.get("entryDate") || ""),
          entry_type: String(data.get("entryType") || "MEAL"),
          name: String(data.get("name") || "").trim(),
          hydration_ml: optionalNumber(String(data.get("hydrationMl") || "")),
          calories: optionalNumber(String(data.get("calories") || "")),
          protein_g: optionalNumber(String(data.get("proteinG") || "")),
        },
      });
      showToast("Nutrition entry saved.");
    } else if (formType === "health-medication") {
      await auth.healthRequest(state.session, "/medications", {
        method: "POST",
        body: {
          name: String(data.get("name") || "").trim(),
          dose: String(data.get("dose") || "").trim() || null,
          frequency: String(data.get("frequency") || "").trim() || null,
          start_date: String(data.get("startDate") || "") || null,
          end_date: String(data.get("endDate") || "") || null,
          reason: String(data.get("reason") || "").trim() || null,
          status: "ACTIVE",
          source_type: "USER_ENTERED",
        },
      });
      showToast("Medication record saved.");
    }
    form.reset();
    await loadHealthRoute(state.route);
  } catch (error) {
    state.healthFormError = friendlyError(error);
    state.healthError = state.healthFormError;
  } finally {
    state.healthBusy = false;
    render();
  }
}

async function loadAthleteProfile() {
  state.profileLoading = true;
  render();
  try {
    state.athleteProfile = await auth.fetchAthleteProfile(state.session);
  } catch (error) {
    showToast(friendlyError(error));
  } finally {
    state.profileLoading = false;
    render();
  }
}

function clearAuthFeedback() {
  state.error = "";
  state.notice = "";
}

function clearHealthState() {
  stopRehabTimer();
  stopFunctionalTestTimer();
  state.healthData = {};
  state.healthError = "";
  state.healthFormError = "";
  state.healthLoading = false;
  state.healthBusy = false;
  state.healthSourceLink = null;
  state.selectedBodyRegion = "";
  state.wellbeing = {
    overview: null,
    checkins: [],
    sleepRecords: [],
    recoveryRecords: [],
    history: [],
    trends: null,
    reports: [],
    loading: false,
    busy: false,
    error: "",
  };
  state.rehabData = {};
  state.rehabSession = null;
  state.functionalTestRun = null;
  state.rehabError = "";
  clearReportState();
}

function setAuthMode(mode) {
  state.authMode = mode;
  state.approvalScreen = false;
  clearAuthFeedback();
  render();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function friendlyError(error) {
  if (error instanceof AuthError) {
    if (error.status === 400 && /invalid login credentials/i.test(error.message)) {
      return "That email and password don't match. Check them and try again.";
    }
    if (error.status === 429) return "Too many attempts. Take a moment, then try again.";
    return error.message;
  }
  if (error instanceof TypeError) return "Couldn't reach VitaPulse. Check your internet connection and try again.";
  return "Something went wrong. Please try again.";
}

function fieldValue(form, name) {
  return String(new FormData(form).get(name) ?? "").trim();
}

async function submitLogin(form) {
  const email = fieldValue(form, "email");
  const password = String(new FormData(form).get("password") ?? "");
  if (!email || !password) {
    state.error = "Enter your email and password to continue.";
    render();
    return;
  }
  state.loading = true;
  state.error = "";
  render();
  try {
    state.session = await auth.signIn(email, password);
    clearHealthState();
    clearConnectContext();
    state.route = state.session.role === "DOCTOR" || state.session.role === "ADMIN"
      ? "doctor-dashboard"
      : "home";
    state.notice = "";
    history.replaceState({ route: state.route }, "", `#${state.route}`);
  } catch (error) {
    state.error = friendlyError(error);
  } finally {
    state.loading = false;
    render();
  }
}

async function submitRegistration(form) {
  const data = new FormData(form);
  const fullName = fieldValue(form, "fullName");
  const email = fieldValue(form, "email");
  const password = String(data.get("password") ?? "");
  const confirmPassword = String(data.get("confirmPassword") ?? "");
  const dateOfBirth = fieldValue(form, "dateOfBirth");
  const heightCm = fieldValue(form, "heightCm");
  const weightKg = fieldValue(form, "weightKg");
  if (password.length < 8) {
    state.error = "Choose a password with at least 8 characters.";
    render();
    return;
  }
  if (password !== confirmPassword) {
    state.error = "Those passwords don't match yet.";
    render();
    return;
  }
  if (!fullName || !email) {
    state.error = "Add your name and email address to continue.";
    render();
    return;
  }
  if (dateOfBirth && dateOfBirth > new Date().toISOString().slice(0, 10)) {
    state.error = "Date of birth cannot be in the future.";
    render();
    return;
  }
  if (heightCm && (!Number.isFinite(Number(heightCm)) || Number(heightCm) < 50 || Number(heightCm) > 260)) {
    state.error = "Height must be between 50 and 260 cm.";
    render();
    return;
  }
  if (weightKg && (!Number.isFinite(Number(weightKg)) || Number(weightKg) < 20 || Number(weightKg) > 350)) {
    state.error = "Weight must be between 20 and 350 kg.";
    render();
    return;
  }

  state.loading = true;
  state.error = "";
  render();
  try {
    const result = await auth.signUp({
      fullName,
      email,
      password,
      accountType: state.accountType,
      sport: fieldValue(form, "sport"),
      licenseId: fieldValue(form, "licenseId"),
      specialization: fieldValue(form, "specialization"),
      organization: fieldValue(form, "organization"),
      phone: fieldValue(form, "phone"),
      dateOfBirth,
      position: fieldValue(form, "position"),
      heightCm,
      weightKg,
      dominantSide: fieldValue(form, "dominantSide"),
      injuryRegion: fieldValue(form, "injuryRegion"),
      rehabilitationGoal: fieldValue(form, "rehabilitationGoal"),
    });
    if (result.session) {
      state.session = result.session;
      clearHealthState();
      clearConnectContext();
      state.athleteProfile = state.session.role === "ATHLETE"
        ? {
          date_of_birth: dateOfBirth || null,
          sport: fieldValue(form, "sport") || null,
          position: fieldValue(form, "position") || null,
          height_cm: heightCm ? Number(heightCm) : null,
          weight_kg: weightKg ? Number(weightKg) : null,
          dominant_side: fieldValue(form, "dominantSide") || null,
          injury_region: fieldValue(form, "injuryRegion") || null,
          rehab_stage: null,
          rehabilitation_goal: fieldValue(form, "rehabilitationGoal") || null,
        }
        : null;
      state.route = "home";
      history.replaceState({ route: "home" }, "", "#home");
    } else if (result.needsDoctorApproval) {
      state.approvalScreen = true;
    } else if (result.needsEmailConfirmation) {
      state.authMode = "login";
      state.notice = result.isDoctorApplication
        ? "Check your inbox to verify your email. Doctor workspace access remains locked until your professional account is approved."
        : "Check your inbox for a verification link. You can sign in after you verify your email.";
    }
  } catch (error) {
    state.error = friendlyError(error);
  } finally {
    state.loading = false;
    render();
  }
}

async function submitPasswordReset(form) {
  const email = fieldValue(form, "email");
  if (!email) {
    state.error = "Enter the email address linked to your account.";
    render();
    return;
  }
  state.loading = true;
  state.error = "";
  state.notice = "";
  render();
  try {
    await auth.sendPasswordReset(email);
    state.notice = "If an account matches that address, a password reset link is on its way.";
  } catch (error) {
    state.error = friendlyError(error);
  } finally {
    state.loading = false;
    render();
  }
}

async function submitNewPassword(form) {
  const data = new FormData(form);
  const password = String(data.get("password") ?? "");
  const confirmation = String(data.get("confirmPassword") ?? "");
  if (password.length < 8) {
    state.error = "Choose a password with at least 8 characters.";
    render();
    return;
  }
  if (password !== confirmation) {
    state.error = "Those passwords don't match yet.";
    render();
    return;
  }
  state.loading = true;
  state.error = "";
  render();
  try {
    await auth.updatePassword(recoveryToken, password);
    state.authMode = "login";
    state.notice = "Your password has been updated. Sign in with your new password.";
  } catch (error) {
    state.error = friendlyError(error);
  } finally {
    state.loading = false;
    render();
  }
}

async function submitProfile(form) {
  const data = new FormData(form);
  const profile = {
    displayName: String(data.get("displayName") ?? "").trim(),
    dateOfBirth: String(data.get("dateOfBirth") ?? ""),
    sport: String(data.get("sport") ?? "").trim(),
    position: String(data.get("position") ?? "").trim(),
    heightCm: String(data.get("heightCm") ?? "").trim(),
    weightKg: String(data.get("weightKg") ?? "").trim(),
    dominantSide: String(data.get("dominantSide") ?? ""),
    injuryRegion: String(data.get("injuryRegion") ?? "").trim(),
    rehabilitationGoal: String(data.get("rehabilitationGoal") ?? "").trim(),
  };
  if (!profile.displayName) {
    state.error = "Add your name before saving your profile.";
    render();
    return;
  }
  if (profile.dateOfBirth && profile.dateOfBirth > new Date().toISOString().slice(0, 10)) {
    state.error = "Date of birth cannot be in the future.";
    render();
    return;
  }
  for (const [label, value, minimum, maximum] of [
    ["Height", profile.heightCm, 50, 260],
    ["Weight", profile.weightKg, 20, 350],
  ]) {
    if (value && (!Number.isFinite(Number(value)) || Number(value) < minimum || Number(value) > maximum)) {
      state.error = `${label} must be between ${minimum} and ${maximum} ${label === "Height" ? "cm" : "kg"}.`;
      render();
      return;
    }
  }
  profile.heightCm = profile.heightCm ? Number(profile.heightCm) : null;
  profile.weightKg = profile.weightKg ? Number(profile.weightKg) : null;
  state.loading = true;
  state.error = "";
  render();
  try {
    await auth.updateAthleteProfile(state.session, profile);
    state.session.name = profile.displayName;
    state.athleteProfile = {
      ...(state.athleteProfile ?? {}),
      date_of_birth: profile.dateOfBirth || null,
      sport: profile.sport || null,
      position: profile.position || null,
      height_cm: profile.heightCm,
      weight_kg: profile.weightKg,
      dominant_side: profile.dominantSide || null,
      injury_region: profile.injuryRegion || null,
      rehabilitation_goal: profile.rehabilitationGoal || null,
    };
    state.profileEditing = false;
    showToast("Your profile has been updated.");
  } catch (error) {
    state.error = friendlyError(error);
  } finally {
    state.loading = false;
    render();
  }
}

async function signOut() {
  state.loading = true;
  render();
  try {
    await auth.signOut();
    state.notice = "";
    state.route = "home";
    history.replaceState({}, "", location.pathname);
  } catch (error) {
    showToast(`Signed out on this browser. ${friendlyError(error)}`);
  } finally {
    state.session = null;
    clearHealthState();
    clearConnectContext();
    state.approvalScreen = false;
    state.loading = false;
    state.authMode = "login";
    render();
  }
}

appRoot.addEventListener("click", async (event) => {
  const bodyRegionButton = event.target.closest("[data-body-region]");
  if (bodyRegionButton) {
    state.selectedBodyRegion = bodyRegionButton.dataset.bodyRegion;
    render();
    return;
  }

  const reportActionButton = event.target.closest("[data-report-action]");
  if (reportActionButton) {
    await performReportAction(reportActionButton.dataset.reportAction, reportActionButton.dataset.reportId);
    return;
  }

  const healthActionButton = event.target.closest("[data-health-action]");
  if (healthActionButton) {
    await performHealthAction(
      healthActionButton.dataset.healthAction,
      healthActionButton.dataset.reportId || healthActionButton.dataset.resourceId,
    );
    return;
  }

  const wellbeingActionButton = event.target.closest("[data-wellbeing-action]");
  if (wellbeingActionButton?.dataset.wellbeingAction === "create-report") {
    await createWellbeingReport();
    return;
  }

  const rehabActionButton = event.target.closest("[data-rehab-action]");
  if (rehabActionButton) {
    await performRehabAction(rehabActionButton.dataset.rehabAction, rehabActionButton);
    return;
  }

  const routeButton = event.target.closest("[data-route]");
  if (routeButton) {
    event.preventDefault();
    navigate(routeButton.dataset.route);
    return;
  }

  const authButton = event.target.closest("[data-auth-mode]");
  if (authButton) {
    setAuthMode(authButton.dataset.authMode);
    return;
  }

  const accountButton = event.target.closest("[data-account-type]");
  if (accountButton) {
    state.accountType = accountButton.dataset.accountType;
    state.error = "";
    render();
    return;
  }

  const demoButton = event.target.closest("[data-demo-sign-in]");
  if (demoButton) {
    const credentials = demoButton.dataset.demoSignIn === "DOCTOR"
      ? { email: "doctor.demo@vitapulse.app", password: "DemoDoctor@12345!" }
      : { email: "demo@vitapulse.app", password: "Demo@12345!" };
    const form = appRoot.querySelector('form[data-form="login"]');
    if (!form || !state.demoMode) return;
    form.elements.email.value = credentials.email;
    form.elements.password.value = credentials.password;
    form.requestSubmit();
    return;
  }

  const themeButton = event.target.closest("[data-theme-choice]");
  if (themeButton) {
    state.theme = themeButton.dataset.themeChoice === "dark" ? "dark" : "light";
    preferenceStore.setItem("vitapulse.theme", state.theme);
    render();
    return;
  }

  const detailButton = event.target.closest("[data-detail]");
  if (detailButton) {
    state.detail = detailButton.dataset.detail;
    navigate("detail");
    return;
  }

  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "logout") {
    await signOut();
  } else if (action === "doctor-request-done") {
    state.approvalScreen = false;
    state.authMode = "login";
    state.notice = "Doctor access is available only after professional verification.";
    render();
  } else if (action === "back") {
    state.detail = "";
    navigate(state.lastModule);
  } else if (action === "home") {
    navigate("home");
  } else if (action === "edit-profile") {
    state.profileEditing = true;
    state.error = "";
    render();
  } else if (action === "cancel-profile-edit") {
    state.profileEditing = false;
    state.error = "";
    render();
  }
});

appRoot.addEventListener("change", (event) => {
  const scenarioSelect = event.target.closest("[data-rehab-scenario]");
  if (scenarioSelect) state.rehabScenario = scenarioSelect.value;
});

appRoot.addEventListener("submit", async (event) => {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  if (form.dataset.form === "login") await submitLogin(form);
  else if (form.dataset.form === "register") await submitRegistration(form);
  else if (form.dataset.form === "forgot") await submitPasswordReset(form);
  else if (form.dataset.form === "reset") await submitNewPassword(form);
  else if (form.dataset.form === "profile") await submitProfile(form);
  else if (form.dataset.form === "report-request") await submitReportRequest(form);
  else if (form.dataset.form === "report-email") await submitReportEmail(form);
  else if (form.dataset.form.startsWith("health-")) await submitHealthForm(form);
  else if (form.dataset.form.startsWith("rehab-")) await submitRehabForm(form);
  else if (form.dataset.form.startsWith("wellbeing-")) await submitWellbeingForm(form);
});

window.addEventListener("online", () => {
  state.offline = false;
  render();
  void syncPendingRehabSessions();
  if (state.route === "wellbeing") void loadWellbeingRoute();
});
window.addEventListener("offline", () => {
  state.offline = true;
  render();
});
window.addEventListener("popstate", () => {
  if (!state.session) return;
  const route = location.hash.slice(1);
  const doctor = state.session.role === "DOCTOR" || state.session.role === "ADMIN";
  const allowed = doctor
    ? ["doctor-dashboard", "doctor-athletes", "doctor-health", "doctor-rehab", "doctor-reports", "profile", "settings"].includes(route)
    : ["home", ...healthRoutes, "wellbeing", "connect", "profile", "settings", "reports"].includes(route) || isRehabRoute(route);
  navigate(allowed ? route : doctor ? "doctor-dashboard" : "home", { replace: true });
});

window.addEventListener("hashchange", () => {
  const token = getRecoveryToken(location.hash);
  if (!token) return;
  recoveryToken = token;
  state.session = null;
  state.approvalScreen = false;
  state.booting = false;
  state.authMode = "reset";
  clearAuthFeedback();
  history.replaceState({}, "", `${location.pathname}${location.search}`);
  render();
});

async function bootstrap() {
  render();
  try {
    state.session = await auth.restoreSession();
    if (state.session) {
      const doctor = state.session.role === "DOCTOR" || state.session.role === "ADMIN";
      const requestedRoute = location.hash.slice(1);
      const allowed = doctor
        ? ["doctor-dashboard", "doctor-athletes", "doctor-health", "doctor-rehab", "doctor-reports", "profile", "settings"].includes(requestedRoute)
        : ["home", ...healthRoutes, "wellbeing", "connect", "profile", "settings", "reports"].includes(requestedRoute) || isRehabRoute(requestedRoute);
      state.route = allowed ? requestedRoute : doctor ? "doctor-dashboard" : "home";
      history.replaceState({ route: state.route }, "", `#${state.route}`);
    }
  } catch (error) {
    if (error instanceof AuthError && ["NETWORK_ERROR", "TIMEOUT"].includes(error.code)) {
      state.offline = !navigator.onLine;
      state.notice = "Your session could not be checked right now. Please reconnect and try again.";
    } else if (auth.readSession()) {
      state.notice = "Your saved session couldn't be restored. Sign in again when you're connected.";
      auth.clearSession();
    }
  } finally {
    state.booting = false;
    render();
    if (state.session && healthRoutes.has(state.route)) void loadHealthRoute(state.route);
    if (state.session && state.route === "reports") void loadReports();
    if (state.session && ["home", "wellbeing", "rehab", "rehab/recovery"].includes(state.route)) {
      void loadConnectContext();
    }
    if (state.session && isRehabRoute(state.route)) void loadRehabRoute(state.route);
    if (state.session && state.route === "wellbeing") void loadWellbeingRoute();
  }
}

bootstrap();
