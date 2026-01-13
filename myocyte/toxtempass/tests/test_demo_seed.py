import pytest

from toxtempass.demo import seed_demo_assay_for_user
from toxtempass.models import (
    Answer,
    Assay,
    Investigation,
    Question,
    QuestionSet,
    Section,
    Study,
    Subsection,
)
from toxtempass.tests.fixtures.factories import PersonFactory


@pytest.mark.django_db
def test_seed_demo_assay_for_user_creates_copy_once():
    template_owner = PersonFactory()
    question_set = QuestionSet.objects.create(display_name="Demo QS", hide_from_display=False)
    section = Section.objects.create(question_set=question_set, title="Section")
    subsection = Subsection.objects.create(section=section, title="Subsection")
    question = Question.objects.create(subsection=subsection, question_text="Demo question?")

    inv = Investigation.objects.create(owner=template_owner, title="Template Investigation")
    study = Study.objects.create(investigation=inv, title="Template Study")
    template_assay = Assay.objects.create(
        study=study,
        title="Template Assay",
        description="",
        question_set=question_set,
        demo_lock=True,
        demo_template=True,
    )
    Answer.objects.create(
        assay=template_assay,
        question=question,
        answer_text="Demo answer",
        accepted=True,
        answer_documents=["demo.pdf"],
    )

    user = PersonFactory() # signal will call seed_demo_assay_for_user on creation
    
    demo_assay = Assay.objects.get(demo_lock=True)
    assert demo_assay is not None
    assert demo_assay.demo_source == template_assay
    assert demo_assay.study.investigation.owner == user
    assert demo_assay.answers.count() == 1

    # Subsequent calls should not create duplicates
    second = seed_demo_assay_for_user(user)
    assert second is None
    assert (
        Assay.objects.filter(
            demo_source=template_assay, study__investigation__owner=user
        ).count()
        == 1
    )
