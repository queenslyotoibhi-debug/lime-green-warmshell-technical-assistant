"""Presentation-only chat UI for the frozen Warmshell backend."""

from html import escape
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import streamlit as st


APP_TITLE = "Lime Green — Warmshell Technical Assistant"
EXAMPLES = (
    "What is the fire classification of Warmshell Internal?",
    "What should I consider around an existing window opening?",
    # Deliberate misspellings: demonstrates noisy-language handling at retrieval.
    "can i put warmshel on a damp ston wall?",
    "house cold, need insulation",
    "For an old solid masonry wall, what preparation is required before installing "
    "Warmshell Internal, and how do the Duro coat, adhesive, woodfibre board and "
    "Solo plaster form the system build-up?",
)
HEADINGS = (
    "ANSWER", "EVIDENCE", "PROJECT CONTEXT / LIMITATIONS",
    "ADDITIONAL INFORMATION REQUIRED", "SOURCES",
)

# Only presentation is changed here; the backend result is retained intact.
CSS = """
<style>
/* ---------- foundations ---------- */
.stApp {
    --ui-font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: #1E1E1E; color: #1F1F1F; color-scheme: light;
    font-family: var(--ui-font);
}
[data-testid="stHeader"], [data-testid="stSidebar"], footer { display: none; }
.stMainBlockContainer { max-width: 1160px; padding: 24px 28px; }
/* System typography for every UI element except the wordmark and icon glyphs. */
.stApp :is(h1, h2, h3, h4, h5, h6, p, li, div, span, a, button, summary, label,
    textarea, input, pre, code, em, strong, small, td, th):not([data-testid="stIconMaterial"]):not(.brand-mark) {
    font-family: var(--ui-font) !important;
}

/* ---------- white application canvas ---------- */
.st-key-app_panel {
    background: #FFFFFF; border-radius: 22px; padding: 30px 38px 24px;
    box-shadow: 0 20px 65px #00000024; color-scheme: light;
    --text-color: #1F1F1F; --primary-color: #60A23A;
    --background-color: #FFFFFF; --secondary-background-color: #F7F7F7;
}
/* Elements that own their colour (wordmark, escalation copy) are excluded here
   rather than re-coloured by competing rules further down the sheet. */
.st-key-app_panel,
.st-key-app_panel :is(h1, h2, h3, h4, p, li, summary, label, span, div):not(
    .brand-mark, .escalation-body, .escalation-note) {
    color: #1F1F1F;
}
.st-key-app_panel [data-testid="stVerticalBlockBorderWrapper"] { background: transparent; }

/* ---------- brand header ---------- */
.brand-row { display: flex; align-items: center; justify-content: space-between;
    gap: 20px; }
.brand-mark { color: #71BF44; font-family: Georgia, "Times New Roman", serif !important;
    font-size: 32px; font-weight: 400; letter-spacing: -1px; line-height: 1.2;
    background: transparent; border: none; }
.assistant-status { font-size: 18px; font-weight: 650; color: #1F1F1F; }
.lime-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #71BF44; margin-right: 9px; vertical-align: middle; }

/* ---------- type scale ---------- */
.st-key-app_panel h1 { font-size: 20px; font-weight: 650; letter-spacing: -0.02em;
    margin-top: 28px; line-height: 1.3; padding: 0 0 6px; color: #1F1F1F; }
.st-key-app_panel :is(h2, h3, h4) { font-size: 15px; font-weight: 650;
    letter-spacing: -0.01em; padding: 8px 0 2px; color: #1F1F1F; }
.st-key-app_panel :is(p, li) { font-size: 15px; font-weight: 400; line-height: 1.55; }
.st-key-app_panel [data-testid="stCaptionContainer"],
.st-key-app_panel [data-testid="stCaptionContainer"] :is(p, div, span) {
    color: #5F5F5F !important; font-size: 13px; line-height: 1.45; opacity: 1 !important; }

/* ---------- conversation ---------- */
.st-key-conversation { height: clamp(260px, calc(100dvh - 475px), 560px) !important;
    padding: 20px 6px 16px 0; background: transparent;
    scrollbar-width: thin; scrollbar-color: #D7D7D7 #FFFFFF; }
.st-key-conversation:has(.welcome) { height: clamp(180px, 24dvh, 240px) !important;
    display: flex; justify-content: center; }
.user-bubble { margin: 8px 0 20px auto; width: fit-content; max-width: 55%;
    background: #F7F7F7; border: none; border-radius: 14px; padding: 12px 16px;
    line-height: 1.55; font-size: 15px; font-weight: 400; color: #1F1F1F;
    white-space: pre-wrap; overflow-wrap: anywhere; }
[class*="st-key-assistant_"] { background: #EDEDED; border-radius: 20px;
    max-width: 88%; padding: 17px 20px; margin: 0 auto 20px 0; }
.welcome { padding: 12px 8px; }
.welcome h2 { font-size: 20px; font-weight: 650; color: #1F1F1F; letter-spacing: -0.02em; }
.welcome p { max-width: 520px; font-size: 15px; line-height: 1.55; color: #5F5F5F; }

/* ---------- thinking state ---------- */
.thinking { display: flex; align-items: center; gap: 9px; color: #5F5F5F;
    font-size: 14px; line-height: 1.45; padding: 4px; }
.pulse-dot { display: block; flex: 0 0 8px; width: 8px; height: 8px; border-radius: 50%;
    background: #71BF44; animation: lg-pulse 1.2s ease-in-out infinite; }
@keyframes lg-pulse {
    0%, 100% { opacity: .35; transform: scale(.85); }
    50% { opacity: 1; transform: scale(1); }
}
/* Status phrases rotate in CSS only, so the blocking backend request is never
   touched and no polling or extra rerun is introduced. */
.thinking-rotator { position: relative; display: block; height: 21px; min-width: 250px; }
.thinking-rotator > span { position: absolute; left: 0; top: 0; white-space: nowrap;
    opacity: 0; animation: lg-phrase 12s ease-in-out infinite; }
.thinking-rotator > span:nth-child(2) { animation-delay: 3s; }
.thinking-rotator > span:nth-child(3) { animation-delay: 6s; }
.thinking-rotator > span:nth-child(4) { animation-delay: 9s; }
.thinking-static { animation: none !important; opacity: 0; }
@keyframes lg-phrase {
    0% { opacity: 0; } 2% { opacity: 1; } 22% { opacity: 1; }
    25%, 100% { opacity: 0; }
}
.thinking-sr { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
    overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }
@media (prefers-reduced-motion: reduce) {
    .pulse-dot { animation: none; opacity: 1; transform: none; }
    .thinking-rotator > span { animation: none !important; opacity: 0 !important; }
    .thinking-static { opacity: 1 !important; }
}

/* ---------- example question disclosure ---------- */
/* A plain green text row: the native button element is kept for its focus and
   keyboard behaviour, and only its chrome is stripped. */
.st-key-examples_toggle button,
.st-key-examples_toggle button:is(:hover, :active, :focus, :focus-visible) {
    width: auto; min-height: 0; height: auto; padding: 2px 0;
    border: none !important; background: transparent !important;
    box-shadow: none !important; }
.st-key-examples_toggle button :is(p, div, span) { font-size: 15px; font-weight: 650;
    line-height: 1.5; color: #60A23A !important; }
.st-key-examples_toggle button p::before { content: ""; display: inline-block;
    width: 6px; height: 6px; margin-right: 10px; vertical-align: 2px;
    border-right: 2px solid currentColor; border-bottom: 2px solid currentColor;
    transition: transform .15s ease; }
.st-key-examples_toggle_closed button p::before { transform: rotate(-45deg); }
.st-key-examples_toggle_open button p::before { transform: rotate(45deg); }
.st-key-examples_toggle button:hover :is(p, div, span) { color: #4E8A2F !important; }
.st-key-examples_toggle button:focus-visible { outline: 2px solid #60A23A !important;
    outline-offset: 2px; border-radius: 6px; }

/* ---------- example question chips ---------- */
.st-key-examples { display: flex; flex-wrap: wrap; gap: 10px; background: transparent; }
.st-key-examples button { width: auto; max-width: 100%; border: 1px solid #D7D7D7 !important;
    border-radius: 999px !important; background: #F7F7F7 !important; color: #1F1F1F !important;
    padding: 10px 16px; text-align: left; min-height: 44px; height: auto;
    white-space: normal; box-shadow: none !important; }
.st-key-examples button :is(p, div, span) { font-size: 14px; font-weight: 500;
    line-height: 1.35; color: #1F1F1F !important; white-space: normal; overflow-wrap: anywhere; }
.st-key-examples button:hover:not(:disabled) { border-color: #BDBDBD !important;
    background: #EEEEEE !important; }

/* ---------- question input: one unified rounded control ---------- */
/* The outer stChatInput is the ONLY visual shell: it owns the single rounded
   stroke in both states, and every nested wrapper is stripped flat. */
.st-key-question [data-testid="stChatInput"] { position: relative;
    border: 1.5px solid #1F1F1F !important; border-radius: 26px !important;
    background: #FFFFFF !important; min-height: 88px; padding: 18px 64px 18px 20px;
    box-sizing: border-box; box-shadow: none !important; outline: none !important;
    transition: border-color .15s ease, box-shadow .15s ease; }
.st-key-question [data-testid="stChatInput"] * { box-shadow: none !important; }
.st-key-question [data-testid="stChatInput"] :is(div, form, section, label),
.st-key-question [data-testid="stChatInput"] :is(div, form, section, label):is(:focus, :focus-visible, :focus-within, [data-focus="true"]),
.st-key-question [data-testid="stChatInput"] [data-baseweb="textarea"],
.st-key-question [data-testid="stChatInput"] [data-baseweb="base-input"],
.st-key-question [data-testid="stChatInputTextArea"],
.st-key-question textarea,
.st-key-question textarea:is(:focus, :focus-visible, [data-focus="true"]) {
    background: transparent !important; background-color: transparent !important;
    background-image: none !important; border: 0 !important;
    border-radius: 0 !important; outline: 0 !important; box-shadow: none !important; }
.st-key-question [data-testid="stChatInput"] > div { padding: 0; position: static; }
.st-key-question textarea, .st-key-question [data-testid="stChatInputTextArea"] {
    color: #1F1F1F !important; -webkit-text-fill-color: #1F1F1F !important;
    caret-color: #1F1F1F; font-size: 15px !important; line-height: 1.5;
    padding: 0 !important; opacity: 1 !important; }
.st-key-question textarea::placeholder {
    color: #707070 !important; -webkit-text-fill-color: #707070 !important;
    opacity: 1 !important; }
.st-key-question [data-testid="stChatInput"]:focus-within {
    border-color: #60A23A !important; outline: none !important;
    box-shadow: 0 0 0 3px rgba(96, 162, 58, .14) !important; }
.st-key-question [data-testid="stChatInput"] [id="stChatInputInstructions"] {
    color: #5F5F5F !important; font-size: 13px; }

/* ---------- circular send button ---------- */
.st-key-question [data-testid="stChatInputSubmitButton"] { position: absolute;
    right: 14px; bottom: 12px; border: none !important; border-radius: 50% !important;
    background: #60A23A !important; color: #FFFFFF !important; width: 38px; height: 38px;
    min-width: 38px; padding: 0; box-shadow: none; cursor: pointer; }
.st-key-question [data-testid="stChatInputSubmitButton"] svg,
.st-key-question [data-testid="stChatInputSubmitButton"] [data-testid="stIconMaterial"] {
    display: none; }
.st-key-question [data-testid="stChatInputSubmitButton"]::after {
    content: "↑"; color: #FFFFFF; font: 18px/1 var(--ui-font); }
.st-key-question [data-testid="stChatInputSubmitButton"]:hover:not(:disabled) {
    background: #4F8630 !important; }
.st-key-question [data-testid="stChatInputSubmitButton"]:disabled { cursor: not-allowed; }

/* ---------- keyboard focus ---------- */
.st-key-app_panel button:focus-visible, .st-key-app_panel a:focus-visible,
.st-key-app_panel summary:focus-visible,
.st-key-app_panel [data-testid="stExpander"] details > :first-child:focus-visible {
    outline: 2px solid #1F1F1F !important; outline-offset: 2px; box-shadow: none !important; }

/* ---------- alerts ---------- */
.st-key-app_panel [data-testid="stAlert"] { background: #F7F7F7 !important;
    border: 1px solid #D7D7D7 !important; border-radius: 14px; }
.st-key-app_panel [data-testid="stAlert"] :is(p, li, div, span) {
    color: #1F1F1F !important; opacity: 1 !important; }
.st-key-app_panel [data-testid="stAlert"] [data-testid="stIconMaterial"] { color: #5F5F5F !important; }

/* ---------- human escalation card ---------- */
.escalation { background: #F3F8EF; border: 1px solid #C9E3B8; border-radius: 14px;
    padding: 14px 16px; margin-top: 14px; }
.st-key-app_panel .escalation-title { color: #1F1F1F; font-size: 15px; font-weight: 650;
    line-height: 1.4; margin: 0 0 6px; }
.st-key-app_panel .escalation-body { color: #3F3F3F; font-size: 14px; line-height: 1.55;
    margin: 0 0 10px; }
.st-key-app_panel a.escalation-cta { color: #4F8630; font-size: 14px; font-weight: 650;
    text-decoration: none; display: inline-flex; align-items: center; min-height: 44px; }
.st-key-app_panel a.escalation-cta:hover { text-decoration: underline; text-underline-offset: 3px; }
.st-key-app_panel .escalation-note { color: #5F5F5F; font-size: 13px; line-height: 1.45;
    margin: 2px 0 0; }

/* ---------- source accordions: readable collapsed AND expanded ---------- */
.st-key-app_panel [data-testid="stExpander"] { background: transparent !important;
    border: none; margin-bottom: 10px; }
.st-key-app_panel [data-testid="stExpander"] details,
.st-key-app_panel [data-testid="stExpander"] > div:first-child {
    background: #FFFFFF !important; border: 1px solid #D7D7D7 !important;
    border-radius: 12px !important; overflow: hidden; }
.st-key-app_panel [data-testid="stExpander"] summary,
.st-key-app_panel [data-testid="stExpander"] details > :first-child {
    background: #FFFFFF !important; color: #1F1F1F !important; border: none !important;
    border-radius: 12px !important; min-height: 44px; padding: 10px 16px !important;
    font-size: 14px; font-weight: 600; }
.st-key-app_panel [data-testid="stExpander"] summary:hover,
.st-key-app_panel [data-testid="stExpander"] details > :first-child:hover {
    background: #F7F7F7 !important; color: #1F1F1F !important; }
.st-key-app_panel [data-testid="stExpander"] summary :is(p, div, span),
.st-key-app_panel [data-testid="stExpander"] details > :first-child :is(p, div, span) {
    color: #1F1F1F !important; font-size: 14px; font-weight: 600; line-height: 1.4;
    opacity: 1 !important; }
.st-key-app_panel [data-testid="stExpander"] [data-testid="stIconMaterial"] {
    color: #1F1F1F !important; opacity: 1 !important; }
.st-key-app_panel [data-testid="stExpanderDetails"] {
    background: #FFFFFF !important; color: #1F1F1F !important;
    border-top: 1px solid #D7D7D7; padding: 14px 16px 16px !important; }
.st-key-app_panel [data-testid="stExpanderDetails"] [data-testid="stCaptionContainer"] :is(p, div, span) {
    color: #5F5F5F !important; font-size: 13px !important; line-height: 1.45; opacity: 1 !important; }
.source-evidence { color: #2B2B2B !important; font-size: 14px; line-height: 1.6;
    opacity: 1; margin: 8px 0 12px; white-space: pre-wrap; overflow-wrap: anywhere; }
.st-key-app_panel [data-testid="stExpanderDetails"] a {
    color: #4F8630 !important; font-weight: 600; background: transparent !important;
    border: none !important; box-shadow: none !important; padding: 8px 0 !important;
    min-height: 44px; display: inline-flex; align-items: center; text-decoration: none; }
.st-key-app_panel [data-testid="stExpanderDetails"] a :is(p, div, span) {
    color: #4F8630 !important; font-size: 14px; font-weight: 600;
    text-decoration: none !important; }
.st-key-app_panel [data-testid="stExpanderDetails"] a:hover,
.st-key-app_panel [data-testid="stExpanderDetails"] a:hover :is(p, div, span) {
    color: #4F8630 !important; text-decoration: underline !important;
    text-underline-offset: 3px; }
.st-key-app_panel a { color: #1F1F1F; text-underline-offset: 3px; }

@media (max-width: 640px) {
    .stMainBlockContainer { padding: 10px; }
    .st-key-app_panel { padding: 20px 16px; border-radius: 18px; }
    .brand-row { flex-wrap: wrap; gap: 12px; }
    .user-bubble { max-width: 92%; }
    .assistant-status { font-size: 18px; }
    [class*="st-key-assistant_"] { padding: 16px 18px; max-width: 96%; }
}
</style>
"""


