import pytest

from toxtempass.tests.fixtures.factories import (
    InvestigationFactory,
    StudyFactory,
    AssayFactory,
)


@pytest.mark.django_db
def test_create_investigation_study_assay():
    """Ensure an Investigation, Study and Assay can be created and linked."""
    # Create an Investigation (with owner)
    investigation = InvestigationFactory()
    assert investigation.pk is not None
    assert investigation.owner is not None

    # Create a Study that belongs to the Investigation
    study = StudyFactory(investigation=investigation)
    assert study.pk is not None
    assert study.investigation == investigation
    # Reverse relation
    assert investigation.studies.filter(pk=study.pk).exists()

    # Create an Assay that belongs to the Study
    assay = AssayFactory(study=study)
    assert assay.pk is not None
    assert assay.study == study
    # Reverse relation
    assert study.assays.filter(pk=assay.pk).exists()
