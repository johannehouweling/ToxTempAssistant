# Implementation Plan: RAGAS Faithfulness Integration

## Overview

Integrate RAGAS faithfulness verification into the ToxTempAssistant evaluation pipeline to address reviewer concerns about hallucinations (#25, #60) and validate the source-bounded prompt design. This implementation adds quantitative faithfulness metrics to evaluation results using the standardized RAGAS framework, providing citable evidence that generated answers are grounded in source documents.

## Types

### Faithfulness Result Structure
```python
# RAGAS returns SingleTurnSample with faithfulness_score attribute
from ragas.dataset_schema import SingleTurnSample

# Our extended structure for CSVs
FaithfulnessColumns = {
    'faithfulness_score': float,      # 0.0-1.0 from RAGAS
    'faithfulness_statements': int,    # Total claims decomposed
    'faithfulness_reason': str         # RAGAS reasoning text
}
```

### Config Extensions
```python
# In evaluation/config.py ExperimentConfig
class ExperimentConfig(TypedDict, total=False):
    # ... existing fields ...
    compute_faithfulness: bool  # Whether to compute faithfulness for this experiment
    faithfulness_model: str     # Model to use for faithfulness (default: gpt-4o-mini)
```

## Files

### New Files to Create

**1. myocyte/toxtempass/evaluation/post_processing/faithfulness_ragas.py**
- Purpose: RAGAS-based faithfulness evaluation functions
- Functions:
  - `faithfulness_score_async()` - Single row async evaluation
  - `add_faithfulness_columns()` - Add multiple faithfulness columns to DataFrame  
  - `summarize_faithfulness()` - Generate summary statistics
  - `faithfulness_score()` - Synchronous wrapper
- Integration: Matches existing pattern from `cosine_similarities.py`

**2. myocyte/toxtempass/migrations/0018_answer_evidence.py**
- Purpose: Django migration to add evidence field to Answer model
- Adds: `evidence_text` TextField to Answer model

### Files to Modify

**1. myocyte/toxtempass/models.py**
- Location: Answer class (around line 300)
- Modification: Add `evidence_text` field
```python
class Answer(AccessibleModel):
    # ... existing fields ...
    evidence_text = models.TextField(
        blank=True,
        default="",
        help_text="Extracted evidence/quotes used to generate this answer"
    )
```

**2. myocyte/toxtempass/llm.py**
- Location: Answer generation section
- Modification: Extract and store evidence from LLM output
- Parse evidence from response before storing answer_text

**3. myocyte/toxtempass/evaluation/post_processing/utils.py**
- Location: `generate_comparison_csv()` function (line ~20)
- Modification: Add `evidence` column to DataFrame from Answer.evidence_text
- Modification: Add `faithfulness_*` columns if experiment requests them

**4. myocyte/toxtempass/evaluation/config.py**
- Location: ExperimentConfig TypedDict (line ~20)
- Modification: Add `compute_faithfulness: bool` and `faithfulness_model: str` optional fields
- Location: Default experiments dict (line ~80)
- Modification: Add new experiment `"baseline_with_faithfulness"` demonstrating the feature

**5. myocyte/toxtempass/evaluation/positive_control/pcontrol.py**
- Location: After `generate_comparison_csv()` call (line ~100)
- Modification: Conditionally compute faithfulness if experiment config requests it
- Modification: Include faithfulness summary in output JSON

**6. pyproject.toml**
- Location: dependencies list (line ~30)
- Modification: Add `"ragas>=0.2.0,<0.3.0"` to dependencies

## Functions

### New Functions

**myocyte/toxtempass/evaluation/post_processing/faithfulness_ragas.py:**

**1. `async faithfulness_score_async(question: str, answer: str, evidence: str, model: str) -> dict`**
- Purpose: Compute RAGAS faithfulness for single Q/A pair
- Parameters:
  - `question`: ToxTemp question text
  - `answer`: LLM-generated answer
  - `evidence`: Evidence/context from documents
  - `model`: OpenAI model for judging (default: gpt-4o-mini)
- Returns: `{faithfulness_score: float, statements: int, reason: str}`
- Implementation: Uses RAGAS Faithfulness metric with AsyncOpenAI

**2. `add_faithfulness_columns(df: pd.DataFrame, model: str, question_col: str, answer_col: str, evidence_col: str) -> pd.DataFrame`**
- Purpose: Add faithfulness columns to evaluation DataFrame
- Parameters:
  - `df`: DataFrame with evaluation results
  - `model`: Model for faithfulness evaluation
  - `question_col`: Column name for questions (default: 'question')
  - `answer_col`: Column name for answers (default: 'llm_answer')
  - `evidence_col`: Column name for evidence (default: 'evidence')
- Returns: DataFrame with added columns: `faithfulness_score`, `faithfulness_statements`, `faithfulness_reason`
- Implementation: Uses `tqdm.pandas()` for progress, async batch processing

**3. `summarize_faithfulness(df: pd.DataFrame) -> dict`**
- Purpose: Generate summary statistics for faithfulness scores
- Parameters: DataFrame with faithfulness_score column
- Returns: Dict with mean, median, std, min, max, high/medium/low counts
- Used for: Manuscript results reporting

**4. `faithfulness_score(question: str, answer: str, evidence: str, model: str) -> dict`**
- Purpose: Synchronous wrapper for single evaluation
- Implementation: `asyncio.run(faithfulness_score_async(...))`

### Modified Functions

**myocyte/toxtempass/evaluation/post_processing/utils.py:**

**`generate_comparison_csv()` - lines ~20-100**
- Current: Extracts question and answer from QA pairs
- Modification: Also extract `evidence_text` from Answer model
- Add to DataFrame: `df['evidence'] = [ans.evidence_text for ans in answers]`
- After cosine similarity calculation: Optionally add faithfulness if requested
```python
# After cosine similarity section
if experiment and eval_config.get_compute_faithfulness(experiment):
    from toxtempass.evaluation.post_processing.faithfulness_ragas import add_faithfulness_columns
    model = eval_config.get_faithfulness_model(experiment)
    df = add_faithfulness_columns(df, model=model)
```

**myocyte/toxtempass/evaluation/positive_control/pcontrol.py:**

**`run()` - lines ~50-150**
- Current: Computes metrics, generates summary JSON
- Modification: After metrics aggregation, add faithfulness summary if computed
```python
# After agg_stats calculation
if eval_config.get_compute_faithfulness(experiment):
    from toxtempass.evaluation.post_processing.faithfulness_ragas import summarize_faithfulness
    faith_summary = summarize_faithfulness(df_passed)
    agg_stats['faithfulness'] = faith_summary
```

**myocyte/toxtempass/llm.py:**

**Answer generation section - location varies**
- Current: Stores only answer_text from LLM response
- Modification: Parse evidence from structured output, store in Answer.evidence_text
- Implementation depends on current LLM response format

## Classes

No new classes required. Modifications to existing:

**Answer model** (myocyte/toxtempass/models.py):
- Add field: `evidence_text = models.TextField(blank=True, default="")`

## Dependencies

### Add to pyproject.toml
```toml
dependencies = [
    # ... existing dependencies ...
    "ragas>=0.2.0,<0.3.0",
]
```

### Installation
```bash
poetry add ragas
```

## Testing

### Unit Tests
Create `myocyte/toxtempass/tests/test_faithfulness_ragas.py`:

```python
import pytest
import pandas as pd
from toxtempass.evaluation.post_processing.faithfulness_ragas import (
    faithfulness_score,
    add_faithfulness_columns,
    summarize_faithfulness
)

@pytest.mark.asyncio
async def test_faithfulness_perfect():
    """Test faithfulness with perfect match"""
    result = await faithfulness_score_async(
        question="What cell line is used?",
        answer="HepG2 cells are used",
        evidence='"HepG2 cells were used" (Source: Methods.pdf)',
        model="gpt-4o-mini"
    )
    assert result['faithfulness_score'] >= 0.95
    
@pytest.mark.asyncio
async def test_faithfulness_unfaithful():
    """Test faithfulness with contradictory evidence"""
    result = await faithfulness_score_async(
        question="Was validation performed?",
        answer="The assay was validated according to OECD guidelines",
        evidence='"No formal validation was performed" (Source: Methods.pdf)',
        model="gpt-4o-mini"
    )
    assert result['faithfulness_score'] < 0.5
```

### Integration Tests
- Test on small subset of positive control data
- Verify CSV contains faithfulness columns
- Verify summary JSON includes faithfulness metrics

### Manual Testing
1. Run evaluation on 1-2 documents: `python manage.py run_evals --experiment baseline_with_faithfulness --tier 1`
2. Check CSV has columns: `faithfulness_score`, `faithfulness_statements`, `faithfulness_reason`
3. Check summary JSON has faithfulness statistics
4. Verify faithfulness scores are reasonable (0.0-1.0 range)

## Implementation Order

### Step 1: Add Dependency
**File:** `pyproject.toml`
- Add `"ragas>=0.2.0,<0.3.0"` to dependencies list
- Run: `poetry lock && poetry install`
- Verify: `python -c "import ragas; print(ragas.__version__)"`

### Step 2: Add Evidence Field to Answer Model
**File:** `myocyte/toxtempass/models.py`
- Add field to Answer class:
```python
evidence_text = models.TextField(
    blank=True,
    default="",
    help_text="Extracted evidence/quotes used to generate this answer"
)
```
- Create migration: `python manage.py makemigrations`
- Apply migration: `python manage.py migrate`

### Step 3: Create RAGAS Faithfulness Module
**File:** `myocyte/toxtempass/evaluation/post_processing/faithfulness_ragas.py`
- Create new file with complete implementation
- Copy code from FAITHFULNESS_IMPLEMENTATION.md Section 1
- Test imports: `python -c "from toxtempass.evaluation.post_processing.faithfulness_ragas import faithfulness_score"`

### Step 4: Modify LLM Processing to Capture Evidence
**File:** `myocyte/toxtempass/llm.py`
- Locate answer generation section
- Add logic to parse and store evidence_text
- Test with single question to verify evidence is captured

### Step 5: Extend Evaluation Config
**File:** `myocyte/toxtempass/evaluation/config.py`
- Add optional fields to ExperimentConfig TypedDict
- Add getter methods:
  - `get_compute_faithfulness(experiment: str) -> bool`
  - `get_faithfulness_model(experiment: str) -> str`
- Add new experiment: `"baseline_with_faithfulness"`

### Step 6: Modify CSV Generation
**File:** `myocyte/toxtempass/evaluation/post_processing/utils.py`
- In `generate_comparison_csv()`:
  - Add evidence column from Answer.evidence_text
  - Conditionally compute faithfulness if experiment requests
- Test: Run on single document, verify CSV has evidence column

### Step 7: Integrate with Positive Control Pipeline
**File:** `myocyte/toxtempass/evaluation/positive_control/pcontrol.py`
- After metrics computation, add faithfulness summary if requested
- Test: Run `python manage.py run_evals --experiment baseline_with_faithfulness --tier 1`
- Verify: Summary JSON includes faithfulness metrics

### Step 8: Create Tests
**File:** `myocyte/toxtempass/tests/test_faithfulness_ragas.py`
- Create unit tests for faithfulness functions
- Run: `pytest myocyte/toxtempass/tests/test_faithfulness_ragas.py`

### Step 9: Documentation Update
**File:** `myocyte/toxtempass/evaluation/README.md`
- Add section on faithfulness evaluation
- Document experiment configuration options
- Add example usage

### Step 10: Full Integration Test
- Run full evaluation: `python manage.py run_evals --experiment baseline_with_faithfulness`
- Verify all outputs contain faithfulness metrics
- Check summary statistics are reasonable
- Review sample CSV rows for data quality

## Rollback Strategy

If issues arise:
1. **Config-based opt-in**: Faithfulness is opt-in per experiment, so existing experiments unaffected
2. **Migration reversible**: Django migration can be reversed: `python manage.py migrate toxtempass 0017`
3. **Module optional**: faithfulness_ragas.py is imported conditionally, won't break existing code
4. **Dependency isolated**: RAGAS only imported when needed, doesn't affect core app

## Success Criteria

- ✅ RAGAS dependency installed successfully
- ✅ Answer model has evidence_text field
- ✅ LLM processing captures evidence
- ✅ CSV generation includes evidence and faithfulness columns
- ✅ Evaluation config supports faithfulness experiments
- ✅ Full evaluation pipeline produces faithfulness metrics
- ✅ Tests pass
- ✅ Faithfulness scores are reasonable (mean ~0.90-0.95 for good answers)
- ✅ Ready for manuscript inclusion

## Manuscript Integration

After implementation, include in manuscript revision:

> "To address reviewer concerns about hallucinations (#25, #60), we implemented faithfulness verification using the RAGAS framework (v0.2.x), a standardized RAG evaluation library. The Faithfulness metric decomposes each generated answer into atomic claims and verifies each claim against the supporting evidence using an LLM-as-judge approach with GPT-4o-mini. Across our evaluation dataset (N=XXX answers), mean faithfulness was 0.9X±0.0X (median=0.9X, range=[0.XX-1.00]), with XX% achieving HIGH faithfulness (≥0.95), confirming effective source-grounding and minimal hallucination."
