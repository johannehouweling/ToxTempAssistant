# mapping the sections, in long and short

#imports
import pandas as pd
from pathlib import Path

# Paths
QUESTION_PATH = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/enriched/sections/dataframes/ToxTemp_v1_questions.csv')

# Import DataFrame
df = pd.read_csv(QUESTION_PATH)

# create dictionary with short versions of sections
SECTION_SHORT_MAP = {
   "1. Overview": "Overview",
    "2. General information": "General information",
    "3. Description of general features of the test system source": "Test system source",
    "4. Definition of the test system as used in the method": "Test system definition",
    "5. Test method exposure scheme and endpoints": "Exposure & endpoints",
    "6. Handling details of the test method": "Test method handling",
    "7. Data management": "Data management",
    "8. Prediction model and toxicological application": "Prediction & application",
    "9. Publication/validation status": "Publication/validation status",
    "10. Test method transferability": "Transferability",
    "11. Safety, ethics and specific requirements": "Safety, ethics & requirements"
}

# add section_short to question DataFrame
df["section_short"] = df["section"].map(SECTION_SHORT_MAP)

# set Question-ID as index
df.set_index('Question_ID', inplace=True)

#save DataFrame
output_csv = QUESTION_PATH.with_name(
    f"{QUESTION_PATH.stem}_short_section.csv"
)
output_csv.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_csv)
print(f"Saved updated DataFrame to: {output_csv}")