from pathlib import Path
import csv
import json
import re

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError as error:
    raise SystemExit(
        "Missing required package. This script needs "
        "requests and beautifulsoup4."
    ) from error


PROJECT_ROOT = Path(__file__).resolve().parent.parent

SOURCE_REGISTER = PROJECT_ROOT / "sources.csv"
OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "structured"
    / "webpages.jsonl"
)

WEBPAGE_SOURCE_IDS = {
    "WSI-WEB-001",
    "WSI-FAQ-001",
}

FAQ_SECTION = "Internal Wall Insulation with Lime Render"


def normalise_text(text):
    return re.sub(
        r"\s+",
        " ",
        text.replace("\xa0", " ")
    ).strip()


def clean_element_text(element):
    lines = []

    for text in element.stripped_strings:
        cleaned = normalise_text(text)

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines)


def source_metadata(source):
    return {
        "source_id": source["source_id"].strip(),
        "title": source["title"].strip(),
        "source_type": source["source_type"].strip(),
        "system": source["system"].strip(),
        "application": source["application"].strip(),
        "url": source["url"].strip(),
        "local_file": source["local_file"].strip(),
        "publication_date": (
            source["publication_date"].strip()
        ),
        "status": source["status"].strip(),
        "authority": source["authority"].strip(),
        "audience": source["audience"].strip(),
        "notes": source["notes"].strip(),
    }


def fetch_page(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "LimeGreenLocalRAG/1.0 "
                "(webpage ingestion prototype)"
            )
        },
        timeout=30
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.content,
        "html.parser",
        from_encoding="utf-8"
    )


def find_main_page_subsection(section, heading_fragment):
    heading = section.find(
        lambda tag: (
            tag.name in {"h1", "h2", "h3", "h4"}
            and heading_fragment.lower()
            in normalise_text(
                tag.get_text(" ", strip=True)
            ).lower()
        )
    )

    if heading is None:
        raise ValueError(
            "Main-page subsection not found: "
            f"{heading_fragment}"
        )

    container = heading

    for parent in heading.parents:
        if parent is section:
            break

        classes = set(parent.get("class", []))

        if parent.name == "div" and (
            "column" in classes
            or "col-i" in classes
        ):
            container = parent
            break

    return container


def extract_heading_text(section, heading_fragment):
    heading = section.find(
        lambda tag: (
            tag.name in {"h1", "h2", "h3", "h4"}
            and heading_fragment.lower()
            in normalise_text(
                tag.get_text(" ", strip=True)
            ).lower()
        )
    )

    if heading is None:
        raise ValueError(
            "Main-page subsection not found: "
            f"{heading_fragment}"
        )

    lines = []

    for element in heading.next_elements:
        if isinstance(element, Tag):
            if element.name in {"h1", "h2", "h3", "h4"}:
                break

            continue

        if not isinstance(element, NavigableString):
            continue

        if heading in element.parents:
            continue

        if section not in element.parents:
            break

        cleaned = normalise_text(str(element))

        if cleaned:
            lines.append(cleaned)

    heading_text = normalise_text(
        heading.get_text(" ", strip=True)
    )

    return "\n".join(
        [heading_text] + lines
    )


def extract_main_page_records(source, soup):
    main = soup.find("main")

    if main is None:
        raise ValueError("Main content was not found.")

    section_specs = [
        (
            "Natural Internal Wall Insulation (IWI)",
            main.find("section", id="section-38")
        ),
        (
            "Warmshell Natural Internal Wall Insulation/IWI",
            main.find("section", id="section-59")
        ),
        (
            "IWI Assessment",
            main.find("section", id="section-62")
        ),
        (
            "Design Warmshell IWI",
            main.find("section", id="section-64")
        ),
        (
            "Installing Warmshell IWI",
            main.find("section", id="section-66")
        ),
        (
            "Warranty",
            main.find("section", id="section-68")
        ),
    ]

    assessment_section = main.find(
        "section",
        id="section-65"
    )

    if assessment_section is None:
        raise ValueError(
            "Certification and environmental section "
            "was not found."
        )

    section_specs[4:4] = [
        (
            "BDA Agrément",
            extract_heading_text(
                assessment_section,
                "BDA Agr"
            )
        ),
        (
            "Environmental Product Declaration",
            extract_heading_text(
                assessment_section,
                "Environmental Product Declaration"
            )
        ),
        (
            "NBS source",
            extract_heading_text(
                assessment_section,
                "NBS source"
            )
        ),
    ]

    records = []
    metadata = source_metadata(source)

    for section_label, element in section_specs:
        if element is None:
            raise ValueError(
                "Main-page section not found: "
                f"{section_label}"
            )

        if isinstance(element, str):
            text = element
        else:
            text = clean_element_text(element)

        if not text:
            raise ValueError(
                "Main-page section is empty: "
                f"{section_label}"
            )

        records.append(
            {
                **metadata,
                "section": section_label,
                "retrieval_enabled": True,
                "text": text,
            }
        )

    combined_text = "\n".join(
        record["text"]
        for record in records
    )

    required_components = [
        "Duro Levelling Coat",
        "Warmshell Board Adhesive",
        "Warmshell Woodfibre",
        "Solo Onecoat Lime Plaster",
    ]

    missing_components = [
        component
        for component in required_components
        if component not in combined_text
    ]

    if missing_components:
        raise ValueError(
            "Main-page components not found: "
            f"{missing_components}"
        )

    return records


