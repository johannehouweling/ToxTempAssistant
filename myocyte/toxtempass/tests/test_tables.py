import pytest
from django.test import RequestFactory

from toxtempass.tables import AssayTable
from toxtempass.tests.fixtures.factories import (
    AssayFactory,
    PersonFactory,
    WorkspaceFactory,
    WorkspaceInvestigationFactory,
)


@pytest.mark.django_db
class TestAssayTableInvestigationColumn:
    def test_shared_investigation_icon_renders_inline_without_absolute_positioning(self):
        user = PersonFactory.create()
        investigation_owner = PersonFactory.create()
        assay = AssayFactory.create(study__investigation__owner=investigation_owner)

        visible_workspace = WorkspaceFactory.create(owner=user, name="Visible workspace")
        hidden_workspace = WorkspaceFactory.create(
            owner=PersonFactory.create(),
            name="Hidden workspace",
        )
        WorkspaceInvestigationFactory.create(
            workspace=visible_workspace,
            investigation=assay.study.investigation,
            added_by=visible_workspace.owner,
        )
        WorkspaceInvestigationFactory.create(
            workspace=hidden_workspace,
            investigation=assay.study.investigation,
            added_by=hidden_workspace.owner,
        )

        request = RequestFactory().get("/")
        request.user = user
        table = AssayTable([assay])
        table.context = {"request": request}

        rendered = str(table.render_investigation(assay))

        assert "bi-share" in rendered
        assert rendered.startswith(
            '<span class="d-inline-flex align-items-center flex-wrap gap-1">'
        )
        assert "d-inline-flex align-items-center flex-wrap gap-1" in rendered
        assert '<button type="button"' in rendered
        assert 'data-bs-toggle="offcanvas"' in rendered
        assert 'data-bs-target="#offcanvasUser"' in rendered
        assert 'aria-label="View workspaces sharing this investigation"' in rendered
        assert 'href="#offcanvasUser"' not in rendered
        assert '<span type="button"' not in rendered
        assert "position-absolute" not in rendered
        assert "start-100" not in rendered
        assert "translate-middle-y" not in rendered
        assert "Visible workspace" in rendered
        assert "Hidden workspace" not in rendered

    def test_non_shared_investigation_renders_title_only(self):
        assay = AssayFactory.create(study__investigation__title="Simple Investigation")
        request = RequestFactory().get("/")
        request.user = PersonFactory.create()
        table = AssayTable([assay])
        table.context = {"request": request}

        rendered = str(table.render_investigation(assay))

        assert rendered == "Simple Investigation"
