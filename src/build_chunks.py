from pathlib import Path
import json
import re

from chunking_config import (
    SOURCE_STRATEGIES,
    PAGE_OVERRIDES,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

PAGES_FILE = (
    PROJECT_ROOT
    / "data"
    / "structured"
    / "pages.jsonl"
)

CHUNKS_FILE = (
    PROJECT_ROOT
    / "data"
    / "structured"
    / "chunks.jsonl"
)

WEBPAGES_FILE = (
    PROJECT_ROOT
    / "data"
    / "structured"
    / "webpages.jsonl"
)


def resolve_page_settings(record):

    source_id = record["source_id"]
    page = record["page"]

    # -----------------------------
    # 1. Find document strategy
    # -----------------------------

    source_config = SOURCE_STRATEGIES.get(
        source_id
    )

    if source_config is None:

        raise ValueError(
            f"No chunking strategy defined "
            f"for source: {source_id}"
        )

    strategy = source_config["strategy"]

    # Default page behaviour
    page_role = "content"

    retrieval_enabled = True

    # -----------------------------
    # 2. Look for page override
    # -----------------------------

    override = PAGE_OVERRIDES.get(
        (source_id, page)
    )

    if override:

        strategy = override.get(
            "strategy",
            strategy
        )

        page_role = override.get(
            "page_role",
            page_role
        )

        retrieval_enabled = override.get(
            "retrieval_enabled",
            retrieval_enabled
        )

    return {
        "strategy": strategy,
        "page_role": page_role,
        "retrieval_enabled": retrieval_enabled,
    }


def create_page_chunk(record, settings):

    text = record["text"].strip()

    chunk_id = (
        f"{record['source_id']}"
        f"-p{record['page']:03d}"
        f"-c01"
    )

    chunk = {
        "chunk_id": chunk_id,

        "source_id": record["source_id"],
        "title": record["title"],
        "source_type": record["source_type"],
        "system": record["system"],
        "application": record["application"],
        "url": record["url"],
        "local_file": record["local_file"],
        "publication_date": record["publication_date"],
        "status": record["status"],
        "authority": record["authority"],
        "audience": record["audience"],
        "notes": record["notes"],

        "page": record["page"],

        "section": None,

        "chunk_index": 1,

        "chunk_type": settings["page_role"],

        "retrieval_enabled": (
            settings["retrieval_enabled"]
        ),

        "word_count": len(text.split()),

        "text": text
    }

    return chunk


def is_numbered_heading(line):
    line = line.strip()

    dotted_heading = re.match(
        r"^\d+(?:\.\d+)+\b",
        line
    )

    top_level_heading = re.match(
        r"^\d+\s+[A-Z][A-Z\s\-&,()]+$",
        line
    )

    return bool(
        dotted_heading
        or top_level_heading
    )


def make_section_label(section_lines):
    first_line = section_lines[0].strip()

    if re.match(
        r"^\d+(?:\.\d+)+$",
        first_line
    ):
        if len(section_lines) > 1:
            second_line = section_lines[1].strip()
            second_words = second_line.split()

            if (
                second_line
                and len(second_words) <= 10
                and not second_line.endswith(
                    (".", ";", "?", "!")
                )
            ):
                return f"{first_line} {second_line}"

    return first_line


def get_heading_number(heading):

    match = re.match(
        r"^(\d+(?:\.\d+)*)",
        heading.strip()
    )

    if not match:
        return None

    return match.group(1)


def get_heading_level(heading):

    number = get_heading_number(
        heading
    )

    if number is None:
        return None

    return len(
        number.split(".")
    )


def is_parent_only_section(
    heading,
    section_lines
):

    section_text = " ".join(
        section_lines
    )

    word_count = len(
        section_text.split()
    )

    if word_count < 10:
        return True

    return False


def create_numbered_section_chunks(
    record,
    settings
):

    text = record["text"].strip()

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    heading_positions = []

    for index, line in enumerate(lines):

        if is_numbered_heading(line):

            heading_positions.append(
                {
                    "index": index,
                    "heading": line
                }
            )

    chunks = []

    hierarchy = {}

    chunk_number = 1

    for heading_number, heading_info in enumerate(
        heading_positions
    ):

        start_index = heading_info["index"]

        if (
            heading_number + 1
            < len(heading_positions)
        ):

            end_index = (
                heading_positions[
                    heading_number + 1
                ]["index"]
            )

        else:

            end_index = len(lines)

        section_lines = lines[
            start_index:end_index
        ]

        section_text = "\n".join(
            section_lines
        )

        section_label = (
            make_section_label(
                section_lines
            )
        )

        level = get_heading_level(
            heading_info["heading"]
        )

        if level is None:
            continue

        levels_to_remove = [
            existing_level
            for existing_level in hierarchy
            if existing_level >= level
        ]

        for existing_level in levels_to_remove:

            del hierarchy[
                existing_level
            ]

        parent_sections = [
            hierarchy[parent_level]
            for parent_level in sorted(
                hierarchy
            )
        ]

        hierarchy[level] = section_label

        if is_parent_only_section(
            heading_info["heading"],
            section_lines
        ):
            continue

        chunk_id = (
            f"{record['source_id']}"
            f"-p{record['page']:03d}"
            f"-c{chunk_number:02d}"
        )

        chunk = {
            "chunk_id": chunk_id,

            "source_id": record["source_id"],
            "title": record["title"],
            "source_type": record["source_type"],
            "system": record["system"],
            "application": record["application"],
            "url": record["url"],
            "local_file": record["local_file"],
            "publication_date": record["publication_date"],
            "status": record["status"],
            "authority": record["authority"],
            "audience": record["audience"],
            "notes": record["notes"],

            "page": record["page"],
            "section": section_label,
            "parent_sections": parent_sections,
            "section_level": level,
            "chunk_index": chunk_number,
            "chunk_type": "technical_section",
            "retrieval_enabled": (
                settings["retrieval_enabled"]
            ),
            "word_count": len(
                section_text.split()
            ),
            "text": section_text
        }

        chunks.append(chunk)

        chunk_number += 1

    return chunks


def is_plain_heading_block(block):

    block = block.strip()

    if not block:
        return False

    lines = [
        line.strip()
        for line in block.splitlines()
        if line.strip()
    ]

    if len(lines) != 1:
        return False

    line = lines[0]

    if re.match(
        r"^Page \d+ of \d+$",
        line,
        re.IGNORECASE
    ):
        return False

    if line.lower().startswith(
        "publication date:"
    ):
        return False

    if "@" in line:
        return False

    if "©" in line:
        return False

    if line.startswith(
        ("•", "-", "\uf0b7")
    ):
        return False

    words = line.split()

    if len(words) > 8:
        return False

    if line.endswith(
        (".", "?", "!", ";", ":")
    ):
        return False

    capitalised_words = sum(
        1
        for word in words
        if word
        and word[0].isupper()
    )

    if capitalised_words < max(
        1,
        len(words) // 2
    ):
        return False

    return True


def find_section_headings(
    text,
    include_numbered,
    include_plain
):

    raw_lines = text.splitlines()
    lines = []
    raw_to_clean_index = {}

    for raw_index, raw_line in enumerate(raw_lines):
        line = raw_line.strip()

        if not line:
            continue

        raw_to_clean_index[raw_index] = len(lines)
        lines.append(line)

    heading_positions = []

    for raw_index, clean_index in raw_to_clean_index.items():
        line = lines[clean_index]

        numbered_heading = (
            include_numbered
            and is_numbered_heading(line)
            and not re.fullmatch(
                r"0\.\d+",
                line
            )
        )

        if numbered_heading:
            heading_positions.append(
                {
                    "index": clean_index,
                    "heading": line,
                    "kind": "numbered",
                }
            )
            continue

        if not include_plain:
            continue

        if is_numbered_heading(line):
            continue

        blank_before = (
            raw_index == 0
            or not raw_lines[raw_index - 1].strip()
        )

        blank_after = (
            raw_index == len(raw_lines) - 1
            or not raw_lines[raw_index + 1].strip()
        )

        if include_numbered:
            blank_separated = (
                blank_before
                and blank_after
            )
        else:
            blank_separated = (
                blank_before
                or blank_after
            )

        if (
            blank_separated
            and is_plain_heading_block(line)
        ):
            heading_positions.append(
                {
                    "index": clean_index,
                    "heading": line,
                    "kind": "plain",
                }
            )

    return lines, heading_positions


def create_section_chunk(
    record,
    settings,
    section_text,
    section_label,
    chunk_number,
    parent_sections=None,
    section_level=None
):

    return {
        "chunk_id": (
            f"{record['source_id']}"
            f"-p{record['page']:03d}"
            f"-c{chunk_number:02d}"
        ),
        "source_id": record["source_id"],
        "title": record["title"],
        "source_type": record["source_type"],
        "system": record["system"],
        "application": record["application"],
        "url": record["url"],
        "local_file": record["local_file"],
        "publication_date": record["publication_date"],
        "status": record["status"],
        "authority": record["authority"],
        "audience": record["audience"],
        "notes": record["notes"],
        "page": record["page"],
        "section": section_label,
        "parent_sections": parent_sections or [],
        "section_level": section_level,
        "chunk_index": chunk_number,
        "chunk_type": "technical_section",
        "retrieval_enabled": (
            settings["retrieval_enabled"]
        ),
        "word_count": len(section_text.split()),
        "text": section_text,
    }


def create_detected_section_chunks(
    record,
    settings,
    include_numbered,
    include_plain
):

    lines, heading_positions = find_section_headings(
        record["text"],
        include_numbered,
        include_plain
    )

    if not lines:
        return []

    if not heading_positions:
        section_text = "\n".join(lines)

        return [
            create_section_chunk(
                record,
                settings,
                section_text,
                None,
                1
            )
        ]

    chunks = []
    hierarchy = {}

    for heading_index, heading_info in enumerate(
        heading_positions
    ):
        heading_line_index = heading_info["index"]

        if heading_index == 0:
            start_index = 0
        else:
            start_index = heading_line_index

        if heading_index + 1 < len(heading_positions):
            end_index = heading_positions[
                heading_index + 1
            ]["index"]
        else:
            end_index = len(lines)

        section_lines = lines[
            heading_line_index:end_index
        ]
        section_text = "\n".join(
            lines[start_index:end_index]
        )
        section_label = make_section_label(
            section_lines
        )

        parent_sections = []
        section_level = None

        if heading_info["kind"] == "numbered":
            section_level = get_heading_level(
                heading_info["heading"]
            )

            if section_level is not None:
                levels_to_remove = [
                    level
                    for level in hierarchy
                    if level >= section_level
                ]

                for level in levels_to_remove:
                    del hierarchy[level]

                parent_sections = [
                    hierarchy[level]
                    for level in sorted(hierarchy)
                ]
                hierarchy[section_level] = section_label

        elif hierarchy:
            parent_sections = [
                hierarchy[level]
                for level in sorted(hierarchy)
            ]

        chunks.append(
            create_section_chunk(
                record,
                settings,
                section_text,
                section_label,
                len(chunks) + 1,
                parent_sections,
                section_level
            )
        )

    return chunks


def merge_tiny_chunks(chunks, minimum_words=10):

    if not chunks:
        return []

    merged_chunks = []
    pending_chunks = []

    for chunk in chunks:

        chunk_copy = chunk.copy()

        if chunk_copy["word_count"] < minimum_words:
            pending_chunks.append(chunk_copy)
            continue

        if pending_chunks:
            preceding_text = [
                pending_chunk["text"]
                for pending_chunk in pending_chunks
            ]

            chunk_copy["text"] = "\n".join(
                preceding_text
                + [chunk_copy["text"]]
            )

            pending_chunks = []

        chunk_copy["word_count"] = len(
            chunk_copy["text"].split()
        )

        merged_chunks.append(chunk_copy)

    if pending_chunks:

        pending_text = "\n".join(
            chunk["text"]
            for chunk in pending_chunks
        )

        if merged_chunks:
            merged_chunks[-1]["text"] = "\n".join(
                [
                    merged_chunks[-1]["text"],
                    pending_text,
                ]
            )

            merged_chunks[-1]["word_count"] = len(
                merged_chunks[-1]["text"].split()
            )

        else:
            final_chunk = pending_chunks[-1]
            final_chunk["text"] = pending_text
            final_chunk["word_count"] = len(
                final_chunk["text"].split()
            )
            merged_chunks.append(final_chunk)

    for chunk_index, chunk in enumerate(
        merged_chunks,
        start=1
    ):
        chunk["chunk_index"] = chunk_index
        chunk["chunk_id"] = (
            f"{chunk['source_id']}"
            f"-p{chunk['page']:03d}"
            f"-c{chunk_index:02d}"
        )

    return merged_chunks


def create_plain_section_chunks(record, settings):

    return merge_tiny_chunks(
        create_detected_section_chunks(
            record,
            settings,
            include_numbered=False,
            include_plain=True
        )
    )


def create_mixed_section_chunks(record, settings):

    return merge_tiny_chunks(
        create_detected_section_chunks(
            record,
            settings,
            include_numbered=True,
            include_plain=True
        )
    )


def create_fire_report_chunks(record, settings):

    return [
        create_page_chunk(
            record,
            settings
        )
    ]


def create_detail_page_chunk(record, settings):

    chunk = create_page_chunk(
        record,
        settings
    )

    chunk["chunk_type"] = "architectural_detail"
    chunk["detail_code"] = None

    if not settings["retrieval_enabled"]:
        return chunk

    detail_match = re.search(
        r"\bIWI\s+(\d{3})([a-z])\b",
        record["text"],
        re.IGNORECASE
    )

    if detail_match is None:
        return chunk

    detail_code = (
        f"IWI {detail_match.group(1)}"
        f"{detail_match.group(2).lower()}"
    )

    chunk["detail_code"] = detail_code
    chunk["section"] = detail_code

    lines = [
        line.strip()
        for line in record["text"].splitlines()
        if line.strip()
    ]

    code_line_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(
                r"IWI\s+\d{3}[a-z]",
                line,
                re.IGNORECASE
            )
        ),
        None
    )

    if code_line_index is None:
        return chunk

    ignored_lines = {
        "Architectural Details - With Notes",
        "Drawing Title",
        "Drawing No.",
    }

    for line in lines[code_line_index + 1:]:

        if re.fullmatch(
            r"IWI\s+\d{3}[a-z]",
            line,
            re.IGNORECASE
        ):
            continue

        if line in ignored_lines:
            continue

        title = re.sub(
            r"\s+-\s+(?:Section|Plan)$",
            "",
            line,
            flags=re.IGNORECASE
        ).strip()

        if not title:
            continue

        if len(title.split()) > 12:
            continue

        chunk["section"] = (
            f"{detail_code} - {title}"
        )
        break

    return chunk


