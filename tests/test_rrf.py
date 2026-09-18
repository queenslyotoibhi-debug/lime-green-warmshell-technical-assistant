"""Deterministic unit tests for Reciprocal Rank Fusion.

Importing hybrid_search is safe offline: the module only reads the index when
hybrid_search() is called, and these tests exercise the pure fusion function
with synthetic candidate lists.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from hybrid_search import RRF_K, reciprocal_rank_fusion  # noqa: E402


def semantic(chunk_id, rank, score=0.5):
    return {"chunk_id": chunk_id, "rank": rank, "similarity_score": score}


def lexical(chunk_id, rank, score=1.0):
    return {"chunk_id": chunk_id, "rank": rank, "bm25_score": score}


class FusionScoreTests(unittest.TestCase):

    def test_single_list_score_is_one_over_k_plus_rank(self):
        [result] = reciprocal_rank_fusion([semantic("a", 1)], [])
        self.assertAlmostEqual(result["rrf_score"], 1 / (RRF_K + 1))

    def test_scores_from_both_retrievers_are_summed(self):
        [result] = reciprocal_rank_fusion([semantic("a", 3)], [lexical("a", 7)])
        self.assertAlmostEqual(
            result["rrf_score"],
            1 / (RRF_K + 3) + 1 / (RRF_K + 7),
        )

    def test_agreement_between_retrievers_beats_a_single_strong_hit(self):
        # "b" is second in both lists; "a" is first in one and absent from the
        # other. Agreement is what RRF is for, so "b" must win.
        results = reciprocal_rank_fusion(
            [semantic("a", 1), semantic("b", 2)],
            [lexical("b", 2), lexical("c", 3)],
        )
        self.assertEqual(results[0]["chunk_id"], "b")

    def test_k_dampens_the_advantage_of_rank_one(self):
        # With k=60 the gap between rank 1 and rank 2 is small by design.
        with_default = reciprocal_rank_fusion([semantic("a", 1)], [])[0]["rrf_score"]
        with_small_k = reciprocal_rank_fusion([semantic("a", 1)], [], k=0)[0]["rrf_score"]
        self.assertLess(with_default, with_small_k)


class FusionOrderingTests(unittest.TestCase):

    def test_results_are_sorted_by_descending_score(self):
        results = reciprocal_rank_fusion(
            [semantic("a", 5), semantic("b", 1)],
            [lexical("a", 6), lexical("b", 2)],
        )
        scores = [result["rrf_score"] for result in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_ranks_are_contiguous_from_one(self):
        results = reciprocal_rank_fusion(
            [semantic("a", 1), semantic("b", 2)],
            [lexical("c", 1)],
        )
        self.assertEqual([result["rank"] for result in results], [1, 2, 3])

    def test_a_chunk_in_both_lists_appears_once(self):
        results = reciprocal_rank_fusion(
            [semantic("a", 1), semantic("b", 2)],
            [lexical("a", 1), lexical("b", 2)],
        )
        chunk_ids = [result["chunk_id"] for result in results]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        self.assertEqual(sorted(chunk_ids), ["a", "b"])

    def test_both_retriever_ranks_are_recorded(self):
        [result] = reciprocal_rank_fusion([semantic("a", 4)], [lexical("a", 9)])
        self.assertEqual(result["semantic_rank"], 4)
        self.assertEqual(result["bm25_rank"], 9)

    def test_absent_retriever_rank_is_none(self):
        [result] = reciprocal_rank_fusion([semantic("a", 1)], [])
        self.assertEqual(result["semantic_rank"], 1)
        self.assertIsNone(result["bm25_rank"])
        self.assertIsNone(result["bm25_score"])


class FusionMetadataTests(unittest.TestCase):

    def test_chunk_lookup_supplies_full_metadata(self):
        lookup = {
            "a": {
                "chunk_id": "a",
                "source_id": "WSI-FIRE-001",
                "title": "Fire report",
                "text": "classified B-s1,d0",
            }
        }
        [result] = reciprocal_rank_fusion(
            [semantic("a", 1)], [], chunk_lookup=lookup
        )
        self.assertEqual(result["source_id"], "WSI-FIRE-001")
        self.assertEqual(result["title"], "Fire report")
        self.assertEqual(result["text"], "classified B-s1,d0")

    def test_missing_metadata_fields_are_present_as_none(self):
        [result] = reciprocal_rank_fusion([semantic("a", 1)], [])
        for field in ("source_id", "title", "page", "section", "url", "text"):
            self.assertIn(field, result)
            self.assertIsNone(result[field])


class FusionValidationTests(unittest.TestCase):
    """Bad candidate lists must fail loudly rather than silently mis-rank."""

    def test_rejects_a_result_without_a_chunk_id(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([{"rank": 1}], [])

    def test_rejects_a_non_positive_rank(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([semantic("a", 0)], [])

    def test_rejects_a_non_integer_rank(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([semantic("a", 1.5)], [])

    def test_rejects_a_bad_bm25_rank_too(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], [lexical("a", -1)])

    def test_rejects_negative_k(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([semantic("a", 1)], [], k=-1)

    def test_empty_inputs_produce_no_results(self):
        self.assertEqual(reciprocal_rank_fusion([], []), [])


if __name__ == "__main__":
    unittest.main()
