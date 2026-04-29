import io
import json
import logging
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

import yaml
from django.core.serializers import serialize
from django.http import FileResponse, HttpRequest, JsonResponse
from django.utils import timezone  # Import timezone utilities
from django.utils.text import slugify

from toxtempass import Config
from toxtempass.models import Assay, Section
from toxtempass.utilities import log_processing_event

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

        # Prepare the data structure
        export_data = {
            "metadata": {
                # Current date and time in ISO format
                "creation_date": current_time.isoformat(),
                # Filename for the export
                "filename": f"toxtemp_{slugify(assay.title)}",
                # Replace with your actual website name
                "reference_toxtemp": getattr(Config, "reference_toxtemp", None),
                "website": "toxtempassistant.vhp4safety.nl",
                # Trimmed config for reproducibility (PII and developer-only fields omitted)
                "config": {
                    "model": getattr(Config, "model", None),
                    "model_info_url": getattr(Config, "model_info_url", None),
                    "reference_toxtempassistant": getattr(
                        Config, "reference_toxtempassistant", None
                    ),
                    "reference_toxtemp": getattr(Config, "reference_toxtemp", None),
                    "website": "toxtempassistant.vhp4safety.nl",
                    "reference_toxtempassistant": getattr(
                        Config, "reference_toxtempassistant", None
                    ),
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
        "author": f"{request.user.first_name} {request.user.last_name}",  # Example author; replace as needed
        "date": str(current_date),  # Current date;
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

    # All export artefacts are written to a short-lived temp directory; nothing
    # is stored permanently on the container filesystem.
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / file_name

        export_data = None
        if export_type == "json":
            export_data = generate_json_from_assay(assay)
            with file_path.open("w", encoding="utf-8") as json_file:
                json.dump(export_data, json_file, indent=4)

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
                log_processing_event(assay, f"[{corr_id}] {type(e).__name__}: {e}")
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
                log_processing_event(assay, f"[{corr_id}] {type(e).__name__}: {e}")
                assay.save()
                return JsonResponse(
                    {
                        "error": f"Export failed (ref {corr_id}). "
                        "Please contact support if the issue persists."
                    },
                    status=500,
                )

        if export_data is None:
            return JsonResponse({"error": "Assay or file_type not found"}, status=404)

        # Read the output file into memory so it can be served after the temp
        # directory is cleaned up.
        file_content = file_path.read_bytes()

    # Prepare the response for the generated file
    try:
        response = FileResponse(
            io.BytesIO(file_content),
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