def create_webpage_chunk(record, chunk_index):

    is_faq = record["source_type"] == "faq_webpage"

    if is_faq:
        text = (
            f"Question: {record['question']}\n"
            f"Answer: {record['answer']}"
        )
        chunk_type = "faq"
    else:
        text = record["text"].strip()
        chunk_type = "web_section"

    chunk = {
        "chunk_id": (
            f"{record['source_id']}"
            f"-web-c{chunk_index:02d}"
        ),
        "source_id": record["source_id"],
        "title": record["title"],
        "source_type": record["source_type"],
        "system": record["system"],
        "application": record["application"],
        "url": record["url"],
        "local_file": record["local_file"],
        "publication_date": record["publication_date"],
        "status": record["status"],
        "authority": record["authority"],
        "audience": record["audience"],
        "notes": record["notes"],
        "page": None,
        "section": record["section"],
        "chunk_index": chunk_index,
        "chunk_type": chunk_type,
        "retrieval_enabled": (
            record["retrieval_enabled"]
        ),
        "word_count": len(text.split()),
        "text": text,
    }

    if is_faq:
        chunk["question"] = record["question"]
        chunk["answer"] = record["answer"]

    return chunk


def create_chunks_for_record(record):

    settings = resolve_page_settings(record)
    strategy = settings["strategy"]

    if strategy == "page":
        return [
            create_page_chunk(
                record,
                settings
            )
        ]

    if strategy == "numbered_sections":
        return create_numbered_section_chunks(
            record,
            settings
        )

    if strategy == "plain_sections":
        return create_plain_section_chunks(
            record,
            settings
        )

    if strategy == "mixed_sections":
        return create_mixed_section_chunks(
            record,
            settings
        )

    if strategy == "fire_report":
        return create_fire_report_chunks(
            record,
            settings
        )

    if strategy == "detail_pages":
        return [
            create_detail_page_chunk(
                record,
                settings
            )
        ]

    raise ValueError(
        f"Unknown chunking strategy: {strategy}"
    )


