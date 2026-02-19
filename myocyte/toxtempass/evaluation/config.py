"""Centralized configuration for evaluation pipelines."""

import hashlib
from typing import TypedDict

from myocyte.settings import BASE_DIR

from toxtempass import Config as AppConfig


class ModelConfig(TypedDict):
    """Configuration for a single model."""

    name: str
    temperature: float | None


class PromptConfig(TypedDict):
    """Configuration for prompts used in an experiment."""

    base_prompt: str
    image_prompt: str


class ExperimentConfig(TypedDict, total=False):
    """Configuration for an experiment.

    Required fields:
        models: List of model configurations to use
        description: Human-readable description of the experiment

    Optional fields:
        base_prompt: Custom base prompt (overrides default)
        image_prompt: Custom image description prompt (overrides default)
        extract_images: Whether to extract and process images from PDFs (overrides default)
        validation_metrics: List of metric names to compute (overrides default)
    """

    models: list[ModelConfig]
    description: str
    base_prompt: str
    image_prompt: str
    extract_images: bool
    validation_metrics: list[str]


class EvaluationConfig:
    """Centralized configuration for evaluation pipelines.

    This class provides a single source of truth for:
    - File paths for input/output
    - Model configurations
    - Evaluation parameters
    - Pre-defined experiments
    """

    eval_root = BASE_DIR / "toxtempass" / "evaluation"

    # Tier 1 Paths (Positive Control)
    ncontrol_input = eval_root / "negative_control" / "input_files"
    ncontrol_output = eval_root / "negative_control" / "output"
    ncontrol_output_input_scores = (
        eval_root / "negative_control" / "output" / "input_scores"
    )

    # Tier 2 Paths (Negative Control)
    pcontrol_input = eval_root / "positive_control" / "input_files"
    pcontrol_processed_input = (
        eval_root / "positive_control" / "input_files" / "processed"
    )
    pcontrol_output = eval_root / "positive_control" / "output"

    # Tier 3 Paths (realworld scenarios)
    realworld_input = eval_root / "realworld_files" / "input_files"
    realworld_output = eval_root / "realworld_files" / "output"

    # Mark sure input files exists:
    for path in [ncontrol_input, pcontrol_input, realworld_input]:
        if path.is_dir() and any(path.glob("*.pdf")):
            pass
        else:
            raise FileNotFoundError(f"Input PDF files in folder not found: {path}")

    # Make sure paths output path exist
    for path in [
        ncontrol_output,
        ncontrol_output_input_scores,
        pcontrol_output,
        realworld_output
    ]:
        if not path.exists():
            path.mkdir(parents=True)

    # Default Model Configuration
    # These are the models used when no experiment is specified
    default_experiment: list[ModelConfig] = [
        {"name": "gpt-4o-mini", "temperature": 0},
        {"name": "gpt-4.1-nano", "temperature": 0},
        {"name": "o3-mini", "temperature": None},
    ]

    # Tier-specific model overrides (None means use default_models)
    tier1_models: list[ModelConfig] | None = None
    tier2_models: list[ModelConfig] | None = None
    tier3_models: list[ModelConfig] | None = None

    # Pre-defined Experiments
    # Add new experiments here to easily run different configurations
    experiments: dict[str, ExperimentConfig] = {
        "test_experiment": {
            "models": [{"name": "gpt-5-nano", "temperature": None}],
            "description": "To test if this workflow works",
        },
        "baseline": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
            ],
            "description": "Baseline experiment with 3 models (TTA paper 1) temp=0)",
        },
        "baseline_with_bert": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
            ],
            "description": "Baseline experiment with 3 models (TTA paper 1) temp=0)",
            "validation_metrics": [
                "cos_similarity",
                "bert_precision",
                "bert_recall",
                "bert_f1",
            ],
        },
        "baseline_with_images": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
            ],
            "description": "Baseline with image extraction enabled (3 models, temp=0)",
            "extract_images": True,
        },
        "temperature_sweep": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4o-mini", "temperature": 0.3},
                {"name": "gpt-4o-mini", "temperature": 0.7},
                {"name": "gpt-4o-mini", "temperature": 1.0},
            ],
            "description": "Test temperature sensitivity on gpt-4o-mini",
        },
        "model_comparison": {
            "models": [
                {"name": "gpt-4o", "temperature": 0},
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
            ],
            "description": "Compare different model families at temp=0",
        },
        "full_suite": {
            "models": [
                {"name": "gpt-4o", "temperature": 0},
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
            ],
            "description": "Full model suite evaluation",
        },
        "test_experiment_2": {
            "models": [{"name": "gpt-5-mini", "temperature": None}],
            "description": "To test if this workflow of Christophe works and test gpt-5-mini",
            "validation_metrics": ["cos_similarity"],
        },
        "model_comparison_with_images": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
                {"name": "gpt-5-mini", "temperature": None},
            ],
            "description": "Comparing the cosine similarity and faithfullness of different models with images on",
            "validation_metrics": [
                "cos_similarity",
                "faithfulness"
            ],
            "extract_images": True,
        },
        "input_type_comparison": {
            "models": [
                {"name": "gpt-4o-mini", "temperature": 0},
                {"name": "gpt-4.1-nano", "temperature": 0},
                {"name": "o3-mini", "temperature": None},
                {"name": "gpt-5-mini", "temperature": None},
                {"name": "gpt-5-nano", "temperature": None}
            ],
            "description": "comparing different input document types (e.g., lab protocol, published paper, technical manual) with each other. Looking at how many questions can be answered per document type and model."
            # "validation_metrics": [
            #     "cos_similarity",
            #     "faithfulness"
            # ],
        #     "extract_images": True,
        #     "input": None # still have to input the documents/ figure out how to change the input from the standard
        }
    }

    # Evaluation Settings
    # Note: extract_images can be overridden per-experiment; metrics can be too if desired.
    # Default metrics exclude BERT to keep runs fast; add bert_* if you need them.
    validation_metrics: list[str] = ["cos_similarity"]
    cos_similarity_threshold: float = 0.7

    # Default Prompts - imported from the main app Config to ensure consistency
    # between production app and evaluation pipeline
    not_found_string: str = AppConfig.not_found_string
    default_base_prompt: str = AppConfig.base_prompt
    default_image_prompt: str = AppConfig.image_description_prompt

    @classmethod
    def get_models(
        cls, tier: int | None = None, experiment: str | None = None
    ) -> list[ModelConfig]:
        """Get model configuration for a tier or experiment.

        Args:
            tier: Tier number (1, 2 or 3). If specified, checks for tier-specific overrides.
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
        if tier == 3 and cls.tier2_models is not None:
            return cls.tier3_models

        # Default models
        return cls.default_experiment

    @classmethod
    def list_experiments(cls) -> dict[str, str]:
        """Get a dictionary of experiment names and descriptions."""
        return {name: exp["description"] for name, exp in cls.experiments.items()}

    @classmethod
    def get_prompts(cls, experiment: str | None = None) -> PromptConfig:
        """Get prompt configuration for an experiment.

        Args:
            experiment: Experiment name. If specified, checks for experiment-specific prompts.

        Returns:
            PromptConfig with base_prompt and image_prompt.

        Priority order:
            1. Experiment-specific prompt (if specified in experiment config)
            2. Default prompts

        """
        base_prompt = cls.default_base_prompt
        image_prompt = cls.default_image_prompt

        if experiment and experiment in cls.experiments:
            exp_config = cls.experiments[experiment]
            if "base_prompt" in exp_config:
                base_prompt = exp_config["base_prompt"]
            if "image_prompt" in exp_config:
                image_prompt = exp_config["image_prompt"]

        return {
            "base_prompt": base_prompt,
            "image_prompt": image_prompt,
        }

    @classmethod
    def get_prompt_hash(cls, experiment: str | None = None) -> str:
        """Get a short hash of the prompts for tracking purposes.

        This helps identify which prompt version was used in results.
        """
        prompts = cls.get_prompts(experiment)
        combined = prompts["base_prompt"] + prompts["image_prompt"]
        return hashlib.md5(combined.encode()).hexdigest()[:8]

    @classmethod
    def get_extract_images(cls, experiment: str | None = None) -> bool:
        """Get the extract_images setting for an experiment.

        Args:
            experiment: Experiment name. If specified, checks for experiment-specific setting.

        Returns:
            Boolean indicating whether to extract images from PDFs.

        Priority order:
            1. Experiment-specific setting (if specified in experiment config)
            2. Default: False (images not extracted unless explicitly enabled in experiment)
        """
        if experiment and experiment in cls.experiments:
            exp_config = cls.experiments[experiment]
            if "extract_images" in exp_config:
                return exp_config["extract_images"]
        return False

    @classmethod
    def get_validation_metrics(cls, experiment: str | None = None) -> list[str]:
        """Get validation metrics for an experiment or default."""
        if experiment and experiment in cls.experiments:
            exp_config = cls.experiments[experiment]
            if "validation_metrics" in exp_config:
                return exp_config["validation_metrics"]
        return cls.validation_metrics

    @classmethod
    def summarize_experiment_config(
        cls, experiment: str | None = None, tier: int | None = None, style=None
    ) -> str:
        """Generate a styled summary of experiment configuration for console output.

        Args:
            experiment: Experiment name to summarize. If None, uses default config.
            tier: Tier number (1, 2 or 3) for displaying appropriate IO paths.
            style: Optional Django style object (from self.style in management commands).
                   If provided, uses built-in styles like HTTP_INFO, WARNING, etc.
                   If not provided, returns unstyled output.

        Returns:
            Formatted string with styled output suitable for stdout.write() or print().

        Example usage in a Django management command:
            output = EvaluationConfig.summarize_experiment_config(
                experiment="baseline",
                tier=1,
                style=self.style
            )
            self.stdout.write(output)
        """
        if style is None:
            # Fallback: create a simple style object that doesn't apply styling
            class NoStyle:
                def __call__(self, text):
                    return text

                HTTP_INFO = __call__
                WARNING = __call__
                ERROR = __call__
                SUCCESS = __call__

            style = NoStyle()

        lines = []
        border = "═" * 70

        # Title section
        lines.append(style.HTTP_INFO(border))
        if experiment:
            exp_config = cls.experiments.get(experiment)
            if exp_config:
                lines.append(style.HTTP_INFO(f"  EXPERIMENT: {experiment}"))
                lines.append(style.HTTP_INFO(border))
                lines.append(
                    f"{style.WARNING('Description:')} {exp_config['description']}"
                )
            else:
                lines.append(style.ERROR(f"  Unknown experiment: {experiment}"))
                lines.append(style.HTTP_INFO(border))
                return "\n".join(lines)
        else:
            lines.append(style.HTTP_INFO("  DEFAULT CONFIGURATION"))
            lines.append(style.HTTP_INFO(border))

        # Models section
        models = cls.get_models(tier=tier, experiment=experiment)
        lines.append("")
        lines.append(style.WARNING("MODELS:"))
        for model in models:
            temp_str = (
                f"{model['temperature']}"
                if model["temperature"] is not None
                else "N/A (reasoning model)"
            )
            lines.append(
                f"  {style.SUCCESS('•')} {model['name']} {style.HTTP_INFO(f'(temperature: {temp_str})')}"
            )

        # Settings section
        lines.append("")
        lines.append(style.WARNING("SETTINGS:"))
        extract_images = cls.get_extract_images(experiment)
        lines.append(
            f"  Extract Images: {style.SUCCESS('Yes') if extract_images else style.ERROR('No')}"
        )
        prompt_hash = cls.get_prompt_hash(experiment)
        prompt_note = ""
        if experiment and experiment in cls.experiments:
            exp_config = cls.experiments[experiment]
            if "base_prompt" in exp_config or "image_prompt" in exp_config:
                prompt_note = " (custom prompts)"
        lines.append(f"  Prompt Hash: {style.HTTP_INFO(prompt_hash + prompt_note)}")

        # Evaluation Metrics section
        lines.append("")
        lines.append(style.WARNING("EVALUATION METRICS:"))
        metrics_str = ", ".join(cls.get_validation_metrics(experiment))
        lines.append(f"  Metrics: {style.HTTP_INFO(metrics_str)}")
        lines.append(
            f"  Cosine Similarity Threshold: {style.HTTP_INFO(str(cls.cos_similarity_threshold))}"
        )

        # IO Paths section
        lines.append("")
        lines.append(style.WARNING("IO PATHS:"))
        if tier == 1:
            lines.append(f"  Input:  {style.HTTP_INFO(str(cls.pcontrol_input))}")
            lines.append(f"  Output: {style.HTTP_INFO(str(cls.pcontrol_output))}")
        elif tier == 2:
            lines.append(f"  Input:  {style.HTTP_INFO(str(cls.ncontrol_input))}")
            lines.append(f"  Output: {style.HTTP_INFO(str(cls.ncontrol_output))}")
        elif tier == 3:
            lines.append(f"  Input: {style.HTTP_INFO(str(cls.realworld_input))}")
            lines.append(f"  Output: {style.HTTP_INFO(str(cls.realworld_output))}")
        else:
            lines.append(f"  Tier 1 Input:  {style.HTTP_INFO(str(cls.pcontrol_input))}")
            lines.append(f"  Tier 1 Output: {style.HTTP_INFO(str(cls.pcontrol_output))}")
            lines.append(f"  Tier 2 Input:  {style.HTTP_INFO(str(cls.ncontrol_input))}")
            lines.append(f"  Tier 2 Output: {style.HTTP_INFO(str(cls.ncontrol_output))}")
            lines.append(f"  Tier 3 Input: {style.HTTP_INFO(str(cls.realworld_input))}")
            lines.append(f"  Tier 3 Output: {style.HTTP_INFO(str(cls.realworld_output))}")


        lines.append(style.HTTP_INFO(border))
        lines.append("")

        return "\n".join(lines)


# Singleton instance for easy import
config = EvaluationConfig()
