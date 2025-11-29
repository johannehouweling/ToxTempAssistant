"""Convenience runner that wires relative paths for Tier1 and Tier2 evaluations."""
from pathlib import Path

from toxtempass.evaluation.positive_control.validation_pipeline_tier1 import run as run_tier1
from toxtempass.evaluation.negative_control.validation_pipeline_tier2 import run as run_tier2


def get_paths() -> dict[str, Path]:
    """Return repo-relative paths for inputs/outputs."""
    repo_root = Path(__file__).resolve().parents[3]
    return {
        "tier1_processed_scored": repo_root / "test-results" / "Tier1" / "processed" / "scored",
        "tier1_raw": repo_root / "test-results" / "Tier1" / "raw",
        "tier1_output": repo_root / "test-results" / "Tier1_results",
        "tier2_input": repo_root / "test-results" / "Tier2",
        "tier2_output": repo_root / "test-results" / "Tier2_results",
    }


def main(question_set_label: str | None = None, repeat: bool = False) -> None:
    paths = get_paths()
    run_tier1(
        question_set_label=question_set_label,
        repeat=repeat,
        processed_scored_dir=paths["tier1_processed_scored"],
        raw_dir=paths["tier1_raw"],
        output_base_dir=paths["tier1_output"],
    )
    run_tier2(
        question_set_label=question_set_label,
        repeat=repeat,
        input_dir=paths["tier2_input"],
        output_base_dir=paths["tier2_output"],
    )


if __name__ == "__main__":
    main()
