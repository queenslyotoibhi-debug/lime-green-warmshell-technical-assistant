"""Explicit regression checks; qualitative technical claims still need human review."""

from collections import Counter
import re
import unicodedata

from rag_answer import answer_question


TESTS = [
    {
        "number": 1, "name": "STRAIGHTFORWARD",
        "question": "What is the fire classification of Warmshell Internal?",
        "sources": {"WSI-FIRE-001"},
    },
    {
        "number": 2, "name": "MULTI-SOURCE",
        "question": (
            "What should be considered when insulating around an existing "
            "window opening with Warmshell Internal?"
        ),
        "sources": {"WSI-DESIGN-001", "WSI-SPEC-001", "WSI-DETAILS-001"},
    },
    {
        "number": 3, "name": "DELIBERATELY INSUFFICIENT",
        "question": (
            "What is the current installed price per m² for 100 mm "
            "Warmshell Internal for my house?"
        ),
        "sources": set(),
    },
]


def normalise(text):
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-"))


def source_numbers(text):
    return [int(number) for number in re.findall(r"\[S(\d+)\]", text, re.I)]


def source_ids(chunks):
    return list(dict.fromkeys(chunk["source_id"] for chunk in chunks))


def validate_citations(result):
    body, separator, sources = result["answer"].partition("\n\nSOURCES\n")
    cited = set(source_numbers(body))
    listed = Counter(source_numbers(sources))
    passed = (
        bool(separator)
        and not result["unavailable_source_numbers"]
        and cited == set(result["cited_source_numbers"])
        and all(1 <= number <= len(result["retrieved_results"]) for number in cited)
        and set(listed) == cited
        and all(count == 1 for count in listed.values())
    )
    # Empty citations are valid, particularly for an unsupported price question.
    return body, cited, passed


def measurements(text):
    # Canonicalise metre spellings and an optional number-unit hyphen only.
    # Keep the numeric value unchanged, so different distances still fail.
    text = re.sub(
        r"(?<=\d)\s*-?\s*(?:meters?|metres?|m)(?!\w)",
        " m",
        normalise(text),
    )
    pattern = (
        r"\b(\d+(?:\.\d+)?)\s*(?:[-x/]\s*(\d+(?:\.\d+)?))?\s*"
        r"(mm|cm|meters?|metres?|m|kpa|pa|w/m2k|w/mk|kg/m3|%)(?!\w)"
    )
    return {
        (float(value), unit)
        for first, second, unit in re.findall(pattern, text)
        for value in (first, second) if value
    }


def technical_checks(answer, evidence):
    """Value/identifier presence is a useful check, not proof of claim meaning."""
    unsupported = measurements(answer) - measurements(evidence)

    def details(text):
        return {
            re.sub(r"\s", "", term)
            for term in re.findall(r"\biwi\s*\d{3}[a-z]\b", normalise(text))
        }

    unmatched = details(answer) - details(evidence)
    failures = []
    if unsupported:
        failures.append(f"Measurements absent from cited evidence: {sorted(unsupported)}")
    if unmatched:
        failures.append(f"Detail IDs absent from cited evidence: {sorted(unmatched)}")
    return failures


