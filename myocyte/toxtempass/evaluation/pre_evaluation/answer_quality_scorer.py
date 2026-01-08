import json
import logging
import re
from pathlib import Path
from langchain_openai import ChatOpenAI

from toxtempass.llm import get_llm
from toxtempass import LLM_API_KEY, LLM_ENDPOINT, config

# Get logger
logger = logging.getLogger("llm")

# Initialize language models based on environment variables
llm = None

if LLM_API_KEY and LLM_ENDPOINT:
    llm = ChatOpenAI(
        api_key=LLM_API_KEY,
        base_url=config.url,
        temperature=config.temperature,
        model_name="gpt-4o",
        default_headers=config.extra_headers,
    )
    logger.info(f"Using ({llm.model_name}) at {LLM_ENDPOINT}.")
else:
    logger.error("Required environment variables are missing")


# Define the scoring prompt
SCORING_INSTRUCTIONS = """
You are evaluating how well each answer addresses the corresponding scientific question from a test method documentation template.

For each question-answer pair, assign:
- "High": Fully or almost fully addresses the question, relevant and complete.
- "Medium": Partially addresses the question or lacks clarity/completeness.
- "Low": Does not address the question or is missing.

Return a JSON object with two fields:
- "score": one of the following words: High, Medium, or Low.
- "justification": a brief explanation of why the score was assigned.

Return only the JSON object.
"""

def score_answer_with_llm(question, answer):
    if not answer or not answer.strip():
        return "Low", "No answer provided; treated as missing."

    prompt = f"{SCORING_INSTRUCTIONS}\n\nQuestion: {question}\nAnswer: {answer}\nResult:"

    llm=llm
    response = llm.invoke(prompt)
    content = response.content.strip()
    # Strip markdown code fences if present
    clean_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()

    try:
        result = json.loads(clean_content)
        score = result.get("score")
        justification = result.get("justification")
        # Validate that both fields are present and valid
        if score not in ("High", "Medium", "Low") or not isinstance(justification, str):
            raise ValueError("Invalid or missing score/justification")
    except (json.JSONDecodeError, ValueError):
        # Fallback parsing if JSON failed or missing fields
        score_text = clean_content.lower()
        if "high" in score_text:
            score = "High"
        elif "medium" in score_text:
            score = "Medium"
        elif "low" in score_text:
            score = "Low"
        else:
            score = None
        justification = clean_content

    return score, justification

def apply_quality_scores(json_path, output_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for section in data.get("sections", []):
        for subsection in section.get("subsections", []):
            question = subsection.get("question", "")
            answer = subsection.get("answer", "")
            score, justification = score_answer_with_llm(question, answer)
            subsection["answer_quality_score"] = score
            subsection["answer_quality_justification"] = justification

            if "subquestions" in subsection:
                for subq in subsection["subquestions"]:
                    subq_question = subq.get("question", "")
                    subq_answer = subq.get("answer", "")
                    score, justification = score_answer_with_llm(subq_question, subq_answer)
                    subq["answer_quality_score"] = score
                    subq["answer_quality_justification"] = justification

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Scored JSON saved to {output_path}")


if __name__ == "__main__":
    # Directory containing input JSON files
    input_dir = Path(__file__).resolve().parent.parent / "positive_control" / "input_files" / "processed"
    # Process each .json file in the directory
    for input_path in input_dir.glob("*.json"):
        # Skip files already scored
        if input_path.stem.endswith("_scored"):
            continue
        output_path = input_path.with_name(f"{input_path.stem}_scored.json")
        print(f"Scoring {input_path.name} -> {output_path.name}")
        apply_quality_scores(str(input_path), str(output_path))
