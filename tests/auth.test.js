import test from "node:test";
import assert from "node:assert/strict";

globalThis.window = {
  location: { hostname: "127.0.0.1" },
  VITAPULSE_CONFIG: {
    supabaseUrl: "https://vitapulse-test.supabase.co",
    supabasePublishableKey: "publishable-test-key",
    apiBaseUrl: "http://127.0.0.1:8000",
    demoModeEnabled: true,
  },
};

const { AuthError, SupabaseAuth, isAllowedRole } = await import("../src/auth.js");
const {
  isClientSafeSupabaseKey,
  isDemoModeEnabled,
  isSecureApiBaseUrl,
  isSecureSupabaseUrl,
} = await import("../src/config.js");

function createStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: (key) => values.delete(key),
  };
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("role validation accepts only the server-defined role names", () => {
  assert.equal(isAllowedRole("ATHLETE"), true);
  assert.equal(isAllowedRole("doctor"), true);
  assert.equal(isAllowedRole("OWNER"), false);
  assert.equal(isAllowedRole(undefined), false);
});

test("browser auth configuration permits HTTPS and loopback development only", () => {
  assert.equal(isSecureSupabaseUrl("https://project.supabase.co"), true);
  assert.equal(isSecureSupabaseUrl("http://127.0.0.1:54321"), true);
  assert.equal(isSecureSupabaseUrl("http://supabase.example.test"), false);
  assert.equal(isSecureSupabaseUrl("https://user:pass@project.supabase.co"), false);
  assert.equal(isSecureSupabaseUrl("https://project.supabase.co/proxy"), false);
});

test("browser configuration rejects service-role Supabase keys", () => {
  const serviceRoleJwt = "eyJhbGciOiJub25lIn0.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.";
  assert.equal(isClientSafeSupabaseKey("sb_publishable_public-key"), true);
  assert.equal(isClientSafeSupabaseKey("eyJhbGciOiJub25lIn0.eyJyb2xlIjoiYW5vbiJ9."), true);
  assert.equal(isClientSafeSupabaseKey("sb_secret_do-not-use-in-browser"), false);
  assert.equal(isClientSafeSupabaseKey(serviceRoleJwt), false);
  assert.equal(isClientSafeSupabaseKey(""), false);
});

test("Health API configuration allows HTTPS and loopback HTTP only", () => {
  assert.equal(isSecureApiBaseUrl("https://api.vitapulse.example"), true);
  assert.equal(isSecureApiBaseUrl("http://127.0.0.1:8000"), true);
  assert.equal(isSecureApiBaseUrl("http://api.vitapulse.example"), false);
  assert.equal(isSecureApiBaseUrl("https://api.vitapulse.example/private"), false);
  assert.equal(isSecureApiBaseUrl("https://user:pass@api.vitapulse.example"), false);
});

test("development demo accounts are enabled only on loopback hosts", () => {
  assert.equal(isDemoModeEnabled(true, "localhost"), true);
  assert.equal(isDemoModeEnabled(true, "127.0.0.1"), true);
  assert.equal(isDemoModeEnabled(true, "vitapulse.example"), false);
  assert.equal(isDemoModeEnabled(false, "localhost"), false);
});

test("demo sign-in and session restore are local-only and expose no patient records", async () => {
  const storage = createStorage();
  let networkRequests = 0;
  const auth = new SupabaseAuth({
    storage,
    fetchImpl: async () => {
      networkRequests += 1;
      throw new Error("Demo auth must not call the network.");
    },
  });

  const session = await auth.signIn("demo@vitapulse.app", "Demo@12345!");
  assert.equal(session.demo, true);
  assert.equal(session.role, "ATHLETE");
  assert.equal((await auth.fetchAthleteProfile(session)).sport, null);
  assert.equal(await auth.restoreSession().then((restored) => restored.demo), true);
  await auth.signOut();

  assert.equal(storage.getItem("vitapulse.auth.session.v1"), null);
  assert.equal(networkRequests, 0);
});

