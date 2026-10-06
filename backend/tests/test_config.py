from app.core.config import Settings


def test_supabase_config_requires_tls_outside_local_development() -> None:
    insecure_remote = Settings(
        supabase_url="http://supabase.example.test",
        supabase_publishable_key="public-key",
        app_env="production",
    )

    assert insecure_remote.supabase_is_configured is False


def test_supabase_allows_loopback_http_only_for_local_development() -> None:
    local_development = Settings(
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="public-key",
        app_env="development",
    )
    local_production = Settings(
        supabase_url="http://127.0.0.1:54321",
        supabase_publishable_key="public-key",
        app_env="production",
    )

    assert local_development.supabase_is_configured is True
    assert local_production.supabase_is_configured is False


def test_supabase_rejects_credentials_and_non_root_paths_in_url() -> None:
    with_credentials = Settings(
        supabase_url="https://user:pass@supabase.example.test",
        supabase_publishable_key="public-key",
    )
    with_path = Settings(
        supabase_url="https://supabase.example.test/custom-path",
        supabase_publishable_key="public-key",
    )

    assert with_credentials.supabase_is_configured is False
    assert with_path.supabase_is_configured is False
