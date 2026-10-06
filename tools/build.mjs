import { cp, mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = resolve(root, "dist");
const publicConfig = {
  apiBaseUrl: process.env.VITAPULSE_API_BASE_URL?.trim() || "",
  supabaseUrl: process.env.VITAPULSE_SUPABASE_URL?.trim() || process.env.SUPABASE_URL?.trim() || "",
  supabasePublishableKey: process.env.VITAPULSE_SUPABASE_PUBLISHABLE_KEY?.trim() ||
    process.env.SUPABASE_PUBLISHABLE_KEY?.trim() || "",
};
const configuredSupabaseValues = [publicConfig.supabaseUrl, publicConfig.supabasePublishableKey].filter(Boolean).length;

if (process.env.VERCEL === "1" && configuredSupabaseValues !== 2) {
  throw new Error(
    "Vercel builds require SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY (or their VITAPULSE_* equivalents).",
  );
}

if (configuredSupabaseValues === 1) {
  throw new Error(
    "Set SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY together, or leave both unset for a local demo build.",
  );
}

if (configuredSupabaseValues === 2) {
  for (const [name, value] of [
    ["apiBaseUrl", publicConfig.apiBaseUrl],
    ["supabaseUrl", publicConfig.supabaseUrl],
  ].filter(([, value]) => value)) {
    let url;
    try {
      url = new URL(value);
    } catch {
      throw new Error(`${name} must be a valid HTTPS URL.`);
    }
    if (url.protocol !== "https:" || url.username || url.password) {
      throw new Error(`${name} must be a valid HTTPS URL without embedded credentials.`);
    }
  }

  const key = publicConfig.supabasePublishableKey;
  let serviceRoleKey = /service[_-]?role/i.test(key);
  const jwtPayload = key.split(".")[1];
  if (!serviceRoleKey && jwtPayload) {
    try {
      serviceRoleKey = JSON.parse(Buffer.from(jwtPayload, "base64url").toString("utf8")).role === "service_role";
    } catch {
      serviceRoleKey = false;
    }
  }
  if (serviceRoleKey) {
    throw new Error("VITAPULSE_SUPABASE_PUBLISHABLE_KEY must not contain a Supabase service-role key.");
  }
}

await mkdir(output, { recursive: true });
for (const entry of ["index.html", "styles.css", "app.js", "src"]) {
  await cp(resolve(root, entry), resolve(output, entry), { recursive: true, force: true });
}

if (configuredSupabaseValues === 2) {
  const generatedConfig = {
    apiBaseUrl: JSON.stringify(publicConfig.apiBaseUrl),
    supabaseUrl: JSON.stringify(publicConfig.supabaseUrl),
    supabasePublishableKey: JSON.stringify(publicConfig.supabasePublishableKey),
  };
  await writeFile(
    resolve(output, "config.js"),
    `window.VITAPULSE_CONFIG = Object.freeze({
  apiBaseUrl: ${generatedConfig.apiBaseUrl},
  supabaseUrl: ${generatedConfig.supabaseUrl},
  supabasePublishableKey: ${generatedConfig.supabasePublishableKey},
  demoModeEnabled: ["localhost", "127.0.0.1"].includes(window.location.hostname),
});
`,
  );
} else {
  await cp(resolve(root, "config.js"), resolve(output, "config.js"), { force: true });
}

console.log(`VitaPulse web build written to ${output}`);
