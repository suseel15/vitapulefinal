import test from "node:test";
import assert from "node:assert/strict";
import { escapeHtml, renderApp, renderAuth } from "../src/ui.js";

test("HTML escaping protects displayed profile values", () => {
  assert.equal(escapeHtml(`<Jordan & "Friends">`), "&lt;Jordan &amp; &quot;Friends&quot;&gt;");
});

test("athlete home uses honest empty states and five product destinations", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan Davis", role: "ATHLETE" },
    route: "home",
    theme: "light",
    offline: false,
  });
  assert.match(markup, /No readiness assessment is available yet/);
  assert.match(markup, /No program has been assigned yet/);
  assert.doesNotMatch(markup, /\b(?:82|87|91)%/);
  for (const route of ["home", "health", "rehab", "wellbeing", "connect"]) {
    assert.match(markup, new RegExp(`data-route="${route}"`));
  }
});

test("athlete feature shells expose the requested Phase 1 destinations", () => {
  const session = { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" };
  const requiredItems = {
    health: ["Medical reports", "Body map", "Biomarkers", "Health intelligence", "Nutrition", "Medication", "Anti-doping", "Skin screening", "Health reports"],
    rehab: ["Today's rehab", "Exercises", "Movement analysis", "Progress", "Functional tests", "Readiness", "Return to sport", "Recovery", "Reports"],
    wellbeing: ["Self check-in", "30-second camera check", "Sleep", "Recovery", "History", "Trends", "Reports"],
    connect: ["Movement device", "Smartwatch", "Data sync", "Permissions", "Diagnostics"],
  };

  for (const [route, labels] of Object.entries(requiredItems)) {
    const markup = renderApp({ session, route, theme: "light", offline: false });
    for (const label of labels) assert.ok(markup.includes(escapeHtml(label)), `${route} should include ${label}`);
  }
});

test("wellbeing hub exposes private check-in and sleep forms without browser camera capture", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE", userId: "athlete-1" },
    route: "wellbeing",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    wellbeing: {
      overview: {
        checkin: { energy: 4, fatigue: 2, created_at: "2026-10-06T12:00:00Z" },
        sleep: { duration_minutes: 480, source: "SELF_REPORTED" },
        recovery_context: { recovery_state: "GOOD" },
        context: { summary: "Recorded information only." },
      },
      history: [
        { type: "CHECK_IN", created_at: "2026-10-06T12:00:00Z", record: { energy: 4, fatigue: 2 } },
      ],
      reports: [],
    },
  });

  assert.match(markup, /data-form="wellbeing-checkin"/);
  assert.match(markup, /data-form="wellbeing-sleep"/);
  assert.match(markup, /name="recoveryFeeling"/);
  assert.match(markup, /type="datetime-local"/);
  assert.match(markup, /Create weekly summary/);
  assert.match(markup, /does not request camera permission/i);
  assert.doesNotMatch(markup, /getUserMedia|camera capture/i);
});

test("wellbeing records and errors are escaped before rendering", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "wellbeing",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    wellbeing: {
      error: "<script>unsafe()</script>",
      history: [
        {
          type: "CHECK_IN",
          created_at: "2026-10-06T12:00:00Z",
          record: { energy: 5, fatigue: 1, note: "<img src=x onerror=alert(1)>" },
        },
      ],
    },
  });

  assert.doesNotMatch(markup, /<script>unsafe\(\)<\/script>/);
  assert.doesNotMatch(markup, /<img src=x onerror=/);
  assert.match(markup, /&lt;script&gt;unsafe\(\)&lt;\/script&gt;/);
});

