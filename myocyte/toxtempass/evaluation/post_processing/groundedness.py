#!/usr/bin/env python3

import argparse
import json
import math
import re
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer

from toxtempass import LLM_API_KEY, config


def build_faithfulness_metric(
    *, model: str, threshold: float, verbose_mode: bool
) -> FaithfulnessMetric:
    # FaithfulnessMetric expects retrieval_context in the LLMTestCase.  [oai_citation:4‡deepeval.com](https://deepeval.com/docs/metrics-faithfulness?utm_source=chatgpt.com)
    return FaithfulnessMetric(
        threshold=threshold,
        model=model,
        include_reason=True,
        verbose_mode=verbose_mode,
        # evaluation_template=, # optional custom prompt template if you want to tweak the default one
    )


def build_groundedness_policy_geval(
    *, model: str, threshold: float, verbose_mode: bool
) -> GEval:
    """GEval as a stricter "policy gate" on top of Faithfulness."""
    return GEval(
        name="ToxTemp Groundedness Policy (counts)",
        evaluation_steps=[
            "Task: evaluate whether ACTUAL_OUTPUT is grounded ONLY in RETRIEVAL_CONTEXT. No outside knowledge.",
            "",
            "Step 1 — Extract atomic factual claims from ACTUAL_OUTPUT limited to: entities, numbers, durations, units, methods, readouts, materials, cell lines, species, instruments, and endpoints. "
            "Do NOT extract vague/subjective claims (e.g., 'robust', 'appropriate').",
            "",
            "Step 2 — For each claim, assign exactly one label:",
            "  - ENTAILED: explicitly supported by RETRIEVAL_CONTEXT (directly stated or unambiguous paraphrase).",
            "  - CONTRADICTED: conflicts with RETRIEVAL_CONTEXT.",
            "  - UNSUPPORTED: not found in RETRIEVAL_CONTEXT and not contradicted.",
            "  - ABSTAINED: ACTUAL_OUTPUT explicitly states the information is not in the context / cannot be determined, and does not assert the missing fact.",
            "",
            "Step 3 — Return VALID JSON ONLY (no markdown, no extra text) with integer counts and an optional short audit list.",
            'Required JSON keys: {"entailed": int, "unsupported": int, "contradicted": int, "abstained": int, "total_claims": int}.',
            'Optional key: "claims": a list of up to 10 items, each with {"claim": str, "label": str, "evidence": str}. Evidence should be a short phrase from context or "N/A".',
            "",
            "Step 4 — Ensure: total_claims = entailed + unsupported + contradicted + abstained.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        model=model,
        threshold=threshold,
        verbose_mode=verbose_mode,
    )

def groundedness_policy_score(counts: dict) -> float:
    e = int(counts.get("entailed", 0))
    u = int(counts.get("unsupported", 0))
    c = int(counts.get("contradicted", 0))

    if c > 0:
        return 0.0
    denom = e + u
    return (e / denom) if denom else 1.0


def groundedness_herman_style_score(counts: dict) -> float:
    e = int(counts.get("entailed", 0))
    u = int(counts.get("unsupported", 0))
    c = int(counts.get("contradicted", 0))

    total = e + u + c
    if total == 0:
        return 1.0
    raw = (e - 0.5 * c) / total
    return max(0.0, min(1.0, raw))


def _parse_counts(reason: str | None) -> Optional[dict]:
    if not reason:
        return None
    try:
        data = json.loads(reason)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def pdf_to_full_text(pdf_path: Path, *, max_pages: Optional[int] = None) -> str:
    """
    Convert a PDF to a single text string (all pages concatenated).
    Each page is prefixed with provenance: [filename p.X].
    """
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise ImportError(
            "pypdf is required for pdf_to_full_text(). Install with: pip install pypdf"
        ) from e

    reader = PdfReader(str(pdf_path))
    n_pages = len(reader.pages)
    if max_pages is not None:
        n_pages = min(n_pages, max_pages)

    pages: list[str] = []
    for i in range(n_pages):
        text = (reader.pages[i].extract_text() or "").strip()
        if not text:
            continue
        pages.append(f"[{pdf_path.name} p.{i + 1}] {text}")

    if not pages:
        return f"[{pdf_path.name}] (no extractable text)"

    return "\n\n---\n\n".join(pages)


def _cosine_similarity(a: dict[str, int], b: dict[str, int]) -> float:
    dot = 0.0
    for k, v in a.items():
        bv = b.get(k)
        if bv:
            dot += v * bv
    if dot == 0.0:
        return 0.0
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _chunk_text_by_tokens(
    text: str,
    model: SentenceTransformer,
    max_tokens: int | None = None,
    overlap: int = 20,
) -> list[str]:
    """Chunk text into pieces based on token count for the given model."""
    # Extract the actual transformer model from SentenceTransformer
    # The first module is typically the transformer layer
    transformer_model = model[0].auto_model
    
    # Load the tokenizer using AutoTokenizer for proper compatibility with newer transformers versions
    tokenizer = AutoTokenizer.from_pretrained(transformer_model.name_or_path)
    
    if max_tokens is None or max_tokens > model.max_seq_length:
        max_tokens = model.max_seq_length

    token_ids = tokenizer.encode(text, add_special_tokens=False)
    chunks = []
    step = max_tokens - overlap
    for start in range(0, len(token_ids), step):
        end = start + max_tokens
        chunk_ids = token_ids[start:end]
        chunk_text = tokenizer.decode(chunk_ids, skip_special_tokens=True)
        chunks.append(chunk_text)
    return chunks


def _sentencetransformer_embeddings(
    input: str,
    max_tokens: int | None = None,
    overlap: int = 20,
    prompt_name: str | None = None,
) -> list[list[float]]:
    """Generate embeddings using SentenceTransformer."""
    model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")
    chunks = _chunk_text_by_tokens(input, model, max_tokens=max_tokens, overlap=overlap)
    embeddings_list: list[list[float]] = []
    for chunk in chunks:
        emb = model.encode(chunk, prompt_name=prompt_name, normalize_embeddings=True)
        embeddings_list.append(emb.tolist())
    return embeddings_list


def select_top_k_chunks(*, question: str, chunks: list[str], k: int) -> list[str]:
    if k <= 0 or not chunks:
        return []

    q_embeddings = _sentencetransformer_embeddings(question)
    c_embeddings = [_sentencetransformer_embeddings(chunk) for chunk in chunks]

    scored = []
    for idx, chunk_emb in enumerate(c_embeddings):
        score = float(
            np.dot(q_embeddings[0], chunk_emb[0])
            / (np.linalg.norm(q_embeddings[0]) * np.linalg.norm(chunk_emb[0]))
        )
        scored.append((score, idx))

    scored.sort(reverse=True)
    top_indices = [idx for _, idx in scored[:k]]
    return [chunks[i] for i in top_indices]


def match_pdf_to_csv(csv_path: Path, pdf_dir: Path) -> Optional[Path]:
    """
    Find the corresponding PDF file for a given comparison CSV.
    """
    csv_name = csv_path.stem
    if csv_name.startswith("tier1_comparison_"):
        base_name = csv_name.replace("tier1_comparison_", "")
    else:
        base_name = csv_name

    pdf_path = pdf_dir / f"{base_name}.pdf"
    if pdf_path.exists():
        return pdf_path

    for pdf_file in pdf_dir.glob("*.pdf"):
        if pdf_file.stem.lower() == base_name.lower():
            return pdf_file

    return None


def run_case(
    *,
    user_input: str,
    actual_output: str,
    retrieval_context: list[str] | str,
    judge_model: str = "305-5-nano",
    faithfulness_threshold: float = 0.5,
    use_geval_policy: bool = True,
    geval_threshold: float = 0.5,
    verbose_mode: bool = False,
) -> dict:
    """Execute the faithfulness metric plus optional groundedness policy gate on one example."""
    if isinstance(retrieval_context, str):
        retrieval_context = [retrieval_context]

    test_case = LLMTestCase(
        input=user_input,
        actual_output=actual_output,
        retrieval_context=retrieval_context,
    )

    results: dict = {}

    faith = build_faithfulness_metric(
        model=judge_model,
        threshold=faithfulness_threshold,
        verbose_mode=verbose_mode,
    )
    faith.measure(test_case)
    results["faithfulness_score"] = float(faith.score)
    results["faithfulness_reason"] = faith.reason or ""

    counts: Optional[dict] = None
    if use_geval_policy:
        policy = build_groundedness_policy_geval(
            model=judge_model,
            threshold=geval_threshold,
            verbose_mode=verbose_mode,
        )
        policy.measure(test_case)
        results["geval_policy_score"] = float(policy.score)
        results["geval_policy_reason"] = policy.reason or ""
        counts = _parse_counts(policy.reason)
    else:
        results["geval_policy_score"] = None
        results["geval_policy_reason"] = None

    if counts:
        results["groundedness_policy_score"] = groundedness_policy_score(counts)
        results["groundedness_herman_score"] = groundedness_herman_style_score(counts)
        results["groundedness_counts"] = counts
    else:
        results["groundedness_policy_score"] = None
        results["groundedness_herman_score"] = None
        results["groundedness_counts"] = None

    if verbose_mode:
        print("\n=== Eval Results ===")
        for k, v in results.items():
            print(f"{k}: {v}")

    return results


def add_groundedness_columns(
    *,
    csv_path: Path,
    pdf_path: Path,
    output_path: Optional[Path] = None,
    judge_model: str = "gpt-5-nano",
    faithfulness_threshold: float = 0.5,
    geval_threshold: float = 0.5,
    chunk_size: int = 4000,
    chunk_overlap: int = 400,
    top_k: int = 8,
    verbose: bool = False,
) -> Path:
    """
    Add groundedness-related columns to a tier1_comparison CSV using a PDF as context.
    """
    df = pd.read_csv(csv_path)
    pdf_text = pdf_to_full_text(pdf_path)
    pdf_chunks = _chunk_text_by_tokens(pdf_text, model=SentenceTransformer("Qwen/Qwen3-Embedding-0.6B"), max_tokens=chunk_size, overlap=chunk_overlap)

    results_full = []
    results_topk = []
    for _, row in df.iterrows():
        question = row.get("question", "")
        actual_output = row.get("llm_answer", "")
        results_full.append(
            run_case(
                user_input=question,
                actual_output=actual_output,
                retrieval_context=pdf_text,
                judge_model=judge_model,
                faithfulness_threshold=faithfulness_threshold,
                use_geval_policy=True,
                geval_threshold=geval_threshold,
                verbose_mode=verbose,
            )
        )
        top_chunks = select_top_k_chunks(question=question, chunks=pdf_chunks, k=top_k)
        results_topk.append(
            run_case(
                user_input=question,
                actual_output=actual_output,
                retrieval_context=top_chunks,
                judge_model=judge_model,
                faithfulness_threshold=faithfulness_threshold,
                use_geval_policy=True,
                geval_threshold=geval_threshold,
                verbose_mode=verbose,
            )
        )

    df["faithfulness_score"] = [r["faithfulness_score"] for r in results_full]
    df["faithfulness_reason"] = [r["faithfulness_reason"] for r in results_full]
    df["geval_policy_score"] = [r["geval_policy_score"] for r in results_full]
    df["geval_policy_reason"] = [r["geval_policy_reason"] for r in results_full]
    df["groundedness_policy_score"] = [
        r["groundedness_policy_score"] for r in results_full
    ]
    df["groundedness_herman_score"] = [
        r["groundedness_herman_score"] for r in results_full
    ]
    df["groundedness_counts"] = [r["groundedness_counts"] for r in results_full]

    df["faithfulness_score_topk"] = [r["faithfulness_score"] for r in results_topk]
    df["faithfulness_reason_topk"] = [r["faithfulness_reason"] for r in results_topk]
    df["geval_policy_score_topk"] = [r["geval_policy_score"] for r in results_topk]
    df["geval_policy_reason_topk"] = [r["geval_policy_reason"] for r in results_topk]
    df["groundedness_policy_score_topk"] = [
        r["groundedness_policy_score"] for r in results_topk
    ]
    df["groundedness_herman_score_topk"] = [
        r["groundedness_herman_score"] for r in results_topk
    ]
    df["groundedness_counts_topk"] = [r["groundedness_counts"] for r in results_topk]

    final_path = output_path or csv_path
    df.to_csv(final_path, index=False)
    return final_path


def add_groundedness_to_directory(
    *,
    output_dir: Path,
    pdf_dir: Path,
    judge_model: str = "gpt-5-nano",
    faithfulness_threshold: float = 0.5,
    geval_threshold: float = 0.5,
    chunk_size: int = 4000,
    chunk_overlap: int = 400,
    top_k: int = 8,
    max_pdfs: Optional[int] = None,
    verbose: bool = False,
) -> None:
    csv_files = sorted(output_dir.glob("tier1_comparison_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No tier1_comparison_*.csv files found in: {output_dir}")

    if max_pdfs:
        csv_files = csv_files[:max_pdfs]

    for csv_path in csv_files:
        pdf_path = match_pdf_to_csv(csv_path, pdf_dir)
        if not pdf_path:
            print(f"WARNING: No matching PDF found for {csv_path.name}, skipping")
            continue
        out_path = add_groundedness_columns(
            csv_path=csv_path,
            pdf_path=pdf_path,
            output_path=csv_path,
            judge_model=judge_model,
            faithfulness_threshold=faithfulness_threshold,
            geval_threshold=geval_threshold,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            top_k=top_k,
            verbose=verbose,
        )
        print(f"Updated: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add groundedness columns to positive_control CSVs."
    )
    parser.add_argument(
        "--csv", type=Path, help="Path to a single tier1_comparison_*.csv"
    )
    parser.add_argument("--pdf", type=Path, help="Path to the corresponding PDF")
    parser.add_argument(
        "--output-dir", type=Path, help="Directory with tier1_comparison_*.csv files"
    )
    parser.add_argument("--pdf-dir", type=Path, help="Directory with PDF inputs")
    parser.add_argument("--judge-model", default="gpt-5-nano", help="LLM judge to use")
    parser.add_argument(
        "--faith-threshold", type=float, default=0.5, help="Faithfulness threshold"
    )
    parser.add_argument(
        "--geval-threshold", type=float, default=0.5, help="GEval threshold"
    )
    parser.add_argument(
        "--chunk-size", type=int, default=4000, help="Fixed character chunk size"
    )
    parser.add_argument(
        "--chunk-overlap", type=int, default=400, help="Character overlap between chunks"
    )
    parser.add_argument(
        "--top-k", type=int, default=8, help="Top-k chunks to use for retrieval context"
    )
    parser.add_argument(
        "--max-pdfs", type=int, default=None, help="Optional limit for batch runs"
    )
    parser.add_argument("--verbose", action="store_true", help="Print per-row details")
    args = parser.parse_args()

    if args.csv and args.pdf:
        out_path = add_groundedness_columns(
            csv_path=args.csv,
            pdf_path=args.pdf,
            output_path=args.csv,
            judge_model=args.judge_model,
            faithfulness_threshold=args.faith_threshold,
            geval_threshold=args.geval_threshold,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            top_k=args.top_k,
            verbose=args.verbose,
        )
        print(f"Updated: {out_path}")
        return

    if args.output_dir and args.pdf_dir:
        add_groundedness_to_directory(
            output_dir=args.output_dir,
            pdf_dir=args.pdf_dir,
            judge_model=args.judge_model,
            faithfulness_threshold=args.faith_threshold,
            geval_threshold=args.geval_threshold,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            top_k=args.top_k,
            max_pdfs=args.max_pdfs,
            verbose=args.verbose,
        )
        return

    parser.error("Provide --csv and --pdf, or --output-dir and --pdf-dir")


# if __name__ == "__main__":
#     main()
