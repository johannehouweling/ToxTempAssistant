# adding colour coding based on RISK-HUNT3R

#imports
import pandas as pd
from pathlib import Path

# Paths 
QEUSTION_PATH = Path('myocyte/toxtempass/evaluation/data_analysis_plotting/christophe_data_analysis/enriched/sections/dataframes/ToxTemp_v1_questions_short_section.csv')

# import DataFrame
df = pd.read_csv(QEUSTION_PATH)

# the colours with corresponding Question_ID
blue_list = [1, 10, 11, 12, 13, 14, 15, 16, 17]
green_list = [2, 3, 4, 5, 6, 7, 8, 9, 18, 19, 20, 25, 34, 35, 36, 39, 40, 41, 53, 55, 60, 62, 63, 64, 65, 67]
yellow_list =  [21, 22, 23, 26, 27, 28, 29, 31, 38, 42, 44, 46, 47, 54, 56, 58, 59, 61]
orange_list = [24, 30, 32, 33, 37, 45, 48, 49, 50, 57, 68]
red_list = [43, 51, 52, 66, 69, 70, 71, 72, 73, 74, 75, 76, 77]

# combine all lists for quality control
all_numbers = (
    blue_list
    + green_list
    + yellow_list
    + orange_list
    + red_list
)

# check if all questions are coloured
set(all_numbers) == set(range(1, 78))

# check if every question has only one colour
duplicates = set()

for num in all_numbers:
    if all_numbers.count(num) > 1:
        duplicates.add(num)
print("Duplicate numbers:", duplicates)

# create dictionaries for Question_ID and colours
colour_map = {
    **{i: "blue" for i in blue_list},
    **{i: "green" for i in green_list},
    **{i: "yellow" for i in yellow_list},
    **{i: "orange" for i in orange_list},
    **{i: "red" for i in red_list},
}
# add colour column to the section DataFrame
df["colour"] = df["Question_ID2"].map(colour_map)
if df["colour"].isna().any():
    raise ValueError("Some questions were not assigned a colour.")

# save DataFrame
output_csv = QEUSTION_PATH.with_name(
    f"{QEUSTION_PATH.stem}_colour.csv"
)
output_csv.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(output_csv)
print(f"Saved DataFrame containing colour coding to: {output_csv}")