test("data-driven wellbeing, rehab and body-map visuals comply with the strict style CSP", () => {
  const session = { email: "athlete@example.test", name: "Jordan", role: "ATHLETE", userId: "athlete-1" };
  const wellbeing = renderApp({
    session,
    route: "wellbeing",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    wellbeing: {
      trends: { series: { energy: { values: [2, 4, 5], trend: { classification: "IMPROVING" } } } },
    },
  });
  assert.match(wellbeing, /class="wellbeing-trend-chart"/);
  assert.match(wellbeing, /<rect[^>]+height="40"/);
  assert.doesNotMatch(wellbeing, /\sstyle=/);

  const rehab = renderApp({
    session,
    route: "rehab/today",
    theme: "light",
    offline: false,
    rehabData: {
      "rehab/today": {
        program: { name: "Recovery plan", stage: "Foundations" },
        exercises: [{ exercise: { id: "exercise-1", name: "Balance" } }],
        completed: 1,
        remaining: 0,
      },
    },
  });
  assert.match(rehab, /<progress class="rehab-progress"/);
  assert.doesNotMatch(rehab, /\sstyle=/);

  const bodyMap = renderApp({
    session,
    route: "health-body-map",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    healthData: {
      "health-body-map": { regions: [{ id: "region-1", name: "Head", system: "General", anatomical_identifier: "head" }] },
    },
  });
  assert.match(bodyMap, /class="body-map-pin body-map-pin--head/);
  assert.doesNotMatch(bodyMap, /\sstyle=/);
});

test("Rehab has a first-class athlete hub and all requested web sections", () => {
  const session = { email: "athlete@example.test", name: "Jordan", role: "ATHLETE", userId: "athlete-1" };
  const routes = [
    "rehab",
    "rehab/today",
    "rehab/program",
    "rehab/exercises",
    "rehab/exercises/exercise-1",
    "rehab/session",
    "rehab/session/session-1",
    "rehab/session/session-1/result",
    "rehab/movement",
    "rehab/movement/session-1",
    "rehab/progress",
    "rehab/recovery",
    "rehab/functional-tests",
    "rehab/functional-tests/test-1",
    "rehab/functional-tests/test-1/result",
    "rehab/readiness",
    "rehab/return-to-sport",
    "rehab/history",
    "rehab/reports",
  ];
  const labels = [
    "Rehabilitation",
    "Today(?:'|&#39;)s Rehabilitation",
    "Your program",
    "Exercise library",
    "Exercise details",
    "Rehab session",
    "Single-Leg Squat",
    "Session complete",
    "Movement analysis",
    "Movement session",
    "Rehabilitation progress",
    "Recovery",
    "Functional tests",
    "Balance Test",
    "Functional test",
    "Today(?:'|&#39;)s rehab readiness",
    "Return-to-sport progression",
    "Rehabilitation history",
    "Rehabilitation reports",
  ];
  for (const [index, route] of routes.entries()) {
    const markup = renderApp({
      session,
      route,
      theme: "light",
      offline: false,
      healthApiConfigured: false,
      rehabData: route.startsWith("rehab/functional-tests") ? {
        [route]: {
          tests: [{
            id: "test-1",
            name: "Balance Test",
            purpose: "Record a timed balance attempt.",
            preparation: "Stand near a stable support.",
            instructions: ["Stand safely.", "Stop if uncomfortable."],
            measurement_method: "Elapsed attempt duration.",
          }],
          history: [],
        },
      } : {},
      rehabSession: route.includes("session-1")
        ? {
          id: "session-1",
          status: route.endsWith("/result") ? "COMPLETED" : "CALIBRATING",
          source: "SIMULATION",
          exercise: { name: "Single-Leg Squat" },
          target_repetitions: 8,
          completed_repetitions: 0,
          samples: [],
          repetitions: [],
        }
        : null,
    });
    assert.match(markup, new RegExp(labels[index].startsWith("Today") ? labels[index] : labels[index].replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    if (route !== "rehab") assert.match(markup, /class="back-link" href="#[^"]+" data-route="[^"]+"/);
  }
});

test("Rehab empty and source states avoid fake readiness and medical clearance", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "rehab",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    rehabData: {
      rehab: {
        program_assigned: false,
        current_program: null,
        today: { exercises: [], completed: 0, remaining: 0 },
        recent_sessions: [],
        progress: {},
        recovery: { status: "UNAVAILABLE" },
      },
    },
  });
  assert.match(markup, /No rehabilitation program assigned/);
  assert.match(markup, /not provide medical clearance/i);
  assert.doesNotMatch(markup, /\b(?:82|87|91)%/);
});

test("Rehab history displays the elapsed time stored for a local session", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "rehab/history",
    theme: "light",
    offline: false,
    healthApiConfigured: false,
    rehabData: {
      "rehab/history": {
        sessions: [{
          id: "session-1",
          exercise: { name: "Single-Leg Squat" },
          source: "SIMULATION",
          status: "COMPLETED",
          elapsed_ms: 57_000,
        }],
      },
    },
  });

  assert.match(markup, /57 sec/);
  assert.doesNotMatch(markup, /Duration not recorded/);
});

test("health overview links to each Phase 2 screen and uses honest empty states", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "health",
    theme: "light",
    offline: false,
    healthApiConfigured: false,
    healthData: {},
  });
  for (const route of [
    "health-reports",
    "health-body-map",
    "health-biomarkers",
    "health-intelligence",
    "health-nutrition",
    "health-medication",
    "health-anti-doping",
    "health-skin-screening",
    "health-history",
  ]) {
    assert.match(markup, new RegExp(`data-route="${route}"`));
  }
  assert.match(markup, /Connect a secure VitaPulse API/);
  assert.doesNotMatch(markup, /\b(?:82|87|91)%/);
});

test("biomarker screen escapes source data and marks trends as descriptive", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "health-biomarkers",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    healthData: {
      "health-biomarkers": {
        biomarkers: [{
          biomarker_name: "Hemoglobin",
          canonical_name: "<script>alert(1)</script>",
          measurement_count: 1,
          trend: "INSUFFICIENT_DATA",
          latest: { value_numeric: 12, unit: "g/dL", source_text: "<script>bad()</script>", source_page: 1 },
        }],
        note: "Trend direction is descriptive only.",
      },
    },
  });
  assert.match(markup, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.match(markup, /&lt;script&gt;bad\(\)&lt;\/script&gt;/);
  assert.match(markup, /not an interpretation/);
  assert.doesNotMatch(markup, /<script>alert\(1\)<\/script>/);
});

