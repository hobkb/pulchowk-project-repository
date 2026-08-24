from pathlib import Path
import shutil

# Siwansh Pathak

txt_file = Path("files.txt")
pdf_folder = Path(r"C:\Users\user\Downloads\RAG\docs")
output_folder = pdf_folder / "completed projects"

print(f"Reading list: {txt_file.resolve()}")
print(f"PDF folder: {pdf_folder}")
print(f"PDF folder exists: {pdf_folder.exists()}")
print(f"List file exists: {txt_file.exists()}")

if not txt_file.exists():
    raise FileNotFoundError(f"Could not find {txt_file.resolve()}")

if not pdf_folder.exists():
    raise FileNotFoundError(f"Could not find {pdf_folder}")

output_folder.mkdir(exist_ok=True)

pdf_names = [
    line.strip()
    for line in txt_file.read_text(encoding="utf-8").splitlines()
    if line.strip()
]

print(f"PDFs listed in files.txt: {len(pdf_names)}")
print()

copied = 0
missing = 0

for pdf_name in pdf_names:
    source = pdf_folder / pdf_name
    destination = output_folder / pdf_name

    if source.is_file():
        shutil.copy2(source, destination)
        copied += 1
        print(f"Copied: {pdf_name}")
    else:
        missing += 1
        print(f"Not found: {pdf_name}")

print()
print("========== SUMMARY ==========")
print(f"Total listed: {len(pdf_names)}")
print(f"Copied: {copied}")
print(f"Not found: {missing}")
print(f"Output folder: {output_folder.resolve()}")