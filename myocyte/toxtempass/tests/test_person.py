import pytest

from toxtempass.tests.fixtures.factories import PersonFactory


@pytest.mark.django_db
def test_create_person():
    """Test creating a Person instance using the factory."""
    person = PersonFactory()
    assert person.pk is not None
    assert person.first_name is not None
    assert person.email is not None
