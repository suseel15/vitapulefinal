import { authIsConfigured, demoModeEnabled, healthApiIsConfigured, publicConfig } from "./config.js";

const SESSION_KEY = "vitapulse.auth.session.v1";
const SESSION_SAFETY_WINDOW_MS = 30_000;
const VALID_ROLES = new Set(["ATHLETE", "DOCTOR", "ADMIN"]);
const DEMO_ACCOUNTS = Object.freeze({
  "demo@vitapulse.app": { password: "Demo@12345!", id: "demo-athlete", name: "Demo Athlete", role: "ATHLETE" },
  "doctor.demo@vitapulse.app": { password: "DemoDoctor@12345!", id: "demo-doctor", name: "Demo Clinician", role: "DOCTOR" },
});

export class AuthError extends Error {
  constructor(message, status = 0, code = "AUTH_ERROR") {
    super(message);
    this.name = "AuthError";
    this.status = status;
    this.code = code;
  }
}

export function isAllowedRole(role) {
  return typeof role === "string" && VALID_ROLES.has(role.toUpperCase());
}

export class SupabaseAuth {
  constructor({ fetchImpl = fetch, storage = sessionStorage } = {}) {
    this.fetchImpl = fetchImpl;
    this.storage = storage;
  }

  get configured() {
    return authIsConfigured;
  }

  async signIn(email, password) {
    const normalizedEmail = email.trim().toLowerCase();
    const demoAccount = DEMO_ACCOUNTS[normalizedEmail];
    if (demoModeEnabled && demoAccount) {
      if (password !== demoAccount.password) {
        throw new AuthError("That email and password don't match. Check them and try again.", 400, "INVALID_CREDENTIALS");
      }
      const session = {
        accessToken: "",
        refreshToken: "",
        expiresAt: Number.MAX_SAFE_INTEGER,
        userId: demoAccount.id,
        email: normalizedEmail,
        name: demoAccount.name,
        role: demoAccount.role,
        demo: true,
      };
      this.saveSession(session);
      return session;
    }

    const result = await this.request("/auth/v1/token?grant_type=password", {
      method: "POST",
      body: { email: email.trim(), password },
    });
    if (!result.access_token || !result.user?.id) {
      throw new AuthError("Sign-in did not return a valid session.", 0, "INVALID_SESSION");
    }
    const profile = await this.fetchProfile(result.access_token, result.user.id);
    const role = profile?.role?.toUpperCase();
    if (!isAllowedRole(role)) {
      throw new AuthError(
        "Your account profile is not set up yet. Please contact VitaPulse support.",
        403,
        "PROFILE_NOT_READY",
      );
    }
    await this.assertNoPendingDoctorApplication(result.access_token, result.user.id, role);
    const session = this.toSession(result, profile, role);
    this.saveSession(session);
    return session;
  }

