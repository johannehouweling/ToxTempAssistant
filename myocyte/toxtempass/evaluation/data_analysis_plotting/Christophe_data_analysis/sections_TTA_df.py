# the goal is to create an dataframe of the sections of the TTA based on the json file <myocyte/ToxTemp_v1.json>
# to combine this with data from the experiments so data can be analysed based on sections. 
## columns to be extracted: 'section', 'subsection' 

#imports
import pandas as pd
import json

#TTA question file location
TTAquestions_path = 'myocyte/ToxTemp_v1.json'

with open(f"myocyte/ToxTemp_v1.json", 'r', encoding="UTF-8") as file:
    data = json.load(file)


comb_df = []
for _, section in sections.items():
    title = section["title"]
    for sub in section["subsections"]:
        d = {'Section': title, 'Subsection': sub["title"]}
        dct = {k:[v] for k,v in d.items()}  
        df_json = pd.DataFrame(dct)
        comb_df.append(df_json)

result = pd.concat(comb_df)
print(result)
print(section_df["sections"])
print(pd.__version__)

section_df.info()

#save sections dataframe as a csv
result.to_csv("myocyte/toxtempass/evaluation/data_analysis_plotting/Christophe_data_analysis/sections_TTA.csv" )