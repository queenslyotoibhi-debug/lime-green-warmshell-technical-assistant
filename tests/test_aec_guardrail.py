"""Deterministic unit tests for the AEC sufficiency guardrail.

This is the safety-critical layer: it decides whether the model is allowed to
turn retrieved guidance into a project-specific recommendation. The tests lock
in three things that must not drift apart:

  1. vague decision questions are held back for missing context;
  2. short factual questions still answer normally;
  3. the three formal evaluation questions keep the status they rely on.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from aec_guardrail import (  # noqa: E402
    assess_sufficiency,
    extract_aec_context,
    find_missing_context,
    has_installation_decision,
    has_recommendation_intent,
    is_project_specific,
    is_suitability_or_design_question,
)
from query_processor import process_query  # noqa: E402


CONTEXT_FIELDS = {
    "wall_material",
    "wall_construction",
    "building_condition",
    "moisture_status",
    "existing_finish",
    "exposure_or_location",
    "assessment_status",
    "proposed_thickness",
}

FULLY_SPECIFIED = (
    "My wall is solid stone in good condition, appears dry, lime plastered, "
    "on a sheltered site, and the assessment is completed. "
    "Can I use Warmshell Internal?"
)


def status_for(query):
    return assess_sufficiency(query, process_query(query), extract_aec_context(query))


class ExtractContextTests(unittest.TestCase):

    def test_returns_every_field_even_when_unknown(self):
        self.assertEqual(set(extract_aec_context("hello")), CONTEXT_FIELDS)
        self.assertTrue(
            all(value is None for value in extract_aec_context("hello").values())
        )

    def test_extracts_stated_building_facts(self):
        context = extract_aec_context(
            "My wall is solid stone, internally lime plastered and appears dry."
        )
        self.assertEqual(context["wall_material"], "stone")
        self.assertEqual(context["wall_construction"], "solid wall")
        self.assertEqual(context["moisture_status"], "appears dry")
        self.assertEqual(context["existing_finish"], "lime plaster")

    def test_distinguishes_rising_damp_from_general_damp(self):
        self.assertEqual(
            extract_aec_context("rising damp in my wall")["moisture_status"],
            "rising damp",
        )
        self.assertEqual(
            extract_aec_context("the wall is damp")["moisture_status"],
            "damp",
        )

    def test_extracts_thickness_and_exposure(self):
        context = extract_aec_context("100 mm board on a coastal elevation")
        self.assertEqual(context["proposed_thickness"], "100 mm")
        self.assertEqual(context["exposure_or_location"], "coastal")

    def test_extracts_assessment_status(self):
        self.assertEqual(
            extract_aec_context("the survey is completed")["assessment_status"],
            "assessment completed",
        )


class FindMissingContextTests(unittest.TestCase):

    def test_combines_material_and_construction_when_both_unknown(self):
        missing = find_missing_context(extract_aec_context("hello"))
        self.assertIn("wall construction/material", missing)
        self.assertNotIn("wall material", missing)
        self.assertNotIn("wall construction", missing)

    def test_asks_only_for_the_half_that_is_missing(self):
        missing = find_missing_context(extract_aec_context("my stone wall"))
        self.assertIn("wall construction", missing)
        self.assertNotIn("wall construction/material", missing)

    def test_nothing_missing_when_all_fields_supplied(self):
        self.assertEqual(find_missing_context(extract_aec_context(FULLY_SPECIFIED)), [])

    def test_thickness_is_not_demanded_as_missing_context(self):
        # Thickness is captured when offered but is not a required field.
        missing = find_missing_context(extract_aec_context("hello"))
        self.assertFalse(any("thickness" in item for item in missing))


class RecommendationIntentTests(unittest.TestCase):
    """The narrow detector added for vague, underspecified decision requests."""

    def test_detects_requests_to_choose_or_apply_for_the_users_building(self):
        for query in (
            "house cold, need insulation",
            "the wall needs insulation",
            "how should I insulate my old house?",
            "should I insulate the walls?",
            "what do you recommend?",
            "best board for my wall",
        ):
            with self.subTest(query=query):
                self.assertTrue(has_recommendation_intent(query))

    def test_does_not_fire_on_factual_questions(self):
        for query in (
            "what is the fire classification?",
            "does Warmshell use a cavity?",
            "what is Warmshell Internal?",
            "what are the system layers?",
            "what thicknesses are covered by the fire classification?",
        ):
            with self.subTest(query=query):
                self.assertFalse(has_recommendation_intent(query))

    def test_does_not_fire_on_general_guidance_wording(self):
        # Formal evaluation test 2 must stay a general question, so "insulating
        # around ..." must not be read as insulating the user's own building.
        self.assertFalse(
            has_recommendation_intent(
                "What should be considered when insulating around an existing "
                "window opening with Warmshell Internal?"
            )
        )
        self.assertFalse(has_recommendation_intent("insulating around a reveal"))


class InstallationDecisionTests(unittest.TestCase):

    def test_requires_both_an_action_and_construction_context(self):
        self.assertTrue(has_installation_decision("can I put this on stone?"))
        # An action with no construction subject is not an installation decision.
        self.assertFalse(has_installation_decision("can I use it?"))

    def test_detects_preparation_questions(self):
        self.assertTrue(
            has_installation_decision("do I need to prepare the wall first?")
        )


class VagueDecisionQueryTests(unittest.TestCase):
    """Underspecified requests for a recommendation must be held back."""

    VAGUE_QUERIES = (
        "house cold, need insulation",
        "what insulation should I use?",
        "can I use Warmshell here?",
        "is this suitable for my wall?",
        "how should I insulate my old house?",
        "can I put this on stone?",
    )

    def test_all_are_treated_as_project_specific_decisions(self):
        for query in self.VAGUE_QUERIES:
            with self.subTest(query=query):
                self.assertTrue(is_project_specific(query))
                self.assertTrue(
                    is_suitability_or_design_question(query, process_query(query))
                )

    def test_all_are_insufficient(self):
        for query in self.VAGUE_QUERIES:
            with self.subTest(query=query):
                self.assertEqual(status_for(query)["status"], "insufficient")

    def test_missing_context_is_reported_for_the_escalation_path(self):
        # The UI turns these into questions, so the list must not be empty.
        for query in self.VAGUE_QUERIES:
            with self.subTest(query=query):
                self.assertTrue(status_for(query)["missing_context"])

    def test_stated_facts_are_not_asked_for_again(self):
        result = status_for("can I put this on stone?")
        self.assertEqual(result["known_context"]["wall_material"], "stone")
        self.assertNotIn("wall construction/material", result["missing_context"])


class FactualQueryTests(unittest.TestCase):
    """Short factual questions must not be blocked merely for being short."""

    FACTUAL_QUERIES = (
        "fire classification?",
        "what is Warmshell Internal?",
        "does Warmshell use a cavity?",
        "what are the system layers?",
        "what thicknesses are covered by the fire classification?",
    )

    def test_are_not_project_specific(self):
        for query in self.FACTUAL_QUERIES:
            with self.subTest(query=query):
                self.assertFalse(is_project_specific(query))

    def test_are_sufficient_with_nothing_outstanding(self):
        for query in self.FACTUAL_QUERIES:
            with self.subTest(query=query):
                result = status_for(query)
                self.assertEqual(result["status"], "sufficient")
                self.assertEqual(result["missing_context"], [])


class FormalEvaluationStatusTests(unittest.TestCase):
    """The three evaluated questions depend on these exact statuses."""

    def test_fire_classification_question_is_a_general_fact_request(self):
        result = status_for("What is the fire classification of Warmshell Internal?")
        self.assertFalse(result["project_specific"])
        self.assertEqual(result["status"], "sufficient")

    def test_window_opening_question_is_a_general_fact_request(self):
        result = status_for(
            "What should be considered when insulating around an existing "
            "window opening with Warmshell Internal?"
        )
        self.assertFalse(result["project_specific"])
        self.assertEqual(result["status"], "sufficient")

    def test_price_question_stays_sufficient(self):
        # This one is project-specific but is not a suitability decision. Its
        # insufficiency is commercial, handled in generation, not here; flipping
        # it would replace the pricing refusal with missing-context questions.
        result = status_for(
            "What is the current installed price per m2 for 100 mm "
            "Warmshell Internal for my house?"
        )
        self.assertTrue(result["project_specific"])
        self.assertEqual(result["status"], "sufficient")


class SufficiencyGradingTests(unittest.TestCase):

    def test_full_context_is_sufficient(self):
        result = status_for(FULLY_SPECIFIED)
        self.assertEqual(result["status"], "sufficient")
        self.assertEqual(result["missing_context"], [])

    def test_partial_context_is_graded_partial(self):
        result = status_for(
            "My wall is solid stone, internally lime plastered and appears dry. "
            "Can I use Warmshell Internal?"
        )
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["missing_context"])

    def test_active_moisture_without_assessment_is_insufficient(self):
        result = status_for(
            "I have rising damp in my solid brick wall. "
            "Can I install Warmshell Internal?"
        )
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["known_context"]["moisture_status"], "rising damp")

    def test_project_reference_without_a_decision_stays_sufficient(self):
        # Mentioning "my" is not by itself a suitability question.
        result = status_for("What does IWI 005e say about my electrical services?")
        self.assertTrue(result["project_specific"])
        self.assertEqual(result["status"], "sufficient")

    def test_result_contract_is_stable(self):
        self.assertEqual(
            set(status_for("house cold, need insulation")),
            {
                "project_specific",
                "status",
                "known_context",
                "missing_context",
                "reason",
            },
        )

    def test_known_context_excludes_unknown_fields(self):
        known = status_for("can I put this on stone?")["known_context"]
        self.assertNotIn(None, known.values())


if __name__ == "__main__":
    unittest.main()
