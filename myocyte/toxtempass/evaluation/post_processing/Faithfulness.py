# creating a definition of a new metric to evaluate the performance of the ToxTempAssistant
# Faithfullness: measures how factually consistent a response is with the retrieved context. It ranges from 0 to 1, with higher scores indicating better consistency.
# From: https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/faithfulness/

# imports
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness
import sys
repo_root = Path.cwd()  # adjust if you're not at repo root
sys.path.insert(0, str(repo_root / "myocyte"))

from toxtempass import LLM_API_KEY, config


# Setup LLM
client = AsyncOpenAI(LLM_API_KEY)
llm = llm_factory("gpt-4o-mini", client=client)

# Create metric
scorer = Faithfulness(llm=llm)

# Evaluate
result = await scorer.ascore(
    user_input="When was the first super bowl?",
    response="The first superbowl was held on Jan 15, 1967",
    retrieved_contexts=[
        "The First AFL–NFL World Championship Game was an American football game played on January 15, 1967, at the Los Angeles Memorial Coliseum in Los Angeles."
    ]
)
print(f"Faithfulness Score: {result.value}")