# ---------------------------------
# Read page records
# ---------------------------------

with PAGES_FILE.open(
    "r",
    encoding="utf-8"
) as file:

    records = [
        json.loads(line)
        for line in file
    ]


# ---------------------------------
# Build all chunks in memory
# ---------------------------------

all_chunks = []
page_chunks = {}

chunks_by_source = {}
chunks_by_strategy = {}

warnings = []


for record in records:

    settings = resolve_page_settings(record)
    strategy = settings["strategy"]

    chunks = create_chunks_for_record(record)

    page_key = (
        record["source_id"],
        record["page"]
    )

    page_chunks[page_key] = chunks
    all_chunks.extend(chunks)

    source_id = record["source_id"]

    chunks_by_source[source_id] = (
        chunks_by_source.get(source_id, 0)
        + len(chunks)
    )

    chunks_by_strategy[strategy] = (
        chunks_by_strategy.get(strategy, 0)
        + len(chunks)
    )

    if (
        settings["retrieval_enabled"]
        and not chunks
    ):
        warnings.append(
            f"{source_id} page {record['page']}: "
            f"retrieval-enabled page produced zero chunks"
        )


if not WEBPAGES_FILE.exists():
    raise ValueError(
        "Webpage records not found. Run "
        "src/extract_webpages.py first."
    )


