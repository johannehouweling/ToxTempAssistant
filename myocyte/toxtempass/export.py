import io
import json
import logging
import re
import subprocess
import uuid
import zipfile
from pathlib import Path

import yaml
from django.core.serializers import serialize
from django.http import FileResponse, HttpRequest, JsonResponse
from django.utils import timezone  # Import timezone utilities
from django.utils.text import slugify

from myocyte import settings
from toxtempass import Config
from toxtempass.models import Assay, Section
from toxtempass.utilities import add_status_context

logger = logging.getLogger(__name__)

# Export control surface lives on Config (see toxtempass/__init__.py). These
# module-level aliases keep call sites terse and let tests patch them.
EXPORT_MIME_SUFFIX = Config.EXPORT_MIME_SUFFIX
EXPORT_MAPPING = Config.EXPORT_MAPPING
PANDOC_EXPORT_TYPES = Config.PANDOC_EXPORT_TYPES

# simple regexes to catch display‐math delimiters

MATH_BLOCK_START = re.compile(r"^\s*(\$\$|\\\[)")
MATH_BLOCK_END = re.compile(r"(\$\$|\\\])\s*$")


def quote_answer(text: str) -> str:
    r"""Take a multi-line answer_text, and return a Markdown fragment.

    where only non-math lines are prefixed with '> '.
    Display math blocks ( $$…$$ or \[…\] ) are emitted raw.
    """
    out = []
    in_math = False

    for line in text.splitlines():
        # start of a display-math block?
        if not in_math and MATH_BLOCK_START.match(line):
            in_math = True
            out.append(line)
            continue

        # end of a display-math block?
        if in_math:
            out.append(line)
            if MATH_BLOCK_END.search(line):
                in_math = False
            continue

        # otherwise normal text → quote it
        out.append(f"> {line}" if line.strip() else ">")  # keep blank lines too

    return "\n".join(out) + "\n\n"


def generate_json_from_assay(assay: Assay) -> dict | None:
    """Generate Json from assay."""
    try:
        # Set the timezone to Amsterdam
        amsterdam_tz = timezone.get_fixed_timezone(
            1
        )  # UTC+1 for Amsterdam (standard time)
        current_time = timezone.now().astimezone(
            amsterdam_tz
        )  # Current time in Amsterdam timezone

        # Build author info from the assay owner; include ORCID when available.
        owner = assay.owner
        author_info: dict = {
            "name": owner.get_full_name() or owner.email,
            "email": owner.email,
        }
        if getattr(owner, "orcid_id", None):
            author_info["orcid"] = f"https://orcid.org/{owner.orcid_id}"

        # Prepare the data structure
        export_data = {
            "metadata": {
                # Persistent identifier for this assay (FAIR: Findable)
                "identifier": f"urn:uuid:{assay.uid}",
                # Current date and time in ISO format
                "creation_date": current_time.isoformat(),
                # Filename for the export
                "filename": f"toxtemp_{slugify(assay.title)}",
                # Replace with your actual website name
                "reference_toxtemp": getattr(Config, "reference_toxtemp", None),
                "website": "toxtempassistant.vhp4safety.nl",
                # Author information (FAIR: Reusable / attributable)
                "author": author_info,
                # Keywords for discovery (FAIR: Findable)
                "keywords": [
                    "metadata template",
                    "cell-based toxicological test methods",
                    "New Approach Methodologies",
                    "ToxTemp",
                ],
                # License for reuse (FAIR: Reusable)
                "license": getattr(Config, "license_url", None),
                # Trimmed config for reproducibility
                # (PII and developer-only fields omitted)
                "config": {
                    "model": getattr(Config, "model", None),
                    "model_info_url": getattr(Config, "model_info_url", None),
                    "reference_toxtempassistant": getattr(
                        Config, "reference_toxtempassistant", None
                    ),
                    "reference_toxtemp": getattr(Config, "reference_toxtemp", None),
                    "website": "toxtempassistant.vhp4safety.nl",
                    "version": getattr(Config, "version", None),
                    "github_repo_url": getattr(Config, "github_repo_url", None),
                    "git_hash": getattr(Config, "git_hash", None),
                    "license_url": getattr(Config, "license_url", None),
                },
            },
            "investigation": json.loads(serialize("json", [assay.study.investigation]))[
                0
            ],
            "study": json.loads(serialize("json", [assay.study]))[0],
            "assay": json.loads(serialize("json", [assay]))[0],
            "answers": json.loads(serialize("json", assay.answers.all())),
        }

        # Add questions and their corresponding answers
        questions_with_answers = []
        for answer in assay.answers.all():
            question_data = json.loads(serialize("json", [answer.question]))[0]
            questions_with_answers.append(
                {
                    "question": question_data,
                    "answer": answer.answer_text,
                    "source": answer.answer_documents,
                }
            )
        export_data["questions_with_answers"] = questions_with_answers

        # Add sections and subsections with questions and answers
        sections = []
        for section in Section.objects.all():
            section_data = {
                "section": json.loads(serialize("json", [section]))[0],
                "subsections": [],
            }
            for subsection in section.subsections.all():
                subsection_data = {
                    "subsection": json.loads(serialize("json", [subsection]))[0],
                    "questions_with_answers": [],
                }
                # Add questions and answers for this subsection
                for question in subsection.questions.all():
                    # Find the corresponding answer, if any
                    answer_text = ""
                    for answer in assay.answers.filter(question=question):
                        answer_text = answer.answer_text
                    subsection_data["questions_with_answers"].append(
                        {
                            "question": json.loads(serialize("json", [question]))[0],
                            "answer": answer_text,
                        }
                    )

                section_data["subsections"].append(subsection_data)
            sections.append(section_data)

        export_data["sections"] = sections
        return export_data

    except Assay.DoesNotExist:
        return None


