"""CLI configuration precedence and reset guards, with no database access."""

from pathlib import Path

import pytest

from app.reviews import seed

pytestmark = pytest.mark.unit
SEED_FILE = Path(__file__).resolve().parents[2] / "review-input/starter/seed.sql"


@pytest.mark.parametrize("environment_url, cli_url, expected", [
    (None, None, "relay_file"),
    ("relay_environment", None, "relay_environment"),
    ("relay_environment", "relay_argument", "relay_argument"),
])
def test_cli_database_precedence(tmp_path, monkeypatch, environment_url, cli_url, expected):
    backend = tmp_path / "backend"
    module = backend / "app/reviews/seed.py"
    module.parent.mkdir(parents=True)
    prefix = "postgresql+psycopg://relay_admin@127.0.0.1:5433/"
    (backend / ".env").write_text("RELAY_ADMIN_DATABASE_URL=" + prefix + "relay_file\n")
    monkeypatch.setattr(seed, "__file__", str(module))
    monkeypatch.delenv("RELAY_ADMIN_DATABASE_URL", raising=False)
    if environment_url:
        monkeypatch.setenv("RELAY_ADMIN_DATABASE_URL", prefix + environment_url)
    calls = []

    def import_spy(path, url, **kwargs):
        calls.append((path, url))
        return "probe"

    monkeypatch.setattr(seed, "run_import", import_spy)
    args = ["--seed-file", str(SEED_FILE)]
    if cli_url:
        args += ["--database-url", prefix + cli_url]
    assert seed.main(args) == 0
    assert calls == [(SEED_FILE, prefix + expected)]


@pytest.mark.parametrize("allow, database", [("0", "relay_test"), ("1", "other_project")])
def test_reset_rejected_before_connecting(monkeypatch, allow, database):
    monkeypatch.setenv("RELAY_ALLOW_RESET", allow)

    def unexpected_connection(*args, **kwargs):
        pytest.fail("reset guard must run before opening a database connection")

    monkeypatch.setattr(seed, "create_engine", unexpected_connection)
    url = "postgresql+psycopg://relay_admin@127.0.0.1:5433/" + database
    assert seed.main(["--seed-file", str(SEED_FILE), "--database-url", url, "--reset"]) == 2
