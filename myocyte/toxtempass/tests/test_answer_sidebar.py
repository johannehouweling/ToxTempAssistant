import pytest
from django.urls import reverse

from toxtempass import config
from toxtempass.models import Answer
from toxtempass.tests.fixtures.factories import (
    AssayFactory,
    InvestigationFactory,
    PersonFactory,
    QuestionFactory,
    QuestionSetFactory,
    SectionFactory,
    StudyFactory,
    SubsectionFactory,
)


@pytest.mark.django_db
def test_sidebar_renders_accepted_draft_and_missing_question_statuses(client):
    owner = PersonFactory.create()
    qs = QuestionSetFactory.create(label=None)
    section = SectionFactory.create(question_set=qs, title="Main section")
    subsection = SubsectionFactory.create(section=section, title="Main subsection")
    accepted_question = QuestionFactory.create(
        subsection=subsection, question_text="Accepted question?"
    )
    draft_question = QuestionFactory.create(
        subsection=subsection, question_text="Draft question?"
    )
    not_found_question = QuestionFactory.create(
        subsection=subsection, question_text="Not found question?"
    )
    empty_question = QuestionFactory.create(
        subsection=subsection, question_text="Empty question?"
    )

    investigation = InvestigationFactory.create(owner=owner)
    study = StudyFactory.create(investigation=investigation)
    assay = AssayFactory.create(study=study, question_set=qs)

    Answer.objects.create(
        assay=assay,
        question=accepted_question,
        answer_text="Reviewed answer",
        accepted=True,
    )
    Answer.objects.create(
        assay=assay,
        question=draft_question,
        answer_text="Draft answer awaiting review",
        accepted=False,
    )
    Answer.objects.create(
        assay=assay,
        question=not_found_question,
        answer_text=config.not_found_string,
        accepted=False,
    )

    client.force_login(owner)
    resp = client.get(reverse("answer_assay_questions", kwargs={"assay_id": assay.pk}))

    assert resp.status_code == 200
    content = resp.content.decode()
    assert 'data-question-status="accepted"' in content
    assert f'href="#id_question_{accepted_question.pk}"' in content
    assert f'aria-label="{accepted_question.question_text} (accepted)"' in content
    assert f'aria-label="{draft_question.question_text} (draft)"' in content
    assert f'aria-label="{not_found_question.question_text} (missing)"' in content
    assert f'aria-label="{empty_question.question_text} (missing)"' in content
    assert content.count('data-question-status="accepted"') == 1
    assert content.count('data-question-status="draft"') == 1
    assert content.count('data-question-status="missing"') == 2
