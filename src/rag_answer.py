import sys
import re
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from aec_guardrail import assess_sufficiency, extract_aec_context
from governed_search import governed_search
from query_processor import process_query


MODEL = "qwen3:4b-instruct"
TEMPERATURE = 0
NUM_PREDICT = 512
NUM_CTX = 8192
TOP_K = 5

TEST_QUESTIONS = [
    "What is the fire classification of Warmshell Internal?",
    "Can I install 100 mm Warmshell on my stone cottage?",
    (
        "My wall is solid stone, internally lime plastered and appears dry. "
        "Can I use Warmshell Internal?"
    ),
]


SYSTEM_INSTRUCTION = """You are a technical assistant for Lime Green Warmshell Internal.

Answer the user's question using ONLY the supplied evidence.

Do not use unsupported technical knowledge.

Do not invent dimensions, U-values, fire performance, installation requirements,
regulatory requirements, warranty conditions or product suitability.

If the evidence does not contain enough information to answer reliably, explicitly
say that the available Lime Green evidence is insufficient.

Never claim that Lime Green guidance, documentation, or the knowledge base does not
address a subject merely because the retrieved top-k evidence does not contain it.
If the retrieved evidence is insufficient to establish something, say: "The retrieved
evidence does not provide enough information to establish..." Do not turn absence from
the retrieved chunks into a claim that the information does not exist elsewhere.

In the EVIDENCE section, include only evidence that materially helps answer the
question, explains a relevant limitation, or justifies the need for additional
information. Do not add unrelated technical values simply because they were retrieved.

For project-specific suitability questions, do not assume unknown building conditions.

Write in clear, helpful, plain English. Be friendly and professional. Avoid unnecessary
technical jargon, explain necessary technical terms simply, and never sound more certain
than the supplied evidence allows.

The user message includes a deterministic AEC project-context assessment. If its status
is PARTIAL or INSUFFICIENT, this is a project-specific question with incomplete context:
- Do not give a definitive project-suitability recommendation.
- Do not convert general product guidance into approval for this building.
- Use the retrieved evidence to explain what is relevant.
- Clearly distinguish facts supplied by the user, facts in Lime Green evidence, and
  information that remains unknown.
- In PROJECT CONTEXT / LIMITATIONS, summarise the known context from the assessment.
- In ADDITIONAL INFORMATION REQUIRED, turn only the assessment's missing_context items
  into natural, friendly questions. Do not invent additional missing requirements.

If the AEC status is SUFFICIENT, follow the normal grounded-answer behaviour. A general
factual question does not require private building context merely to report a documented
fact.

The AEC assessment concerns building context, not the currency of commercial evidence.
For current or installed prices, quotations, stock, availability, lead times, supplier
pricing, or other live commercial information, check whether the supplied evidence is
sufficiently current to verify what is requested. If it is not, do not invent or estimate
a value. State that the available knowledge base cannot verify the current information,
and distinguish static technical/product guidance from live or project-specific
commercial information. Give an appropriate next action: obtain a current quotation or
confirmation from Lime Green or a relevant supplier. Put that required external action
under ADDITIONAL INFORMATION REQUIRED; never say "None required" when it is needed.
This applies regardless of AEC status and is separate from missing building-context
questions. Do not invent contact details, prices, dates, supplier names or commercial
terms. Cite only evidence that materially supports the response.

For consequential claims involving fire, thermal performance or U-values, moisture
or condensation, structural or fixing suitability, certification, warranty, durability,
or regulatory/technical performance, inspect
ALL supplied evidence for relevant qualifications, limitations, field-of-application
conditions, assumptions, and exclusions. Do not stop after finding the headline claim.
Never detach a technical value, classification or certification from its material scope,
test conditions or restrictions in authoritative retrieved evidence. Prioritise the
conditions given by the strongest retrieved source and retain them alongside the claim.

If the supplied evidence contains any such conditions relevant to the answer, you MUST
summarise the important ones under PROJECT CONTEXT / LIMITATIONS and cite their [S#]
source. Never write "None applicable" merely because the question is general. Say that
there are no material limitations only when the supplied evidence genuinely contains
none relevant to the answer.

For consequential claims, prefer the strongest available evidence in this order:
independent testing or classification, independent certification, manufacturer
technical documents, then manufacturer webpages or FAQ. Lower-authority sources may
still support the answer. When sources repeat the same claim, avoid unnecessary
repetition and cite the strongest source first.

Where the evidence states conditions or a field of application, distinguish an
unqualified statement such as "the system is classified" from the qualified statement
"the system is classified within the report's stated field of application".

When summarising consequential technical limitations, preserve the evidence's meaning
and category for every condition. Do not relabel a substrate, facing, fixing method,
test orientation, asymmetry condition, thickness range, density requirement, air gap,
or cavity condition as something else. Include all materially relevant conditions from
the stated field of application rather than selecting only some of them. Summarise the
conditions clearly instead of copying every numerical detail unless a number is needed
to answer the question. Never invent, infer, or reinterpret a technical condition.

For fire-classification evidence specifically, if the report describes asymmetry or
the fire-exposed face, state explicitly that the classification is asymmetrical and is
valid for fire exposure on the stated face. Do not reduce this to "tested face" and do
not describe the facing as an application method. If the field of application states
that no air gap or cavity is permitted, include that condition explicitly. For a user
who asks only for the classification, summarise thickness and density as the report's
specified ranges; do not reproduce detailed numerical limits unless the user asks for
them or they are necessary to answer reliably.

Before finalising a fire-classification answer, apply this evidence-faithfulness check:
- Describe Solo One coat Lime Plaster only as the fire-exposed face in the report's
  asymmetry condition. Never call Solo the substrate or an application method.
- Keep the substrate condition separate from the fire-exposed-facing condition.
- State the no-air-gap-or-cavity condition when it appears in the field of application.
- For a classification-only question, refer to the report's specified thickness and
  density ranges without reproducing their numerical values.
- Include the report's limitation that the classification document does not represent
  type approval or certification when that limitation appears in the supplied evidence.

Cite evidence using [S1], [S2], etc.

Never cite a source that was not supplied in the evidence.

Citation fidelity: attach each [S#] only to a statement directly supported by that
specific evidence block. Do not cite a nearby or topically related block when another
retrieved block is the actual source of the claim. If a sentence combines claims from
different blocks, split it or cite the relevant blocks separately with each claim.
Never move a citation onto an unsupported claim for convenience. Every technical
dimension, tolerance, requirement or installation instruction must be traceable to
the evidence block cited immediately with it.

Keep the complete generated response concise, preferably under about 280 words.
This word target and section lengths are secondary to material technical completeness.
Prioritise a complete answer and complete sentences over unnecessary explanation.
Do not repeat the same fact in multiple sections. Preserve citations such as [S1]
and [S2]. Never omit important safety information, technical conditions, uncertainty,
or insufficiency information merely to save words.
- ANSWER: normally 1-3 sentences.
- EVIDENCE: only materially necessary support, normally 2-4 concise points.
- PROJECT CONTEXT / LIMITATIONS: normally 1-3 sentences.
- ADDITIONAL INFORMATION REQUIRED: only genuinely needed information, using concise
  bullets or questions without repeating limitations already stated. If no additional
  project information is required, say so briefly.

Use this response structure:

ANSWER
<direct answer>

EVIDENCE
<key supporting evidence with [S#] references>

PROJECT CONTEXT / LIMITATIONS
<important limitations or missing project context, if applicable>

ADDITIONAL INFORMATION REQUIRED
<only include content here if more information is genuinely required>

Do not generate a SOURCES section. The application will build it from the [S#]
citations actually used in your response.

MANDATORY FIRE-CLASSIFICATION OUTPUT CHECK:
When the user asks for the fire classification and the supplied evidence contains these
conditions, the response is incomplete unless PROJECT CONTEXT / LIMITATIONS explicitly:
1. says the classification applies within the report's stated field of application;
2. says it is asymmetrical and valid for fire exposure on the Solo One coat Lime
   Plaster face, without calling Solo a substrate or application method;
3. says no air gap or cavity is permitted;
4. retains the tested product/system formulation restriction;
5. states the applicable substrate conditions separately from the exposed face;
6. states the permitted adhesive/mechanical fixing conditions; and
7. says the classification document does not represent type approval or certification.
Summarise ALL materially applicable conditions found in the report, not just a selection.
Only include restrictions actually present in the supplied evidence; do not invent them.
For that classification-only question, do not print numerical thickness or density
limits; refer only to the report's specified thickness and density ranges.

Do not output hidden reasoning or analysis. Begin with ANSWER."""


PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_INSTRUCTION),
    (
        "human",
        "USER QUESTION:\n{question}\n\n"
        "AEC PROJECT-CONTEXT ASSESSMENT:\n{aec_assessment}\n\n"
        "SUPPLIED EVIDENCE:\n{evidence}\n\n"
        "MANDATORY FINAL RESPONSE CONSTRAINTS:\n"
        "{aec_generation_instruction}"
    ),
])


def display_value(value):
    if value is None or value == "":
        return "Not provided"

    return str(value)


def format_evidence(retrieved_results):
    evidence_blocks = []

    for source_number, result in enumerate(
        retrieved_results,
        start=1
    ):
        evidence_blocks.append(
            f"[S{source_number}]\n"
            f"Title: {display_value(result.get('title'))}\n"
            f"Source ID: {display_value(result.get('source_id'))}\n"
            f"Page: {display_value(result.get('page'))}\n"
            f"Section: {display_value(result.get('section'))}\n"
            f"Detail Code: {display_value(result.get('detail_code'))}\n"
            f"Authority: {display_value(result.get('authority'))}\n"
            f"URL: {display_value(result.get('url'))}\n"
            "Evidence:\n"
            f"{display_value(result.get('text'))}"
        )

    return "\n\n".join(evidence_blocks)


def build_aec_generation_instruction(aec_assessment):
    citation_instruction = (
        "Cite evidence only with the exact bracket format [S1], [S2], etc. "
        "Never write an evidence reference as S1 or (S1)."
    )

    if aec_assessment["status"] == "sufficient":
        return (
            "The AEC status is SUFFICIENT. Answer normally from the supplied "
            f"evidence. {citation_instruction}"
        )

    known_context = json.dumps(
        aec_assessment["known_context"],
        ensure_ascii=False,
        indent=2
    )
    missing_context = json.dumps(
        aec_assessment["missing_context"],
        ensure_ascii=False,
        indent=2
    )

    return (
        f"The AEC status is {aec_assessment['status'].upper()}. "
        "Do not begin with Yes or No. Do not state that Warmshell Internal is "
        "suitable, unsuitable, approved, or not approved for this project. "
        "State clearly that you can explain the relevant Lime Green guidance "
        "but cannot confirm suitability from the information supplied.\n\n"
        "Facts explicitly supplied by the user:\n"
        f"{known_context}\n\n"
        "The complete and exclusive list of missing context is:\n"
        f"{missing_context}\n\n"
        "In PROJECT CONTEXT / LIMITATIONS, acknowledge the supplied facts and "
        "keep them separate from evidence facts and unknown facts. In "
        "ADDITIONAL INFORMATION REQUIRED, ask one natural question for each "
        "item in that missing-context list and ask for nothing else. Do not ask "
        "again for a field already present in the supplied facts. Never claim "
        "that Lime Green guidance does not address a subject, or infer that a "
        "product is designed to exclude a construction type, merely because the "
        "retrieved chunks do not establish it. Use the wording: 'The retrieved "
        "evidence does not provide enough information to establish...' Exclude "
        "retrieved details that do not materially answer the question, explain "
        "a relevant limitation, or justify requested context. "
        f"{citation_instruction}"
    )