def extract_faq_records(source, soup):
    section_heading = soup.find(
        string=lambda text: (
            text
            and normalise_text(text) == FAQ_SECTION
        )
    )

    if section_heading is None:
        raise ValueError(
            "The scoped IWI FAQ subsection was not found."
        )

    faq_section = section_heading.find_parent(
        "section",
        class_="faq-section"
    )

    if faq_section is None:
        raise ValueError(
            "The scoped IWI FAQ container was not found."
        )

    accordion = faq_section.find("dl", class_="accordian")

    if accordion is None:
        raise ValueError(
            "The scoped IWI FAQ accordion was not found."
        )

    records = []
    metadata = source_metadata(source)

    for question_element in accordion.find_all(
        "dt",
        recursive=False
    ):
        answer_element = question_element.find_next_sibling(
            "dd"
        )

        if answer_element is None:
            raise ValueError(
                "FAQ question has no matching answer: "
                f"{question_element.get_text(' ', strip=True)}"
            )

        question = normalise_text(
            question_element.get_text(" ", strip=True)
        )
        answer = normalise_text(
            answer_element.get_text(" ", strip=True)
        )

        if not question or not answer:
            raise ValueError(
                "An empty FAQ question or answer was found."
            )

        records.append(
            {
                **metadata,
                "question": question,
                "answer": answer,
                "section": FAQ_SECTION,
                "retrieval_enabled": True,
            }
        )

    if not records:
        raise ValueError(
            "No FAQ pairs were extracted from the "
            "scoped IWI subsection."
        )

    return records


with SOURCE_REGISTER.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as file:
    sources = {
        row["source_id"].strip(): row
        for row in csv.DictReader(file)
        if row["source_id"].strip()
        in WEBPAGE_SOURCE_IDS
    }


if set(sources) != WEBPAGE_SOURCE_IDS:
    missing_sources = WEBPAGE_SOURCE_IDS - set(sources)

    raise ValueError(
        "Missing webpage sources in sources.csv: "
        f"{sorted(missing_sources)}"
    )


webpage_records = []

main_source = sources["WSI-WEB-001"]
main_soup = fetch_page(main_source["url"].strip())
main_records = extract_main_page_records(
    main_source,
    main_soup
)
webpage_records.extend(main_records)

faq_source = sources["WSI-FAQ-001"]
faq_soup = fetch_page(faq_source["url"].strip())
faq_records = extract_faq_records(
    faq_source,
    faq_soup
)
webpage_records.extend(faq_records)


OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

with OUTPUT_FILE.open(
    "w",
    encoding="utf-8"
) as file:
    for record in webpage_records:
        file.write(
            json.dumps(
                record,
                ensure_ascii=False
            )
            + "\n"
        )


with OUTPUT_FILE.open(
    "r",
    encoding="utf-8"
) as file:
    validated_records = [
        json.loads(line)
        for line in file
    ]


if validated_records != webpage_records:
    raise ValueError(
        "Written webpage records failed validation."
    )


print(f"WSI-WEB-001 records: {len(main_records)}")
print(f"WSI-FAQ-001 records: {len(faq_records)}")
print(f"Total webpage records: {len(webpage_records)}")
print(f"Saved to: {OUTPUT_FILE}")
print("\nFAQ questions:")

for record in faq_records:
    print(f"- {record['question']}")
