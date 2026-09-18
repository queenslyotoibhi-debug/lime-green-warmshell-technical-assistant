from pathlib import Path
import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_FOLDER = PROJECT_ROOT / "data" / "raw"
PROCESSED_FOLDER = PROJECT_ROOT / "data" / "processed"


PROCESSED_FOLDER.mkdir(parents=True, exist_ok=True)


pdf_files = list(RAW_FOLDER.glob("*.pdf"))


print(f"Found {len(pdf_files)} PDF files.\n")


for pdf_path in pdf_files:

    print(f"Processing: {pdf_path.name}")

    document = pymupdf.open(pdf_path)

    extracted_pages = []

    for page_number, page in enumerate(document, start=1):

        page_text = page.get_text()

        page_output = (
            f"\n--- PAGE {page_number} ---\n\n"
            f"{page_text}"
        )

        extracted_pages.append(page_output)

    document.close()

    full_text = "".join(extracted_pages)

    output_path = PROCESSED_FOLDER / f"{pdf_path.stem}.txt"

    output_path.write_text(
        full_text,
        encoding="utf-8"
    )

    print(
        f"Saved: {output_path.name} "
        f"({len(extracted_pages)} pages)\n"
    )


print("Extraction complete.")
