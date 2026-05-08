"""Tests for the assay_time_sync endpoint and AssayTimeLog model."""

import pytest
from django.test import Client
from django.urls import reverse

from toxtempass.models import AssayTimeLog
from toxtempass.tests.fixtures.factories import (
    AssayFactory,
    InvestigationFactory,
    PersonFactory,
    StudyFactory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    return PersonFactory.create()


@pytest.fixture
def other_user(db):
    return PersonFactory.create()


@pytest.fixture
def assay(db, user):
    """An assay whose investigation is owned by *user* so access checks pass."""
    investigation = InvestigationFactory.create(owner=user)
    study = StudyFactory.create(investigation=investigation)
    return AssayFactory.create(study=study)


@pytest.fixture
def sync_url(assay):
    return reverse("assay_time_sync", kwargs={"assay_id": assay.id})


# ---------------------------------------------------------------------------
# assay_time_sync view
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssayTimeSyncView:
    def test_unauthenticated_redirects(self, client, sync_url):
        resp = client.post(sync_url, {"seconds": "100"})
        assert resp.status_code == 302

    def test_get_not_allowed(self, client, user, sync_url):
        client.force_login(user)
        resp = client.get(sync_url)
        assert resp.status_code == 405

    def test_creates_time_log_row(self, client, user, assay, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "120"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        row = AssayTimeLog.objects.get(user=user, assay=assay)
        assert row.seconds == 120

    def test_updates_existing_row(self, client, user, assay, sync_url):
        AssayTimeLog.objects.create(user=user, assay=assay, seconds=60)
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "180"})
        assert resp.status_code == 200
        assert AssayTimeLog.objects.filter(user=user, assay=assay).count() == 1
        assert AssayTimeLog.objects.get(user=user, assay=assay).seconds == 180

    def test_total_seconds_aggregates_across_users(self, client, user, other_user, assay, sync_url):
        """total_seconds in the response is the sum across all collaborators."""
        # Grant other_user access via the investigation
        assay.study.investigation.share(other_user)

        client.force_login(user)
        client.post(sync_url, {"seconds": "100"})

        client2 = Client()
        client2.force_login(other_user)
        resp = client2.post(sync_url, {"seconds": "200"})

        data = resp.json()
        assert data["success"] is True
        assert data["total_seconds"] == 300

    def test_invalid_seconds_non_integer(self, client, user, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "abc"})
        assert resp.status_code == 400
        assert resp.json()["success"] is False

    def test_invalid_seconds_negative(self, client, user, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "-5"})
        assert resp.status_code == 400

    def test_zero_seconds_accepted(self, client, user, assay, sync_url):
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "0"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total_seconds"] == 0

    def test_total_seconds_is_zero_with_no_logs(self, client, user, assay, sync_url):
        """First call with 0 seconds returns total_seconds 0."""
        client.force_login(user)
        resp = client.post(sync_url, {"seconds": "0"})
        assert resp.json()["total_seconds"] == 0

    def test_inaccessible_assay_returns_403(self, client, db):
        """A user with no access to the assay gets a 403."""
        outsider = PersonFactory.create()
        assay = AssayFactory.create()
        # The assay owner is the investigation owner; outsider has no access
        url = reverse("assay_time_sync", kwargs={"assay_id": assay.id})
        client.force_login(outsider)
        resp = client.post(url, {"seconds": "60"})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# AssayTimeLog model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssayTimeLogModel:
    def test_unique_together_constraint(self, user, assay):
        AssayTimeLog.objects.create(user=user, assay=assay, seconds=10)
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            AssayTimeLog.objects.create(user=user, assay=assay, seconds=20)

    def test_str_representation(self, user, assay):
        log = AssayTimeLog(user=user, assay=assay, seconds=42)
        assert str(log.user.email) in str(log)
        assert "42" in str(log)