with WEBPAGES_FILE.open(
    "r",
    encoding="utf-8"
) as file:
    webpage_records = [
        json.loads(line)
        for line in file
    ]


web_chunk_indexes = {}

for record in webpage_records:
    source_id = record["source_id"]

    chunk_index = (
        web_chunk_indexes.get(source_id, 0)
        + 1
    )

    web_chunk_indexes[source_id] = chunk_index

    chunk = create_webpage_chunk(
        record,
        chunk_index
    )

    all_chunks.append(chunk)

    chunks_by_source[source_id] = (
        chunks_by_source.get(source_id, 0)
        + 1
    )

    chunks_by_strategy[chunk["chunk_type"]] = (
        chunks_by_strategy.get(
            chunk["chunk_type"],
            0
        )
        + 1
    )


retrieval_enabled_chunks = sum(
    1
    for chunk in all_chunks
    if chunk["retrieval_enabled"]
)

retrieval_disabled_chunks = (
    len(all_chunks)
    - retrieval_enabled_chunks
)


chunk_id_counts = {}


for chunk in all_chunks:

    chunk_id = chunk["chunk_id"]

    chunk_id_counts[chunk_id] = (
        chunk_id_counts.get(chunk_id, 0)
        + 1
    )

    section = chunk["section"]
    word_count = chunk["word_count"]

    if (
        section
        and re.fullmatch(
            r"\d+(?:\.\d+)*",
            section
        )
    ):
        warnings.append(
            f"{chunk_id}: number-only section label "
            f"({section})"
        )

    if word_count < 10:
        warnings.append(
            f"{chunk_id}: chunk under 10 words "
            f"({word_count})"
        )

    if word_count > 550:
        warnings.append(
            f"{chunk_id}: chunk over 550 words "
            f"({word_count})"
        )


