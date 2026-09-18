"""Deterministic unit tests for query understanding.

No Ollama, no index, no network: these cover the pure logic that runs before
retrieval, so a regression is caught in under a second rather than by the full
evaluation run.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from query_processor import (  # noqa: E402
    detect_entities,
    detect_stage,
    detect_topics,
    extract_exact_terms,
    normalize_query,
    process_query,
)


class NormalizeQueryTests(unittest.TestCase):
    """Typo repair is deliberately limited to one missing letter."""

    def test_repairs_single_missing_letter_in_domain_terms(self):
        self.assertEqual(normalize_query("warmshel"), "Warmshell")
        self.assertEqual(normalize_query("ston wall"), "stone wall")
        self.assertEqual(normalize_query("instal"), "install")
        self.assertEqual(normalize_query("insulaton"), "insulation")

    def test_leaves_ordinary_words_alone(self):
        # "sold" and "tone" are real words; correcting them to solid/stone
        # would rewrite the user's meaning, so short terms must share a prefix.
        self.assertEqual(normalize_query("sold wall"), "sold wall")
        self.assertEqual(normalize_query("tone"), "tone")

    def test_preserves_correct_terms_and_technical_identifiers(self):
        for query in ("Warmshell", "stone", "walls", "damp"):
            self.assertEqual(normalize_query(query), query)

    def test_preserves_exact_identifiers(self):
        self.assertEqual(normalize_query("IWI 005e"), "IWI 005e")
        self.assertEqual(normalize_query("B-s1,d0"), "B-s1,d0")

    def test_collapses_whitespace(self):
        self.assertEqual(
            normalize_query("  what   is   the\nfire  classification? "),
            "what is the fire classification?",
        )


class ExactTermTests(unittest.TestCase):
    """Exact identifiers must survive into BM25 as literal tokens."""

    def test_extracts_detail_and_standard_identifiers(self):
        self.assertEqual(
            extract_exact_terms("What does IWI 005e say about services?"),
            ["IWI 005e"],
        )
        self.assertIn(
            "BS EN 13501-1",
            extract_exact_terms("classified to BS EN 13501-1:2018"),
        )
        self.assertEqual(extract_exact_terms("B-s1,d0 rating"), ["B-s1,d0"])
        self.assertEqual(extract_exact_terms("the U-value"), ["U-value"])

    def test_deduplicates_repeated_terms(self):
        self.assertEqual(
            extract_exact_terms("IWI 005e and again IWI 005e"),
            ["IWI 005e"],
        )

    def test_returns_empty_list_when_no_identifiers(self):
        self.assertEqual(extract_exact_terms("is the wall damp?"), [])


class EntityAndTopicTests(unittest.TestCase):

    def test_detects_named_entities(self):
        self.assertIn(
            "Warmshell Internal",
            detect_entities("What is Warmshell Internal?"),
        )
        self.assertIn("IWI", detect_entities("IWI guidance"))

    def test_detects_topics(self):
        self.assertIn("fire", detect_topics("what is the fire classification?"))
        self.assertIn("moisture", detect_topics("there is damp in the wall"))
        self.assertIn("services", detect_topics("electrical cables and sockets"))
        self.assertIn("openings", detect_topics("the window reveal detail"))

    def test_unrelated_query_has_no_topics(self):
        self.assertEqual(detect_topics("what colour is it?"), [])


class DetectStageTests(unittest.TestCase):
    """Stage drives lifecycle re-ranking, so precedence order matters."""

    def test_recognises_each_stage(self):
        self.assertEqual(detect_stage("what are the warranty conditions?"), "warranty")
        self.assertEqual(detect_stage("how should the reveal be detailed?"), "design")
        self.assertEqual(detect_stage("how do I install the boards?"), "install")
        self.assertEqual(detect_stage("has the survey been done?"), "assess")

    def test_warranty_outranks_later_stages(self):
        # Warranty is checked first, so it wins even alongside install wording.
        self.assertEqual(
            detect_stage("what is the warranty after installation?"),
            "warranty",
        )

    def test_maintain_outranks_install_for_post_installation_wording(self):
        self.assertEqual(
            detect_stage("damp appearing after the insulation was installed"),
            "maintain",
        )

    def test_plain_factual_question_has_no_stage(self):
        self.assertEqual(detect_stage("what is the fire classification?"), "unknown")


class ProcessQueryTests(unittest.TestCase):

    def test_returns_the_full_contract(self):
        processed = process_query("What does IWI 005e say about electrical services?")
        self.assertEqual(
            set(processed),
            {
                "original_query",
                "normalized_query",
                "entities",
                "topics",
                "exact_terms",
                "stage",
            },
        )

    def test_preserves_original_and_normalises_separately(self):
        processed = process_query("can I use warmshel here?")
        self.assertEqual(processed["original_query"], "can I use warmshel here?")
        self.assertEqual(processed["normalized_query"], "can I use Warmshell here?")

    def test_downstream_fields_are_built_from_the_normalised_query(self):
        # The typo is repaired first, so the entity is still detected.
        self.assertIn("IWI", process_query("iwi guidance")["entities"])


if __name__ == "__main__":
    unittest.main()
