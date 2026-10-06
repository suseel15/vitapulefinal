import { cp, mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const output = resolve(root, "dist");
const publicConfig = {
  apiBaseUrl: process.env.VITAPULSE_API_BASE_URL?.trim() || "",
  supabaseUrl: process.env.VITAPULSE_SUPABASE_URL?.trim() || "",
  supabasePublishableKey: process.env.VITAPULSE_SUPABASE_PUBLISHABLE_KEY?.trim() || "",
};
const configuredValues = Object.values(publicConfig).filter(Boolean).length;

if (process.env.VERCEL === "1" && configuredValues !== Object.keys(publicConfig).length) {
  throw new Error(
    "Vercel builds require VITAPULSE_API_BASE_URL, VITAPULSE_SUPABASE_URL, and VITAPULSE_SUPABASE_PUBLISHABLE_KEY.",
  );
}

if (configuredValues > 0 && configuredValues !== Object.keys(publicConfig).length) {
  throw new Error(
    "Set all three VITAPULSE public configuration variables together, or leave all unset for a local demo build.",
  );
}

if (configuredValues) {
  for (const [name, value] of Object.entries(publicConfig).filter(([name]) => name !== "supabasePublishableKey")) {
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

if (configuredValues) {
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
