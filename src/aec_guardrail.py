import json
import re

from query_processor import normalize_query, process_query


PROJECT_SPECIFIC_PATTERNS = [
    r"\bmy\b",
    r"\bour\b",
    r"\bcan\s+i\b",
    r"\bcan\s+we\b",
    r"\bi\s+have\b",
    r"\bwe\s+have\b",
    r"\bsuitable\s+for\b",
    r"\bshould\s+i\s+use\b",
    r"\bwhat\s+should\s+i\s+use\b",
    r"\bon\s+(?:this|my|our)\s+(?:wall|property|building)\b",
]


SUITABILITY_PATTERNS = [
    r"\bcan\s+(?:i|we)\s+(?:use|install|apply|fit)\b",
    r"\bis\b.{0,40}\bsuitable\s+for\b",
    r"\bshould\s+(?:i|we)\s+use\b",
    r"\bwhat\s+should\s+(?:i|we)\s+use\b",
]


CONSTRUCTION_CONTEXT = (
    r"\b(?:Warmshell|IWI|EWI|walls?|insulation|masonry|brick|stone|"
    r"substrates?|plaster|render|roofs?|ceilings?|floors?|buildings?)\b"
)
INSTALLATION_ACTION = r"(?:install|fit|apply|attach|stick|put|use)"
INSTALLATION_DECISION_PATTERNS = [
    rf"\b(?:can|should)\s+(?:i|we)\s+(?:(?:just|simply)\s+)?{INSTALLATION_ACTION}\b",
    rf"\bdo\s+(?:i|we)\s+need\s+to\s+(?:{INSTALLATION_ACTION}|"
    r"prepare|dry|clean|level|treat|do\s+anything)\b",
    r"\b(?:can|should)\s+(?:i|we)\b[^.!?]{0,80}\bstraight\s+on\b",
]


# Asking the assistant to choose, recommend, or apply insulation to the user's own
# building. Deliberately narrow: reporting documented guidance is a fact request,
# not a project decision, so the wording must be first-person or refer to the user's
# own building before it counts as a recommendation request.
RECOMMENDATION_INTENT_PATTERNS = [
    r"\bneeds?\s+(?:\w+\s+){0,2}insulation\b",
    r"\binsulat(?:e|ing)\s+(?:my|our)\b",
    r"\b(?:how\s+(?:should|do|can)\s+(?:i|we)|should\s+(?:i|we))\s+insulate\b",
    r"\bwhat\s+(?:do|would|should)\s+(?:you|i|we)\s+recommend\b",
    r"\b(?:recommend|best|right)\s+(?:\w+\s+){0,3}for\s+(?:my|our|this)\b",
]


def has_recommendation_intent(query):
    return any(
        re.search(pattern, query, re.IGNORECASE)
        for pattern in RECOMMENDATION_INTENT_PATTERNS
    )


def has_installation_decision(query):
    if not re.search(CONSTRUCTION_CONTEXT, query, re.IGNORECASE):
        return False
    return any(
        re.search(pattern, query, re.IGNORECASE)
        for pattern in INSTALLATION_DECISION_PATTERNS
    )


TEST_QUERIES = [
    "What is the fire classification of Warmshell Internal?",
    "Can I install 100 mm Warmshell on my stone cottage?",
    (
        "I have rising damp in my solid brick wall. "
        "Can I install Warmshell Internal?"
    ),
    "What does IWI 005e say about electrical services?",
    (
        "My wall is solid stone, internally lime plastered and appears dry. "
        "Can I use Warmshell Internal?"
    ),
]


def is_project_specific(query):
    query = normalize_query(query)
    return (
        has_installation_decision(query)
        or has_recommendation_intent(query)
        or any(
            re.search(pattern, query, re.IGNORECASE)
            for pattern in PROJECT_SPECIFIC_PATTERNS
        )
    )


def first_matching_value(query, options):
    for value, pattern in options:
        if re.search(pattern, query, re.IGNORECASE):
            return value

    return None


