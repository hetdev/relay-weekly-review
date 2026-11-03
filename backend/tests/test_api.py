"""API contract tests over hand-calculated synthetic data: nullability,
classification reasons, ranking, isolation, error envelope, request ids."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from tests.conftest import (
    TARGET_MONDAY,
    TEST_ADMIN_URL,
    insert_account,
    make_test_settings,
)
from app.db.engine import create_db_engine
from app.main import create_app

WEEK = {"week_start": TARGET_MONDAY.isoformat()}


def get_review(client: TestClient, account_id: int, **params):
    response = client.get(f"/api/v1/accounts/{account_id}/weekly-review", params=params)
    assert response.status_code == 200, response.text
    return response.json()


class TestAccountsEndpoint:
    def test_lists_only_permitted_accounts(self, client):
        accounts = client.get("/api/v1/accounts").json()
        assert [a["id"] for a in accounts] == [9001, 9002, 9003, 9004]

    def test_permitted_account_hidden_from_unrestricted_listing(self, admin_engine):
        insert_account(admin_engine, 9101, "Allowed One", "UTC")
        insert_account(admin_engine, 9102, "Forbidden Two", "UTC")
        engine = create_db_engine(make_test_settings().database_url)
        app = create_app(
            settings=make_test_settings(allowed=frozenset({9101})), engine=engine
        )
        with TestClient(app) as restricted:
            accounts = restricted.get("/api/v1/accounts").json()
            assert [a["id"] for a in accounts] == [9101]
            missing = restricted.get(
                "/api/v1/accounts/9102/weekly-review", params=WEEK
            )
            assert missing.status_code == 404
            assert missing.json()["error"]["code"] == "account_not_found"
        engine.dispose()


class TestHappyPathContract:
    def test_response_shape_and_metadata(self, client):
        data = get_review(client, 9001, **WEEK)
        assert data["scope"] == {
            "account_id": 9001,
            "account_name": "Isolation Alpha",
            "metric": "call_received",
            "location": None,
            "week_start": "2026-07-20",
        }
        assert data["time"]["timezone"] == "America/Chicago"
        assert data["time"]["week_start_local"] == "2026-07-20T00:00:00-05:00"
        assert data["time"]["week_end_local"] == "2026-07-27T00:00:00-05:00"
        assert data["time"]["week_start_utc"] == "2026-07-20T05:00:00Z"
        assert data["time"]["week_end_utc"] == "2026-07-27T05:00:00Z"
        assert data["baseline"] == {
            "week_count": 8,
            "weeks_covered": 8,
            "start_utc": "2026-05-25T05:00:00Z",
        }
        assert data["policy"]["version"] == "v1"
        assert data["policy"]["baseline_weeks"] == 8
        assert data["policy"]["min_absolute_change"] == 5
        assert data["policy"]["min_relative_change"] == 0.2
        assert data["coverage"]["demo_now_utc"].startswith("2026-07-28T12:00:00")
        assert data["coverage"]["coverage_start_utc"] == "2026-02-01T00:00:00Z"
        assert data["coverage"]["coverage_end_utc"] == "2026-07-28T00:00:00Z"
        assert isinstance(data["coverage"]["last_observed_event_utc"], str)
        assert data["request_id"]

    def test_weeks_are_nine_with_dates_and_coverage_flags(self, client):
        data = get_review(client, 9001, **WEEK)
        weeks = data["summary"]["weeks"]
        assert [w["week_start"] for w in weeks] == [
            "2026-05-25", "2026-06-01", "2026-06-08", "2026-06-15",
            "2026-06-22", "2026-06-29", "2026-07-06", "2026-07-13", "2026-07-20",
        ]
        assert all(w["covered"] for w in weeks)
        assert len(weeks) == 9  # 8 baseline + target


class TestClassificationReasons:
    def test_below_recent_range(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site A")
        assert view["count"] == 4
        assert view["reference"] == 10.0
        assert view["delta"] == -6.0
        assert view["percent_change"] == pytest.approx(-60.0)
        assert view["observed_min"] == 10 and view["observed_max"] == 10
        assert view["reason"] == "below_recent_range"

    def test_above_recent_range(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site B")
        assert view["reason"] == "above_recent_range"
        assert view["percent_change"] == pytest.approx(100.0)

    def test_insufficient_history_for_late_location(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site C")
        assert view["reason"] == "insufficient_history"
        assert view["reference"] is None and view["percent_change"] is None
        assert view["count"] == 30  # counts remain visible
        assert all(w["covered"] for w in view["weeks"])

    def test_low_volume(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site D")
        assert view["reason"] == "low_volume"
        assert view["reference"] == 2.0
        assert view["percent_change"] == pytest.approx(400.0)  # arithmetic shown, not labeled

    def test_activity_after_zero_baseline_has_null_percent(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site E")
        assert view["reason"] == "activity_after_zero_baseline"
        assert view["percent_change"] is None
        assert view["reference"] == 0.0 and view["delta"] == 7.0

    def test_no_recent_activity(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site F")
        assert view["reason"] == "no_recent_activity"
        assert view["percent_change"] is None

    def test_zero_filled_weeks_present(self, client):
        view = next(l["view"] for l in get_review(client, 9001, **WEEK)["locations"] if l["location"] == "Site E")
        assert [w["count"] for w in view["weeks"]] == [0, 0, 0, 0, 0, 0, 0, 0, 7]


class TestAccountRollup:
    def test_totals_sum_locations_and_population_change_suppresses(self, client):
        data = get_review(client, 9001, **WEEK)
        # Target week: 4 + 20 + 30 + 10 + 7 + 0 = 71 (hand-summed)
        assert data["account_summary"]["count"] == 71
        # Baseline weeks 1-3: 10+10+0+2 = 22; weeks 4-8: 10+10+5+2 = 27
        counts = [w["count"] for w in data["account_summary"]["weeks"]]
        assert counts == [22, 22, 22, 27, 27, 27, 27, 27, 71]
        # Site C first appeared Jun 16 (inside the baseline window)
        assert data["coverage"]["warnings"] == ["population_change"]
        assert data["account_summary"]["classification_suppressed"] is True
        assert data["account_summary"]["reason"] is None  # suppressed, totals visible
        # Unfiltered headline equals the (suppressed) account summary
        assert data["summary"] == data["account_summary"]

    def test_rollup_not_suppressed_when_population_stable(self, client):
        data = get_review(client, 9002, **WEEK)
        assert data["coverage"]["warnings"] == []
        assert data["account_summary"]["reason"] == "no_review_flag"
        assert data["account_summary"]["count"] == 100


class TestRanking:
    def test_flagged_decreases_then_increases_then_others_deterministic(self, client):
        locations = [l["location"] for l in get_review(client, 9001, **WEEK)["locations"]]
        assert locations == ["Site A", "Site B", "Site C", "Site D", "Site E", "Site F"]


class TestLocationFilter:
    def test_filtered_scope_headline_and_single_row(self, client):
        data = get_review(client, 9001, location="Site A", **WEEK)
        assert data["scope"]["location"] == "Site A"
        assert [l["location"] for l in data["locations"]] == ["Site A"]
        assert data["summary"]["reason"] == "below_recent_range"
        assert data["summary"]["count"] == 4
        # Full-account rollup stays unfiltered
        assert data["account_summary"]["count"] == 71

    def test_filtered_location_before_its_first_event_is_insufficient(self, client):
        # Site C's first event is Jun 16; ask about the week of Mar 9
        data = get_review(client, 9001, week_start="2026-03-09", location="Site C")
        view = data["summary"]
        assert view["reason"] == "insufficient_history"
        assert view["count"] == 0


class TestEarlyAndEmptyWeeks:
    def test_early_week_shows_insufficient_baseline(self, client):
        data = get_review(client, 9003, week_start="2026-02-16")
        assert data["baseline"]["weeks_covered"] == 2  # Feb 2 + Feb 9 only
        assert data["summary"]["reason"] == "insufficient_history"
        # Weeks outside coverage are flagged, not manufactured
        flags = [w["covered"] for w in data["summary"]["weeks"]]
        assert flags == [False] * 6 + [True] * 3

    def test_empty_account_reports_no_activity(self, client):
        data = get_review(client, 9004, **WEEK)
        assert data["summary"]["reason"] == "no_activity_recorded"
        assert data["summary"]["count"] == 0
        assert data["summary"]["reference"] is None
        assert data["locations"] == []
        options = client.get("/api/v1/accounts/9004/review-options").json()
        assert options["locations"] == []


class TestMetricEnum:
    def test_lead_created_uses_same_path_other_values(self, client):
        data = get_review(client, 9001, metric="lead_created", **WEEK)
        # Site C opened late regardless of metric, so the account-level
        # classification stays suppressed under the population-change warning.
        assert data["coverage"]["warnings"] == ["population_change"]
        assert data["summary"]["reason"] is None
        assert data["summary"]["classification_suppressed"] is True
        # Locations E and F have full history (April leads, outside the
        # baseline window) with an all-zero lead baseline -> no_recent_activity
        by_location = {row["location"]: row["view"] for row in data["locations"]}
        assert by_location["Site E"]["reason"] == "no_recent_activity"
        assert by_location["Site F"]["reason"] == "no_recent_activity"

    def test_invalid_metric_rejected_with_envelope(self, client):
        response = client.get("/api/v1/accounts/9001/weekly-review", params={**WEEK, "metric": "churn"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_input"


class TestErrorContract:
    def test_unknown_account_is_404_envelope(self, client):
        response = client.get("/api/v1/accounts/424242/weekly-review", params=WEEK)
        assert response.status_code == 404
        body = response.json()["error"]
        assert body["code"] == "account_not_found"
        assert body["request_id"]

    def test_non_monday_rejected(self, client):
        response = client.get("/api/v1/accounts/9001/weekly-review", params={"week_start": "2026-07-21"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_week"

    def test_malformed_date_rejected(self, client):
        for bad in ("2026-7-20", "not-a-date", "2026-07-20T00:00:00Z"):
            response = client.get("/api/v1/accounts/9001/weekly-review", params={"week_start": bad})
            assert response.status_code == 422, bad

    def test_incomplete_future_week_rejected(self, client):
        response = client.get("/api/v1/accounts/9001/weekly-review", params={"week_start": "2026-07-27"})
        assert response.status_code == 422
        assert "not complete" in response.json()["error"]["message"]

    def test_week_before_coverage_rejected(self, client):
        response = client.get("/api/v1/accounts/9001/weekly-review", params={"week_start": "2026-01-19"})
        assert response.status_code == 422

    def test_unknown_location_rejected(self, client):
        response = client.get(
            "/api/v1/accounts/9001/weekly-review", params={**WEEK, "location": "Nowhere"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "unknown_location"

    def test_sql_like_location_is_safe_and_unknown(self, client):
        response = client.get(
            "/api/v1/accounts/9001/weekly-review",
            params={**WEEK, "location": "'; DROP TABLE accounts; --"},
        )
        assert response.status_code == 422

    def test_request_id_header_present(self, client):
        response = client.get("/api/v1/accounts", )
        assert response.headers["X-Request-ID"]

    def test_internal_error_returns_safe_envelope(self, admin_engine):
        engine = create_db_engine(make_test_settings().database_url)
        app = create_app(settings=make_test_settings(), engine=engine)

        def broken_account(account_id: int):
            raise RuntimeError("secret stack detail")

        from app.api.deps import get_service

        app.dependency_overrides[get_service] = broken_account
        with TestClient(app, raise_server_exceptions=False) as test_client:
            response = test_client.get("/api/v1/accounts/9001/weekly-review", params=WEEK)
            assert response.status_code == 500
            body = response.json()["error"]
            assert body["code"] == "internal_error"
            assert "secret" not in body["message"]
            assert body["request_id"]
        engine.dispose()


class TestHealth:
    def test_liveness_never_touches_storage(self, client):
        assert client.get("/healthz").json() == {"status": "ok"}

    def test_readiness_reports_storage_outage(self, admin_engine):
        engine = create_db_engine("postgresql+psycopg://relay_app@127.0.0.1:59999/relay_test")
        app = create_app(settings=make_test_settings(), engine=engine)
        with TestClient(app) as test_client:
            response = test_client.get("/readyz")
            assert response.status_code == 503
        engine.dispose()

    def test_readiness_ok_with_storage(self, client):
        assert client.get("/readyz").status_code == 200


class TestAccountIsolation:
    def test_sibling_account_data_never_leaks(self, client):
        """Same location name in two accounts; every number must reconcile to
        the requested account only (hand-calculated)."""
        alpha = get_review(client, 9001, **WEEK)
        beta = get_review(client, 9002, **WEEK)
        # Alpha's Site A: 4 events, reference 10 — not 100+4 or 100
        alpha_site_a = next(l for l in alpha["locations"] if l["location"] == "Site A")
        assert alpha_site_a["view"]["count"] == 4
        assert alpha_site_a["view"]["reference"] == 10.0
        assert alpha["account_summary"]["count"] == 71
        # Beta's Site A: 100, reference 100, and no other locations visible
        assert [l["location"] for l in beta["locations"]] == ["Site A"]
        assert beta["account_summary"]["count"] == 100
        assert beta["account_summary"]["reference"] == 100.0
        # Options never cross accounts either
        beta_options = client.get("/api/v1/accounts/9002/review-options").json()
        assert beta_options["locations"] == ["Site A"]
