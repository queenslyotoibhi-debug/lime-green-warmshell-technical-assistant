import re

from hybrid_search import hybrid_search
from query_processor import process_query


MATCH_FACTOR = 1.10
MISMATCH_FACTOR = 0.95
NEUTRAL_FACTOR = 1.00


SOURCE_STAGE_PREFIXES = {
    "WSI-ASSESS-": "assess",
    "WSI-DESIGN-": "design",
    "WSI-DETAILS-": "design",
    "WSI-SPEC-": "design",
    "WSI-INSTALL-": "install",
    "WSI-MAINT-": "maintain",
    "WSI-WARRANTY-": "warranty",
}


SECTION_STAGE_PATTERNS = [
    (
        "warranty",
        re.compile(r"\b(?:warranty|guarantee)\b", re.IGNORECASE)
    ),
    (
        "maintain",
        re.compile(
            r"\b(?:maintenance|maintain|care|repair)\b",
            re.IGNORECASE
        )
    ),
    (
        "assess",
        re.compile(
            r"\b(?:assessment|survey|suitability|existing condition|"
            r"external condition)\b",
            re.IGNORECASE
        )
    ),
    (
        "install",
        re.compile(
            r"\b(?:install|installed|installing|installation|fixing|"
            r"apply|fit|fitting)\b",
            re.IGNORECASE
        )
    ),
    (
        "design",
        re.compile(
            r"\b(?:design|detail|detailed|detailing|drawing)\b",
            re.IGNORECASE
        )
    ),
]


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


def detect_document_stage(result):
    source_id = result.get("source_id") or ""

    for prefix, stage in SOURCE_STAGE_PREFIXES.items():
        if source_id.startswith(prefix):
            return stage

    # Supporting documents stay neutral unless their section metadata contains
    # an explicit lifecycle cue. This avoids guessing from general body text.
    section_metadata = " ".join(
        str(value)
        for value in (
            result.get("section"),
            result.get("detail_code"),
        )
        if value
    )

    for stage, pattern in SECTION_STAGE_PATTERNS:
        if pattern.search(section_metadata):
            return stage

    return "neutral"


def apply_lifecycle_reranking(results, query_stage):
    reranked_results = []

    for result in results:
        governed_result = dict(result)
        document_stage = detect_document_stage(result)

        if query_stage == "unknown" or document_stage == "neutral":
            stage_match = None
            stage_factor = NEUTRAL_FACTOR
        elif document_stage == query_stage:
            stage_match = True
            stage_factor = MATCH_FACTOR
        else:
            stage_match = False
            stage_factor = MISMATCH_FACTOR

        # The adjustment is deliberately small: stage evidence can reorder
        # close RRF results, while every mismatched result remains eligible.
        governed_result.update({
            "original_rrf_rank": result["rank"],
            "query_stage": query_stage,
            "document_stage": document_stage,
            "stage_match": stage_match,
            "stage_factor": stage_factor,
            "governed_score": result["rrf_score"] * stage_factor,
        })
        reranked_results.append(governed_result)

    reranked_results.sort(
        key=lambda result: result["governed_score"],
        reverse=True
    )

    for final_rank, result in enumerate(reranked_results, start=1):
        result["final_rank"] = final_rank

    return reranked_results


def governed_search(query, top_k=5):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    processed_query = process_query(query)
    hybrid_output = hybrid_search(query, top_k=20)
    governed_results = apply_lifecycle_reranking(
        hybrid_output["results"],
        processed_query["stage"]
    )
    final_results = governed_results[:top_k]
    final_chunk_ids = [
        result["chunk_id"]
        for result in final_results
    ]

    if len(final_chunk_ids) != len(set(final_chunk_ids)):
        raise ValueError(
            "Duplicate chunk IDs found in final governed results."
        )

    return {
        "processed_query": processed_query,
        "rrf_results": hybrid_output["results"],
        "results": final_results,
    }


def print_comparison(query, output):
    processed_query = output["processed_query"]

    print(f"QUERY: {query}")
    print(f"Stage: {processed_query['stage']}")
    print(f"Topics: {processed_query['topics']}")
    print(f"Exact terms: {processed_query['exact_terms']}")

    print("\nRRF TOP 5")
    for result in output["rrf_results"][:5]:
        print(
            f"{result['rank']}. {result['chunk_id']} "
            f"| RRF {result['rrf_score']:.8f}"
        )

    print("\nGOVERNED TOP 5")
    for result in output["results"]:
        section_or_detail = (
            result.get("detail_code")
            or result.get("section")
        )
        print(f"\nFinal rank: {result['final_rank']}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(
            f"Source: {result['source_id']} - "
            f"{result['title']}"
        )
        print(f"Section / Detail: {section_or_detail}")
        print(f"Original RRF rank: {result['original_rrf_rank']}")
        print(f"RRF score: {result['rrf_score']:.8f}")
        print(f"Semantic rank: {result['semantic_rank']}")
        print(f"BM25 rank: {result['bm25_rank']}")
        print(f"Query stage: {result['query_stage']}")
        print(f"Document stage: {result['document_stage']}")
        print(f"Stage match: {result['stage_match']}")
        print(f"Stage factor: {result['stage_factor']:.2f}")
        print(f"Governed score: {result['governed_score']:.8f}")


def main():
    for query_number, query in enumerate(TEST_QUERIES, start=1):
        if query_number > 1:
            print(f"\n{'=' * 78}\n")

        print(f"TEST QUERY {query_number}")
        output = governed_search(query, top_k=5)
        print_comparison(query, output)


if __name__ == "__main__":
    main()
