"""Deterministic unit tests for lifecycle stage governance and re-ranking.

The governance layer must stay a gentle re-ordering: it may promote evidence
that matches the question's lifecycle stage, but it must never make a
mismatched chunk ineligible.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from governed_search import (  # noqa: E402
    MATCH_FACTOR,
    MISMATCH_FACTOR,
    NEUTRAL_FACTOR,
    apply_lifecycle_reranking,
    detect_document_stage,
)


def candidate(chunk_id, rank, rrf_score, source_id="WSI-WEB-001", **extra):
    result = {
        "chunk_id": chunk_id,
        "rank": rank,
        "rrf_score": rrf_score,
        "source_id": source_id,
    }
    result.update(extra)
    return result


class DetectDocumentStageTests(unittest.TestCase):

    def test_maps_source_id_prefix_to_a_stage(self):
        expected = {
            "WSI-ASSESS-001": "assess",
            "WSI-DESIGN-001": "design",
            "WSI-SPEC-001": "design",
            "WSI-DETAILS-001": "design",
            "WSI-INSTALL-001": "install",
            "WSI-MAINT-001": "maintain",
            "WSI-WARRANTY-001": "warranty",
        }
        for source_id, stage in expected.items():
            with self.subTest(source_id=source_id):
                self.assertEqual(
                    detect_document_stage({"source_id": source_id}), stage
                )

    def test_supporting_documents_are_neutral_without_a_cue(self):
        self.assertEqual(
            detect_document_stage({"source_id": "WSI-WEB-001"}), "neutral"
        )
        self.assertEqual(detect_document_stage({}), "neutral")

    def test_falls_back_to_section_metadata(self):
        self.assertEqual(
            detect_document_stage(
                {"source_id": "WSI-WEB-001", "section": "Warranty conditions"}
            ),
            "warranty",
        )
        self.assertEqual(
            detect_document_stage(
                {"source_id": "WSI-FAQ-001", "section": "Installation sequence"}
            ),
            "install",
        )

    def test_body_text_is_not_used_to_guess_a_stage(self):
        # Only section/detail metadata may supply a cue; guessing from body
        # text would let an incidental mention re-rank the whole result set.
        self.assertEqual(
            detect_document_stage(
                {"source_id": "WSI-WEB-001", "text": "installation and warranty"}
            ),
            "neutral",
        )

    def test_source_prefix_wins_over_section_metadata(self):
        self.assertEqual(
            detect_document_stage(
                {"source_id": "WSI-INSTALL-001", "section": "Warranty"}
            ),
            "install",
        )


class LifecycleRerankingTests(unittest.TestCase):

    def test_matching_stage_is_promoted(self):
        [result] = apply_lifecycle_reranking(
            [candidate("a", 1, 0.01, source_id="WSI-INSTALL-001")], "install"
        )
        self.assertTrue(result["stage_match"])
        self.assertEqual(result["stage_factor"], MATCH_FACTOR)
        self.assertAlmostEqual(result["governed_score"], 0.01 * MATCH_FACTOR)

    def test_mismatched_stage_is_demoted_but_kept(self):
        [result] = apply_lifecycle_reranking(
            [candidate("a", 1, 0.01, source_id="WSI-INSTALL-001")], "warranty"
        )
        self.assertFalse(result["stage_match"])
        self.assertEqual(result["stage_factor"], MISMATCH_FACTOR)
        self.assertGreater(result["governed_score"], 0)

    def test_neutral_document_is_unchanged(self):
        [result] = apply_lifecycle_reranking(
            [candidate("a", 1, 0.01, source_id="WSI-WEB-001")], "install"
        )
        self.assertIsNone(result["stage_match"])
        self.assertEqual(result["stage_factor"], NEUTRAL_FACTOR)
        self.assertAlmostEqual(result["governed_score"], 0.01)

    def test_unknown_query_stage_leaves_every_result_neutral(self):
        results = apply_lifecycle_reranking(
            [
                candidate("a", 1, 0.02, source_id="WSI-INSTALL-001"),
                candidate("b", 2, 0.01, source_id="WSI-WARRANTY-001"),
            ],
            "unknown",
        )
        for result in results:
            self.assertIsNone(result["stage_match"])
            self.assertEqual(result["stage_factor"], NEUTRAL_FACTOR)
        self.assertEqual([result["chunk_id"] for result in results], ["a", "b"])

    def test_stage_evidence_can_reorder_close_results(self):
        results = apply_lifecycle_reranking(
            [
                candidate("mismatch", 1, 0.0160, source_id="WSI-WARRANTY-001"),
                candidate("match", 2, 0.0155, source_id="WSI-INSTALL-001"),
            ],
            "install",
        )
        self.assertEqual(results[0]["chunk_id"], "match")
        self.assertEqual(results[0]["original_rrf_rank"], 2)

    def test_a_large_gap_is_not_overturned(self):
        # The factors are deliberately small, so governance must not rescue a
        # clearly weaker chunk.
        results = apply_lifecycle_reranking(
            [
                candidate("strong", 1, 0.0300, source_id="WSI-WARRANTY-001"),
                candidate("weak", 2, 0.0100, source_id="WSI-INSTALL-001"),
            ],
            "install",
        )
        self.assertEqual(results[0]["chunk_id"], "strong")

    def test_original_rank_and_final_rank_are_both_recorded(self):
        results = apply_lifecycle_reranking(
            [
                candidate("a", 1, 0.02, source_id="WSI-WEB-001"),
                candidate("b", 2, 0.01, source_id="WSI-WEB-001"),
            ],
            "install",
        )
        self.assertEqual([result["final_rank"] for result in results], [1, 2])
        self.assertEqual([result["original_rrf_rank"] for result in results], [1, 2])

    def test_no_candidate_is_dropped(self):
        candidates = [
            candidate("a", 1, 0.03, source_id="WSI-WARRANTY-001"),
            candidate("b", 2, 0.02, source_id="WSI-INSTALL-001"),
            candidate("c", 3, 0.01, source_id="WSI-WEB-001"),
        ]
        results = apply_lifecycle_reranking(candidates, "install")
        self.assertEqual(
            sorted(result["chunk_id"] for result in results), ["a", "b", "c"]
        )

    def test_input_candidates_are_not_mutated(self):
        original = candidate("a", 1, 0.01, source_id="WSI-INSTALL-001")
        apply_lifecycle_reranking([original], "install")
        self.assertNotIn("governed_score", original)


if __name__ == "__main__":
    unittest.main()
