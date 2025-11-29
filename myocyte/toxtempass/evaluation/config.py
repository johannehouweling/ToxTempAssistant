"""Centralized configuration for evaluation pipelines."""
from pathlib import Path
from typing import TypedDict


class ModelConfig(TypedDict):
    """Configuration for a single model."""
    name: str
    temperature: float | None


class ExperimentConfig(TypedDict):
    """Configuration for an experiment."""
    models: list[ModelConfig]
    description: str


class EvaluationConfig:
    """Centralized configuration for evaluation pipelines.
    
    This class provides a single source of truth for:
    - File paths for input/output
    - Model configurations
    - Evaluation parameters
    - Pre-defined experiments
    """
    
    # Path Configuration
    repo_root = Path(__file__).resolve().parents[3]
    
    # Tier 1 Paths (Positive Control)
    tier1_processed_scored = repo_root / "test-results" / "Tier1" / "processed" / "scored"
    tier1_raw = repo_root / "test-results" / "Tier1" / "raw"
    tier1_output = repo_root / "test-results" / "Tier1_results"
    
    # Tier 2 Paths (Negative Control)
    tier2_input = repo_root / "test-results" / "Tier2"
    tier2_output = repo_root / "test-results" / "Tier2_results"
    
    # Default Model Configuration
    # These are the models used when no experiment is specified
    default_models: list[ModelConfig] = [
        {"name": "gpt-4o-mini", "temperature": 0},
        {"name": "gpt-4.1-nano", "temperature": 0},
        {"name": "o3-mini", "temperature": None},
    ]
    
    # Tier-specific model overrides (None means use default_models)
    tier1_models: list[ModelConfig] | None = None
    tier2_models: list[ModelConfig] | None = None
    
    # Pre-defined Experiments
    # Add new experiments here to easily run different configurations
    experiments: dict[str, ExperimentConfig] = {
        "baseline": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None}
            ],
            "description": "Baseline experiment with 3 models (TTA paper 1) temp=0)"
        },
        "temperature_sweep": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4o-mini", "temperature": 0.3},
                {"name": "gpt-4o-mini", "temperature": 0.7},
                {"name": "gpt-4o-mini", "temperature": 1.0},
            ],
            "description": "Test temperature sensitivity on gpt-4o-mini"
        },
        "model_comparison": {
            "models": [
                {"name": "gpt-4o", "temperature": 0},
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
            ],
            "description": "Compare different model families at temp=0"
        },
        "full_suite": {
            "models": [
                {"name": "gpt-4o", "temperature": 0},
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
            ],
            "description": "Full model suite evaluation"
        },
    }
    
    # Evaluation Settings
    extract_images: bool = True
    validation_metrics: list[str] = [
        "cos_similarity", 
        "bert_precision", 
        "bert_recall", 
        "bert_f1"
    ]
    cos_similarity_threshold: float = 0.7
    
    @classmethod
    def get_models(
        cls, 
        tier: int | None = None, 
        experiment: str | None = None
    ) -> list[ModelConfig]:
        """Get model configuration for a tier or experiment.
        
        Args:
            tier: Tier number (1 or 2). If specified, checks for tier-specific overrides.
            experiment: Experiment name. If specified, uses experiment configuration.
            
        Returns:
            List of model configurations to use.
            
        Priority order:
            1. Experiment configuration (if specified)
            2. Tier-specific override (if specified and available)
            3. Default models
        """
        # Experiment configuration takes priority
        if experiment:
            if experiment not in cls.experiments:
                raise ValueError(
                    f"Unknown experiment '{experiment}'. "
                    f"Available: {', '.join(cls.experiments.keys())}"
                )
            return cls.experiments[experiment]["models"]
        
        # Tier-specific override
        if tier == 1 and cls.tier1_models is not None:
            return cls.tier1_models
        if tier == 2 and cls.tier2_models is not None:
            return cls.tier2_models
        
        # Default models
        return cls.default_models
    
    @classmethod
    def list_experiments(cls) -> dict[str, str]:
        """Get a dictionary of experiment names and descriptions."""
        return {
            name: exp["description"] 
            for name, exp in cls.experiments.items()
        }


# Singleton instance for easy import
config = EvaluationConfig()
