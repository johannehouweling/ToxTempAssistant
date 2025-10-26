"""Utilities for seeding demo assays for new users."""

from __future__ import annotations

import logging
from typing import Optional

from django.db import transaction

from toxtempass.models import (
    Answer,
    Assay,
    Investigation,
    LLMStatus,
    Study,
)

logger = logging.getLogger("demo")


def seed_demo_assay_for_user(user) -> Optional[Assay]:
    """Clone the demo template assay for the given user if not already present."""
    if not user or not getattr(user, "pk", None):
        return None

    template = (
        Assay.objects.filter(demo_template=True)
        .select_related("study__investigation", "question_set")
        .prefetch_related("answers__question")
        .first()
    )
    if not template:
        logger.info("No demo template assay configured; skipping seeding.")
        return None

    already_exists = Assay.objects.filter(
        demo_source=template, study__investigation__owner=user
    ).exists()
    if already_exists:
        return None

    with transaction.atomic():
        template_inv = template.study.investigation
        inv = Investigation.objects.create(
            owner=user,
            title=f"{template_inv.title} (Demo)",
            description=template_inv.description,
            public_release_date=template_inv.public_release_date,
        )
        study = Study.objects.create(
            investigation=inv,
            title=f"{template.study.title} (Demo)",
            description=template.study.description,
        )
        assay = Assay.objects.create(
            study=study,
            title=template.title,
            description=template.description,
            question_set=template.question_set,
            status=LLMStatus.DONE,
            status_context=template.status_context,
            demo_lock=True,
            demo_source=template,
        )

        answers_to_create = []
        for answer in template.answers.all():
            answers_to_create.append(
                Answer(
                    assay=assay,
                    question=answer.question,
                    answer_text=answer.answer_text,
                    accepted=answer.accepted,
                    answer_documents=answer.answer_documents,
                )
            )
        Answer.objects.bulk_create(answers_to_create)

    logger.info("Seeded demo assay %s for user %s", assay.id, user.id)
    return assay
