import datetime
from pathlib import Path
from myocyte import settings
from toxtempass.models import Question, Answer, Assay, Section, Subsection
import json
from django.core.serializers import serialize
from django.http import FileResponse, HttpRequest, JsonResponse
from django.utils.text import slugify
from django.utils import timezone  # Import timezone utilities
from toxtempass import Config  # Import your configuration module

mime_type_suffix_dict = {
    "xml": {"mime_type": "application/xml", "suffix": ".xml"},
    "pdf": {"mime_type": "application/pdf", "suffix": ".pdf"},
    "docx": {
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "suffix": ".docx",
    },
    "json": {"mime_type": "application/json", "suffix": ".json"},
    "md": {"mime_type": "text/markdown", "suffix": ".md"},
}


def generate_json_from_assay(assay: Assay):
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
                "creation_date": current_time.isoformat(),  # Current date and time in ISO format
                "filename": f"assay_{slugify(assay.title)}.json",  # Filename for the export
                "website": "Your Website Name",  # Replace with your actual website name
                "config": {
                    key: value
                    for key, value in vars(Config).items()
                    if not key.startswith("__")
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
                {"question": question_data, "answer": answer.answer_text}
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


def generate_markdown_from_assay(assay: Assay):
    export_data = generate_json_from_assay(assay)
    # Start with metadata
    markdown = []
    markdown.append("# Metadata\n")
    markdown.append(
        f"- **Creation Date:** {export_data['metadata']['creation_date']}\n"
    )
    markdown.append(f"- **Filename:** {export_data['metadata']['filename']}\n")
    markdown.append(f"- **Website:** {export_data['metadata']['website']}\n")
    markdown.append(f"## App Config\n")
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
                markdown.append(f">{answer_text.replace('\n','\n>')}\n\n")

        markdown.append("\n")  # Add an empty line for spacing between sections

    return "".join(markdown)


def export_assay_to_file(
    request: HttpRequest, assay: Assay, export_type: str
) -> FileResponse:
    file_name = f"assay_{slugify(assay.title)}.{export_type}"
    file_path = Path(settings.MEDIA_ROOT) / "toxtempass" / file_name  # Use pathlib.Path
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True)

    export_data = None
    if export_type == "json":
        export_data = generate_json_from_assay(assay)
        with file_path.open("w", encoding="utf-8") as json_file:
            json.dump(export_data, json_file, indent=4)

    if export_type == "md":
        export_data = generate_markdown_from_assay(assay)
        with file_path.open("w", encoding="utf-8") as md_file:
            md_file.write(export_data)

    if export_data is None:
        return JsonResponse({"error": "Assay or file_type not found"}, status=404)

    # Define the file name and path using pathlib

    # Write JSON data to a file

    # Return the JSON file as a FileResponse
    try:
        response = FileResponse(
            file_path.open("rb"),
            as_attachment=True,
            filename=file_name,
            content_type=mime_type_suffix_dict[
                export_type
            ],  # Set the content type for JSON
        )
        return response
    except Exception as e:
        JsonResponse(
            dict(
                success=False,
                errors={"__all__": ["This export format is unsupported."]},
            ),
            status=500,
        )
