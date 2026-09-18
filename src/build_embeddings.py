from pathlib import Path
import hashlib
import json

import numpy as np
import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHUNKS_FILE = (
    PROJECT_ROOT
    / "data"
    / "structured"
    / "chunks.jsonl"
)

EMBEDDINGS_FOLDER = (
    PROJECT_ROOT
    / "data"
    / "embeddings"
)

EMBEDDINGS_FILE = (
    EMBEDDINGS_FOLDER
    / "embeddings.npy"
)

INDEX_FILE = (
    EMBEDDINGS_FOLDER
    / "embedding_index.jsonl"
)

MANIFEST_FILE = (
    EMBEDDINGS_FOLDER
    / "embedding_manifest.json"
)

OLLAMA_URL = "http://localhost:11434/api/embed"
MODEL = "qwen3-embedding:4b"

EXPECTED_CHUNK_COUNT = 219
EMBEDDING_DIMENSIONS = 2560
BATCH_SIZE = 16
REQUEST_TIMEOUT = 600


def load_retrieval_chunks():
    chunks = []

    with CHUNKS_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:

        for line_number, line in enumerate(
            file,
            start=1
        ):
            if not line.strip():
                continue

            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    "Invalid JSON in chunks.jsonl at "
                    f"line {line_number}."
                ) from error

            if chunk.get("retrieval_enabled") is True:
                chunks.append(chunk)

    return chunks


def build_embedding_text(chunk):
    parts = []

    title = chunk.get("title")
    section = chunk.get("section")
    detail_code = chunk.get("detail_code")
    question = chunk.get("question")
    text = chunk.get("text")

    if title:
        parts.append(f"Title: {title}")

    if detail_code:
        parts.append(f"Detail: {detail_code}")

    if section:
        section_text = section

        detail_prefix = f"{detail_code} - "

        if (
            detail_code
            and section_text.startswith(detail_prefix)
        ):
            section_text = section_text[
                len(detail_prefix):
            ]

        parts.append(f"Section: {section_text}")

    if (
        question
        and (
            not text
            or question not in text
        )
    ):
        parts.append(f"Question: {question}")

    if text:
        parts.append(f"Content: {text}")

    if not parts:
        raise ValueError(
            "Chunk has no usable embedding text: "
            f"{chunk.get('chunk_id')}"
        )

    return "\n".join(parts)


def embed_batch(texts):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "input": texts,
        },
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()
    embeddings = data.get("embeddings")

    if not isinstance(embeddings, list):
        raise ValueError(
            "Ollama response does not contain an "
            "embeddings list."
        )

    if len(embeddings) != len(texts):
        raise ValueError(
            "Ollama returned an unexpected number "
            f"of embeddings: expected {len(texts)}, "
            f"found {len(embeddings)}."
        )

    for embedding_number, embedding in enumerate(
        embeddings,
        start=1
    ):
        if len(embedding) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                "Unexpected embedding dimensions in "
                f"batch item {embedding_number}: "
                f"expected {EMBEDDING_DIMENSIONS}, "
                f"found {len(embedding)}."
            )

    return embeddings


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(block)

    return digest.hexdigest()


