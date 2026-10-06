export const publicConfig = Object.freeze({
  supabaseUrl: window.VITAPULSE_CONFIG?.supabaseUrl?.trim() ?? "",
  supabasePublishableKey:
    window.VITAPULSE_CONFIG?.supabasePublishableKey?.trim() ?? "",
  apiBaseUrl: window.VITAPULSE_CONFIG?.apiBaseUrl?.trim() ?? "",
});

export function isDemoModeEnabled(enabled, hostname) {
  return Boolean(enabled) && ["localhost", "127.0.0.1"].includes(hostname);
}

export const demoModeEnabled = isDemoModeEnabled(
  window.VITAPULSE_CONFIG?.demoModeEnabled,
  window.location?.hostname ?? "",
);

export function isSecureSupabaseUrl(value) {
  try {
    const url = new URL(value);
    const secureProtocol = url.protocol === "https:" ||
      (url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname));
    return secureProtocol && ["", "/"].includes(url.pathname) &&
      !url.username && !url.password && !url.search && !url.hash;
  } catch {
    return false;
  }
}

export function isClientSafeSupabaseKey(value) {
  if (typeof value !== "string" || !value.trim() || value.startsWith("sb_secret_")) {
    return false;
  }
  const segments = value.split(".");
  if (segments.length !== 3) return true;
  try {
    const payload = JSON.parse(atob(segments[1].replace(/-/g, "+").replace(/_/g, "/")));
    return payload.role !== "service_role";
  } catch {
    return false;
  }
}

export const authIsConfigured =
  isSecureSupabaseUrl(publicConfig.supabaseUrl) &&
  isClientSafeSupabaseKey(publicConfig.supabasePublishableKey);

export function isSecureApiBaseUrl(value) {
  try {
    const url = new URL(value);
    const secureProtocol = url.protocol === "https:" ||
      (url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname));
    return secureProtocol && ["", "/"].includes(url.pathname) &&
      !url.username && !url.password && !url.search && !url.hash;
  } catch {
    return false;
  }
}

export const healthApiIsConfigured =
  authIsConfigured && isSecureApiBaseUrl(publicConfig.apiBaseUrl);