for chunk_id, count in chunk_id_counts.items():

    if count > 1:
        warnings.append(
            f"{chunk_id}: duplicate chunk ID "
            f"({count} occurrences)"
        )


# ---------------------------------
# Concise audit
# ---------------------------------

print("CHUNK AUDIT")
print("=" * 70)

print(
    f"Total pages processed: "
    f"{len(records)}"
)

print(
    f"Total chunks produced: "
    f"{len(all_chunks)}"
)

print("\nChunks by source:")

for source_id, count in sorted(
    chunks_by_source.items()
):
    print(f"{source_id}: {count}")


print("\nChunks by strategy:")

for strategy, count in sorted(
    chunks_by_strategy.items()
):
    print(f"{strategy}: {count}")


print(
    f"\nRetrieval-enabled chunks: "
    f"{retrieval_enabled_chunks}"
)

print(
    f"Retrieval-disabled chunks: "
    f"{retrieval_disabled_chunks}"
)


print(f"\nWarnings: {len(warnings)}")

for warning in warnings:
    print(f"- {warning}")


# ---------------------------------
# Targeted summaries
# ---------------------------------

summary_pages = [
    ("WSI-ASSESS-001", 14),
    ("WSI-DESIGN-001", 17),
    ("WSI-FIRE-001", 2),
    ("WSI-FIRE-001", 4),
    ("WSI-FIRE-001", 5),
]


