from types import SimpleNamespace

import yaml

from toxtempass.export import get_create_meta_data_yaml


def test_metadata_author_includes_affiliation_footnote(tmp_path):
    request = SimpleNamespace(
        user=SimpleNamespace(
            first_name="Ada",
            last_name="Lovelace",
            organization="Analytical Engine Institute",
            email="ada@example.com",
        )
    )
    assay = SimpleNamespace(title="Demo assay")

    yaml_path = get_create_meta_data_yaml(
        request=request,
        assay=assay,
        file_path=tmp_path / "demo.pdf",
        export_type="pdf",
    )

    metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert metadata["author"] == ["Ada Lovelace^[Analytical Engine Institute]"]


def test_metadata_author_uses_plain_name_without_affiliation(tmp_path):
    request = SimpleNamespace(
        user=SimpleNamespace(
            first_name="Ada",
            last_name="Lovelace",
            organization="",
            email="ada@example.com",
        )
    )
    assay = SimpleNamespace(title="Demo assay")

    yaml_path = get_create_meta_data_yaml(
        request=request,
        assay=assay,
        file_path=tmp_path / "demo.pdf",
        export_type="pdf",
    )

    metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert metadata["author"] == ["Ada Lovelace"]


def test_metadata_author_escapes_affiliation_for_footnote_markup(tmp_path):
    request = SimpleNamespace(
        user=SimpleNamespace(
            first_name="Ada",
            last_name="Lovelace",
            organization=r"Lab]^2",
            email="ada@example.com",
        )
    )
    assay = SimpleNamespace(title="Demo assay")

    yaml_path = get_create_meta_data_yaml(
        request=request,
        assay=assay,
        file_path=tmp_path / "demo.pdf",
        export_type="pdf",
    )

    metadata = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert metadata["author"] == [r"Ada Lovelace^[Lab\]\^2]"]
