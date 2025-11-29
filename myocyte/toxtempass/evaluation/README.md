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
python manage.py run_evals --skip-tier2

# Skip Tier 1, only run Tier 2
python manage.py run_evals --skip-tier1
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
│   └── validation_pipeline_tier1.py
├── negative_control/
│   └── validation_pipeline_tier2.py
└── README.md                    # This file

management/commands/
└── run_evals.py                 # Django management command entry point
```

### Configuration Options

The `EvaluationConfig` class in `config.py` contains:

#### Path Configuration
```python
# Tier 1 Paths
tier1_processed_scored = repo_root / "test-results" / "Tier1" / "processed" / "scored"
tier1_raw = repo_root / "test-results" / "Tier1" / "raw"
tier1_output = repo_root / "test-results" / "Tier1_results"

# Tier 2 Paths
tier2_input = repo_root / "test-results" / "Tier2"
tier2_output = repo_root / "test-results" / "Tier2_results"
```

#### Model Configuration
```python
default_models = [
    {"name": "gpt-4o-mini", "temperature": 0},
    {"name": "gpt-4.1-nano", "temperature": 0},
    {"name": "o3-mini", "temperature": None},
]
```

#### Evaluation Settings
```python
extract_images = True
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

## Pre-defined Experiments

### baseline
- **Models**: gpt-4o-mini (temp=0)
- **Purpose**: Quick baseline test with single model
- **Use case**: Fast validation or debugging

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