def extract_aec_context(query):
    query = normalize_query(query)
    wall_material = first_matching_value(query, [
        ("stone", r"\bstone\b"),
        ("brick", r"\bbrick\b"),
    ])
    wall_construction = first_matching_value(query, [
        ("solid wall", r"\bsolid\s+(?:stone|brick\s+)?wall\b"),
        ("solid wall", r"\bsolid\s+(?:stone|brick)\b"),
        ("cavity wall", r"\bcavity\s+wall\b"),
    ])
    building_condition = first_matching_value(query, [
        ("good condition", r"\bgood\s+condition\b"),
        ("poor condition", r"\bpoor\s+condition\b"),
        ("sound", r"\bsound\s+(?:wall|condition|substrate)\b"),
        ("damaged", r"\bdamaged\b"),
        ("cracked", r"\bcrack(?:ed|ing|s)?\b"),
        ("unstable", r"\bunstable\b"),
    ])
    moisture_status = first_matching_value(query, [
        ("rising damp", r"\brising\s+damp\b"),
        ("damp", r"\bdamp\b"),
        ("wet", r"\bwet\b"),
        ("appears dry", r"\bappears?\s+dry\b"),
        ("dry", r"\bdry\b"),
    ])
    existing_finish = first_matching_value(query, [
        ("gypsum plaster", r"\bgypsum\s+plaster(?:ed)?\b"),
        ("lime plaster", r"\blime\s+plaster(?:ed)?\b"),
        ("painted", r"\bpainted\b"),
    ])
    exposure_or_location = first_matching_value(query, [
        ("coastal", r"\bcoastal\b"),
        ("exposed", r"\bexposed\s+(?:site|location|wall|elevation)\b"),
        ("sheltered", r"\bsheltered\b"),
        ("driving rain", r"\bdriving\s+rain\b"),
        ("rural", r"\brural\b"),
        ("urban", r"\burban\b"),
    ])
    assessment_status = first_matching_value(query, [
        (
            "assessment completed",
            r"\b(?:assessment|survey)\s+(?:is\s+)?completed\b"
        ),
        (
            "not assessed",
            r"\b(?:not\s+assessed|assessment\s+not\s+completed|"
            r"survey\s+not\s+completed)\b"
        ),
        (
            "remedial work completed",
            r"\bremedial\s+work\s+(?:is\s+)?completed\b"
        ),
    ])
    thickness_match = re.search(
        r"\b(\d+(?:\.\d+)?)\s*mm\b",
        query,
        re.IGNORECASE
    )
    proposed_thickness = (
        f"{thickness_match.group(1)} mm"
        if thickness_match
        else None
    )

    return {
        "wall_material": wall_material,
        "wall_construction": wall_construction,
        "building_condition": building_condition,
        "moisture_status": moisture_status,
        "existing_finish": existing_finish,
        "exposure_or_location": exposure_or_location,
        "assessment_status": assessment_status,
        "proposed_thickness": proposed_thickness,
    }


def is_suitability_or_design_question(query, processed_query):
    query = processed_query.get("normalized_query") or normalize_query(query)
    explicit_suitability = any(
        re.search(pattern, query, re.IGNORECASE)
        for pattern in SUITABILITY_PATTERNS
    )
    lifecycle_question = processed_query.get("stage") in {
        "assess",
        "design",
        "install",
    }

    return (
        explicit_suitability
        or has_installation_decision(query)
        or has_recommendation_intent(query)
        or lifecycle_question
    )


def find_missing_context(aec_context):
    missing_context = []
    wall_material = aec_context["wall_material"]
    wall_construction = aec_context["wall_construction"]

    if wall_material is None and wall_construction is None:
        missing_context.append("wall construction/material")
    elif wall_material is None:
        missing_context.append("wall material")
    elif wall_construction is None:
        missing_context.append("wall construction")

    field_labels = [
        ("building_condition", "wall/building condition"),
        ("moisture_status", "moisture/damp condition"),
        ("exposure_or_location", "external exposure/location"),
        (
            "existing_finish",
            "existing finish/substrate condition"
        ),
        (
            "assessment_status",
            "assessment/remedial status"
        ),
    ]

    for field, label in field_labels:
        if aec_context[field] is None:
            missing_context.append(label)

    return missing_context


def assess_sufficiency(query, processed_query, aec_context):
    query = processed_query.get("normalized_query") or normalize_query(query)
    project_specific = is_project_specific(query)
    known_context = {
        field: value
        for field, value in aec_context.items()
        if value is not None
    }

    if not project_specific:
        return {
            "project_specific": False,
            "status": "sufficient",
            "known_context": known_context,
            "missing_context": [],
            "reason": (
                "This is a general factual question. Project-specific building "
                "context is not required to report the documented fact."
            ),
        }

    if not is_suitability_or_design_question(query, processed_query):
        return {
            "project_specific": True,
            "status": "sufficient",
            "known_context": known_context,
            "missing_context": [],
            "reason": (
                "The question refers to the user's project but does not ask for "
                "a suitability, design, or installation decision."
            ),
        }

    missing_context = find_missing_context(aec_context)
    active_moisture = aec_context["moisture_status"] in {
        "rising damp",
        "damp",
        "wet",
    }

    if not missing_context:
        status = "sufficient"
        reason = (
            "The stated context covers this prototype's basic checks. This does "
            "not establish suitability or replace a professional assessment."
        )
    elif active_moisture and aec_context["assessment_status"] is None:
        status = "insufficient"
        reason = (
            "The question states an active moisture condition, but its assessment "
            "or remedial status and other building context are missing. Suitability "
            "cannot be assessed from the supplied facts."
        )
    elif len(missing_context) >= 4:
        status = "insufficient"
        reason = (
            "The question is project-specific, but too little of the relevant "
            "building-assessment context has been supplied to assess suitability."
        )
    else:
        status = "partial"
        reason = (
            "Some relevant project facts are stated, but important assessment "
            "context remains missing. This is not a professional survey."
        )

    return {
        "project_specific": True,
        "status": status,
        "known_context": known_context,
        "missing_context": missing_context,
        "reason": reason,
    }


def main():
    for query_number, query in enumerate(TEST_QUERIES, start=1):
        processed_query = process_query(query)
        aec_context = extract_aec_context(query)
        sufficiency = assess_sufficiency(
            query,
            processed_query,
            aec_context
        )

        if query_number > 1:
            print()

        print(f"QUERY {query_number}")
        print(query)
        print(
            "Project specific? "
            f"{sufficiency['project_specific']}"
        )
        print("Extracted context:")
        print(json.dumps(aec_context, indent=2))
        print(
            "Sufficiency status: "
            f"{sufficiency['status']}"
        )
        print("Missing context:")
        print(json.dumps(sufficiency["missing_context"], indent=2))
        print(f"Reason: {sufficiency['reason']}")


if __name__ == "__main__":
    main()
