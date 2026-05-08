import json
from unittest.mock import Mock, patch

import pytest
from django.test import RequestFactory

from toxtempass.forms import SignupForm
from toxtempass.views import ror_organization_lookup


def test_signup_form_marks_organization_as_required():
    form = SignupForm()
    assert form.fields["organization"].required is True


@pytest.mark.django_db
def test_signup_form_rejects_missing_organization():
    form = SignupForm(
        data={
            "email": "newuser@example.com",
            "first_name": "New",
            "last_name": "User",
            "organization": "   ",
            "password1": "VeryStrongPass123!",
            "password2": "VeryStrongPass123!",
            "has_accepted_tos": True,
        }
    )

    assert form.is_valid() is False
    assert "organization" in form.errors


def test_ror_lookup_ignores_short_query():
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "ab"})

    with patch("toxtempass.views.requests.get") as mocked_get:
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload == {"items": []}
    mocked_get.assert_not_called()


def test_ror_lookup_rejects_invalid_query_chars():
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "abc<script>"})

    with patch("toxtempass.views.requests.get") as mocked_get:
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload == {"items": []}
    mocked_get.assert_not_called()


def test_ror_lookup_returns_suggestions():
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "Leiden"})
    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = {
        "items": [
            {
                "name": "Leiden University",
                "country": {"country_name": "Netherlands"},
                "id": "https://ror.org/027bh9e22",
            }
        ]
    }

    with patch("toxtempass.views.requests.get", return_value=mocked_response):
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload["items"] == [
        {
            "name": "Leiden University",
            "label": "Leiden University (Netherlands)",
            "id": "https://ror.org/027bh9e22",
        }
    ]


def test_ror_lookup_returns_suggestions_for_nested_ror_payload():
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "Leiden"})
    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = {
        "items": [
            {
                "organization": {
                    "name": "Leiden University",
                    "country": {"country_name": "Netherlands"},
                    "id": "https://ror.org/027bh9e22",
                }
            }
        ]
    }

    with patch("toxtempass.views.requests.get", return_value=mocked_response):
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload["items"] == [
        {
            "name": "Leiden University",
            "label": "Leiden University (Netherlands)",
            "id": "https://ror.org/027bh9e22",
        }
    ]
