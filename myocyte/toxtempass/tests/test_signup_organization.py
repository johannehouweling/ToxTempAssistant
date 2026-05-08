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


def test_ror_lookup_returns_suggestions_for_v2_payload():
    """ROR v2 schema: names[] tagged with types, locations[].geonames_details."""
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "Leiden"})
    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = {
        "items": [
            {
                "id": "https://ror.org/027bh9e22",
                "names": [
                    {"types": ["acronym"], "value": "LU"},
                    {
                        "types": ["ror_display", "label"],
                        "value": "Leiden University",
                    },
                ],
                "locations": [
                    {"geonames_details": {"country_name": "Netherlands"}}
                ],
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


def test_ror_lookup_uses_advanced_query_param():
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "Leiden"})
    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = {"items": []}

    with patch(
        "toxtempass.views.requests.get", return_value=mocked_response
    ) as mocked_get:
        ror_organization_lookup(request)

    mocked_get.assert_called_once()
    assert mocked_get.call_args.kwargs["params"] == {
        "query.advanced": 'names.value:"Leiden"'
    }


def test_ror_lookup_tries_domain_queries_first_when_email_given():
    request = RequestFactory().get(
        "/login/signup/ror-organizations/",
        {"q": "Leiden", "email": "person@rivm.nl"},
    )
    strict_response = Mock()
    strict_response.raise_for_status.return_value = None
    strict_response.json.return_value = {"items": []}

    domain_response = Mock()
    domain_response.raise_for_status.return_value = None
    domain_response.json.return_value = {
        "items": [
            {
                "name": "RIVM",
                "country": {"country_name": "Netherlands"},
                "id": "https://ror.org/012345678",
            }
        ]
    }

    with patch(
        "toxtempass.views.requests.get", side_effect=[strict_response, domain_response]
    ) as mocked_get:
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload["items"][0]["name"] == "RIVM"
    assert mocked_get.call_count == 2
    assert mocked_get.call_args_list[0].kwargs["params"] == {
        "query.advanced": 'links.value:"rivm.nl" AND names.value:"Leiden"'
    }
    assert mocked_get.call_args_list[1].kwargs["params"] == {
        "query.advanced": 'links.value:"rivm.nl"'
    }


def test_ror_lookup_falls_back_to_wide_query_when_domain_queries_are_empty():
    request = RequestFactory().get(
        "/login/signup/ror-organizations/",
        {"q": "Leiden", "email": "person@rivm.nl"},
    )
    empty_response_one = Mock()
    empty_response_one.raise_for_status.return_value = None
    empty_response_one.json.return_value = {"items": []}
    empty_response_two = Mock()
    empty_response_two.raise_for_status.return_value = None
    empty_response_two.json.return_value = {"items": []}
    wide_response = Mock()
    wide_response.raise_for_status.return_value = None
    wide_response.json.return_value = {
        "items": [
            {
                "name": "Leiden University",
                "country": {"country_name": "Netherlands"},
                "id": "https://ror.org/027bh9e22",
            }
        ]
    }

    with patch(
        "toxtempass.views.requests.get",
        side_effect=[empty_response_one, empty_response_two, wide_response],
    ) as mocked_get:
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload["items"][0]["name"] == "Leiden University"
    assert mocked_get.call_count == 3
    assert mocked_get.call_args_list[2].kwargs["params"] == {
        "query.advanced": 'names.value:"Leiden"'
    }


def test_ror_lookup_ignores_invalid_email_domain():
    request = RequestFactory().get(
        "/login/signup/ror-organizations/",
        {"q": "Leiden", "email": "person@localhost"},
    )
    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = {"items": []}

    with patch("toxtempass.views.requests.get", return_value=mocked_response) as mocked_get:
        ror_organization_lookup(request)

    mocked_get.assert_called_once()
    assert mocked_get.call_args.kwargs["params"] == {
        "query.advanced": 'names.value:"Leiden"'
    }


def test_ror_lookup_strips_www_from_email_domain_query():
    request = RequestFactory().get(
        "/login/signup/ror-organizations/",
        {"q": "Leiden", "email": "person@www.rivm.nl"},
    )
    first_response = Mock()
    first_response.raise_for_status.return_value = None
    first_response.json.return_value = {"items": []}
    second_response = Mock()
    second_response.raise_for_status.return_value = None
    second_response.json.return_value = {"items": []}
    third_response = Mock()
    third_response.raise_for_status.return_value = None
    third_response.json.return_value = {"items": []}

    with patch(
        "toxtempass.views.requests.get",
        side_effect=[first_response, second_response, third_response],
    ) as mocked_get:
        ror_organization_lookup(request)

    assert mocked_get.call_args_list[0].kwargs["params"] == {
        "query.advanced": 'links.value:"rivm.nl" AND names.value:"Leiden"'
    }
    assert mocked_get.call_args_list[1].kwargs["params"] == {
        "query.advanced": 'links.value:"rivm.nl"'
    }


def test_ror_lookup_deduplicates_same_name_without_id():
    request = RequestFactory().get("/login/signup/ror-organizations/", {"q": "Leiden"})
    mocked_response = Mock()
    mocked_response.raise_for_status.return_value = None
    mocked_response.json.return_value = {
        "items": [
            {"name": "Leiden University", "country": {"country_name": "Netherlands"}},
            {"name": "Leiden University", "country": {"country_name": "Netherlands"}},
        ]
    }

    with patch("toxtempass.views.requests.get", return_value=mocked_response):
        response = ror_organization_lookup(request)

    payload = json.loads(response.content.decode("utf-8"))
    assert payload["items"] == [
        {
            "name": "Leiden University",
            "label": "Leiden University (Netherlands)",
            "id": None,
        }
    ]