print("\nTARGETED CHUNK SUMMARIES")
print("=" * 70)


for source_id, page in summary_pages:

    chunks = page_chunks.get(
        (source_id, page),
        []
    )

    print(
        f"\n{source_id} page {page} "
        f"({len(chunks)} chunks)"
    )

    for chunk in chunks:

        preview = " ".join(
            chunk["text"].split()
        )[:150]

        print(f"chunk_id: {chunk['chunk_id']}")
        print(f"section: {chunk['section']}")
        print(f"chunk_type: {chunk['chunk_type']}")
        print(f"word_count: {chunk['word_count']}")
        print(
            "retrieval_enabled: "
            f"{chunk['retrieval_enabled']}"
        )
        print(f"preview: {preview}")
        print("-" * 70)


# ---------------------------------
# Architectural detail sanity check
# ---------------------------------

detail_page_chunks = []

for page in range(1, 25):

    chunks = page_chunks.get(
        ("WSI-DETAILS-001", page),
        []
    )

    if len(chunks) != 1:
        raise ValueError(
            "Expected one architectural-detail chunk "
            f"for page {page}, found {len(chunks)}."
        )

    detail_page_chunks.append(chunks[0])


detail_disabled_pages = {
    chunk["page"]
    for chunk in detail_page_chunks
    if not chunk["retrieval_enabled"]
}

detail_enabled_pages = {
    chunk["page"]
    for chunk in detail_page_chunks
    if chunk["retrieval_enabled"]
}


if detail_disabled_pages != {1, 2, 3, 4, 24}:
    raise ValueError(
        "Unexpected retrieval-disabled architectural "
        f"detail pages: {sorted(detail_disabled_pages)}"
    )

