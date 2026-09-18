import json
import re
from difflib import get_close_matches


DOMAIN_TERMS = {
    "warmshell": "Warmshell",
    "stone": "stone",
    "brick": "brick",
    "solid": "solid",
    "damp": "damp",
    "wall": "wall",
    "install": "install",
    "insulation": "insulation",
}


EXACT_TERM_PATTERN = re.compile(
    r"\b(?:"
    r"IWI\s+\d{3}[a-z]?"
    r"|BS\s+EN\s+\d+(?:-\d+)*"
    r"|BS\s+\d+(?:-\d+)*"
    r"|B-s\d+,d\d"
    r"|WUFI"
    r"|U-value"
    r")\b",
    re.IGNORECASE
)


ENTITY_PATTERNS = {
    "Warmshell Internal": r"\bWarmshell\s+Internal\b",
    "IWI": r"\bIWI\b",
    "Solo": r"\bSolo\b",
    "Duro": r"\bDuro\b",
    "Board Adhesive": r"\bBoard\s+Adhesive\b",
    "Woodfibre": r"\bWood\s*fibre\b",
}


TOPIC_KEYWORDS = {
    "moisture": [
        r"\bdamp\b",
        r"\bmoisture\b",
        r"\bcondensation\b",
        r"\bmould\b",
        r"\bwet\b",
    ],
    "fire": [
        r"\bfire\b",
        r"\bB-s1,d0\b",
        r"\bcombustible\b",
        r"\bclassification\b",
    ],
    "thermal": [
        r"\bthermal\b",
        r"\bU-value\b",
        r"\bheat\s+loss\b",
    ],
    "warranty": [
        r"\bwarranty\b",
        r"\bguarantee\b",
    ],
    "services": [
        r"\belectrical\b",
        r"\bcables?\b",
        r"\bsockets?\b",
        r"\bpipes?\b",
        r"\bservices?\b",
    ],
    "openings": [
        r"\bwindows?\b",
        r"\breveals?\b",
        r"\bdoors?\b",
        r"\bopenings?\b",
    ],
    "installation": [
        r"\binstall(?:ed|ing|ation)?\b",
        r"\bfix(?:ed|ing|ings)?\b",
        r"\bappl(?:y|ied|ying|ication)\b",
    ],
    "assessment": [
        r"\bassess(?:ed|ing|ment)?\b",
        r"\bsurveys?\b",
        r"\bsuitability\b",
        r"\bsuitable\b",
    ],
}


TEST_QUERIES = [
    (
        "What should be considered if there is damp or moisture in the wall "
        "before installing Warmshell Internal?"
    ),
    "What does IWI 005e say about electrical services?",
    "What is the B-s1,d0 fire classification?",
    "How should an existing window reveal be detailed?",
    (
        "There is damp appearing after the insulation was installed. "
        "What should I check?"
    ),
]


def normalize_query(query):
    query = " ".join(query.strip().split())

    def correct_domain_term(match):
        original = match.group(0)
        word = original.lower()
        if word in DOMAIN_TERMS:
            return original

        candidates = get_close_matches(word, DOMAIN_TERMS, n=2, cutoff=0.88)
        if len(candidates) != 1:
            return original
        candidate = candidates[0]

        # Only repair one missing letter, not general spelling or valid inflections.
        # For short terms, require a missing final letter: avoid sold -> solid,
        # tone -> stone, or changing ordinary words and technical identifiers.
        if len(candidate) != len(word) + 1:
            return original
        if len(candidate) <= 5 and not candidate.startswith(word):
            return original
        if not any(
            candidate[:index] + candidate[index + 1:] == word
            for index in range(len(candidate))
        ):
            return original
        return DOMAIN_TERMS[candidate]

    return re.sub(
        r"(?<![\w-])[A-Za-z]{4,}(?![\w-])",
        correct_domain_term,
        query,
    )


def extract_exact_terms(query):
    terms = []

    for match in EXACT_TERM_PATTERN.finditer(query):
        term = match.group(0)

        if term not in terms:
            terms.append(term)

    return terms


def detect_entities(query):
    entities = []

    for entity, pattern in ENTITY_PATTERNS.items():
        if re.search(pattern, query, re.IGNORECASE):
            entities.append(entity)

    return entities


def detect_topics(query):
    topics = []

    for topic, patterns in TOPIC_KEYWORDS.items():
        if any(
            re.search(pattern, query, re.IGNORECASE)
            for pattern in patterns
        ):
            topics.append(topic)

    return topics


def detect_stage(query):
    query_lower = query.lower()

    warranty_patterns = [
        r"\bwarranty\b",
        r"\bguarantee\b",
    ]
    maintain_patterns = [
        r"\bafter\b.{0,50}\binstall(?:ed|ation)\b",
        r"\bpost[- ]installation\b",
        r"\bmaintain(?:ed|ing|ance)?\b",
    ]
    assess_patterns = [
        r"\bbefore\b.{0,50}\binstall(?:ing|ation)?\b",
        r"\bprior to\b.{0,50}\binstall(?:ing|ation)?\b",
        r"\bcan i use (?:this|it) on my wall\b",
        r"\bassess(?:ed|ing|ment)?\b",
        r"\bsurveys?\b",
        r"\bsuitability\b",
    ]
    design_patterns = [
        r"\bdesign(?:ed|ing)?\b",
        r"\bdetail(?:ed|ing)?\b",
        r"\bspecif(?:y|ied|ication)\b",
    ]
    install_patterns = [
        r"\bhow (?:do|should) i\b.{0,50}\b(?:apply|install|fix)\b",
        r"\binstall(?:ing|ation)\b",
        r"\bapply(?:ing|ication)?\b",
        r"\bfix(?:ing|ings)?\b",
    ]

    stage_patterns = [
        ("warranty", warranty_patterns),
        ("maintain", maintain_patterns),
        ("assess", assess_patterns),
        ("design", design_patterns),
        ("install", install_patterns),
    ]

    for stage, patterns in stage_patterns:
        if any(re.search(pattern, query_lower) for pattern in patterns):
            return stage

    return "unknown"


def process_query(query):
    normalized_query = normalize_query(query)

    return {
        "original_query": query,
        "normalized_query": normalized_query,
        "entities": detect_entities(normalized_query),
        "topics": detect_topics(normalized_query),
        "exact_terms": extract_exact_terms(normalized_query),
        "stage": detect_stage(normalized_query),
    }


def main():
    for number, query in enumerate(TEST_QUERIES, start=1):
        print(f"QUERY {number}")
        print(
            json.dumps(
                process_query(query),
                ensure_ascii=False,
                indent=2
            )
        )

        if number < len(TEST_QUERIES):
            print()


if __name__ == "__main__":
    main()
