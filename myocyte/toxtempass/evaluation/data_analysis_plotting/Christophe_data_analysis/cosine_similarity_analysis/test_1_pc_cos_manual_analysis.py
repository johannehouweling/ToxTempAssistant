# Manual visualisation of cosine data analysis of positive controls
#no images
#tested model: gpt-5-mini
#metric: cosine_similarity

#imports
import pandas as pd
import glob
import plotly.express as px

#getting the data frames
cminc_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_cMINC(UKN2).csv')
mitocomp_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_MitoComplexesLUHMESassay(MCL).csv')
mitometa_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_MitoMetassay(UKN4b).csv')
mitostress_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_MitoStressLUHMESassay(MSL).csv')
neuritox_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_NeuriToxassay(UKN4).csv')
npc1_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_NPC1.csv')
npc2_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_NPC2-5.csv')
peritox_df = pd.read_csv('myocyte/toxtempass/evaluation/positive_control/output/gpt-5-mini/tier1_comparison_PeriToxtest(UKN5).csv')
section_df = pd.read_excel('myocyte/toxtempass/evaluation/data_analysis_plotting/Christophe_data_analysis/Toxtemplate_sections.xlsx')

#adding the sections to the dataframes
s_cminc_df = pd.concat([section_df, cminc_df], axis=1)
mitocomp_df = pd.concat([section_df, mitocomp_df], axis=1)
mitometa_df = pd.concat([section_df, mitometa_df], axis=1)
mitostress_df = pd.concat([section_df, mitostress_df], axis=1)
neuritox_df = pd.concat([section_df, neuritox_df], axis=1)
npc1_df = pd.concat([section_df, npc1_df], axis=1)
npc2_df = pd.concat([section_df, npc2_df], axis=1)
peritox_df = pd.concat([section_df, peritox_df], axis=1)

#adding all the dataframes together
all_positivecontrol = pd.concat(
    [s_cminc_df,
    mitocomp_df,
    mitometa_df,
    mitostress_df,
    neuritox_df,
    npc1_df,
    npc2_df,
    peritox_df]
)

# excluding rows which have no gtruth_answer
all_positivecontrol = all_positivecontrol.dropna(subset=['gtruth_answer'])
all_positivecontrol.info() #check if it worked, yess all files 544 rows

# visualisation
## scatterplot
scatter_all_pcontrol = px.scatter(
    all_positivecontrol,
    x=all_positivecontrol.index,
    y='cos_similarity',
)
scatter_all_pcontrol.show()

## boxplot
box_all_pcontrol = px.box(
    all_positivecontrol,
    x='gtruth_answer_quality_score',
    y='cos_similarity'
)
box_all_pcontrol.show()

## scatter based on section
all_positivecontrol.columns
scatter_all_pcontrol = px.scatter(
    all_positivecontrol,
    x='Section',
    y='cos_similarity',
)
scatter_all_pcontrol.show()

# boxplot based on section
box_all_pcontrol = px.box(
    all_positivecontrol,
    x='Section',
    y='cos_similarity',
)
box_all_pcontrol.show()