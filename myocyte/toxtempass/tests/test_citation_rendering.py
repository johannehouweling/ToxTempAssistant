"""Regression tests for the client-side citation / markdown renderer.

The renderer (``renderCitations``) is browser JavaScript living in
``templates/toxtempass/answer_extras/markdown_inline_edit.html``. To guard the
REAL function — instead of a Python re-implementation that could silently drift —
these tests run it through a tiny Node harness
(``tests/js/render_citations_harness.js``) that extracts the actual functions
from the template and evaluates them with ``toHtml`` stubbed to identity and
``DOMPurify`` left undefined. That keeps the assertions focused on the
marker-parsing / footnote-reconstruction stage, which is where every bug below
lived. Tests skip automatically when Node is unavailable (e.g. a CI image
without it) rather than failing.

Bugs guarded here (all reproduced as cases):

* **paren-in-filename truncation** — a source label that is an uploaded filename
  containing parentheses, e.g.
  ``Generation_..._Cells_(NPCs)_using_..._2022.docx``, used to truncate the
  citation at the first inner ``)``, mangling the footnote and leaving the
  filename tail as dangling literal text after the ``[n]`` markers. (The
  original report; see the screenshots in the PR.)
* **unwrapped marker eating a following italic** — an unwrapped ``(Source: X)``
  must not consume a following ``_`` that opens an adjacent markdown italic.
* **same-label / different-URL collapse** — two consecutive citations sharing a
  label but resolving to different URLs are distinct references and must not be
  deduplicated into one (which dropped a link).
* **URL hardening** — only whitespace-free ``http(s)://…`` values may become an
  ``href``; a smuggled second scheme or control characters are rejected.
* **markup escaping** — a label is HTML-escaped into ``data-bs-title``; a
  ``javascript:`` URL never reaches an ``href``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1]
HARNESS = APP_DIR / "tests" / "js" / "render_citations_harness.js"
TEMPLATE = (
    APP_DIR
    / "templates"
    / "toxtempass"
    / "answer_extras"
    / "markdown_inline_edit.html"
)

NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(
    NODE is None,
    reason="node not installed; the JS renderer cannot be exercised",
)

# The real screenshot filename — the exact label that triggered the original bug.
NPCS = (
    "Generation_and_culture_of_Neural_Progenitor_Cells_(NPCs)"
    "_using_the_STEMdiff Neural System_v1_2022.docx"
)

# Each case: (name, raw, url_map, must_contain, must_not_contain).
# Substrings are matched against the harness output (identity ``toHtml``), so
# markdown such as ``_italic_`` stays literal — which is exactly what lets us
# assert that a wrapping underscore was/wasn't consumed.
CASES: list[tuple[str, str, dict, list[str], list[str]]] = [
    # ---- paren-in-filename truncation (the original report) -----------------
    (
        "real-case-single-source",
        f"Neural progenitor cells were generated _(Source: {NPCS})_ "
        "following the manufacturer protocol.",
        {},
        [
            f'data-bs-title="{NPCS}"',
            ">[1]</sup>",
            " following the manufacturer protocol.",
        ],
        # the classic dangling tail must be gone, and no phantom 2nd footnote
        ["docx)_", "_using_the_STEMdiff Neural System_v1_2022.docx)_", "[2]"],
    ),
    (
        "real-case-two-sources",
        "Frozen NPCs are thawed and expanded before use. "
        f"_(Sources: file1.pdf, {NPCS})_",
        {},
        [
            'data-bs-title="file1.pdf">[1]</sup>',
            f'data-bs-title="{NPCS}">[2]</sup>',
        ],
        ["docx)_", "[3]", "_(Sources"],
    ),
    (
        "paren-source-first-then-second",
        "Explicit batch acceptance criteria are not provided. "
        f"_(Sources: {NPCS}, Protocol_difftox_test hNPT_v1_2022.docx)_",
        {},
        [
            f'data-bs-title="{NPCS}">[1]</sup>',
            'data-bs-title="Protocol_difftox_test hNPT_v1_2022.docx">[2]</sup>',
        ],
        ["docx)_", "[3]"],
    ),
    (
        "paren-at-start-of-label",
        "See the protocol _(Source: (draft)_assay_protocol_v2.pdf)_ for details.",
        {},
        ['data-bs-title="(draft)_assay_protocol_v2.pdf"', ">[1]</sup>", " for details."],
        ["pdf)_", "[2]"],
    ),
    (
        "paren-at-end-of-label",
        "Documented in _(Source: assay_protocol_final_(2022))_ thoroughly.",
        {},
        ['data-bs-title="assay_protocol_final_(2022)"', ">[1]</sup>", " thoroughly."],
        ["(2022))_", ")_ thoroughly", "[2]"],
    ),
    (
        "doubly-nested-parens",
        "Method a(b(c)d)e _(Source: a(b(c)d)e_method.docx)_ applied.",
        {},
        [
            "Method a(b(c)d)e <sup",
            'data-bs-title="a(b(c)d)e_method.docx"',
            "</sup> applied.",
        ],
        ["docx)_", "[2]"],
    ),
    # ---- de-duplication ----------------------------------------------------
    (
        "dedup-consecutive-collapses-to-last",
        "The cells were cultured _(Sources: DocA)_ then differentiated "
        "_(Sources: DocA)_ and finally fixed _(Sources: DocA)_.",
        {},
        ['and finally fixed <sup', 'data-bs-title="DocA">[1]</sup>.'],
        ["[2]", "_(Sources"],
    ),
    (
        "dedup-distinct-sources-kept",
        "A _(Source: x.pdf)_ B _(Source: y.pdf)_",
        {},
        ['data-bs-title="x.pdf">[1]</sup>', 'data-bs-title="y.pdf">[2]</sup>'],
        ["[3]"],
    ),
    (
        "dedup-same-label-different-url-both-kept",  # regression: don't drop a link
        "a (Source: Smith | https://doi.org/10.1/a) and "
        "(Source: Smith | https://doi.org/10.2/b) end",
        {},
        ['href="https://doi.org/10.1/a"', 'href="https://doi.org/10.2/b"'],
        [],
    ),
    (
        "dedup-same-label-same-url-collapses",
        "a (Source: Smith | https://x.org/p) and (Source: Smith | https://x.org/p) end",
        {},
        ["a  and <sup", '>[1]</a></sup> end'],
        ["[2]"],
    ),
    # ---- headings ----------------------------------------------------------
    (
        "leading-heading-marker-stripped",
        "# Section title\nbody _(Source: a.pdf)_",
        {},
        ["Section title", 'data-bs-title="a.pdf"'],
        ["# Section title"],
    ),
    # ---- link resolution (inline "LABEL | URL", bare URL, or DOI) ----------
    (
        "bare-doi-becomes-link",
        "Q _(Sources: 10.1234/abc.def)_",
        {},
        ['<a href="https://doi.org/10.1234/abc.def"', ">[1]</a></sup>"],
        ["[2]"],
    ),
    (
        "pipe-form-label-and-url",
        "R _(Source: Title of paper | https://example.com/page)_",
        {},
        ['<a href="https://example.com/page"', 'data-bs-title="Title of paper"'],
        ["[2]"],
    ),
    (
        "plain-label-stays-hover-only",
        "S _(Source: just a label.pdf)_",
        {},
        ['data-bs-title="just a label.pdf">[1]</sup>'],
        ["<a href", "[2]"],
    ),
    # ---- malformed / adversarial ------------------------------------------
    (
        "unbalanced-marker-left-untouched",
        "Findings here _(Sources: broken.pdf",
        {},
        ["Findings here _(Sources: broken.pdf"],
        ["<sup", "[1]", "data-bs-title"],
    ),
    (
        "unbalanced-then-later-closeable-still-found",
        "_(Sources: ( open and then (Source: ok.pdf)_ tail",
        {},
        ['data-bs-title="ok.pdf">[1]</sup>'],
        [],
    ),
    (
        "label-html-escaped-and-js-url-rejected",
        "Cite _(Source: <script>evil</script> | javascript:alert(1))_ x",
        {},
        [
            'data-bs-title="&lt;script&gt;evil&lt;/script&gt;">[1]</sup>',
            "Cite <sup",
            "</sup> x",
        ],
        ["<a href", "javascript:", "<script>evil", "[2]"],
    ),
    # ---- underscore / italic handling (fix: gate "_" consumption on wrap) ---
    (
        "unwrapped-marker-keeps-following-italic",
        "cultured (Source: protocol.pdf)_in vitro_ today",
        {},
        ['data-bs-title="protocol.pdf">[1]</sup>', "_in vitro_ today"],
        ["[2]"],
    ),
    (
        "wrapped-marker-consumes-its-underscore",
        "see _(Source: A.pdf)_ now",
        {},
        ['data-bs-title="A.pdf">[1]</sup> now'],
        ["</sup>_ now", "[2]"],
    ),
    # ---- URL hardening (whole-URL validation, not just the scheme prefix) ---
    (
        "url-with-embedded-space-and-second-scheme-rejected",
        "x _(Source: L | https://a.com x javascript:alert(1))_ y",
        {},
        ['data-bs-title="L">[1]</sup>'],
        ["<a href", "javascript:"],
    ),
    (
        "clean-https-still-links",
        "x _(Source: Title | https://good.example/p)_ y",
        {},
        ['<a href="https://good.example/p"', 'data-bs-title="Title"'],
        [],
    ),
]


@pytest.fixture(scope="module")
def rendered() -> dict[str, str]:
    """Render every case in a single Node invocation; keyed by case name.

    A non-zero exit (e.g. the harness can no longer locate the renderer
    functions in the template) fails loudly here instead of silently passing.
    """
    payload = json.dumps(
        [
            {"name": name, "raw": raw, "urlMap": url_map}
            for name, raw, url_map, _, _ in CASES
        ]
    )
    proc = subprocess.run(
        [NODE, str(HARNESS), str(TEMPLATE)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"harness failed (exit {proc.returncode}):\n{proc.stderr}"
    )
    return {r["name"]: r["output"] for r in json.loads(proc.stdout)}


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_citation_rendering(rendered: dict[str, str], case: tuple) -> None:
    name, _raw, _url_map, must_contain, must_not_contain = case
    out = rendered[name]
    for needle in must_contain:
        assert needle in out, (
            f"[{name}] expected substring missing:\n  {needle!r}\nin output:\n  {out!r}"
        )
    for needle in must_not_contain:
        assert needle not in out, (
            f"[{name}] forbidden substring present:\n  {needle!r}\nin output:\n  {out!r}"
        )