def fire_checks(answer, cited_evidence, fire_evidence):
    text = normalise(answer)

    def classifications(value):
        return {
            re.sub(r"\s", "", match)
            for match in re.findall(r"\b[a-f][12]?\s*-\s*s\d\s*,\s*d\d\b", normalise(value))
        }

    failures = []
    claimed = classifications(text)
    if "b-s1,d0" not in claimed:
        failures.append("Expected classification B-s1,d0 is missing.")
    if claimed - classifications(cited_evidence):
        failures.append("A fire classification is absent from cited evidence.")

    # Check only conditions actually present in the retrieved fire report.
    # These patterns check coverage, not the full meaning of every paraphrase.
    conditions = {
        "thickness range": (r"thickness", r"thickness"),
        "density requirement": (r"density", r"density"),
        "tested product/formulation restriction": (
            r"same formulation|tested type of product",
            r"same formulation|tested (?:type of )?product|tested formulation",
        ),
        "Solo fire-exposed face/asymmetry": (
            r"asymmetry",
            r"(?:fire|expos\w*).{0,100}solo.{0,60}(?:face|plaster)",
        ),
        "substrate restriction": (r"substrate", r"substrate"),
        "no air gap/cavity": (
            r"without any air gap", r"(?:no|without)(?: any)? air gap.{0,30}cavit",
        ),
        "fixing condition": (r"fixing of", r"fixing|board adhesive"),
        "not type approval/certification": (
            r"does not represent type approval",
            r"(?:not|no).{0,45}type approval.{0,30}certification",
        ),
    }
    missing = [
        label for label, (evidence_pattern, answer_pattern) in conditions.items()
        if re.search(evidence_pattern, normalise(fire_evidence))
        and not re.search(answer_pattern, text)
    ]
    return failures, missing


def contains_numeric_price(answer):
    patterns = [
        r"[£$€]\s*\d",
        r"\b(?:gbp|usd|eur)\s*\d",
        r"\b\d+(?:\.\d+)?\s*(?:gbp|pounds?|euros?|dollars?)\b",
        r"\b\d+(?:\.\d+)?\s*(?:per|/)\s*m2\b",
    ]
    return any(re.search(pattern, normalise(answer)) for pattern in patterns)


def insufficiency_checks(answer):
    sentences = [
        normalise(sentence).replace("’", "'")
        for sentence in re.split(r"[.!?\n]", answer)
        if sentence.strip()
    ]
    commercial = r"\b(?:price|prices|pricing|costs?|quotations?|quotes?)\b"
    evidence = r"evidence|knowledge base|corpus|documentation|documents?|guidance|sources?"
    uncertainty = (
        r"not (?:provide|contain|have) enough information|insufficient|"
        r"(?:cannot|can't|can not|unable to).{0,60}"
        r"(?:verify|establish|determine|confirm|provide|quote|give)|"
        r"(?:does|do) not (?:contain|include|provide|cover|give)|"
        r"\bno (?:current |live |up-to-date )?(?:pricing|price|cost|quotation|quote)"
        r"(?: data| information| details)?|"
        r"(?:unavailable|not available|not verified|not established|not supplied)"
    )
    # Accept both explicit inability to verify and explicit absence of pricing data.
    # Tie that acknowledgement to commercial information and the evidence, rather
    # than accepting an unrelated statement about insufficient building context.
    insufficient = any(
        re.search(commercial, sentence)
        and re.search(evidence, sentence)
        and re.search(uncertainty, sentence)
        for sentence in sentences
    )
    distinction = any(
        re.search(r"technical|materials?|product specifications?|installation guidance|static", sentence)
        and re.search(commercial, sentence)
        and re.search(r"\b(?:but|not|no|only|rather than|instead of)\b|doesn't|cannot", sentence)
        for sentence in sentences
    )
    confirmation = any(
        re.search(r"lime green|suppliers?|technical team", sentence)
        and re.search(r"contact|confirm|check|obtain|request|seek|ask|get|consult", sentence)
        and re.search(commercial, sentence)
        and not re.search(
            r"\b(?:do not|don't|no need to|not necessary to|need not)\b", sentence
        )
        for sentence in sentences
    )
    checks = {
        "Explicit evidence insufficiency": insufficient,
        "Technical evidence distinguished from pricing": bool(distinction),
        "Confirm pricing with Lime Green/supplier": confirmation,
    }
    return [label for label, passed in checks.items() if not passed]


