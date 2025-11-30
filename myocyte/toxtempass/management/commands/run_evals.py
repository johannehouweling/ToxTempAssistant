from django.core.management.base import BaseCommand

from toxtempass.evaluation.config import config as eval_config
from toxtempass.evaluation.negative_control.ncontrol import (
    run as run_ncontrol,
)
from toxtempass.evaluation.positive_control.pcontrol import (
    run as run_pcontrol,
)


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
            "--skip-pcontrol",
            action="store_true",
            help="Skip positive control run.",
        )
        parser.add_argument(
            "--skip-ncontrol",
            action="store_true",
            help="Skip negative control run.",
        )

    def handle(self, *args, **options):
        # List experiments and exit if requested
        if options.get("list_experiments"):
            self.stdout.write(self.style.SUCCESS("Available experiments:"))
            for name, desc in eval_config.list_experiments().items():
                self.stdout.write(self.style.HTTP_INFO(f"• {name}: ") + f"{desc}")
            self.stdout.write(
                self.style.NOTICE(
                    "You can define new experiemnts in 'evaluation/config.py'."
                )
            )
            return

        question_set_label = options.get("question_set_label")
        experiment = options.get("experiment")
        repeat = options.get("repeat", False)
        skip_pcontrol = options.get("skip_pcontrol", False)
        skip_ncontrol = options.get("skip_ncontrol", False)

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
            self.stdout.write(self.style.SUCCESS(f"Running experiment: {experiment}"))
            self.stdout.write(
                f"Description: {eval_config.experiments[experiment]['description']}"
            )

        if not skip_pcontrol:
            self.stdout.write(self.style.SUCCESS("Starting positive control..."))
            run_pcontrol(
                question_set_label=question_set_label,
                repeat=repeat,
                experiment=experiment,
                stdout=self.stdout,
            )

        if not skip_ncontrol:
            self.stdout.write(self.style.SUCCESS("Starting negative control..."))
            run_ncontrol(
                question_set_label=question_set_label,
                repeat=repeat,
                experiment=experiment,
                stdout=self.stdout,
            )

        self.stdout.write(self.style.SUCCESS("Evaluation complete!"))