def parse_sections(answer):
    """Recognise section headings without rewriting any answer content."""
    sections = {name: [] for name in HEADINGS}
    current = "ANSWER"
    for line in answer.splitlines():
        heading = line.strip().strip("#* ").rstrip(":").strip().upper()
        if heading in sections:
            current = heading
        else:
            sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def readable_text(text):
    """Hide machine citation labels in the display, keeping the raw result."""
    text = re.sub(r"\[S\d+\](?:\s*[,;]?\s*\[S\d+\])*", "", text)
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


NO_FOLLOW_UP = re.compile(
    r"^(none|none required|not applicable|n/?a|"
    r"no additional information( required)?)$", re.IGNORECASE)

ESCALATION = (
    '<div class="escalation">'
    '<p class="escalation-title">Need project-specific advice?</p>'
    '<p class="escalation-body">This question depends on details that cannot be '
    "confirmed from the available guidance alone. Lime Green's technical team can "
    'help you review the project before you proceed.</p>'
    '<a class="escalation-cta" href="https://www.lime-green.co.uk/contact" '
    'target="_blank" rel="noopener noreferrer">Talk to the lime experts ↗</a>'
    '<p class="escalation-note">We\'re here to help with technical guidance and '
    'project-specific questions.</p></div>'
)


def needs_expert_help(follow_up, insufficient):
    """Display-only cue: does the parsed answer show meaningful uncertainty?

    The backend often writes "None required." plus a short explanation, so the
    opening sentence decides whether anything is actually outstanding.
    """
    if insufficient:
        return True
    stripped = re.sub(r"^[\s\-–—•*#>]+", "", follow_up).strip()
    opening = re.split(r"(?<=[.!?])\s", stripped, maxsplit=1)[0].strip().rstrip(".")
    return bool(stripped) and not NO_FOLLOW_UP.match(opening)