def validate_outputs(expected_chunks, expected_hash):
    saved_vectors = np.load(
        EMBEDDINGS_FILE,
        allow_pickle=False
    )

    with INDEX_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        saved_index = [
            json.loads(line)
            for line in file
            if line.strip()
        ]

    with MANIFEST_FILE.open(
        "r",
        encoding="utf-8"
    ) as file:
        saved_manifest = json.load(file)

    chunk_ids = [
        chunk["chunk_id"]
        for chunk in saved_index
    ]

    if saved_vectors.shape != (
        EXPECTED_CHUNK_COUNT,
        EMBEDDING_DIMENSIONS
    ):
        raise ValueError(
            "Unexpected saved NumPy shape: "
            f"{saved_vectors.shape}."
        )

    if saved_vectors.dtype != np.float32:
        raise ValueError(
            "Unexpected saved vector dtype: "
            f"{saved_vectors.dtype}."
        )

    if saved_index != expected_chunks:
        raise ValueError(
            "Saved index records do not match the "
            "retrieval chunks in their original order."
        )

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "Duplicate chunk IDs found in the "
            "embedding index."
        )

    if saved_manifest["embedding_model"] != MODEL:
        raise ValueError(
            "Unexpected model in embedding manifest."
        )

    if saved_manifest["chunks_jsonl_sha256"] != expected_hash:
        raise ValueError(
            "Stored chunks.jsonl SHA-256 does not "
            "match the source corpus."
        )

    print("\nEMBEDDING INDEX COMPLETE")
    print(
        f"Retrieval chunks loaded: "
        f"{len(expected_chunks)}"
    )
    print(
        f"Vectors generated: "
        f"{saved_vectors.shape[0]}"
    )
    print(
        f"Vector dimensions: "
        f"{saved_vectors.shape[1]}"
    )
    print(f"NumPy shape: {saved_vectors.shape}")
    print(
        f"Duplicate chunk IDs: "
        f"{len(chunk_ids) - len(set(chunk_ids))}"
    )
    print(f"Index records: {len(saved_index)}")
    print(
        f"Manifest model: "
        f"{saved_manifest['embedding_model']}"
    )
    print("chunks.jsonl SHA-256 stored: YES")
    print("Validation: PASSED")


def main():
    retrieval_chunks = load_retrieval_chunks()

    if len(retrieval_chunks) != EXPECTED_CHUNK_COUNT:
        raise ValueError(
            "Expected 219 retrieval-enabled chunks, "
            f"found {len(retrieval_chunks)}. "
            "Embedding build stopped."
        )

    chunk_ids = [
        chunk["chunk_id"]
        for chunk in retrieval_chunks
    ]

    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError(
            "Duplicate chunk IDs found before "
            "embedding."
        )

    embedding_texts = [
        build_embedding_text(chunk)
        for chunk in retrieval_chunks
    ]

    all_embeddings = []

    for start_index in range(
        0,
        len(embedding_texts),
        BATCH_SIZE
    ):
        end_index = min(
            start_index + BATCH_SIZE,
            len(embedding_texts)
        )

        print(
            f"Embedding {start_index + 1}-"
            f"{end_index} / {len(embedding_texts)}"
        )

        batch_embeddings = embed_batch(
            embedding_texts[start_index:end_index]
        )

        all_embeddings.extend(batch_embeddings)

    vectors = np.asarray(
        all_embeddings,
        dtype=np.float32
    )

    expected_shape = (
        EXPECTED_CHUNK_COUNT,
        EMBEDDING_DIMENSIONS
    )

    if vectors.shape != expected_shape:
        raise ValueError(
            "Unexpected final embedding shape: "
            f"expected {expected_shape}, "
            f"found {vectors.shape}."
        )

    chunks_hash = calculate_sha256(CHUNKS_FILE)

    EMBEDDINGS_FOLDER.mkdir(
        parents=True,
        exist_ok=True
    )

    np.save(
        EMBEDDINGS_FILE,
        vectors,
        allow_pickle=False
    )

    with INDEX_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        for chunk in retrieval_chunks:
            file.write(
                json.dumps(
                    chunk,
                    ensure_ascii=False
                )
                + "\n"
            )

    manifest = {
        "embedding_model": MODEL,
        "embedding_dimensions": (
            EMBEDDING_DIMENSIONS
        ),
        "chunk_count": len(retrieval_chunks),
        "source_chunks_file": (
            "data/structured/chunks.jsonl"
        ),
        "retrieval_enabled_only": True,
        "batch_size": BATCH_SIZE,
        "chunks_jsonl_sha256": chunks_hash,
    }

    with MANIFEST_FILE.open(
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            manifest,
            file,
            ensure_ascii=False,
            indent=2
        )
        file.write("\n")

    validate_outputs(
        retrieval_chunks,
        chunks_hash
    )


if __name__ == "__main__":
    main()
