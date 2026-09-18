from pathlib import Path
import csv
import json
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_REGISTER = PROJECT_ROOT / "sources.csv"
PROCESSED_FOLDER = PROJECT_ROOT / "data" / "processed"
STRUCTURED_FOLDER = PROJECT_ROOT / "data" / "structured"

OUTPUT_FILE = STRUCTURED_FOLDER / "pages.jsonl"


# Create the structured folder if it does not already exist
STRUCTURED_FOLDER.mkdir(parents=True, exist_ok=True)


# Read the source register
with SOURCE_REGISTER.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as csv_file:

    reader = csv.DictReader(csv_file)

    sources = list(reader)


# Check that the CSV contains the fields our program requires
required_fields = {
    "source_id",
    "title",
    "source_type",
    "system",
    "application",
    "url",
    "local_file",
    "publication_date",
    "status",
    "authority",
    "audience",
    "notes",
}

actual_fields = set(reader.fieldnames or [])

missing_fields = required_fields - actual_fields

if missing_fields:
    raise ValueError(
        f"Missing columns in sources.csv: {sorted(missing_fields)}"
    )


page_records = []


# Process each source from the register
for source in sources:

    source_id = source["source_id"].strip()
    status = source["status"].strip().lower()
    local_file = source["local_file"].strip()

    # Do not ingest superseded or excluded sources
    if status != "current":
        print(
            f"Skipping {source_id} "
            f"(status: {status})"
        )
        continue

    # Webpages do not have a local PDF file
    if not local_file:
        print(
            f"Skipping {source_id} "
            f"(no local PDF file)"
        )
        continue

    # Convert the PDF filename into its processed TXT filename
    pdf_name = Path(local_file)

    text_filename = f"{pdf_name.stem}.txt"

    text_path = PROCESSED_FOLDER / text_filename

    # Check that the processed text file actually exists
    if not text_path.exists():
        print(
            f"WARNING: Processed text not found for "
            f"{source_id}: {text_filename}"
        )
        continue

    # Read the extracted text
    text = text_path.read_text(
        encoding="utf-8"
    )

    # Separate the text using our page markers
    parts = re.split(
        r"\n--- PAGE (\d+) ---\n\n",
        text
    )

    pages_added = 0

    # Build one structured record for every page
    for index in range(1, len(parts), 2):

        page_number = int(parts[index])

        page_text = parts[index + 1].strip()

        record = {
            "source_id": source_id,
            "title": source["title"].strip(),
            "source_type": source["source_type"].strip(),
            "system": source["system"].strip(),
            "application": source["application"].strip(),
            "url": source["url"].strip(),
            "local_file": local_file,
            "publication_date": source["publication_date"].strip(),
            "status": source["status"].strip(),
            "authority": source["authority"].strip(),
            "audience": source["audience"].strip(),
            "notes": source["notes"].strip(),
            "page": page_number,
            "text": page_text
        }

        page_records.append(record)

        pages_added += 1

    print(
        f"{source_id}: "
        f"created {pages_added} page records"
    )


# Save all page records as JSONL
with OUTPUT_FILE.open(
    "w",
    encoding="utf-8"
) as output:

    for record in page_records:

        output.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


print()
print(f"Total page records: {len(page_records)}")
print(f"Saved to: {OUTPUT_FILE}")
