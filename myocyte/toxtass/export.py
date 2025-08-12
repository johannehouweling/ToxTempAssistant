import json
import logging
import re
import subprocess
from pathlib import Path

import yaml
from django.core.serializers import serialize
from django.http import FileResponse, HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.text import slugify
from toxtass import Config
from toxtass.models import Assay, Section

from myocyte import settings

_LOG = logging.getLogger(__name__)

MATH_BLOCK_START = re.compile(r"^(\\$\\$|\\\\\\[)")
MATH_BLOCK_END = re.compile(r"(\\$\\$|\\\\\\])$")


def quote_answer(text: str) -> str:
    """Format multi-line answer text as Markdown blockquote.

    Preserving math blocks without quoting.
    """
    out = []
    in_math = False

    for line in text.splitlines():
        if not in_math and MATH_BLOCK_START.match(line):
            in_math = True
            out.append(line)
            continue
        if in_math:
            out.append(line)
            if MATH_BLOCK_END.search(line):
                in_math = False
            continue
        out.append(f"> {line}" if line.strip() else ">")

    return "\\n".join(out) + "\\n\\n"

mime_type_str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
mime_types = {
    "html": {"mime_type": "text/html", "suffix": ".html"},
    "xml": {"mime_type": "application/xml", "suffix": ".xml"},
    "pdf": {"mime_type": "application/pdf", "suffix": ".pdf"},
    "docx": {
        "mime_type": mime_type_str,
        "suffix": ".docx",
    },
    "json": {"mime_type": "application/json", "suffix": ".json"},
    "md": {"mime_type": "text/markdown", "suffix": ".md"},
}


def generate_json_from_assay(assay: Assay)->dict|None:
    """Serialize assay data and associated related objects to JSON dictionary."""
    try:
        tod = timezone.get_current_timezone()
        now = timezone.now().astimezone(tod)
        data = {
            "metadata": {
                "creation_date": now.isoformat(),
                "filename": f"documentation_{slugify(assay.title)}",
                "website": "toxtassistant.vhp4safety.nl",
                "config": {
                    k: v for k, v in vars(Config).items() if not k.startswith("_")
                },
            },
            "investigation": json.loads(serialize("json", [assay.study.investigation]))[
                0
            ],
            "study": json.loads(serialize("json", [assay.study]))[0],
            "assay": json.loads(serialize("json", [assay]))[0],
            "answers": json.loads(serialize("json", assay.answers.all())),
        }
        qa_list = []
        for ans in assay.answers.all():
            qd = json.loads(serialize("json", [ans.question]))[0]
            qa_list.append(
                {
                    "question": qd,
                    "answer": ans.answer_text,
                    "source": ans.answer_documents,
                }
            )
        data["questions_answers"] = qa_list

        sect_list = []
        for sec in Section.objects.all():
            sec_d = {
                "section": json.loads(serialize("json", [sec]))[0],
                "subsections": [],
            }
            for sub in sec.subsections.all():
                sub_d = {
                    "subsection": json.loads(serialize("json", [sub]))[0],
                    "questions_answers": [],
                }
                for q in sub.questions.all():
                    ans_text = ""
                    for a in assay.answers.filter(question=q):
                        ans_text = a.answer_text
                    sub_d["questions_answers"].append(
                        {
                            "question": json.loads(serialize("json", [q]))[0],
                            "answer": ans_text,
                        }
                    )
                sec_d["subsections"].append(sub_d)
            sect_list.append(sec_d)
        data["sections"] = sect_list
        return data
    except Assay.DoesNotExist:
        return None