test("medical report upload requires explicit processing consent", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "health-reports",
    theme: "light",
    offline: false,
    healthApiConfigured: true,
    healthData: { "health-reports": { reports: [] } },
  });
  assert.match(markup, /name="consent" value="true" required/);
  assert.match(markup, /I agree to upload this report and have it processed/);
  assert.match(markup, /type="file" name="report"/);
});

test("doctor shell uses its own five-destination navigation", () => {
  const markup = renderApp({
    session: { email: "doctor@example.test", name: "Doctor", role: "DOCTOR" },
    route: "doctor-dashboard",
    theme: "light",
    offline: false,
  });
  assert.match(markup, /CLINICAL WORKSPACE/);
  assert.match(markup, /class="bottom-nav doctor-bottom-nav" aria-label="Clinical navigation"/);
  for (const route of ["doctor-dashboard", "doctor-athletes", "doctor-health", "doctor-rehab", "doctor-reports"]) {
    assert.match(markup, new RegExp(`data-route="${route}"`));
  }
  assert.doesNotMatch(markup, /data-route="wellbeing"/);
  assert.match(markup, /No athletes linked yet/);
});

test("profile editing uses escaped session data and the profile form", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: `Jordan "J" Davis`, role: "ATHLETE" },
    route: "profile",
    theme: "light",
    offline: false,
    profileEditing: true,
    athleteProfile: { sport: "Track", position: "Sprinter", rehabilitation_goal: "Return to running" },
  });
  assert.match(markup, /data-form="profile"/);
  assert.match(markup, /value="Jordan &quot;J&quot; Davis"/);
  assert.match(markup, /value="Track"/);
  assert.match(markup, /name="heightCm"/);
  assert.match(markup, /name="dominantSide"/);
  assert.match(markup, /Return to running/);
  assert.doesNotMatch(markup, /Jordan "J" Davis/);
});

test("athlete registration covers optional sports and profile details", () => {
  const markup = renderAuth({ authMode: "register", accountType: "ATHLETE", configured: true });
  for (const name of [
    "dateOfBirth",
    "sport",
    "position",
    "heightCm",
    "weightKg",
    "dominantSide",
    "injuryRegion",
    "rehabilitationGoal",
  ]) {
    assert.match(markup, new RegExp(`name="${name}"`));
  }
  assert.match(markup, /Optional — you can add these details later/);
});

test("development login visibly identifies local demo accounts", () => {
  const markup = renderAuth({ authMode: "login", demoMode: true, configured: false });
  assert.match(markup, /DEMO MODE/);
  assert.match(markup, /demo@vitapulse\.app/);
  assert.match(markup, /doctor\.demo@vitapulse\.app/);
  assert.match(markup, /data-demo-sign-in="DOCTOR"/);
});

test("demo mode remains visible during registration and account recovery", () => {
  for (const authMode of ["register", "forgot", "reset"]) {
    assert.match(renderAuth({ authMode, demoMode: true }), /DEMO MODE/, `${authMode} should retain the demo notice`);
  }
});

test("demo sessions show a persistent no-real-records notice", () => {
  const markup = renderApp({
    session: { email: "demo@vitapulse.app", name: "Demo Athlete", role: "ATHLETE", demo: true },
    route: "home",
    theme: "light",
    offline: false,
  });
  assert.match(markup, /DEMO MODE/);
  assert.match(markup, /No real athlete or patient data is used/);
});

test("doctor dashboard foundation shows only truthful empty summaries", () => {
  const markup = renderApp({
    session: { email: "doctor@example.test", name: "Doctor", role: "DOCTOR" },
    route: "doctor-dashboard",
    theme: "light",
    offline: false,
  });
  for (const card of ["No athletes linked yet", "No pending reviews", "No shared reports", "No rehabilitation alerts"]) {
    assert.match(markup, new RegExp(card));
  }
  assert.doesNotMatch(markup, /\b(?:82|87|91)%/);
});

test("settings includes each Phase 1 section and account access", () => {
  const markup = renderApp({
    session: { email: "athlete@example.test", name: "Jordan", role: "ATHLETE" },
    route: "settings",
    theme: "light",
    offline: false,
  });
  for (const section of ["Appearance", "Notifications", "Privacy", "Permissions", "Connected devices", "Account", "About VitaPulse"]) {
    assert.match(markup, new RegExp(section));
  }
});

test("registration includes a separate doctor verification notice", () => {
  const markup = renderAuth({ authMode: "register", accountType: "DOCTOR", configured: true });
  assert.match(markup, /Doctor accounts require verification/);
  assert.match(markup, /data-account-type="DOCTOR"/);
  assert.match(markup, /Registration never grants access to athlete records/);
});
