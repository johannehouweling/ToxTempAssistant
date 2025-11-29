from django.core.management.base import BaseCommand

from toxtempass.evaluation.negative_control.validation_pipeline_tier2 import (
    run as run_tier2,
)
from toxtempass.evaluation.positive_control.validation_pipeline_tier1 import (
    run as run_tier1,
)
from toxtempass.evaluation.config import config as eval_config


class Command(BaseCommand):
    help = (
        "Run Tier1 (positive control) then Tier2 (negative control) evaluation pipelines. "
        "Use --list-experiments to see available experiment configurations."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--question-set-label",
            dest="question_set_label",
            help="Optional QuestionSet label to use; defaults to latest visible set.",
        )
        parser.add_argument(
            "--experiment",
            help="Experiment name to run (from config). If not specified, uses default models.",
        )
        parser.add_argument(
            "--list-experiments",
            action="store_true",
            help="List available experiments and exit.",
        )
        parser.add_argument(
            "--repeat",
            action="store_true",
            help="Re-run even if output already exists for a model.",
        )
        parser.add_argument(
            "--skip-tier1",
            action="store_true",
            help="Skip Tier1 (positive control) run.",
        )
        parser.add_argument(
            "--skip-tier2",
            action="store_true",
            help="Skip Tier2 (negative control) run.",
        )

    def handle(self, *args, **options):
        # List experiments and exit if requested
        if options.get("list_experiments"):
            self.stdout.write(self.style.SUCCESS("Available experiments:"))
            for name, desc in eval_config.list_experiments().items():
                self.stdout.write(f"  {name}: {desc}")
            return

        question_set_label = options.get("question_set_label")
        experiment = options.get("experiment")
        repeat = options.get("repeat", False)
        skip_tier1 = options.get("skip_tier1", False)
        skip_tier2 = options.get("skip_tier2", False)

        # Validate experiment if provided
        if experiment and experiment not in eval_config.experiments:
            self.stdout.write(
                self.style.ERROR(
                    f"Unknown experiment '{experiment}'. "
                    f"Use --list-experiments to see available options."
                )
            )
            return

        if experiment:
            self.stdout.write(
                self.style.SUCCESS(f"Running experiment: {experiment}")
            )
            self.stdout.write(
                f"Description: {eval_config.experiments[experiment]['description']}"
            )

        if not skip_tier1:
            self.stdout.write(self.style.SUCCESS("Starting Tier1 (positive control)..."))
            run_tier1(
                question_set_label=question_set_label,
                repeat=repeat,
                experiment=experiment,
            )

        if not skip_tier2:
            self.stdout.write(self.style.SUCCESS("Starting Tier2 (negative control)..."))
            run_tier2(
                question_set_label=question_set_label,
                repeat=repeat,
                experiment=experiment,
            )
        
        self.stdout.write(self.style.SUCCESS("Evaluation complete!"))
