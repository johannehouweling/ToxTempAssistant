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
from toxtempass import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("upload/", views.upload, name="upload"),
    path("init/", views.init_db),
]

urlpatterns += [
    path("start/", views.start_form_view, name="start"),
    # Investigation URLs
    path(
        "investigation/create/",
        views.create_or_update_investigation,
        name="create_investigation",
    ),
    path(
        "investigation/update/<int:pk>/",# hard-coded in start.html
        views.create_or_update_investigation,
        name="update_investigation",
    ),
    path(
        "investigation/delete/<int:pk>/",# hard-coded in start.html
        views.delete_investigation,
        name="delete_investigation",
    ),
    # Study URLs
    path("study/create/", views.create_or_update_study, name="create_study"),
    path("study/update/<int:pk>/", views.create_or_update_study, name="update_study"), # hard-coded in start.html
    path("study/delete/<int:pk>/", views.delete_study, name="delete_study"),# hard-coded in start.html
    # Assay URLs
    path("assay/create/", views.create_or_update_assay, name="create_assay"),
    path("assay/update/<int:pk>/", views.create_or_update_assay, name="update_assay"),# hard-coded in start.html
    path("assay/delete/<int:pk>/", views.delete_assay, name="delete_assay"),# hard-coded in start.html
    path(
        "assay/<int:assay_id>/answer/",
        views.answer_assay_questions,
        name="answer_assay_questions",
    ),
]