test("demo credentials reject incorrect passwords", async () => {
  const auth = new SupabaseAuth({ storage: createStorage(), fetchImpl: async () => assert.fail("Unexpected network request") });
  await assert.rejects(
    auth.signIn("demo@vitapulse.app", "wrong-password"),
    (error) => error instanceof AuthError && error.code === "INVALID_CREDENTIALS",
  );
});

test("demo doctor sign-in remains separate and contains no athlete data", async () => {
  const auth = new SupabaseAuth({ storage: createStorage(), fetchImpl: async () => assert.fail("Unexpected network request") });
  const session = await auth.signIn("doctor.demo@vitapulse.app", "DemoDoctor@12345!");

  assert.equal(session.role, "DOCTOR");
  assert.equal(session.demo, true);
  assert.equal(await auth.fetchAthleteProfile(session), null);
});

test("health requests refuse demo accounts and use the authenticated backend envelope", async () => {
  const demoAuth = new SupabaseAuth({ storage: createStorage(), fetchImpl: async () => assert.fail("Demo must not call the API") });
  await assert.rejects(
    demoAuth.healthRequest({ demo: true }, "/overview"),
    (error) => error instanceof AuthError && error.code === "HEALTH_DEMO_UNAVAILABLE",
  );

  let request;
  const auth = new SupabaseAuth({
    storage: createStorage(),
    fetchImpl: async (url, options) => {
      request = { url, options };
      return jsonResponse({ success: true, data: { status: "ok" }, error: null });
    },
  });
  const data = await auth.healthRequest(
    { demo: false, accessToken: "athlete-access-token" },
    "/overview",
  );

  assert.deepEqual(data, { status: "ok" });
  assert.equal(request.url, "http://127.0.0.1:8000/api/v1/health/overview");
  assert.equal(request.options.headers.Authorization, "Bearer athlete-access-token");
});

test("connect API requests use the versioned backend path and bearer session", async () => {
  let request;
  const auth = new SupabaseAuth({
    storage: createStorage(),
    fetchImpl: async (url, options) => {
      request = { url, options };
      return jsonResponse({ success: true, data: { health_connect: { status: "AUTHORIZED" } } });
    },
  });
  const data = await auth.apiRequest(
    { demo: false, accessToken: "athlete-access-token" },
    "/connect/status",
  );

  assert.deepEqual(data, { health_connect: { status: "AUTHORIZED" } });
  assert.equal(request.url, "http://127.0.0.1:8000/api/v1/connect/status");
  assert.equal(request.options.headers.Authorization, "Bearer athlete-access-token");
});

test("athlete registration sends optional profile details as user metadata", async () => {
  let signupBody;
  let signupUrl;
  const auth = new SupabaseAuth({
    storage: createStorage(),
    redirectUrl: "https://vitapulse-eosin.vercel.app",
    fetchImpl: async (url, options) => {
      signupUrl = String(url);
      signupBody = JSON.parse(options.body);
      return jsonResponse({ user: { id: "athlete-1", email: "athlete@example.test" } });
    },
  });

  const result = await auth.signUp({
    fullName: "Jordan Davis",
    email: "athlete@example.test",
    password: "long-password",
    dateOfBirth: "2000-01-02",
    sport: "Track",
    position: "Sprinter",
    heightCm: "178",
    weightKg: "72",
    dominantSide: "RIGHT",
    injuryRegion: "Knee",
    rehabilitationGoal: "Return to running",
  });

  assert.equal(result.needsEmailConfirmation, true);
  assert.equal(new URL(signupUrl).searchParams.get("redirect_to"), "https://vitapulse-eosin.vercel.app");
  assert.deepEqual(
    Object.fromEntries(Object.entries(signupBody.data).filter(([key]) => key !== "full_name" && key !== "requested_account_type")),
    {
      sport: "Track",
      position: "Sprinter",
      date_of_birth: "2000-01-02",
      height_cm: 178,
      weight_kg: 72,
      dominant_side: "RIGHT",
      injury_region: "Knee",
      rehabilitation_goal: "Return to running",
    },
  );
});

