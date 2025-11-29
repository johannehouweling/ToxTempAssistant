# Evaluation Pipeline Documentation

This directory contains the evaluation pipelines for ToxTempAssistant, including centralized configuration for easy experiment management.

## Overview

The evaluation system consists of:
- **Tier 1 (Positive Control)**: Tests LLM accuracy against ground truth data
- **Tier 2 (Negative Control)**: Tests that LLM correctly identifies when answers cannot be found
- **Centralized Configuration**: Single source of truth for paths, models, and experiments

## Quick Start

### List Available Experiments

```bash
python manage.py run_evals --list-experiments
```

### Run Default Configuration

```bash
# Run both tiers with default models
python manage.py run_evals
```

### Run a Specific Experiment

```bash
# Run the baseline experiment (single model)
python manage.py run_evals --experiment baseline

# Run temperature sweep experiment
python manage.py run_evals --experiment temperature_sweep

# Run model comparison
python manage.py run_evals --experiment model_comparison
```

### Run Only One Tier

```bash
# Skip Tier 2, only run Tier 1
python manage.py run_evals --skip-ncontrol

# Skip Tier 1, only run Tier 2
python manage.py run_evals --skip-pcontrol
```

### Force Re-run

```bash
# Re-run even if results already exist
python manage.py run_evals --repeat
```

## Configuration System

All configuration is centralized in `evaluation/config.py`.

### File Structure

```
evaluation/
├── config.py                    # Central configuration
├── positive_control/
│   └── pcontrol.py
├── negative_control/
│   └── ncontrol.py
└── README.md                    # This file

management/commands/
└── run_evals.py                 # Django management command entry point
```

### Configuration Options

The `EvaluationConfig` class in `config.py` contains:

#### Path Configuration
```python
# output negative control
ncontrol_output = eval_root / "negative_control" / "output"

# output positive control
pcontrol_output = eval_root / "positive_control" / "output"
```

#### Model Configuration
```python
default_models = [
    {"name": "gpt-4o-mini", "temperature": 0},
    {"name": "gpt-4.1-nano", "temperature": 0},
    {"name": "o3-mini", "temperature": None},
]
```

#### Image Extraction
Image extraction is now controlled per-experiment. By default, images are NOT extracted unless explicitly enabled in an experiment configuration:

```python
"baseline_with_images": {
    "models": [...],
    "description": "...",
    "extract_images": True,  # Enable image extraction for this experiment
}
```

#### Validation Settings
```python
validation_metrics = ["cos_similarity", "bert_precision", "bert_recall", "bert_f1"]
cos_similarity_threshold = 0.7
```

## Creating Custom Experiments

To create a new experiment, add an entry to the `experiments` dictionary in `config.py`:

```python
experiments = {
    # ... existing experiments ...
    
    "my_custom_experiment": {
        "models": [
            {"name": "gpt-4o", "temperature": 0},
            {"name": "gpt-4o", "temperature": 0.5},
        ],
        "description": "Test gpt-4o at different temperatures"
    }
}
```

Then run it:
```bash
python manage.py run_evals --experiment my_custom_experiment
```

### Experiments with Custom Prompts

You can override the default prompts for specific experiments by adding `base_prompt` and/or `image_prompt` fields:

```python
experiments = {
    "prompt_experiment": {
        "models": [
            {"name": "gpt-4o-mini", "temperature": 0},
        ],
        "description": "Test modified prompt wording",
        "base_prompt": """
        You are a scientific assistant...
        [Your custom base prompt here]
        """,
        "image_prompt": "You are an image analyzer...[custom image prompt]"
    }
}
```

- `base_prompt`: Overrides the default question-answering prompt
- `image_prompt`: Overrides the default image description prompt

If not specified, experiments use the default prompts defined in `EvaluationConfig`.

## Pre-defined Experiments

### baseline
- **Models**: gpt-4o-mini, gpt-4.1-nano, o3-mini (all at temp=0)
- **Images**: Disabled (default)
- **Purpose**: Baseline evaluation without image extraction
- **Use case**: Fast validation or text-only testing

### baseline_with_images
- **Models**: gpt-4o-mini, gpt-4.1-nano, o3-mini (all at temp=0)
- **Images**: Enabled
- **Purpose**: Baseline evaluation with image extraction and description
- **Use case**: Testing image-aware LLM capabilities

