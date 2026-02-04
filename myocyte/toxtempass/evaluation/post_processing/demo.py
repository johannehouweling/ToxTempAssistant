from pathlib import Path
import pandas as pd

# from myocyte.toxtempass.evaluation.post_processing.groundedness import add_groundedness_columns



#from myocyte.toxtempass.evaluation.post_processing.groundedness import add_groundedness_columns


csv_path = Path("/Users/johannehouweling/ToxTempAssistant/myocyte/toxtempass/evaluation/positive_control/output/gpt-4.1-nano/tier1_comparison_cMINC(UKN2).csv")
pdf_path = Path("/Users/johannehouweling/ToxTempAssistant/myocyte/toxtempass/evaluation/positive_control/input_files/cMINC(UKN2).pdf")

demo_path = Path("demo_input.csv")

add_groundedness_columns(
            csv_path=demo_path,
            pdf_path=pdf_path,
            output_path=Path.cwd() / "groundedness_demo_output.csv",
            judge_model="gpt-5-nano",
            faithfulness_threshold=0.5,
            chunk_size=500,
            chunk_overlap=200,
            top_k=8,
            geval_threshold=0.5,
            verbose=True,
            )