def generate_markdown_from_assay(assay: Assay) -> str:
    """Generate markdown from assay."""
    export_data = generate_json_from_assay(assay)
    # Start with metadata
    markdown = []
    markdown.append("## Metadata\n")
    markdown.append(f"- **Creation Date:** {export_data['metadata']['creation_date']}\n")
    markdown.append(f"- **Filename:** {export_data['metadata']['filename']}\n")
    markdown.append(f"- **Website:** {export_data['metadata']['website']}\n")
    markdown.append("\n## ToxTempAssistant configuration\n")
    for key, value in export_data["metadata"]["config"].items():
        markdown.append(f"- {key}: {value}\n")
    markdown.append("\n")

    # Include investigation details
    investigation_title = export_data["investigation"]["fields"]["title"]
    investigation_description = export_data["investigation"]["fields"]["description"]
    markdown.append("# Investigation\n")
    markdown.append(f"- **Title:** {investigation_title}\n")
    markdown.append(f"- **Description:** {investigation_description}\n")
    markdown.append("\n")

    # Include study details
    study_title = export_data["study"]["fields"]["title"]
    study_description = export_data["study"]["fields"]["description"]
    markdown.append("# Study\n")
    markdown.append(f"- **Title:** {study_title}\n")
    markdown.append(f"- **Description:** {study_description}\n")
    markdown.append("\n")

    # Include assay details
    assay_title = export_data["assay"]["fields"]["title"]
    markdown.append("# Assay\n")
    markdown.append(f"- **Title:** {assay_title}\n")
    markdown.append("\n")

    # Directly use the sections from export_data
    sections = export_data.get("sections", [])

    # Add sections and subsections to Markdown
    for section in sections:
        # Add section title
        section_title = section["section"]["fields"][
            "title"
        ]  # Adjust based on your model's field names
        markdown.append(f"# {section_title}\n")  # Section title

        for subsection in section["subsections"]:
            # Add subsection title
            subsection_title = subsection["subsection"]["fields"][
                "title"
            ]  # Adjust based on your model's field names
            markdown.append(f"## {subsection_title}\n")  # Subsection title

            for qa in subsection["questions_with_answers"]:
                question_text = qa["question"]["fields"][
                    "question_text"
                ]  # Adjust based on your model's field names
                answer_text = (
                    qa["answer"] if qa["answer"] else "Answer not found in documents."
                )

                # Add question and answer in a list format
                markdown.append(f"{question_text}\n\n")
                markdown.append(quote_answer(answer_text))

        markdown.append("\n")  # Add an empty line for spacing between sections

    return "".join(markdown)