def generate_markdown_from_assay(assay: Assay) -> str:
    """Generate a Markdown report string for the assay.

    Including metadata, investigation, study, and sections.
    """
    d = generate_json_from_assay(assay)
    out = []
    out.append("## Metadata\n")
    out.append(f"Creation Date: {d['metadata']['creation_date']}\n")
    out.append(f"Filename: {d['metadata']['filename']}\n")
    out.append(f"Website: {d['metadata']['website']}\n\n")
    for k, v in d["metadata"]["config"].items():
        out.append(f"{k}: {v}\n")
    out.append("\n")
    out.append("# Investigation\n")
    out.append(f"{d['investigation']['fields']['title']}\n")
    out.append(f"{d['investigation']['fields']['description']}\n\n")
    out.append("# Study\n")
    out.append(f"{d['study']['fields']['title']}\n")
    out.append(f"{d['study']['fields']['description']}\n\n")
    out.append("# Assay\n")
    out.append(f"{d['assay']['fields']['title']}\n\n")

    for sect in d.get("sections", []):
        out.append(f"# {sect['section']['fields']['title']}\n")
        for sub_sec in sect.get("subsections", []):
            out.append(f"## {sub_sec['subsection']['fields']['title']}\n")
            for qa in sub_sec.get("questions_answers", []):
                q_text = qa["question"]["fields"]["question_text"]
                ans = qa.get("answer", "Answer not found in documents.")
                out.append(q_text + "\n")
                out.append(quote_answer(ans))
            out.append("\n")
    return "".join(out)


def create_metadata_yaml(req: HttpRequest, assay: Assay, path: Path) -> Path:
    """Create YAML metadata file used for document conversion."""
    tz = timezone.get_current_timezone()
    now = timezone.now().astimezone(tz)
    meta = {
        "author": str(req.user.first_name),
        "date": now.date().isoformat(),
        "keywords": ("metadata template, cell-based toxicological methods, "
                     "New Approach Methodologies"),
        "header-includes": [
            "\\usepackage{amsmath}",
            "\\usepackage{unicode-math}",
            "\\setmainfont{TeX Gyre Termes}",
            "\\setmathfont{TeX Gyre Termes}",
            "\\usepackage[a4paper, margin=3cm]{geometry}",
        ],
        "title": f"ToxTemp for {assay.title}",
        "toc": True,
        "toc-title": "Table of Contents",
    }
    yaml_path = path.with_name("metadata_" + path.name).with_suffix(".yaml")
    with open(yaml_path, "w") as f:
        yaml.dump(meta, f, default_flow_style=False)
    return yaml_path


def export_assay_to_file(req: HttpRequest, assay: Assay, ext: str) -> FileResponse:
    """Export assay data to requested format (json, md, pdf, docx, etc.) with Pandoc."""
    filename = f"document_{slugify(assay.title)}.{ext}"
    filepath = Path(settings.MEDIA_ROOT) / "toxtass" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    content = None
    if ext == "json":
        content = generate_json_from_assay(assay)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=4)
    elif ext in ["md", "pdf", "docx", "html", "xml"]:
        content = generate_markdown_from_assay(assay)
        md_path = filepath.with_suffix(".md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)
        yaml_path = create_metadata_yaml(req, assay, filepath)

        pandoc_cmd = [
            "pandoc",
            str(md_path),
            "--from=markdown+tex_math_dollars+tex_math_single_backslash+tex_math_doublebackslash",
            f"--metadata-file={yaml_path}",
            "--toc",
        ]

        if ext == "pdf":
            pandoc_cmd.extend(["--pdf-engine=lualatex", "--standalone"])
        elif ext == "md":
            pandoc_cmd.append("--to=gfm")
        elif ext == "docx":
            pandoc_cmd.append("--to=docx+auto_identifiers")
        elif ext == "html":
            pandoc_cmd.extend(["--embed-resources", "--standalone", "--to=html+smart"])

        pandoc_cmd.extend(["-o", str(filepath)])

        try:
            subprocess.run(pandoc_cmd, check=True)  # noqa: S603
        except subprocess.CalledProcessError as e:
            return JsonResponse({"error": f"Pandoc conversion failed: {e}"}, status=500)
        except Exception as e:
            return JsonResponse({"error": f"Unexpected error: {e}"}, status=500)

        try:
            yaml_path.unlink()
            md_path.unlink()
        except Exception:
            _LOG.warning("Problem encountered try to delete {yaml_path} or {md_path}.")

    if content is None:
        return JsonResponse(
            {"error": "Export format unsupported or assay not found"}, status=404
        )

    try:
        return FileResponse(
            open(filepath, "rb"),
            as_attachment=True,
            filename=filename,
            content_type=mime_types.get(ext, {}).get(
                "mime_type", "application/octet-stream"
            ),
        )
    except Exception:
        return JsonResponse({"error": "Unsupported export format"}, status=500)