if detail_enabled_pages != set(range(5, 24)):
    raise ValueError(
        "Unexpected retrieval-enabled architectural "
        f"detail pages: {sorted(detail_enabled_pages)}"
    )


print("\nARCHITECTURAL DETAIL SANITY CHECK")
print("=" * 70)

for chunk in detail_page_chunks:
    print(f"page: {chunk['page']}")
    print(f"detail_code: {chunk['detail_code']}")
    print(f"section: {chunk['section']}")
    print(
        "retrieval_enabled: "
        f"{chunk['retrieval_enabled']}"
    )
    print(f"word_count: {chunk['word_count']}")
    print("-" * 70)


# ---------------------------------
# Write and validate final JSONL
# ---------------------------------

with CHUNKS_FILE.open(
    "w",
    encoding="utf-8"
) as file:

    for chunk in all_chunks:
        file.write(
            json.dumps(
                chunk,
                ensure_ascii=False
            )
            + "\n"
        )


with CHUNKS_FILE.open(
    "r",
    encoding="utf-8"
) as file:

    written_chunks = [
        json.loads(line)
        for line in file
    ]


written_chunk_ids = {
    chunk["chunk_id"]
    for chunk in written_chunks
}

written_retrieval_enabled = sum(
    1
    for chunk in written_chunks
    if chunk["retrieval_enabled"]
)

written_retrieval_disabled = sum(
    1
    for chunk in written_chunks
    if not chunk["retrieval_enabled"]
)


if not CHUNKS_FILE.exists():
    raise ValueError("Chunk output file was not created.")

if len(records) != 122:
    raise ValueError(
        "Expected 122 page records, "
        f"found {len(records)}."
    )

if written_chunks != all_chunks:
    raise ValueError(
        "Written chunks do not match the chunks "
        "built in memory."
    )

if len(written_chunk_ids) != len(written_chunks):
    raise ValueError(
        "Duplicate chunk IDs found in written output."
    )

if (
    written_retrieval_enabled
    != retrieval_enabled_chunks
):
    raise ValueError(
        "Written retrieval-enabled count does not "
        "match the in-memory count."
    )

if (
    written_retrieval_disabled
    != retrieval_disabled_chunks
):
    raise ValueError(
        "Written retrieval-disabled count does not "
        "match the in-memory count."
    )


page_source_ids = {
    record["source_id"]
    for record in records
}

chunk_source_ids = {
    chunk["source_id"]
    for chunk in written_chunks
}

webpage_source_ids = {
    record["source_id"]
    for record in webpage_records
}

pdf_chunk_source_ids = {
    source_id
    for source_id in chunk_source_ids
    if source_id in page_source_ids
}


if len(page_source_ids) != 13:
    raise ValueError(
        "Expected 13 registered PDF sources, "
        f"found {len(page_source_ids)}."
    )

if pdf_chunk_source_ids != page_source_ids:
    raise ValueError(
        "Not every registered PDF source is "
        "represented in chunks.jsonl."
    )

if webpage_source_ids != {
    "WSI-WEB-001",
    "WSI-FAQ-001",
}:
    raise ValueError(
        "Expected both registered webpage sources, "
        f"found {sorted(webpage_source_ids)}."
    )

if chunk_source_ids != (
    page_source_ids
    | webpage_source_ids
):
    raise ValueError(
        "Not every registered source is represented "
        "in chunks.jsonl."
    )


print("\nCHUNKING V1 COMPLETE")
print(f"Output: {CHUNKS_FILE}")
print(f"Records written: {len(written_chunks)}")
print(f"Unique chunk IDs: {len(written_chunk_ids)}")
print(
    f"Retrieval enabled: "
    f"{written_retrieval_enabled}"
)
print(
    f"Retrieval disabled: "
    f"{written_retrieval_disabled}"
)
print("JSON validation: PASSED")