def get_create_meta_data_yaml(
    request: HttpRequest, assay: Assay, file_path: Path
) -> Path:
    """Create meta data yaml file for pandoc."""
    # get date:
    # Define the Amsterdam timezone (UTC+1)
    amsterdam_tz = timezone.get_fixed_timezone(1)  # 1 means UTC+1

    # Get the current time in UTC and convert it to Amsterdam time
    current_time = timezone.now().astimezone(amsterdam_tz)

    # Optionally, you can extract the date from the current_time if needed
    current_date = current_time.date()

    metadata_dict = {
        "author": (
            f"{request.user.first_name} {request.user.last_name}"
        ),
        "date": str(current_date),
        "keywords": (
            "metadata template, "
            "cell-based toxicological test methods, "
            "New Approach Methodologies"
        ),  # Example keywords; customize as required
        "header-includes": [
            r"\usepackage{amsmath}",
            r"\usepackage{unicode-math}",
            r"\setmainfont{TeX Gyre Termes}",
            r"\setmathfont{TeX Gyre Termes Math}",
            r"\usepackage[a4paper, margin=3cm]{geometry}",
        ],
        "title": f"ToxTemp for Test Method: {assay.title}",
        "toc": "true",
        "toc-title": "Table of Contents",
    }
    yaml_file_path = file_path.with_name("yaml" + file_path.name).with_suffix(".yaml")
    with open(yaml_file_path, "w") as file:
        yaml.dump(metadata_dict, file, default_flow_style=False)
    return yaml_file_path


def generate_provenance_dict(assay: Assay, export_timestamp: str) -> dict:
    """Build a W3C PROV-JSON-inspired provenance record for an assay export.

    Args:
        assay: The assay being exported.
        export_timestamp: ISO-8601 timestamp of the export action.

    Returns:
        A dict that can be serialised to PROVENANCE.json inside a FAIR ZIP.

    """
    owner = assay.owner
    agent: dict = {
        "prov:type": "prov:Person",
        "foaf:name": owner.get_full_name() or owner.email,
        "foaf:mbox": owner.email,
    }
    if getattr(owner, "orcid_id", None):
        agent["schema:identifier"] = f"https://orcid.org/{owner.orcid_id}"

    return {
        "@context": {
            "prov": "http://www.w3.org/ns/prov#",
            "foaf": "http://xmlns.com/foaf/0.1/",
            "schema": "https://schema.org/",
            "dc": "http://purl.org/dc/terms/",
        },
        "prov:entity": {
            "@id": f"urn:uuid:{assay.uid}",
            "prov:type": "schema:Dataset",
            "dc:title": assay.title,
            "dc:created": assay.submission_date.isoformat(),
        },
        "prov:activity": {
            "prov:type": "toxtempassistant:export",
            "prov:endTime": export_timestamp,
            "prov:used": {
                "@id": getattr(Config, "reference_toxtempassistant_zenodo_code", ""),
                "prov:type": "prov:SoftwareAgent",
                "dc:title": "ToxTempAssistant",
                "schema:version": getattr(Config, "version", ""),
                "schema:url": getattr(Config, "github_repo_url", ""),
            },
        },
        "prov:wasAttributedTo": agent,
        "prov:wasGeneratedBy": f"urn:uuid:{assay.uid}",
    }


def generate_jsonld_from_assay(assay: Assay) -> dict:
    """Generate a JSON-LD document for an assay following schema.org vocabulary.

    The returned dict is ready to be serialised with ``json.dumps``.  It uses
    the schema.org Dataset type and embeds the structured Q&A as
    PropertyValue items so that downstream tools can parse the content without
    knowing ToxTemp internals.

    Args:
        assay: The assay to serialise.

    Returns:
        A JSON-LD dict with ``@context``, ``@type``, ``@id`` and standard
        schema.org / Dublin Core fields.

    """
    amsterdam_tz = timezone.get_fixed_timezone(1)
    export_timestamp = timezone.now().astimezone(amsterdam_tz).isoformat()

    owner = assay.owner
    creator: dict = {
        "@type": "Person",
        "name": owner.get_full_name() or owner.email,
        "email": owner.email,
    }
    if getattr(owner, "orcid_id", None):
        creator["identifier"] = f"https://orcid.org/{owner.orcid_id}"

    # Build structured Q&A as schema:PropertyValue items
    has_part = []
    for section in Section.objects.filter(
        question_set=assay.question_set
    ).prefetch_related("subsections__questions"):
        for subsection in section.subsections.all():
            for question in subsection.questions.all():
                answer_obj = assay.answers.filter(question=question).first()
                answer_text = answer_obj.answer_text if answer_obj else ""
                has_part.append(
                    {
                        "@type": "PropertyValue",
                        "name": question.question_text,
                        "description": f"[{section.title} / {subsection.title}]",
                        "value": answer_text,
                    }
                )

    return {
        "@context": {
            "@vocab": "https://schema.org/",
            "toxtemp": "https://doi.org/10.14573/altex.1909271#",
            "dc": "http://purl.org/dc/terms/",
            "prov": "http://www.w3.org/ns/prov#",
        },
        "@type": "Dataset",
        "@id": f"urn:uuid:{assay.uid}",
        "identifier": f"urn:uuid:{assay.uid}",
        "name": assay.title,
        "description": assay.description,
        "dateCreated": assay.submission_date.isoformat(),
        "dateModified": export_timestamp,
        "creator": creator,
        "publisher": {
            "@type": "Organization",
            "name": "VHP4Safety",
            "url": "https://toxtempassistant.vhp4safety.nl",
        },
        "license": getattr(Config, "license_url", ""),
        "keywords": [
            "metadata template",
            "cell-based toxicological test methods",
            "New Approach Methodologies",
            "ToxTemp",
        ],
        "citation": getattr(Config, "reference_toxtemp", ""),
        "isPartOf": {
            "@type": "Study",
            "name": assay.study.title,
            "isPartOf": {
                "@type": "ResearchProject",
                "name": assay.study.investigation.title,
            },
        },
        "hasPart": has_part,
        "prov:wasAttributedTo": creator,
        "prov:generatedAtTime": export_timestamp,
        "toxtemp:questionSetVersion": (
            assay.question_set.display_name if assay.question_set else None
        ),
    }


