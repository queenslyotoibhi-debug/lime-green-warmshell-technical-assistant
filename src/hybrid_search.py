from bm25_search import bm25_search
from query_processor import process_query
from semantic_search import load_index, semantic_search


SEMANTIC_CANDIDATES = 20
BM25_CANDIDATES = 20
RRF_K = 60


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


CHUNK_METADATA_FIELDS = [
    "chunk_id",
    "source_id",
    "title",
    "source_type",
    "authority",
    "page",
    "section",
    "detail_code",
    "chunk_type",
    "url",
    "text",
]


def reciprocal_rank_fusion(
    semantic_results,
    bm25_results,
    chunk_lookup=None,
    k=RRF_K
):
    if k < 0:
        raise ValueError("RRF k must be zero or greater.")

    chunk_lookup = chunk_lookup or {}
    fused = {}

    def get_fused_record(result):
        chunk_id = result.get("chunk_id")

        if not chunk_id:
            raise ValueError("A retrieval result is missing its chunk_id.")

        if chunk_id not in fused:
            full_chunk = chunk_lookup.get(chunk_id, {})
            fused[chunk_id] = {
                field: full_chunk.get(field, result.get(field))
                for field in CHUNK_METADATA_FIELDS
            }
            fused[chunk_id].update({
                "semantic_rank": None,
                "semantic_score": None,
                "bm25_rank": None,
                "bm25_score": None,
                "rrf_score": 0.0,
            })

        return fused[chunk_id]

    for result in semantic_results:
        rank = result.get("rank")

        if not isinstance(rank, int) or rank < 1:
            raise ValueError("Semantic results must have positive integer ranks.")

        fused_record = get_fused_record(result)
        fused_record["semantic_rank"] = rank
        fused_record["semantic_score"] = result.get("similarity_score")
        fused_record["rrf_score"] += 1 / (k + rank)

    for result in bm25_results:
        rank = result.get("rank")

        if not isinstance(rank, int) or rank < 1:
            raise ValueError("BM25 results must have positive integer ranks.")

        fused_record = get_fused_record(result)
        fused_record["bm25_rank"] = rank
        fused_record["bm25_score"] = result.get("bm25_score")
        fused_record["rrf_score"] += 1 / (k + rank)

    ranked_results = sorted(
        fused.values(),
        key=lambda result: result["rrf_score"],
        reverse=True
    )

    for rank, result in enumerate(ranked_results, start=1):
        result["rank"] = rank

    return ranked_results


def hybrid_search(query, top_k=5):
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    processed_query = process_query(query)
    semantic_results = semantic_search(
        query,
        top_k=SEMANTIC_CANDIDATES
    )
    bm25_output = bm25_search(
        query,
        top_k=BM25_CANDIDATES
    )
    bm25_results = bm25_output["results"]

    if len(semantic_results) != SEMANTIC_CANDIDATES:
        raise ValueError(
            "Expected 20 semantic candidates, "
            f"found {len(semantic_results)}."
        )

    if len(bm25_results) != BM25_CANDIDATES:
        raise ValueError(
            "Expected 20 BM25 candidates, "
            f"found {len(bm25_results)}."
        )

    _, chunks, _ = load_index()
    chunk_lookup = {
        chunk["chunk_id"]: chunk
        for chunk in chunks
    }
    fused_results = reciprocal_rank_fusion(
        semantic_results,
        bm25_results,
        chunk_lookup=chunk_lookup,
        k=RRF_K
    )
    final_results = fused_results[:top_k]
    final_chunk_ids = [
        result["chunk_id"]
        for result in final_results
    ]

    if len(final_chunk_ids) != len(set(final_chunk_ids)):
        raise ValueError("Duplicate chunk IDs found in final hybrid results.")

    return {
        "processed_query": processed_query,
        "semantic_candidates": semantic_results,
        "bm25_candidates": bm25_results,
        "rrf_k": RRF_K,
        "fused_candidate_count": len(fused_results),
        "results": final_results,
    }


def print_hybrid_output(query, output):
    processed_query = output["processed_query"]

    print(f"QUERY: {query}")
    print(f"Stage: {processed_query['stage']}")
    print(f"Topics: {processed_query['topics']}")
    print(f"Exact terms: {processed_query['exact_terms']}")
    print("\nHYBRID TOP 5")

    for result in output["results"]:
        section_or_detail = (
            result["detail_code"]
            or result["section"]
        )

        print(f"\nRank: {result['rank']}")
        print(f"RRF score: {result['rrf_score']:.8f}")
        print(f"Chunk ID: {result['chunk_id']}")
        print(
            f"Source: {result['source_id']} - "
            f"{result['title']}"
        )
        print(f"Section / Detail: {section_or_detail}")
        print(f"Semantic rank: {result['semantic_rank']}")
        print(f"BM25 rank: {result['bm25_rank']}")

    semantic_top_five = [
        result["chunk_id"]
        for result in output["semantic_candidates"][:5]
    ]
    bm25_top_five = [
        result["chunk_id"]
        for result in output["bm25_candidates"][:5]
    ]
    hybrid_top_five = [
        result["chunk_id"]
        for result in output["results"]
    ]

    print("\nSEMANTIC TOP 5:")
    print(semantic_top_five)
    print("BM25 TOP 5:")
    print(bm25_top_five)
    print("HYBRID TOP 5:")
    print(hybrid_top_five)

    duplicate_count = (
        len(hybrid_top_five)
        - len(set(hybrid_top_five))
    )

    print("\nVALIDATION")
    print(
        "Semantic candidates per query: "
        f"{len(output['semantic_candidates'])}"
    )
    print(
        "BM25 candidates per query: "
        f"{len(output['bm25_candidates'])}"
    )
    print(f"RRF k: {output['rrf_k']}")
    print(
        "Duplicate chunk IDs in fused result: "
        f"{duplicate_count}"
    )
    print(f"Final results: {len(output['results'])}")


def main():
    for query_number, query in enumerate(TEST_QUERIES, start=1):
        if query_number > 1:
            print(f"\n{'=' * 78}\n")

        print(f"TEST QUERY {query_number}")
        output = hybrid_search(query, top_k=5)
        print_hybrid_output(query, output)


if __name__ == "__main__":
    main()
