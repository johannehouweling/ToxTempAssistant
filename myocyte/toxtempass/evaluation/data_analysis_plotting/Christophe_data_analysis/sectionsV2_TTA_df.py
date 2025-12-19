# the goal is to create an dataframe of the sections of the TTA based on the json file <myocyte/ToxTemp_v1.json>
# to combine this with data from the experiments so data can be analysed based on sections. 
## The column 'question' will be extracted and used as a key to be able to combine it with the correct rows in the experimental data
### columns to be extracted: 'section', 'subsection' and 'question'
#### additionally the subquestions will be extracted and added to the 'question column (unsuccesvol yet)


#imports
import pandas as pd
import json

#TTA question file location
TTAquestions_path = 'myocyte/ToxTemp_v1.json'

#read the json and convert to python readable data
with open(f"myocyte/ToxTemp_v1.json", 'r', encoding="UTF-8") as file:
    data = json.load(file)

#creating a dataframe of the json
section_df = pd.DataFrame(data)

# extracting the sections
sections = section_df["sections"]
subsections_q = section_df["subsections"] #this does not work

#building the dataframe
comb_df = []
for _, section in sections.items():
    title = section["title"]
    for sub in section["subsections"]:
        d = {'section': title,'subsection': sub["title"],'question': sub["question"]}
        dct = {k:[v] for k,v in d.items()}  
        df_json = pd.DataFrame(dct)
        comb_df.append(df_json)

        for sq in section["subquestions"].items(): #does not work, have to find another way to put in the subquestions
            subquestions = sq["question"]
            b = {'section': title,'subsection': sub["title"],'question': subquestions}
            bct = {k:[v] for k,v in b.items()}  
            df_b = pd.DataFrame(bct)
            comb_df.append(df_b)


result = pd.concat(comb_df)
print(result)
print(section_df["sections"])
print(result.info())