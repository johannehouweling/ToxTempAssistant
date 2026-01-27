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
   "1. Overview": "1. Overview",
    "2. General information": "2. General information",
    "3. Description of general features of the test system source": "3. Test system source",
    "4. Definition of the test system as used in the method": "4. Test system definition",
    "5. Test method exposure scheme and endpoints": "5. Exposure & endpoints",
    "6. Handling details of the test method": "6. Test method handling",
    "7. Data management": "7. Data management",
    "8. Prediction model and toxicological application": "8. Prediction & application",
    "9. Publication/validation status": "9. Publication/validation status",
    "10. Test method transferability": "10. Transferability",
    "11. Safety, ethics and specific requirements": "11. Safety, ethics & requirements"
}

# add section_short to question DataFrame
df["section_short"] = df["section"].map(SECTION_SHORT_MAP)

# set Question-ID as index
df.set_index('Question_ID', inplace=True)

# adding question-id as seperate column, so it is easier for further evaluation analysis
df["Question_ID2"] = df.index

#save DataFrame
output_csv = QUESTION_PATH.with_name(
    f"{QUESTION_PATH.stem}_short_section.csv"
)
output_csv.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_csv)
print(f"Saved updated DataFrame to: {output_csv}")