  async signUp({
    fullName,
    email,
    password,
    accountType = "ATHLETE",
    sport = "",
    licenseId = "",
    specialization = "",
    organization = "",
    phone = "",
    dateOfBirth = "",
    position = "",
    heightCm = "",
    weightKg = "",
    dominantSide = "",
    injuryRegion = "",
    rehabilitationGoal = "",
  }) {
    const requestedRole = accountType.toUpperCase();
    if (!["ATHLETE", "DOCTOR"].includes(requestedRole)) {
      throw new AuthError("Choose an available account type.", 400, "INVALID_ROLE");
    }

    const result = await this.request("/auth/v1/signup", {
      method: "POST",
      body: {
        email: email.trim(),
        password,
        data: {
          full_name: fullName.trim(),
          requested_account_type: requestedRole,
          ...(requestedRole === "ATHLETE" && sport.trim() ? { sport: sport.trim() } : {}),
          ...(requestedRole === "ATHLETE" && position.trim() ? { position: position.trim() } : {}),
          ...(requestedRole === "ATHLETE" && dateOfBirth ? { date_of_birth: dateOfBirth } : {}),
          ...(requestedRole === "ATHLETE" && heightCm ? { height_cm: Number(heightCm) } : {}),
          ...(requestedRole === "ATHLETE" && weightKg ? { weight_kg: Number(weightKg) } : {}),
          ...(requestedRole === "ATHLETE" && dominantSide ? { dominant_side: dominantSide } : {}),
          ...(requestedRole === "ATHLETE" && injuryRegion.trim() ? { injury_region: injuryRegion.trim() } : {}),
          ...(requestedRole === "ATHLETE" && rehabilitationGoal.trim()
            ? { rehabilitation_goal: rehabilitationGoal.trim() }
            : {}),
          ...(requestedRole === "DOCTOR" && specialization.trim()
            ? { specialization: specialization.trim() }
            : {}),
          ...(requestedRole === "DOCTOR" && licenseId.trim()
            ? { license_id: licenseId.trim() }
            : {}),
          ...(requestedRole === "DOCTOR" && organization.trim()
            ? { organization: organization.trim() }
            : {}),
          ...(requestedRole === "DOCTOR" && phone.trim()
            ? { phone: phone.trim() }
            : {}),
        },
      },
    });

    if (!result.access_token || !result.user?.id) {
      return {
        needsEmailConfirmation: true,
        isDoctorApplication: requestedRole === "DOCTOR",
      };
    }

    if (requestedRole === "DOCTOR") {
      if (result.access_token) {
        await this.request("/auth/v1/logout", {
          method: "POST",
          accessToken: result.access_token,
        });
      }
      return { needsDoctorApproval: true };
    }

    const profile = await this.fetchProfile(result.access_token, result.user.id);
    const role = profile?.role?.toUpperCase();
    if (role !== "ATHLETE") {
      this.clearSession();
      throw new AuthError(
        "Your athlete profile could not be confirmed. Please contact support.",
        403,
        "PROFILE_NOT_READY",
      );
    }
    const session = this.toSession(result, profile, role);
    this.saveSession(session);
    return { session };
  }

  async sendPasswordReset(email) {
    await this.request("/auth/v1/recover", {
      method: "POST",
      body: { email: email.trim() },
    });
  }

  async updatePassword(recoveryToken, password) {
    if (!recoveryToken) {
      throw new AuthError("This password-reset link is missing or has expired. Request a new link.", 400, "INVALID_RECOVERY_LINK");
    }
    await this.request("/auth/v1/user", {
      method: "PUT",
      accessToken: recoveryToken,
      body: { password },
    });
    this.clearSession();
  }

  async signOut() {
    const session = this.readSession();
    try {
      if (session?.accessToken && !session.demo) {
        await this.request("/auth/v1/logout", {
          method: "POST",
          accessToken: session.accessToken,
        });
      }
    } finally {
      this.clearSession();
    }
  }

  async restoreSession() {
    const session = this.readSession();
    if (!session) return null;
    if (session.demo) {
      const demoAccount = Object.values(DEMO_ACCOUNTS).find(
        (account) => account.id === session.userId && account.role === session.role,
      );
      if (!demoModeEnabled || !demoAccount || session.email !== Object.keys(DEMO_ACCOUNTS).find(
        (email) => DEMO_ACCOUNTS[email].id === session.userId,
      )) {
        this.clearSession();
        return null;
      }
      return session;
    }
    let refreshed = false;
    try {
      let activeSession = session;
      if (session.expiresAt - Date.now() <= SESSION_SAFETY_WINDOW_MS) {
        refreshed = true;
        activeSession = await this.refreshSession(session);
        this.saveSession(activeSession);
      }
      const profile = await this.fetchProfile(activeSession.accessToken, activeSession.userId);
      const role = profile?.role?.toUpperCase();
      if (!isAllowedRole(role)) {
        throw new AuthError("Your account profile is not available.", 403, "PROFILE_NOT_READY");
      }
      await this.assertNoPendingDoctorApplication(activeSession.accessToken, activeSession.userId, role);
      const verified = { ...activeSession, name: profile.display_name || activeSession.name, role };
      this.saveSession(verified);
      return verified;
    } catch (error) {
      if (error.status === 401 && session.refreshToken && !refreshed) {
        try {
          const renewedSession = await this.refreshSession(session);
          this.saveSession(renewedSession);
          return renewedSession;
        } catch (refreshError) {
          if (!["NETWORK_ERROR", "TIMEOUT"].includes(refreshError.code)) this.clearSession();
          throw refreshError;
        }
      }
      if (["NETWORK_ERROR", "TIMEOUT"].includes(error.code)) throw error;
      this.clearSession();
      throw error;
    }
  }