def remove_model_sources_section(answer):
    sources_heading = re.compile(
        r"^\s*(?:#{1,6}\s*)?(?:\*\*)?SOURCES(?:\*\*)?\s*:?\s*$",
        re.IGNORECASE
    )
    answer_lines = answer.splitlines()

    for line_number, line in enumerate(answer_lines):
        if sources_heading.match(line):
            return "\n".join(answer_lines[:line_number]).rstrip()

    return answer.strip()


def extract_cited_source_numbers(answer):
    return sorted({
        int(source_number)
        for source_number in re.findall(
            r"\[S(\d+)\]",
            answer,
            flags=re.IGNORECASE
        )
    })


def build_sources_section(answer, retrieved_results):
    cited_source_numbers = extract_cited_source_numbers(answer)
    retrieved_by_number = {
        source_number: result
        for source_number, result in enumerate(
            retrieved_results,
            start=1
        )
    }
    unavailable_source_numbers = [
        source_number
        for source_number in cited_source_numbers
        if source_number not in retrieved_by_number
    ]
    lines = ["SOURCES"]

    for source_number in cited_source_numbers:
        result = retrieved_by_number.get(source_number)

        if result is None:
            continue

        title = result.get("title") or result.get(
            "source_id") or "Untitled source"
        source_parts = [f"[S{source_number}] {title}"]
        page = result.get("page")
        section = result.get("detail_code") or result.get("section")

        if page is not None and str(page).strip():
            source_parts.append(f"page {page}")

        if section is not None and str(section).strip():
            source_parts.append(str(section).strip())

        lines.append(" — ".join(source_parts))

    if len(lines) == 1:
        lines.append("No evidence sources cited.")

    if unavailable_source_numbers:
        unavailable_labels = ", ".join(
            f"[S{source_number}]"
            for source_number in unavailable_source_numbers
        )
        lines.extend([
            "",
            "CITATION VALIDATION ERROR",
            "Unavailable cited source(s): "
            f"{unavailable_labels}",
        ])

    return (
        "\n".join(lines),
        cited_source_numbers,
        unavailable_source_numbers,
    )