test("password recovery redirects back to the configured VitaPulse origin", async () => {
  let recoveryUrl;
  const auth = new SupabaseAuth({
    storage: createStorage(),
    redirectUrl: "https://vitapulse-eosin.vercel.app",
    fetchImpl: async (url) => {
      recoveryUrl = String(url);
      return jsonResponse({});
    },
  });

  await auth.sendPasswordReset("athlete@example.test");

  assert.equal(new URL(recoveryUrl).searchParams.get("redirect_to"), "https://vitapulse-eosin.vercel.app");
});

test("sign in trusts the profile role and never persists the password", async () => {
  const storage = createStorage();
  const auth = new SupabaseAuth({
    storage,
    fetchImpl: async (url) => {
      if (String(url).includes("/auth/v1/token")) {
        return jsonResponse({
          access_token: "access-token-value",
          refresh_token: "refresh-token-value",
          expires_in: 3600,
          user: { id: "user-1", email: "athlete@example.test", user_metadata: { full_name: "Jordan" } },
        });
      }
      if (String(url).includes("/rest/v1/profiles")) {
        return jsonResponse([{ role: "ATHLETE", display_name: "Jordan" }]);
      }
      return jsonResponse([]);
    },
  });

  const session = await auth.signIn("athlete@example.test", "correct-horse-password");
  const storedSession = storage.getItem("vitapulse.auth.session.v1");

  assert.equal(session.role, "ATHLETE");
  assert.equal(session.name, "Jordan");
  assert.equal(storedSession.includes("correct-horse-password"), false);
  assert.equal(storedSession.includes("access-token-value"), true);
});

test("sign in rejects an unknown profile role without saving a session", async () => {
  const storage = createStorage();
  const auth = new SupabaseAuth({
    storage,
    fetchImpl: async (url) => String(url).includes("/auth/v1/token")
      ? jsonResponse({
        access_token: "access-token-value",
        user: { id: "user-1", email: "athlete@example.test" },
      })
      : jsonResponse([{ role: "SUPERUSER" }]),
  });

  await assert.rejects(
    auth.signIn("athlete@example.test", "password-value"),
    (error) => error instanceof AuthError && error.code === "PROFILE_NOT_READY",
  );
  assert.equal(storage.getItem("vitapulse.auth.session.v1"), null);
});

test("sign in blocks pending doctor applicants from athlete navigation", async () => {
  const storage = createStorage();
  const auth = new SupabaseAuth({
    storage,
    fetchImpl: async (url) => {
      if (String(url).includes("/auth/v1/token")) {
        return jsonResponse({
          access_token: "access-token-value",
          user: { id: "doctor-1", email: "doctor@example.test" },
        });
      }
      if (String(url).includes("/rest/v1/profiles")) {
        return jsonResponse([{ role: "ATHLETE", display_name: "Pending Doctor" }]);
      }
      return jsonResponse([{ status: "PENDING" }]);
    },
  });

  await assert.rejects(
    auth.signIn("doctor@example.test", "password-value"),
    (error) => error instanceof AuthError && error.code === "DOCTOR_APPLICATION_REVIEW",
  );
  assert.equal(storage.getItem("vitapulse.auth.session.v1"), null);
});

test("doctor registration never installs an athlete-side session", async () => {
  const storage = createStorage();
  const requests = [];
  const auth = new SupabaseAuth({
    storage,
    fetchImpl: async (url, options) => {
      requests.push({ url: String(url), method: options.method });
      return String(url).includes("/auth/v1/signup")
        ? jsonResponse({
          access_token: "temporary-access-token",
          user: { id: "doctor-1", email: "doctor@example.test" },
        })
        : new Response(null, { status: 204 });
    },
  });

  const result = await auth.signUp({
    fullName: "Doctor Example",
    email: "doctor@example.test",
    password: "temporary-password",
    accountType: "DOCTOR",
    licenseId: "TEST-LICENSE",
  });

  assert.deepEqual(result, { needsDoctorApproval: true });
  assert.equal(storage.getItem("vitapulse.auth.session.v1"), null);
  assert.equal(requests.some((request) => request.url.includes("/rest/v1/profiles")), false);
  assert.equal(requests.some((request) => request.url.includes("/auth/v1/logout")), true);
});
