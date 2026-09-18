from pathlib import Path
import hashlib
import json

import numpy as np
import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent

EMBEDDINGS_FOLDER = PROJECT_ROOT / "data" / "embeddings"
EMBEDDINGS_FILE = EMBEDDINGS_FOLDER / "embeddings.npy"
INDEX_FILE = EMBEDDINGS_FOLDER / "embedding_index.jsonl"
MANIFEST_FILE = EMBEDDINGS_FOLDER / "embedding_manifest.json"
CHUNKS_FILE = PROJECT_ROOT / "data" / "structured" / "chunks.jsonl"

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "qwen3-embedding:4b"
EMBEDDING_DIMENSIONS = 2560
REQUEST_TIMEOUT = 600

QUERY_INSTRUCTION = (
    "Given a user question about Warmshell Internal, "
    "retrieve the most relevant technical passage that can answer the question."
)

TEST_QUERY = (
    "What should be considered if there is damp or moisture in the wall "
    "before installing Warmshell Internal?"
)


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def load_index():
    embeddings = np.load(EMBEDDINGS_FILE, allow_pickle=False)

    with INDEX_FILE.open("r", encoding="utf-8") as file:
        chunks = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    with MANIFEST_FILE.open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    if embeddings.ndim != 2:
        raise ValueError(
            "Expected embeddings.npy to contain a two-dimensional array, "
            f"found shape {embeddings.shape}."
        )

    if embeddings.shape[0] != len(chunks):
        raise ValueError(
            "Embedding index is inconsistent: "
            f"{embeddings.shape[0]} vectors but {len(chunks)} index records."
        )

    manifest_dimensions = manifest.get("embedding_dimensions")

    if embeddings.shape[1] != manifest_dimensions:
        raise ValueError(
            "Embedding dimensions do not match the manifest: "
            f"vectors have {embeddings.shape[1]}, "
            f"manifest has {manifest_dimensions}."
        )

    manifest_model = manifest.get("embedding_model")

    if manifest_model != MODEL:
        raise ValueError(
            "Unexpected embedding model in manifest: "
            f"expected {MODEL}, found {manifest_model}."
        )

    stored_hash = manifest.get("chunks_jsonl_sha256")
    current_hash = calculate_sha256(CHUNKS_FILE)

    if stored_hash != current_hash:
        raise ValueError(
            "The embeddings are stale because data/structured/chunks.jsonl "
            "does not match the SHA-256 stored in the embedding manifest. "
            "Rebuild the embeddings before searching."
        )

    return embeddings, chunks, manifest


def embed_query(query):
    embedding_input = (
        f"Instruct: {QUERY_INSTRUCTION}\n"
        f"Query: {query}"
    )

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "input": embedding_input,
            "keep_alive": 0,
        },
        timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    data = response.json()
    embeddings = data.get("embeddings")

    if not isinstance(embeddings, list) or len(embeddings) != 1:
        raise ValueError(
            "Ollama response must contain exactly one query embedding."
        )

    query_vector = np.asarray(embeddings[0], dtype=np.float32)

    if query_vector.shape != (EMBEDDING_DIMENSIONS,):
        raise ValueError(
            "Unexpected query vector dimensions: "
            f"expected {EMBEDDING_DIMENSIONS}, found {query_vector.size}."
        )

    return query_vector


def cosine_similarity(query_vector, document_vectors):
    query_norm = np.linalg.norm(query_vector)
    document_norms = np.linalg.norm(document_vectors, axis=1)

    if query_norm == 0:
        raise ValueError("Cannot compare a zero-length query vector.")

    if np.any(document_norms == 0):
        raise ValueError("The index contains a zero-length document vector.")

    normalised_query = query_vector / query_norm
    normalised_documents = document_vectors / document_norms[:, np.newaxis]

    return normalised_documents @ normalised_query


def semantic_search(query, top_k=5):
    embeddings, chunks, manifest = load_index()
    query_vector = embed_query(query)
    scores = cosine_similarity(query_vector, embeddings)

    result_count = min(top_k, len(chunks))
    ranked_indices = np.argsort(scores)[::-1][:result_count]
    results = []

    for rank, index in enumerate(ranked_indices, start=1):
        chunk = chunks[int(index)]
        results.append({
            "rank": rank,
            "similarity_score": float(scores[index]),
            "chunk_id": chunk.get("chunk_id"),
            "source_id": chunk.get("source_id"),
            "title": chunk.get("title"),
            "source_type": chunk.get("source_type"),
            "authority": chunk.get("authority"),
            "page": chunk.get("page"),
            "section": chunk.get("section"),
            "detail_code": chunk.get("detail_code"),
            "chunk_type": chunk.get("chunk_type"),
            "url": chunk.get("url"),
            "text": chunk.get("text"),
        })

    return results


def print_results(query, results):
    print("QUERY:")
    print(query)

    for result in results:
        preview = (result["text"] or "")[:350].replace("\n", " ")

        print(f"\nRESULT {result['rank']}")
        print(f"Score: {result['similarity_score']:.6f}")
        print(f"Chunk: {result['chunk_id']}")
        print(
            f"Source: {result['source_id']} - "
            f"{result['title']}"
        )
        print(f"Authority: {result['authority']}")
        print(f"Page: {result['page']}")
        print(f"Section: {result['section']}")
        print(f"Preview: {preview}")


def main():
    results = semantic_search(TEST_QUERY, top_k=5)
    print_results(TEST_QUERY, results)


if __name__ == "__main__":
    main()