  async refreshSession(session) {
    if (!session.refreshToken) {
      this.clearSession();
      throw new AuthError("Your session has expired. Please sign in again.", 401, "SESSION_EXPIRED");
    }
    const result = await this.request("/auth/v1/token?grant_type=refresh_token", {
      method: "POST",
      body: { refresh_token: session.refreshToken },
    });
    if (!result.access_token || !result.user?.id) {
      throw new AuthError("Session refresh did not return a valid session.", 0, "INVALID_SESSION");
    }
    const profile = await this.fetchProfile(result.access_token, result.user.id);
    const role = profile?.role?.toUpperCase();
    if (!isAllowedRole(role)) {
      throw new AuthError("Your account profile is not available.", 403, "PROFILE_NOT_READY");
    }
    await this.assertNoPendingDoctorApplication(result.access_token, result.user.id, role);
    return this.toSession(result, profile, role);
  }

  async assertNoPendingDoctorApplication(accessToken, userId, role) {
    if (role !== "ATHLETE") return;
    const query = new URLSearchParams({
      select: "status",
      profile_id: `eq.${userId}`,
      limit: "1",
    });
    const applications = await this.request(`/rest/v1/doctor_applications?${query}`, {
      accessToken,
    });
    if (Array.isArray(applications) && applications.length > 0) {
      throw new AuthError(
        "This account has a doctor access application. Clinical or athlete access is unavailable until the application is resolved by an administrator.",
        403,
        "DOCTOR_APPLICATION_REVIEW",
      );
    }
  }

  async healthRequest(session, path, { method = "GET", body } = {}) {
    if (session.demo) {
      throw new AuthError(
        "Health records are unavailable in demo mode. Sign in with a real athlete account and configure the Health API.",
        403,
        "HEALTH_DEMO_UNAVAILABLE",
      );
    }
    const baseUrl = publicConfig.apiBaseUrl.replace(/\/+$/, "");
    if (!healthApiIsConfigured || !session.accessToken) {
      throw new AuthError(
        "Health records need a signed-in account and a configured VitaPulse API.",
        503,
        "HEALTH_API_NOT_CONFIGURED",
      );
    }
    let response;
    try {
      response = await this.fetchImpl(`${baseUrl}/api/v1/health${path}`, {
        method,
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
          ...(body && !(body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        },
        ...(body
          ? { body: body instanceof FormData ? body : JSON.stringify(body) }
          : {}),
        signal: AbortSignal.timeout(60_000),
      });
    } catch (error) {
      if (error.name === "AbortError" || error.name === "TimeoutError") {
        throw new AuthError("The health request timed out. Please try again.", 0, "TIMEOUT");
      }
      if (error instanceof TypeError) {
        throw new AuthError("Couldn't reach the Health API. Check your connection and try again.", 0, "NETWORK_ERROR");
      }
      throw error;
    }
    if (response.status === 204) return null;
    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      throw new AuthError("The Health API returned an unreadable response.", response.status, "INVALID_RESPONSE");
    }
    if (!response.ok || payload?.success === false) {
      throw new AuthError(
        payload?.error?.message || "The health request could not be completed.",
        response.status,
        payload?.error?.code || "HEALTH_API_ERROR",
      );
    }
    return payload?.data;
  }

  async request(path, { method = "GET", body, accessToken } = {}) {
    if (!this.configured) {
      throw new AuthError(
        "Authentication needs a valid HTTPS Supabase URL and publishable key in config.js.",
        0,
        "AUTH_NOT_CONFIGURED",
      );
    }

    let response;
    try {
      response = await this.fetchImpl(`${publicConfig.supabaseUrl.replace(/\/+$/, "")}${path}`, {
        method,
        headers: {
          apikey: publicConfig.supabasePublishableKey,
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
        signal: AbortSignal.timeout(12_000),
      });
    } catch (error) {
      if (error.name === "AbortError" || error.name === "TimeoutError") {
        throw new AuthError("The request timed out. Please try again.", 0, "TIMEOUT");
      }
      if (error instanceof TypeError) {
        throw new AuthError("Couldn't reach VitaPulse. Check your internet connection and try again.", 0, "NETWORK_ERROR");
      }
      throw error;
    }

    if (response.status === 204) return null;
    let payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      if (response.ok) {
        throw new AuthError("The authentication service returned an unreadable response.", response.status, "INVALID_RESPONSE");
      }
    }
    if (!response.ok) {
      const detail = payload?.msg ?? payload?.message ?? payload?.error_description ?? payload?.error;
      const code = payload?.code ?? payload?.error_code ?? "AUTH_ERROR";
      throw new AuthError(
        typeof detail === "string" && detail ? detail : "We couldn't complete that request. Please try again.",
        response.status,
        String(code),
      );
    }
    return payload;
  }

