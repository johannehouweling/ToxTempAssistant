from pathlib import Path
import subprocess


cwd = Path(__file__).parent.parent
out_folder = cwd / "auto_generated_html"
if not out_folder.exists():
    out_folder.mkdir()
for md_file in list(cwd.glob("**/*.md")):
    # Define the output file name (you can adjust the extension or output directory as needed)
    output_file = (
        out_folder / md_file.with_suffix(".html").name
    )  # Convert markdown to HTML

    # Run pandoc using subprocess
    try:
        subprocess.run(
            [
                "pandoc",
                str(md_file),
                f"--template={cwd / 'dependencies/GitHub.html5'}",
                "-o",
                str(output_file),
            ],
            check=True,
        )
        print(f"Successfully converted {md_file} to {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"Error processing {md_file}: {e}")
