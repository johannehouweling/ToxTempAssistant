# import pytest
# from django.urls import reverse
# from toxtempass.models import Investigation
# from toxtempass.tests.fixtures.factories import PersonFactory, InvestigationFactory


# @pytest.fixture
# def owner(db):
#     return PersonFactory.create()


# @pytest.fixture
# def other(db):
#     return PersonFactory.create()


# @pytest.fixture
# def investigation(db, owner):
#     return InvestigationFactory.create(owner=owner)


# @pytest.mark.django_db
# class TestInvestigationPermission:
#     def test_owner_can_access_update(self, client, owner, investigation):
#         client.force_login(owner)
#         url = reverse("update_investigation", kwargs={"pk": investigation.pk})
#         response = client.get(url)
#         assert response.status_code == 200
#         # ensure page contains the investigation title
#         assert investigation.title in response.content.decode()

#     def test_non_owner_cannot_access_update(self, client, other, investigation):
#         client.force_login(other)
#         url = reverse("update_investigation", kwargs={"pk": investigation.pk})
#         response = client.get(url)
#         assert response.status_code == 404

#     def test_anonymous_redirected_on_update(self, client, investigation):
#         url = reverse("update_investigation", kwargs={"pk": investigation.pk})
#         response = client.get(url)
#         login_url = reverse("login")
#         assert response.status_code == 302
#         assert response.url == f"{login_url}?next={url}"

#     def test_owner_can_delete(self, client, owner, investigation):
#         client.force_login(owner)
#         url = reverse("delete_investigation", kwargs={"pk": investigation.pk})
#         # follow the redirect after successful delete
#         response = client.post(url, follow=True)
#         # should eventually land on your start view
#         assert response.redirect_chain[-1][0] == reverse("overview")
#         # and the object should be gone
#         assert not Investigation.objects.filter(pk=investigation.pk).exists()

#     def test_non_owner_cannot_delete(self, client, other, investigation):
#         client.force_login(other)
#         url = reverse("delete_investigation", kwargs={"pk": investigation.pk})
#         response = client.post(url)
#         assert response.status_code == 404

#     def test_anonymous_redirected_on_delete(self, client, investigation):
#         url = reverse("delete_investigation", kwargs={"pk": investigation.pk})
#         response = client.post(url)
#         login_url = reverse("login")
#         assert response.status_code == 302
#         assert response.url == f"{login_url}?next={url}"