def evaluate_test(test):
    result = answer_question(test["question"])
    answer, numbers, citations_passed = validate_citations(result)
    chunks = result["retrieved_results"]
    cited_chunks = [chunk for number, chunk in enumerate(chunks, 1) if number in numbers]
    retrieved_ids, cited_ids = source_ids(chunks), source_ids(cited_chunks)
    evidence = "\n".join(chunk.get("text") or "" for chunk in cited_chunks)
    relevant_retrieved = test["sources"].intersection(retrieved_ids)
    relevant_cited = test["sources"].intersection(cited_ids)
    source_passed = bool(relevant_retrieved and relevant_cited)
    reasons, unsupported = [], []
    insufficiency = "N/A"

    if test["number"] == 1:
        fire_evidence = "\n".join(
            chunk.get("text") or "" for chunk in chunks
            if chunk.get("source_id") == "WSI-FIRE-001"
        )
        unsupported, missing = fire_checks(answer, evidence, fire_evidence)
        if missing:
            reasons.append("Missing applicable fire conditions: " + "; ".join(missing))
    elif test["number"] == 2:
        source_passed = len(relevant_retrieved) >= 2 and len(relevant_cited) >= 2
        unsupported = technical_checks(answer, evidence)
        if not source_passed:
            reasons.append("Fewer than two distinct relevant documents retrieved and cited.")
    else:
        if contains_numeric_price(answer):
            unsupported.append("Answer supplies a numeric price unsupported by this corpus.")
        source_passed = not unsupported  # No source is required for an uncited refusal.
        missing = insufficiency_checks(answer)
        insufficiency = "FAIL" if missing else "PASS"
        reasons.extend(missing)

    if not citations_passed:
        reasons.append("Citations do not map correctly to retrieved evidence/SOURCES.")
    if not source_passed:
        reasons.append("Expected-source behaviour failed.")
    reasons.extend(unsupported)
    return {
        "test": test, "answer": result["answer"],
        "aec_status": result["aec_guardrail"]["status"],
        "retrieved_ids": retrieved_ids, "cited_ids": cited_ids,
        "citations_passed": citations_passed, "source_passed": source_passed,
        "unsupported_passed": not unsupported, "insufficiency": insufficiency,
        "relevant_retrieved_count": len(relevant_retrieved),
        "relevant_cited_count": len(relevant_cited),
        "reasons": reasons, "passed": not reasons,
    }


def status(passed):
    return "PASS" if passed else "FAIL"


def print_result(evaluation):
    test = evaluation["test"]
    print(f"\nTEST {test['number']} — {test['name']}")
    print(f"Question: {test['question']}")
    print(f"AEC guardrail status: {evaluation['aec_status']}")
    print(f"Retrieved source IDs: {evaluation['retrieved_ids']}")
    print(f"Cited source IDs: {evaluation['cited_ids']}")
    print(f"Citation validation: {status(evaluation['citations_passed'])}")
    print(f"Expected-source behaviour: {status(evaluation['source_passed'])}")
    print(f"Unsupported/invented information check: {status(evaluation['unsupported_passed'])}")
    print(f"Insufficiency behaviour: {evaluation['insufficiency']}")
    if test["number"] == 2:
        print(f"Distinct relevant retrieved source count: {evaluation['relevant_retrieved_count']}")
        print(f"Distinct relevant cited source count: {evaluation['relevant_cited_count']}")
    for reason in evaluation["reasons"]:
        print(f"Failure: {reason}")
    print(f"Final result: {status(evaluation['passed'])}")
    print("Generated answer (for manual technical review):")
    print(evaluation["answer"], flush=True)


def main():
    print("Deterministic checks only; qualitative technical claims require human review.", flush=True)
    passed_count = 0
    for test in TESTS:
        print(f"\nRunning Test {test['number']} — {test['name']}...", flush=True)
        try:
            evaluation = evaluate_test(test)
        except Exception as error:
            # Complete all three required tests even if one call fails.
            print(f"Test {test['number']}: FAIL — {type(error).__name__}: {error}", flush=True)
            continue
        print_result(evaluation)
        passed_count += evaluation["passed"]
    print(f"\nSUMMARY\n{passed_count}/3 tests passed", flush=True)


if __name__ == "__main__":
    main()
