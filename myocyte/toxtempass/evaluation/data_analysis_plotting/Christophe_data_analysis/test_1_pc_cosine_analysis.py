#visualise cosine similarity distribution of test_experiment_2
# metrics: cosine_similarity
# model: gpt-5-mini

##import packages
import numpy as np
import pandas as pd
import plotly.express as px
import glob
import json

# get data file names, first create path to map with .csv files
path = 'myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini'
filenames = glob.glob(path + '/*.csv')

#upload excel with sections as a dataframe
section_df = pd.read_excel('myocyte/toxtempass/evaluation/data_analysis_plotting/Christophe_data_analysis/Toxtemplate_sections.xlsx')
section_df.info()

#create dataframe with individual files combined with sections from excel
#combine individual files into one large dataframe
df = []
for file in filenames:
    df_individual_pc = pd.read_csv(file)
    df_individual_pc["source_file"] = file
    combined_df = pd.concat([df_individual_pc, section_df], axis = 1)
    df.append(combined_df)

result_df = pd.concat(df)
print(result_df)

# exclude rows which have no gtruth_answer
result_df_tidy = result_df.dropna(subset=['gtruth_answer'])
result_df_tidy.info() #check if it worked, yess all files 544 rows

# plot
scatter_results = px.scatter(
    result_df_tidy,
    x=result_df_tidy.index,
    y='cos_similarity',
)
scatter_results.show()

# boxplot
box_results = px.box(
    result_df_tidy,
    x='gtruth_answer_quality_score',
    y='cos_similarity'
)
box_results.show()

# save results as csv file
result_df_tidy.to_csv("myocyte/toxtempass/evaluation/data_analysis_plotting/Christophe_data_analysis/pc_summary_cos_gpt-5-mini.csv" )