Run with:
```bash
python manage.py run_evals --experiment baseline_with_images
```

### temperature_sweep
- **Models**: gpt-4o-mini at temperatures 0, 0.3, 0.7, 1.0
- **Purpose**: Test temperature sensitivity
- **Use case**: Understanding how temperature affects answer quality

### model_comparison
- **Models**: gpt-4o, gpt-4o-mini, gpt-4.1-nano (all at temp=0)
- **Purpose**: Compare different model families
- **Use case**: Selecting the best model for production

### full_suite
- **Models**: gpt-4o, gpt-4o-mini, gpt-4.1-nano, o3-mini
- **Purpose**: Comprehensive evaluation across all models
- **Use case**: Full regression testing or research

## Output Structure

Results are organized by model and temperature:

```
test-results/
├── Tier1_results/
│   ├── gpt-4o-mini/
│   │   └── tier1_summary_YYYYMMDD_HHMM.json
│   ├── gpt-4o-mini_temp0.3/
│   │   └── tier1_summary_YYYYMMDD_HHMM.json
│   └── ...
└── Tier2_results/
    ├── gpt-4o-mini/
    │   └── tier2_summary_YYYYMMDD_HHMM.json
    └── ...
```

### Summary File Contents

Each summary JSON file includes experiment metadata for traceability:

```json
{
    "timestamp": "20241129_1830",
    "experiment": "baseline",
    "model": "gpt-4o-mini",
    "temperature": 0,
    "prompt_hash": "4aa6ca3f",
    "prompts": {
        "base_prompt": "You are an agent...",
        "image_prompt": "You are a scientific assistant..."
    },
    "records": [...]
}
```

The `prompt_hash` allows quick comparison of which prompt version was used across experiments.

## Advanced Usage

### Custom Paths

The Django management command uses the centralized paths from `config.py`. To use custom paths, you can:
1. Modify the paths in `evaluation/config.py`, or
2. Set tier-specific overrides in the config

Note: The management command does not currently support CLI path overrides, but you can easily add this if needed.

### Custom Question Set

Use a specific question set:

```bash
python manage.py run_evals --question-set-label "v2.0"
```

### Combining Options

```bash
# Run only Tier 1, with temperature_sweep experiment, forcing re-run
python manage.py run_evals \
    --experiment temperature_sweep \
    --skip-tier2 \
    --repeat
```

## Tier-Specific Model Overrides

If you want different models for Tier 1 vs Tier 2, you can set tier-specific overrides in `config.py`:

```python
# These override default_models for specific tiers
tier1_models = [
    {"name": "gpt-4o-mini", "temperature": 0},
]

tier2_models = [
    {"name": "gpt-4o", "temperature": 0},
]
```

Priority order for model selection:
1. Experiment configuration (if `--experiment` is specified)
2. Tier-specific override (if set in config)
3. Default models

## Best Practices

### For Development
```bash
# Quick test with single model
python manage.py run_evals --experiment baseline
```

### For Research
```bash
# Full evaluation across all models
python manage.py run_evals --experiment full_suite
```

### For CI/CD
```bash
# Automated testing with repeat to ensure fresh results
python manage.py run_evals --experiment baseline --repeat
```

### For Temperature Studies
```bash
# Dedicated temperature sweep
python manage.py run_evals --experiment temperature_sweep
```

## Troubleshooting

### Experiment Not Found
```
Error: Unknown experiment 'my_exp'
```
**Solution**: Use `--list-experiments` to see available experiments, or add your experiment to `config.py`.

### Output Already Exists
Results are skipped if output directory contains `tier*_summary*.json` files.

**Solution**: Use `--repeat` flag to force re-run.

### Missing API Keys
```
ERROR: Required environment variables are missing
```
**Solution**: Ensure `OPENAI_API_KEY` or `OPENROUTER_API_KEY` is set in your `.env` file.

## Contributing

When adding new experiments or modifying the configuration:

1. Update the `experiments` dictionary in `config.py`
2. Add a description explaining the purpose
3. Test your changes with `--list-experiments`
4. Update this README if needed

## Related Files

- `config.py` - Central configuration
- `positive_control/validation_pipeline_tier1.py` - Tier 1 implementation
- `negative_control/validation_pipeline_tier2.py` - Tier 2 implementation
- `../management/commands/run_evals.py` - Django management command entry point
