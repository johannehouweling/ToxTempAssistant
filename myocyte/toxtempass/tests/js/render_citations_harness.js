// Test harness for the citation/markdown renderer that lives in the Django
// template `templates/toxtempass/answer_extras/markdown_inline_edit.html`.
//
// We have no JS test runner in this project (pytest only), so to regression-test
// the REAL `renderCitations` — not a drifting copy — this harness extracts the
// three pure functions (`esc`, `resolveSource`, `renderCitations`) straight out
// of the template and evaluates them with stubbed collaborators.
//
//   * `toHtml`     -> identity. The bug we guard (issue: paren-in-filename source
//                    labels) lives entirely in the marker-parsing/reconstruction
//                    step that runs BEFORE markdown rendering, so an identity
//                    `toHtml` exercises exactly the regression surface while
//                    keeping the harness free of the `marked` npm dependency.
//   * `DOMPurify`  -> left undefined; the function's `typeof` guard skips it.
//   * `marked`     -> not referenced by the three extracted functions.
//
// Usage:  node render_citations_harness.js <template_path>
//         (cases read as JSON array from stdin -> results JSON array on stdout)
// Each case: {name, raw, urlMap?}  ->  result: {name, output}

const fs = require("fs");

const templatePath = process.argv[2];
if (!templatePath) {
    process.stderr.write("usage: node render_citations_harness.js <template_path>\n");
    process.exit(2);
}

const template = fs.readFileSync(templatePath, "utf8");

// Slice out the three pure helpers. Anchored on stable function names rather than
// line numbers so the extraction survives edits elsewhere in the script. If these
// anchors ever move, this throws loudly instead of silently testing nothing.
const startAnchor = "function esc(s)";
const endAnchor = "function initTooltips(";
const startIdx = template.indexOf(startAnchor);
const endIdx = template.indexOf(endAnchor);
if (startIdx < 0 || endIdx < 0 || endIdx <= startIdx) {
    process.stderr.write(
        "harness: could not locate esc(...)/initTooltips(...) anchors in template; " +
        "the renderer functions may have been renamed or moved.\n"
    );
    process.exit(3);
}
const fnSource = template.slice(startIdx, endIdx);

// Build a callable from the extracted source. `toHtml`/`DOMPurify` are injected as
// formal parameters so the closure references inside renderCitations resolve.
// eslint-disable-next-line no-new-func
const factory = new Function(
    "toHtml",
    "DOMPurify",
    fnSource + "\nreturn renderCitations;"
);
const renderCitations = factory(function (x) { return x; }, undefined);

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", function (d) { input += d; });
process.stdin.on("end", function () {
    let cases;
    try {
        cases = JSON.parse(input || "[]");
    } catch (e) {
        process.stderr.write("harness: invalid JSON on stdin: " + e.message + "\n");
        process.exit(4);
    }
    const results = cases.map(function (c) {
        return { name: c.name, output: renderCitations(c.raw, c.urlMap || {}) };
    });
    process.stdout.write(JSON.stringify(results));
});