def generate_fair_zip_bytes(assay: Assay) -> bytes:
    """Build a FAIR ZIP package for an assay.

    The archive contains:
    - ``<slug>.jsonld``     — JSON-LD main data (machine-readable)
    - ``PROVENANCE.json``  — W3C PROV-JSON provenance record
    - ``LICENSE.txt``      — The project's AGPL-3 licence
    - ``README.md``        — Access instructions and citation guidance

    Args:
        assay: The assay to package.

    Returns:
        Raw bytes of the in-memory ZIP archive.

    """
    amsterdam_tz = timezone.get_fixed_timezone(1)
    export_timestamp = timezone.now().astimezone(amsterdam_tz).isoformat()
    slug = slugify(assay.title)

    jsonld_data = generate_jsonld_from_assay(assay)
    provenance_data = generate_provenance_dict(assay, export_timestamp)

    license_text = (
        "This export is released under the GNU Affero General Public License v3.0.\n"
        f"Full text: {getattr(Config, 'license_url', 'https://www.gnu.org/licenses/agpl-3.0.html')}\n"
    )

    owner = assay.owner
    author_name = owner.get_full_name() or owner.email
    orcid_line = ""
    if getattr(owner, "orcid_id", None):
        orcid_line = f"\nAuthor ORCID: https://orcid.org/{owner.orcid_id}"
    api_url = f"/api/assay/{assay.uid}/metadata/"
    zenodo_doi = getattr(Config, "reference_toxtempassistant_zenodo_code", "")
    toxtemp_ref = getattr(
        Config, "reference_toxtemp", "https://doi.org/10.14573/altex.1909271"
    )
    accessible_line = (
        f"- **Accessible**: Available via RESTful API endpoint: `{api_url}`"
        " (authentication required)"
    )
    findable_line = (
        f"- **Findable**: Each export carries a UUID persistent identifier"
        f" (`urn:uuid:{assay.uid}`)"
    )
    readme_text = (
        "# ToxTemp FAIR Export Package\n\n"
        "## Assay\n"
        f"**Title:** {assay.title}\n"
        f"**Identifier:** urn:uuid:{assay.uid}\n"
        f"**Created:** {assay.submission_date.isoformat()}\n"
        f"**Author:** {author_name}{orcid_line}\n\n"
        "## Contents\n"
        f"- `{slug}.jsonld` — Main ToxTemp data in JSON-LD format"
        " (machine-readable, schema.org)\n"
        "- `PROVENANCE.json` — W3C PROV-JSON provenance record\n"
        "- `LICENSE.txt` — Data use licence\n"
        "- `README.md` — This file\n\n"
        "## FAIR Data Principles\n"
        "This package is designed to support FAIR data principles:\n"
        f"{findable_line}\n"
        f"{accessible_line}\n"
        "- **Interoperable**: JSON-LD format with schema.org and Dublin Core"
        " vocabularies\n"
        "- **Reusable**: Includes AGPL-3 licence and W3C PROV provenance"
        " information\n\n"
        "## Citation\n"
        "If you use this export, please cite ToxTempAssistant:\n"
        f"{zenodo_doi}\n\n"
        "And the ToxTemp method template:\n"
        f"{toxtemp_ref}\n\n"
        "## Programmatic Access\n"
        "The JSON-LD metadata for this assay is also available via the API:\n"
        f"  GET {api_url}\n"
        "  Content-Type: application/ld+json\n"
        "  (Requires authentication)\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{slug}.jsonld", json.dumps(jsonld_data, indent=2))
        zf.writestr("PROVENANCE.json", json.dumps(provenance_data, indent=2))
        zf.writestr("LICENSE.txt", license_text)
        zf.writestr("README.md", readme_text)
    return buf.getvalue()


