# creating a definition of a new metric to evaluate the performance of the ToxTempAssistant
# Faithfullness: measures how factually consistent a response is with the retrieved context. It ranges from 0 to 1, with higher scores indicating better consistency.
# From: https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/faithfulness/

# imports
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness
from pathlib import Path
import glob
import pandas as pd
from toxtempass import LLM_API_KEY, config

# Setup LLM
client = AsyncOpenAI()
llm = llm_factory("gpt-4o-mini", client=client)

# Create metric
scorer = Faithfulness(llm=llm)

# Evaluate example
result = await scorer.ascore(
    user_input="When was the first super bowl?",
    response="The first superbowl was held on Jan 15, 1967",
    retrieved_contexts=[
        "The First AFL–NFL World Championship Game was an American football game played on January 15, 1967, at the Los Angeles Memorial Coliseum in Los Angeles."
    ]
)
print(f"Faithfulness Score: {result.value}")

# Evaluate try 2
try_2_result = await scorer.ascore(
    user_input="Which hazard(s) do(es) your test method (potentially) predict? (8.1; 8.6)",
    response="The assay potentially predicts hazards related to adverse effects on cell migration and differentiation processes during neurodevelopment, which may lead to cognitive dysfunction (Source: NPC2-5.pdf).",
    retrieved_contexts=[
        "adverse effect on cell migration and differentiation."
    ]
)
print(f"Faithfulness Score: {try_2_result.value}")

# Evaluate try 3
try_3_result = await scorer.ascore(
    user_input="Which test system and readout(s) are used? (4.1; 5.2)",
    response="The test system used in the assay is primary human neural progenitor cells (hNPCs) derived from human cortex (gestational weeks 16-19) (Source: NPC2-5.pdf). The readouts include migration distance, cell number (all cells), number of neurons/oligodendrocytes, neurite length, neurite area, and fluorescence intensity (Source: NPC2-5.pdf).",
    retrieved_contexts=["Test system: primary human neural progenitor cells (hNPCs) from human cortex (Gestion week (GW)16-19). Readout(s): migration distance, cell number (all cells) number of neurons/oligodendrocytes, neurite length, neurite area, fluorescence intensity"
    ]
)
print(f"Faithfulness Score: {try_3_result.value}")

# create the funciont

def faithfulness() -> float:
    result = await scorer.ascore(
        user_input="",
        response="",
        retrieved_contexts=[
            ""
        ]
    )
    print(f"Faithfulness Score: {result.value}")
