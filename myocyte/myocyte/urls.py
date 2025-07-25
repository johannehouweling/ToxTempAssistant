"""
URL configuration for myocyte project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from myocyte import settings
from toxtempass import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "init/<slug:label>", views.init_db, name="init_db"
    ),  # initializes database, meaning it creates the questions, subsections and sections.
]

urlpatterns += [
    path("add/", views.new_form_view, name="add_new"),
    # Login stuff
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("login/orcid/", views.orcid_login, name="orcid_login"),
    path("login/signup/", views.signup, name="signup"),
    path("orcid/callback/", views.orcid_callback, name="orcid_callback"),
    path("orcid/signup/", views.orcid_signup, name="orcid_signup"),
    # Investigation URLs
    path(
        "investigation/create/",
        views.create_or_update_investigation,
        name="create_investigation",
    ),
    path(
        "investigation/update/<int:pk>/",  # hard-coded in start.html
        views.create_or_update_investigation,
        name="update_investigation",
    ),
    path(
        "investigation/delete/<int:pk>/",  # hard-coded in start.html
        views.delete_investigation,
        name="delete_investigation",
    ),
    # Study URLs
    path("study/create/", views.create_or_update_study, name="create_study"),
    path(
        "study/update/<int:pk>/", views.create_or_update_study, name="update_study"
    ),  # hard-coded in start.html
    path(
        "study/delete/<int:pk>/", views.delete_study, name="delete_study"
    ),  # hard-coded in start.html
    # Assay URLs
    path("", views.AssayListView.as_view(), name="start"),
    path("assay/create/", views.create_or_update_assay, name="create_assay"),
    path(
        "assay/gpt-allowed/<int:pk>",
        views.initial_gpt_allowed_for_assay,
        name="assay_gpt_allowed",
    ),
    path(
        "assay/update/<int:pk>/", views.create_or_update_assay, name="update_assay"
    ),  # hard-coded in start.html
    path(
        "assay/delete/<int:pk>/", views.delete_assay, name="delete_assay"
    ),  # hard-coded in start.html
    path(
        "assay/<int:assay_id>/answer/",
        views.answer_assay_questions,
        name="answer_assay_questions",
    ),
]
# Version History

urlpatterns += [
    path(
        "assay/<int:assay_id>/answer/question/<int:question_id>/version-history/",
        views.get_version_history,
        name="get_version_history",
    ),
]
# Exports

urlpatterns += [
    path(
        "assay/<int:assay_id>/answer/hasfeedback/",
        views.assay_hasfeedback,
        name="assay_hasfeedback",
    ),
    path(
        "assay/<int:assay_id>/answer/feedback/",
        views.assay_feedback,
        name="assay_feedback",
    ),
    path(
        "assay/<int:assay_id>/answer/export/<str:export_type>/",
        views.export_assay,
        name="export_assay",
    ),
]

# Filter Investigation and Study for the first menu on start.html (so we only show hierachical options and not all)

urlpatterns += [
    # Other paths
    path(
        "filter-studies-by-investigation/<int:investigation_id>/",
        views.get_filtered_studies,
        name="filter_studie_by_investigation",
    ),
    path(
        "filter-assays-by-study/<int:study_id>/",
        views.get_filtered_assays,
        name="filter_assays_by_study",
    ),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