def export_assay_to_file(
    request: HttpRequest, assay: Assay, export_type: str
) -> FileResponse:
    """Export assay to file."""
    # EXPORT_MAPPING (defined in toxtempass/__init__.py) is the single security
    # gate: only types with both trusted Pandoc options and known MIME/suffix
    # metadata are permitted.
    if export_type not in EXPORT_MAPPING or export_type not in EXPORT_MIME_SUFFIX:
        return JsonResponse({"error": "Invalid export type"}, status=400)
    mapped_suffix = EXPORT_MIME_SUFFIX[export_type]["suffix"]
    file_name = f"toxtemp_{slugify(assay.title)}{mapped_suffix}"
    file_path = Path(settings.MEDIA_ROOT) / "toxtempass" / file_name  # Use pathlib.Path
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True)

    export_data = None
    if export_type == "json":
        export_data = generate_json_from_assay(assay)
        with file_path.open("w", encoding="utf-8") as json_file:
            json.dump(export_data, json_file, indent=4)

    elif export_type == "jsonld":
        export_data = generate_jsonld_from_assay(assay)
        with file_path.open("w", encoding="utf-8") as jsonld_file:
            json.dump(export_data, jsonld_file, indent=2)

    elif export_type == "zip":
        zip_bytes = generate_fair_zip_bytes(assay)
        file_path.write_bytes(zip_bytes)
        export_data = zip_bytes  # truthy sentinel so the None-check below passes

    # elif export_type == "md":
    #     export_data = generate_markdown_from_assay(assay)
    #     with file_path.open("w", encoding="utf-8") as md_file:
    #         md_file.write(export_data)

    elif export_type in PANDOC_EXPORT_TYPES:
        # Generate the markdown file
        export_data = generate_markdown_from_assay(assay)
        md_file_path = (file_path.with_name(f"{file_path.stem}_md")).with_suffix(".md")
        with md_file_path.open("w", encoding="utf-8") as md_file:
            md_file.write(export_data)

        yaml_metadata_file_path = get_create_meta_data_yaml(request, assay, file_path)

        # Convert the markdown file to the requested format using Pandoc
        pandoc_command = [
            "pandoc",
            str(md_file_path),
            "--from=markdown+tex_math_dollars+tex_math_single_backslash+tex_math_double_backslash",
            f"--metadata-file={str(yaml_metadata_file_path)}",
            "--toc",
        ]
        # Add ONLY safe mapped Pandoc options
        pandoc_command.extend(EXPORT_MAPPING[export_type])
        pandoc_command.extend(["-o", str(file_path)])

        try:
            subprocess.run(pandoc_command, check=True)  # noqa: S603
        except subprocess.CalledProcessError as e:
            corr_id = uuid.uuid4().hex[:8]
            logger.exception(
                "Pandoc conversion failed [corr=%s] for assay %s", corr_id, assay.id
            )
            add_status_context(assay, f"[{corr_id}] {type(e).__name__}: {e}")
            assay.save()
            return JsonResponse(
                {
                    "error": f"Export failed (ref {corr_id}). "
                    "Please contact support if the issue persists."
                },
                status=500,
            )
        except Exception as e:
            corr_id = uuid.uuid4().hex[:8]
            logger.exception(
                "Unexpected export error [corr=%s] for assay %s", corr_id, assay.id
            )
            add_status_context(assay, f"[{corr_id}] {type(e).__name__}: {e}")
            assay.save()
            return JsonResponse(
                {
                    "error": f"Export failed (ref {corr_id}). "
                    "Please contact support if the issue persists."
                },
                status=500,
            )

        # cleanup the auxiliary files
        try:
            yaml_metadata_file_path.unlink()
            md_file_path.unlink()
        except FileNotFoundError:
            # If the file doesn't exist, there's nothing to unlink, so pass
            pass

    if export_data is None:
        return JsonResponse({"error": "Assay or file_type not found"}, status=404)

    # Prepare the response for the genrated file
    try:
        response = FileResponse(
            file_path.open("rb"),
            as_attachment=True,
            filename=file_name,
            content_type=EXPORT_MIME_SUFFIX[export_type]["mime_type"],
        )
        return response
    except Exception:
        JsonResponse(
            dict(
                success=False,
                errors={"__all__": ["This export format is unsupported."]},
            ),
            status=500,
        )