def source_cards(result):
    """Map only actually cited IDs to their corresponding retrieved chunks."""
    retrieved = result.get("retrieved_results", [])
    cards = []
    for number in sorted(set(result.get("cited_source_numbers", []))):
        if 1 <= number <= len(retrieved):
            cards.append(retrieved[number - 1])
    return cards


def short_excerpt(text, limit=340):
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def original_url(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme in ("https", "http") and parsed.netloc:
            return value.strip()
    except ValueError:
        pass
    return None


def render_answer(result):
    sections = parse_sections(result["answer"])
    main_answer = readable_text(sections["ANSWER"])
    # This is a display cue, not a new sufficiency decision or backend rule.
    insufficient = re.search(
        r"insufficient|not (?:provide |have |contain )?enough information|"
        r"cannot (?:establish|confirm|determine|provide)|can't (?:confirm|determine)|"
        r"does not (?:provide|contain|include).{0,60}(?:price|pricing|information)",
        " ".join(sections["ANSWER"].split()), re.IGNORECASE,
    )
    if insufficient:
        st.info(main_answer)
    elif main_answer:
        st.markdown(main_answer)
    follow_up = ""
    for heading, label in (
        ("PROJECT CONTEXT / LIMITATIONS", "Project considerations"),
        ("ADDITIONAL INFORMATION REQUIRED", "What I still need to know"),
    ):
        if sections[heading]:
            body = readable_text(sections[heading])
            if heading == "ADDITIONAL INFORMATION REQUIRED":
                follow_up = body
            st.markdown(f"### {label}")
            st.markdown(body)

    # Routes genuinely uncertain questions to Lime Green's technical team. This
    # reads the parsed answer only; no backend sufficiency rule is re-decided.
    if needs_expert_help(follow_up, insufficient):
        st.html(ESCALATION)

    cards = source_cards(result)
    if cards:
        st.markdown("### Further guidance")
        st.caption("Open a source to see where the answer came from.")
    for source in cards:
        title = source.get("title") or source.get("source_id") or "Source document"
        page = source.get("page")
        with st.expander(title):
            if page is not None:
                st.caption(f"Page {page}")
            section = source.get("section")
            detail = source.get("detail_code")
            if section:
                st.caption(section)
            if detail and detail not in (section or ""):
                st.caption(detail)
            excerpt = short_excerpt(source.get("text"))
            if excerpt:
                # Rendered as styled text rather than st.text so the evidence is
                # readable prose, not pale monospace. The excerpt is unchanged.
                st.html(f'<div class="source-evidence">{escape(excerpt)}</div>')
            url = original_url(source.get("url"))
            if url:
                st.link_button("View original source ↗", url)
    if result.get("unavailable_source_numbers"):
        st.info("A source reference could not be verified. Please confirm the affected guidance with Lime Green.")


def queue_question(question):
    if question.strip() and not st.session_state.pending_question:
        st.session_state.messages.append({"role": "user", "content": question})
        st.session_state.pending_question = question


def submit_question():
    queue_question(st.session_state.question)


def examples_are_open():
    """Open on an empty conversation, collapsed once questions are being asked.
    A choice made this session outranks both."""
    if st.session_state.examples_open is None:
        return not st.session_state.messages
    return st.session_state.examples_open


def toggle_examples():
    st.session_state.examples_open = not examples_are_open()


st.set_page_config(page_title=APP_TITLE, layout="wide", initial_sidebar_state="collapsed")
st.session_state.setdefault("messages", [])
st.session_state.setdefault("pending_question", None)
# None means "follow the stage default"; a bool records a deliberate choice.
st.session_state.setdefault("examples_open", None)
st.html(CSS)

with st.container(key="app_panel", gap="small"):
    st.html('''<div class="brand-row">
        <div class="brand-mark" aria-label="Lime Green">lime|green</div>
        <div class="assistant-status"><span class="lime-dot"></span>AI Chat Assistant</div>
    </div>''')
    st.title(APP_TITLE)
    st.caption("Local AI assistant grounded in Lime Green technical guidance.")

    with st.container(height=420, border=False, key="conversation", autoscroll=True):
        if not st.session_state.messages:
            st.html('''<div class="welcome"><h2>How can I help?</h2>
                <p>Ask about Warmshell Internal, explore the technical guidance,
                or tell me about the wall you have in mind.</p></div>''')
        for index, message in enumerate(st.session_state.messages):
            if message["role"] == "user":
                st.html(f'<div class="user-bubble">{escape(message["content"])}</div>')
            else:
                with st.container(key=f"assistant_{index}"):
                    if "error" in message:
                        st.info(message["error"])
                    else:
                        render_answer(message["result"])

    examples_open = examples_are_open()
    with st.container(key=f"examples_toggle_{'open' if examples_open else 'closed'}"):
        st.button("Try an example", key="examples_toggle", width="content",
                  on_click=toggle_examples)
    if examples_open:
        with st.container(key="examples", horizontal=True, gap=10):
            for example in EXAMPLES:
                st.button(example, key=f"example_{EXAMPLES.index(example)}", width="content",
                          wrap=True, on_click=queue_question, args=(example,),
                          disabled=bool(st.session_state.pending_question))
    thinking = st.empty()
    if st.session_state.pending_question:
        # Progress is never colour-only: the pulsing dot accompanies live text.
        # Assistive tech gets one stable phrase; the visible phrases rotate in CSS.
        thinking.html(
            '<div class="thinking" role="status" aria-live="polite">'
            '<span class="pulse-dot"></span>'
            '<span class="thinking-sr">Reviewing Lime Green guidance...</span>'
            '<span class="thinking-rotator" aria-hidden="true">'
            '<span>Searching technical guidance...</span>'
            '<span>Reviewing relevant sources...</span>'
            '<span>Checking the evidence...</span>'
            '<span>Preparing a grounded answer...</span>'
            '<span class="thinking-static">Reviewing Lime Green guidance...</span>'
            '</span></div>')
    st.chat_input("Ask about Warmshell Internal…", key="question", on_submit=submit_question,
                  disabled=bool(st.session_state.pending_question), submit_mode="disable")

# Streamlit's native send label is not configurable. Change only its accessible
# name; native keyboard handling, submission, and session state stay untouched.
st.html('''<script>
(() => {
    window.warmshellSendLabelObserver?.disconnect();
    const labelSendButton = () => {
        const button = document.querySelector('.st-key-question [data-testid="stChatInputSubmitButton"]');
        if (button && button.getAttribute('aria-label') !== 'Send question') {
            button.setAttribute('aria-label', 'Send question');
            button.setAttribute('title', 'Send question');
        }
    };
    labelSendButton();
    window.warmshellSendLabelObserver = new MutationObserver(labelSendButton);
    window.warmshellSendLabelObserver.observe(document.body, {
        childList: true, subtree: true, attributes: true, attributeFilter: ['aria-label']
    });
})();
</script>''', unsafe_allow_javascript=True)

# Draw all controls before starting local inference. Never call the backend on
# a plain rerun, and retain its entire result for citation traceability.
if st.session_state.pending_question:
    question = st.session_state.pending_question
    try:
        source_directory = str(Path(__file__).resolve().parent / "src")
        if source_directory not in sys.path:
            sys.path.insert(0, source_directory)
        from rag_answer import answer_question

        result = answer_question(question)
        st.session_state.messages.append({"role": "assistant", "result": result})
    except Exception:
        st.session_state.messages.append({
            "role": "assistant",
            "error": "I couldn't complete that answer. Please check that the local AI service is running, then try your question again.",
        })
    finally:
        st.session_state.pending_question = None
    st.rerun()
