"""Smoke-test every discovered Azure Foundry deployment.

Usage::

    poetry run python manage.py test_llm_endpoints
    poetry run python manage.py test_llm_endpoints --only KIMI
    poetry run python manage.py test_llm_endpoints --prompt "ping"
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from toxtempass.azure_registry import get_registry
from toxtempass.llm import run_health_check


class Command(BaseCommand):
    help = "Ping each discovered Azure Foundry deployment with a trivial prompt."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prompt",
            default="What is the capital of France? Answer in one word.",
            help="Prompt to send to every deployment.",
        )
        parser.add_argument(
            "--only",
            default="",
            help="Comma-separated tags to restrict testing (e.g. 'KIMI,CLAUDE').",
        )
        parser.add_argument(
            "--save",
            action="store_true",
            help="Persist results to LLMConfig.last_health_check (same as admin action).",
        )

    def handle(self, *args, **opts):
        if not get_registry():
            self.stdout.write(self.style.ERROR("No AZURE_E*_ENDPOINT vars found."))
            return

        only = {t.strip().upper() for t in opts["only"].split(",") if t.strip()}
        results = run_health_check(prompt=opts["prompt"])

        filtered = {
            k: v for k, v in results.items() if not only or k.split(":")[1] in only
        }

        ok = 0
        for key, r in filtered.items():
            label = f"{key} ({r['model_id']}, api={r['api']})"
            self.stdout.write(self.style.HTTP_INFO(f"→ {label}"))
            if r["ok"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {r['latency_ms']}ms · {r['response']}"
                    )
                )
                ok += 1
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ {r['error']}"))

        if opts["save"]:
            from toxtempass.models import LLMConfig
            cfg = LLMConfig.load()
            cfg.last_health_check = results
            cfg.save()
            self.stdout.write(self.style.HTTP_INFO("Saved results to LLMConfig."))

        total = len(filtered)
        style = self.style.SUCCESS if ok == total else self.style.WARNING
        self.stdout.write("")
        self.stdout.write(style(f"{ok}/{total} deployments responded."))