  async fetchProfile(accessToken, userId) {
    const query = new URLSearchParams({
      select: "role,display_name",
      id: `eq.${userId}`,
      limit: "1",
    });
    const rows = await this.request(`/rest/v1/profiles?${query}`, { accessToken });
    return Array.isArray(rows) ? rows[0] ?? null : null;
  }

  async fetchAthleteProfile(session) {
    if (session.role !== "ATHLETE") return null;
    if (session.demo) {
      return session.athleteProfile ?? {
        date_of_birth: null,
        sport: null,
        position: null,
        height_cm: null,
        weight_kg: null,
        dominant_side: null,
        injury_region: null,
        rehab_stage: null,
        rehabilitation_goal: null,
      };
    }
    const query = new URLSearchParams({
      select: "date_of_birth,sport,position,height_cm,weight_kg,dominant_side,injury_region,rehab_stage,rehabilitation_goal",
      id: `eq.${session.userId}`,
      limit: "1",
    });
    const rows = await this.request(`/rest/v1/athlete_profiles?${query}`, {
      accessToken: session.accessToken,
    });
    return Array.isArray(rows) ? rows[0] ?? {} : {};
  }

  async updateAthleteProfile(session, profile) {
    if (session.role !== "ATHLETE") {
      throw new AuthError("Only an athlete can edit this sports profile.", 403, "FORBIDDEN");
    }
    if (session.demo) {
      session.name = profile.displayName.trim();
      session.athleteProfile = {
        ...(session.athleteProfile ?? {}),
        date_of_birth: profile.dateOfBirth || null,
        sport: profile.sport || null,
        position: profile.position || null,
        height_cm: profile.heightCm || null,
        weight_kg: profile.weightKg || null,
        dominant_side: profile.dominantSide || null,
        injury_region: profile.injuryRegion || null,
        rehabilitation_goal: profile.rehabilitationGoal || null,
      };
      this.saveSession(session);
      return;
    }
    await this.request("/rest/v1/rpc/update_my_athlete_profile", {
      method: "POST",
      accessToken: session.accessToken,
      body: {
        p_display_name: profile.displayName.trim(),
        p_sport: profile.sport.trim(),
        p_position: profile.position.trim(),
        p_rehabilitation_goal: profile.rehabilitationGoal.trim(),
        p_date_of_birth: profile.dateOfBirth || null,
        p_height_cm: profile.heightCm || null,
        p_weight_kg: profile.weightKg || null,
        p_dominant_side: profile.dominantSide || null,
        p_injury_region: profile.injuryRegion.trim(),
      },
    });
    session.name = profile.displayName.trim();
    this.saveSession(session);
  }

  toSession(result, profile, role) {
    return {
      accessToken: result.access_token,
      refreshToken: result.refresh_token,
      expiresAt: Date.now() + (Number(result.expires_in) || 3600) * 1000,
      userId: result.user.id,
      email: result.user.email ?? "",
      name: profile.display_name || result.user.user_metadata?.full_name || "",
      role,
    };
  }

  readSession() {
    try {
      const session = JSON.parse(this.storage.getItem(SESSION_KEY) ?? "null");
      if (
        !session ||
        typeof session.accessToken !== "string" ||
        typeof session.userId !== "string" ||
        !isAllowedRole(session.role) ||
        (session.demo && (!demoModeEnabled || !["ATHLETE", "DOCTOR"].includes(session.role)))
      ) {
        this.clearSession();
        return null;
      }
      return session;
    } catch {
      this.clearSession();
      return null;
    }
  }

  saveSession(session) {
    this.storage.setItem(SESSION_KEY, JSON.stringify(session));
  }

  clearSession() {
    this.storage.removeItem(SESSION_KEY);
  }
}
