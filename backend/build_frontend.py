import base64
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit


BACKEND_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = BACKEND_ROOT.parent
PUBLIC_ROOT = BACKEND_ROOT / "public"


def _https_origin(value: str, name: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{name} must be an HTTPS origin without a path or embedded credentials.")
    return value.rstrip("/")


def _safe_publishable_key(value: str) -> str:
    if not value or value.startswith("sb_secret_") or re.search(r"service[_-]?role", value, re.IGNORECASE):
        raise ValueError("SUPABASE_PUBLISHABLE_KEY must not contain a service-role or secret key.")

    segments = value.split(".")
    if len(segments) == 3:
        payload = segments[1] + "=" * (-len(segments[1]) % 4)
        try:
            token_claims = json.loads(base64.urlsafe_b64decode(payload))
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must be a valid client-safe key.") from None
        if token_claims.get("role") == "service_role":
            raise ValueError("SUPABASE_PUBLISHABLE_KEY must not contain a service-role or secret key.")

    return value


def build_frontend() -> None:
    supabase_url = _https_origin(os.environ.get("SUPABASE_URL", "").strip(), "SUPABASE_URL")
    publishable_key = _safe_publishable_key(os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip())

    PUBLIC_ROOT.mkdir(parents=True, exist_ok=True)
    for entry in ("index.html", "styles.css", "app.js"):
        shutil.copy2(REPOSITORY_ROOT / entry, PUBLIC_ROOT / entry)
    shutil.copytree(REPOSITORY_ROOT / "src", PUBLIC_ROOT / "src", dirs_exist_ok=True)
    (PUBLIC_ROOT / "config.js").write_text(
        "window.VITAPULSE_CONFIG = Object.freeze({\n"
        "  apiBaseUrl: window.location.origin,\n"
        f"  supabaseUrl: {json.dumps(supabase_url)},\n"
        f"  supabasePublishableKey: {json.dumps(publishable_key)},\n"
        '  demoModeEnabled: ["localhost", "127.0.0.1"].includes(window.location.hostname),\n'
        "});\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_frontend()