def answer_question(question):
    processed_query = process_query(question)
    aec_context = extract_aec_context(question)
    aec_assessment = assess_sufficiency(
        question,
        processed_query,
        aec_context
    )
    retrieval_output = governed_search(
        question,
        top_k=TOP_K
    )
    retrieved_results = retrieval_output["results"]

    if len(retrieved_results) != TOP_K:
        raise ValueError(
            f"Expected {TOP_K} governed evidence chunks, "
            f"found {len(retrieved_results)}."
        )

    evidence = format_evidence(retrieved_results)
    aec_generation_instruction = (
        build_aec_generation_instruction(
            aec_assessment
        )
    )
    model = ChatOllama(
        model=MODEL,
        temperature=TEMPERATURE,
        num_predict=NUM_PREDICT,
        num_ctx=NUM_CTX
    )
    chain = PROMPT | model
    response = chain.invoke({
        "question": question,
        "aec_assessment": json.dumps(
            aec_assessment,
            ensure_ascii=False,
            indent=2
        ),
        "evidence": evidence,
        "aec_generation_instruction": (
            aec_generation_instruction
        ),
    })
    model_answer = remove_model_sources_section(
        response.content
    )
    (
        sources_section,
        cited_source_numbers,
        unavailable_source_numbers,
    ) = build_sources_section(
        model_answer,
        retrieved_results
    )
    final_answer = f"{model_answer}\n\n{sources_section}"

    return {
        "answer": final_answer,
        "retrieved_results": retrieved_results,
        "aec_guardrail": aec_assessment,
        "cited_source_numbers": cited_source_numbers,
        "unavailable_source_numbers": unavailable_source_numbers,
    }


def print_retrieved_evidence(retrieved_results):
    for source_number, result in enumerate(
        retrieved_results,
        start=1
    ):
        section = (
            result.get("detail_code")
            or result.get("section")
        )
        print(
            f"S{source_number} → "
            f"{display_value(result.get('chunk_id'))} / "
            f"{display_value(result.get('title'))} / "
            f"page {display_value(result.get('page'))} / "
            f"{display_value(section)}"
        )


def print_aec_guardrail(aec_assessment):
    print("AEC GUARDRAIL")
    print(
        "project_specific: "
        f"{aec_assessment['project_specific']}"
    )
    print(f"status: {aec_assessment['status']}")
    print("known_context:")
    print(
        json.dumps(
            aec_assessment["known_context"],
            ensure_ascii=False,
            indent=2
        )
    )
    print("missing_context:")
    print(
        json.dumps(
            aec_assessment["missing_context"],
            ensure_ascii=False,
            indent=2
        )
    )
    print(f"reason: {aec_assessment['reason']}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(
            encoding="utf-8",
            line_buffering=True
        )

    for question_number, question in enumerate(
        TEST_QUESTIONS,
        start=1
    ):
        if question_number > 1:
            print(f"\n{'=' * 78}\n")

        output = answer_question(question)

        print("USER QUESTION")
        print(question)
        print("\nGENERATED ANSWER")
        print(output["answer"])
        print()
        print_aec_guardrail(output["aec_guardrail"])
        print("\nRETRIEVED EVIDENCE")
        print_retrieved_evidence(output["retrieved_results"])


if __name__ == "__main__":
    main()
