from collections import Counter
from pathlib import Path
import json
import math
import re

import numpy as np

from query_processor import process_query


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = (
    PROJECT_ROOT
    / "data"
    / "embeddings"
    / "embedding_index.jsonl"
)

EXPECTED_RECORD_COUNT = 219
K1 = 1.5
B = 0.75


TEST_QUERIES = [
    (
        "What should be considered if there is damp or moisture in the wall "
        "before installing Warmshell Internal?"
    ),
    "What does IWI 005e say about electrical services?",
    "What is the B-s1,d0 fire classification?",
    "How should an existing window reveal be detailed?",
    "What are the Warmshell warranty conditions?",
]


def load_chunks():
    with INDEX_FILE.open("r", encoding="utf-8") as file:
        chunks = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    if len(chunks) != EXPECTED_RECORD_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_RECORD_COUNT} BM25 index records, "
            f"found {len(chunks)}."
        )

    chunk_ids = [chunk.get("chunk_id") for chunk in chunks]
    duplicate_count = len(chunk_ids) - len(set(chunk_ids))

    if duplicate_count:
        raise ValueError(
            f"BM25 index contains {duplicate_count} duplicate chunk IDs."
        )

    return chunks


def build_searchable_text(chunk):
    parts = []
    title = chunk.get("title")
    section = chunk.get("section")
    detail_code = chunk.get("detail_code")
    question = chunk.get("question")
    text = chunk.get("text")

    if title:
        parts.append(title)

    if detail_code:
        parts.append(detail_code)

    if section:
        parts.append(section)

    if question and (not text or question not in text):
        parts.append(question)

    if text:
        parts.append(text)

    return "\n".join(parts)


def tokenize(text):
    return re.findall(
        r"[a-z0-9]+(?:[-,][a-z0-9]+)*",
        text.lower()
    )


def build_bm25_index(chunks):
    document_tokens = [
        tokenize(build_searchable_text(chunk))
        for chunk in chunks
    ]
    term_frequencies = [
        Counter(tokens)
        for tokens in document_tokens
    ]
    document_lengths = np.asarray(
        [len(tokens) for tokens in document_tokens],
        dtype=np.float32
    )

    if np.any(document_lengths == 0):
        raise ValueError("The BM25 corpus contains an empty document.")

    document_frequencies = Counter()

    for frequencies in term_frequencies:
        document_frequencies.update(frequencies.keys())

    document_count = len(chunks)
    inverse_document_frequencies = {
        term: math.log(
            1
            + (
                document_count
                - frequency
                + 0.5
            )
            / (frequency + 0.5)
        )
        for term, frequency in document_frequencies.items()
    }

    return {
        "term_frequencies": term_frequencies,
        "document_lengths": document_lengths,
        "average_document_length": float(document_lengths.mean()),
        "inverse_document_frequencies": inverse_document_frequencies,
    }


def calculate_bm25_scores(query, bm25_index, k1=K1, b=B):
    term_frequencies = bm25_index["term_frequencies"]
    document_lengths = bm25_index["document_lengths"]
    average_document_length = bm25_index["average_document_length"]
    inverse_document_frequencies = (
        bm25_index["inverse_document_frequencies"]
    )
    scores = np.zeros(len(term_frequencies), dtype=np.float64)

    for term in set(tokenize(query)):
        inverse_document_frequency = inverse_document_frequencies.get(term)

        if inverse_document_frequency is None:
            continue

        for document_index, frequencies in enumerate(term_frequencies):
            term_frequency = frequencies.get(term, 0)

            if term_frequency == 0:
                continue

            length_normalisation = (
                1
                - b
                + b
                * document_lengths[document_index]
                / average_document_length
            )
            term_score = (
                inverse_document_frequency
                * term_frequency
                * (k1 + 1)
                / (term_frequency + k1 * length_normalisation)
            )
            scores[document_index] += term_score

    return scores


def bm25_search(query, top_k=5):
    chunks = load_chunks()
    bm25_index = build_bm25_index(chunks)
    processed_query = process_query(query)
    scores = calculate_bm25_scores(
        processed_query["normalized_query"],
        bm25_index
    )

    result_count = min(top_k, len(chunks))
    ranked_indices = np.argsort(-scores, kind="stable")[:result_count]
    results = []

    for rank, index in enumerate(ranked_indices, start=1):
        chunk = chunks[int(index)]
        results.append({
            "rank": rank,
            "bm25_score": float(scores[index]),
            "chunk_id": chunk.get("chunk_id"),
            "source_id": chunk.get("source_id"),
            "title": chunk.get("title"),
            "authority": chunk.get("authority"),
            "page": chunk.get("page"),
            "section": chunk.get("section"),
            "detail_code": chunk.get("detail_code"),
            "chunk_type": chunk.get("chunk_type"),
            "text": chunk.get("text"),
        })

    return {
        "processed_query": processed_query,
        "results": results,
    }


def print_search(search_output):
    processed_query = search_output["processed_query"]

    print(f"Processed query: {processed_query['normalized_query']}")
    print(f"Exact terms: {processed_query['exact_terms']}")
    print(f"Entities: {processed_query['entities']}")
    print(f"Topics: {processed_query['topics']}")
    print(f"Stage: {processed_query['stage']}")
    print("\nTop 5:")

    for result in search_output["results"]:
        section_or_detail = (
            result["detail_code"]
            or result["section"]
        )
        preview = (result["text"] or "")[:200].replace("\n", " ")

        print(f"\nRank: {result['rank']}")
        print(f"Score: {result['bm25_score']:.6f}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(
            f"Source: {result['source_id']} - "
            f"{result['title']}"
        )
        print(f"Section/detail code: {section_or_detail}")
        print(f"Preview: {preview}")


def main():
    chunks = load_chunks()
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]

    print(f"Index records loaded: {len(chunks)}")
    print(
        "Duplicate chunk IDs: "
        f"{len(chunk_ids) - len(set(chunk_ids))}"
    )

    for query_number, query in enumerate(TEST_QUERIES, start=1):
        print(f"\n{'=' * 72}")
        print(f"QUERY {query_number}")
        print_search(bm25_search(query, top_k=5))


if __name__ == "__main__":
    main()
