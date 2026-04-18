# ToxTempAssistant Evaluation Plan

## 1. Dataset Overview

### 1.1 Data Structure

| Dimension | Count | Description |
|-----------|-------|-------------|
| Questions | 77 | ToxTemp questions across ~11 sections |
| Assays | 8 | Assay name + description + context document set |
| Models | 6 | LLM models |
| **Total** | **3,696** | Question × Assay × Model combinations |

### 1.2 Evaluation Settings

| Setting | Value |
|---------|-------|
| Image inclusion | Enabled |
| Prompt | Base prompt (unoptimised) |
| Context provided | Assay name + assay description |
| Temperature | 0 |

### 1.3 Ground Truth Status

| Aspect | Status |
|--------|--------|
| Pre-existing ground truth | **None** |
| Reference answers | Not available |
| Evaluation approach | **Creating ground truth** |

---

## 2. Research Questions

How well do LLM-generated answers to ToxTemp questions align with source documents and how can we reliably evaluate this through a combination of automated metrics and human judgment?

1. **Metric calibration**: Does inter-model cosine similarity reliably distinguish correct from incorrect answers?

2. **Inter-rater reliability**: What is the agreement (Cohen's κ) between LLM-based evaluation and human expert judgment?

3. **Model comparison**: Do models differ in faithfulness as judged by humans?

4. **Citation compliance**: Does source attribution correlate with answer quality?

---

## 3. Stage 1: Deterministic Analysis (Automated Pre-Screening)

Stage 1 performs automated analysis on all 3,696 Q-A pairs to:
- Verify data quality and completeness
- Compute metrics that inform sampling strategy
- Identify patterns before human evaluation

### 3.1 Quality Check

Expected structure:

| Check | Expected | Query |
|-------|----------|-------|
| Total rows | 3,696 | `COUNT(*)` |
| Unique questions | 77 | `COUNT(DISTINCT question_id)` |
| Unique assays | 8 | `COUNT(DISTINCT assay_id)` |
| Unique models | 6 | `COUNT(DISTINCT model_id)` |

#### 3.1.1 Metrics

Flag and count number of empty/null answers

### 3.2 Citation Compliance

#### 3.2.1 Citation Detection

Parse `_(Source: X)_` pattern from each answer.

Something like:

```python
import re
citation_pattern = r'_?\(Source[s]?:\s*[^)]+\)_?'
has_citation = bool(re.search(citation_pattern, answer))
```

#### 3.2.2 Metrics

| Metric | Definition | Aggregation |
|--------|------------|-------------|
| Citation present | Boolean per answer | - |
| Citation rate (overall) | % of non-refusal answers with citation | Global |
| Citation rate by model | % per model | Per model |
| Citation rate by assay | % per assay | Per assay |
| Citation rate by section | % per ToxTemp section | Per section |

### 3.4 Refusal Pattern Analysis

#### 3.4.1 Refusal Detection

Identify answers that indicate no relevant information found.

```python
refusal_patterns = [
    "Answer not found in document",
    "Answer not found in documents", 
    "not found in the provided",
    "no information available",
    "cannot find",
    "does not contain"
]
is_refusal = any(pattern.lower() in answer.lower() for pattern in refusal_patterns)
```

#### 3.4.2 Metrics

| Metric | Definition |
|--------|------------|
| Refusal count | Total refusals |
| Refusal rate (overall) | Refusals / Total |
| Completeness | 1 - Refusal rate |
| Refusal rate by model | Per model |
| Refusal rate by assay | Per assay |
| Refusal rate by section | Per ToxTemp section |
| Refusal rate by question | Per ToxTemp question |

#### 3.4.3 Output

- Refusal rate table (model × assay)
- Refusal heatmap (model × ToxTemp section/section)
- Questions with highest refusal rates
- Models ranked by completeness

### 3.5 Intra-Model Agreement (Reproducibility)

> For gpt-4o-mini (production model) only

Establish baseline variance inherent to the model under identical conditions.

1. All question-assay pairs (n = 8 * 77)
2. Re-run inference with identical settings
3. Compute cosine similarity between original and duplicate

#### 3.5.3 Metrics

| Metric | Definition | Note |
|--------|------------|-----------|
| Mean intra-model cosine | Average similarity | For non-trivial answers |
| Std intra-model cosine | Variation | For non-trivial answers |

### 3.6 Inter-Model Agreement

Compute agreement between models as a proxy for answer quality/uncertainty.

For each question-assay pair (n = 616):

- Do notinclude refusals in cosine calculation, conflates two questions "Is the answer correct?" vs. "Should the model have answered at all?"
- Rule: Require 4o-mini answered + at least 1 other model answered.

1. Collect all 6 model answers, excluding trivial answers (refusals or empty)
2. Generate embeddings using `text-embedding-3-large`
3. Compute pairwise cosine similarity (16 pairs per question-assay)
   
#### 3.6.1 Metrics

| Metric | Definition |
|--------|------------|
| `mean_cosine` | Mean of pairwise cosine similarities |
| `min_cosine` | Minimum pairwise cosine |
| `max_cosine` | Maximum pairwise cosine |
| `std_cosine` | Standard deviation of pairwise cosine |

- Identify question-assay pairs with highest/lowest agreement across models
- High vs. Low agreement: all models. Does consensus predict quality generally?
- Does quality differ when some models refused? Do low-agreement pairs have more refusals?


---

## 4. Stage 2: Strategic Sampling (n = 120)

### 4.1 Literature Basis

| Source | Principle Applied |
|--------|-------------------|
| Fisch et al. (2024) - StratPPI | Stratify by proxy metric; maintain random baseline |
| Merlo et al. (2026) - ECIR | Use LLM judgments as stratification variable |
| Yang et al. (2015) - Active Learning | Combine uncertainty + diversity sampling |
| Ground truth best practices | Balance easy/hard cases; ensure representation |

### 4.2 Principles

1. **Stratify by proxy metric**: Use inter-model cosine similarity as stratification variable
2. **Sample extremes**: Include both high and low agreement cases
3. **Maintain random baseline**: Preserve ability to make unbiased population estimates
4. **Ensure diversity**: Guarantee coverage across assays and models

### 4.3 Sampling Unit

**One case = one question × one assay × one model = one answer**

- 120 sampled cases = 120 individual answers to evaluate
- Human reviews 120 answers total
- LLM evaluates same 120 answers for comparison

### 4.4 Exclusion Criteria

| Criterion | Handling |
|-----------|----------|
| Refusal answers | Exclude from sampling pool |
| Partial refusals | ? |

### 4.5 Sampling Allocation

| Stratum | n | % | Selection Criteria | Purpose |
|---------|---|---|-------------------|---------|
| **Random baseline** | 36 | 30% | Simple random from all non-refusals | Unbiased population estimate |
| **Low agreement** | 24 | 20% | Bottom 24 question-assay pairs by mean cosine | Uncertainty calibration; failure modes |
| **High agreement** | 24 | 20% | Top 24 question-assay pairs by mean cosine | Validate consensus = correctness |
| **Diversity guaranteed** | 36 | 30% | Stratified by assay and model (3 per assay, 2 per model) | Ensure representation across contexts |
| **Total** | **120** | 100% | | |

### 4.6 Stratum Specifications


#### 4.6.2 Stratum 1: cosine stratified

- plot of mean_cosine and std_cosine across models for 616 question-assay pairs
- Where to draw "low" vs "high" cutoffs?

#### Low Agreement (n = 24)

| Parameter | Value |
|-----------|-------|
| Stratification variable | Mean inter-model cosine similarity |
| Selection basis | Bottom 24 question-assay pairs by `mean_cosine` |
| Model selection | Random model from within the pair |
| Exclusion | Skip pairs already fully sampled; skip if all models refused |

**Purpose:**
- Calibrate cosine threshold on difficult cases: 
  - Quick cross-tab: low-cosine cases by assay. Catch if low agreement is concentrated in one assay

1. Counts per stratum after applying cutoffs
   → Verify enough cases exist in each bin

2. Quick cross-tab: low-cosine cases by assay
   → Catch if low agreement is concentrated in one assay
- Identify failure modes when models disagree
- Answer: "Who is correct when models disagree?"
- Answer: "Does low agreement indicate low quality?"

#### High Agreement (n = 24)

| Parameter | Value |
|-----------|-------|
| Stratification variable | Mean inter-model cosine similarity |
| Selection basis | Top 24 question-assay pairs by `mean_cosine` |
| Model selection | Random model from within the pair |
| Exclusion | Skip pairs already sampled |

**Purpose:**
- Validate that high consensus indicates correctness
- Detect "confident but wrong" failure mode (shared hallucination)
- Answer: "Does high agreement indicate high quality?"

---

#### 4.6.1 Stratum 3: Random Baseline (n = 36)

| Parameter | Value |
|-----------|-------|
| Pool | All non-refusal answers |
| Selection | Simple random sample |
| Model constraint | None (natural distribution) |
| Assay constraint | None (natural distribution) |
| Priority | First (before other strata) |

**Expected coverage:**
- ~6 per model
- ~5 per assay

**Purpose:**
- Unbiased estimate of overall acceptance rate
- Supports generalisable claims about system quality

---

#### 4.6.4 Stratum 4: Diversity-Guaranteed (n = 36)


### 4.7 Pre-Sampling Verification Checklist

| Check | Requirement | Status |
|-------|-------------|--------|
| Total non-refusal answers | Sufficient pool (>500) | ☐ |
| Question-assay pairs with cosine > 0.8 | ≥ 24 available | ☐ |
| Question-assay pairs with cosine < 0.5 | ≥ 24 available | ☐ |
| Non-refusal answers per assay | ≥ 10 each | ☐ |
| Non-refusal answers per model | ≥ 15 each | ☐ |
| Inter-model cosine computed | All 616 pairs | ☐ |
| Random seed set | Documented | ☐ |

---

## 5. Stage 3: Dual Evaluation (Human + LLM Review)

### 5.1 Overview

| Evaluator | Scope | Output |
|-----------|-------|--------|
| Human expert | 120 answers | Ground truth ratings |
| LLM judge | 120 answers | Automated ratings |

**Goal:** Create ground truth and validate automated evaluation methods.

### 5.2 Evaluation Materials

#### 5.2.1 Materials Provided per Case

| Material | Human | LLM Judge |
|----------|-------|-----------|
| ToxTemp question text | ✓ | ✓ |
| ToxTemp section context | ✓ | ✓ |
| Source document (PDF/text) | ✓ | ✓ |
| Model-generated answer | ✓ | ✓ |
| Model identity | ✗ Blinded | N/A |
| Inter-model cosine score | ✗ Blinded | N/A |
| Stratum assignment | ✗ Blinded | N/A |
| Other model answers | ✗ Not shown | N/A |

#### 5.2.2 Blinding Protocol

| Phase | Model Identity | Cosine Score | Stratum |
|-------|----------------|--------------|---------|
| Human evaluation | Blinded | Blinded | Blinded |
| Initial analysis | Blinded | Unblinded | Unblinded |
| Full analysis | Unblinded | Unblinded | Unblinded |

### 5.3 Human Evaluation Protocol

## 7. Deliverables

### 7.1 Datasets

| Dataset | Rows | Key Columns |
|---------|------|-------------|
| Full evaluation data | 3,696 | All Stage 1 metrics |
| Sampled dataset | 120 | Human + LLM ratings |
| Ground truth | 120 | Final labels |

---

## 8. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Insufficient high/low cosine cases | Verify in Stage 1; adjust thresholds |
| Evaluator fatigue | Break into sessions; pilot first 10 cases |
| Model coverage gaps | Model-stratified stratum guarantees minimum |
| Assay coverage gaps | Assay-stratified stratum guarantees minimum |

---

## 10. References

1. Fisch, A., et al. (2024). Stratified Prediction-Powered Inference for Hybrid Language Model Evaluation. *NeurIPS 2024*.

2. Merlo, S., et al. (2026). Reducing Human Effort to Validate LLM Relevance Judgements via Stratified Sampling. *ECIR 2026*.

3. Yang, Y., et al. (2015). Multi-Class Active Learning by Uncertainty Sampling with Diversity Maximization. *International Journal of Computer Vision*.

4. Es, S., et al. (2024). RAGAS: Automated Evaluation of Retrieval Augmented Generation. *EACL 2024*.

---

## Appendix A: Sampling Diagram

```
                              Total Pool
                             (n = 3,696)
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │       Exclude Refusals       │
                   └──────────────────────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │   Calculate Inter-Model      │
                   │   Cosine Similarity          │
                   │   (per question-assay pair)  │
                   └──────────────────────────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
    ┌─────────────┐       ┌─────────────┐       ┌─────────────┐
    │   RANDOM    │       │   COSINE    │       │  DIVERSITY  │
    │  BASELINE   │       │ STRATIFIED  │       │ GUARANTEED  │
    │   n = 36    │       │   n = 48    │       │   n = 36    │
    │   (30%)     │       │   (40%)     │       │   (30%)     │
    └─────────────┘       └─────────────┘       └─────────────┘
           │                      │                      │
           │              ┌───────┴───────┐              │
           │              ▼               ▼              │
           │       ┌───────────┐   ┌───────────┐         │
           │       │    LOW    │   │   HIGH    │         │
           │       │  COSINE   │   │  COSINE   │         │
           │       │  n = 24   │   │  n = 24   │         │
           │       └───────────┘   └───────────┘         │
           │                                             │
           │                                     ┌───────┴───────┐
           │                                     ▼               ▼
           │                              ┌───────────┐   ┌───────────┐
           │                              │   ASSAY   │   │   MODEL   │
           │                              │  3 × 8    │   │  2 × 6    │
           │                              │  n = 24   │   │  n = 12   │
           │                              └───────────┘   └───────────┘
           │                                                     │
           └──────────────────────┬──────────────────────────────┘
                                  ▼
                      ┌───────────────────────┐
                      │     FINAL SAMPLE      │
                      │       n = 120         │
                      └───────────────────────┘
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │   DUAL EVALUATION     │
                      │  Human + LLM Judge    │
                      └───────────────────────┘
 
---
