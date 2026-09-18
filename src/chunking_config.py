SOURCE_STRATEGIES = {

    "WSI-ASSESS-001": {
        "strategy": "plain_sections"
    },

    "WSI-DESIGN-001": {
        "strategy": "mixed_sections"
    },

    "WSI-BDA-001": {
        "strategy": "numbered_sections"
    },

    "WSI-FIRE-001": {
        "strategy": "fire_report"
    },

    "WSI-INSTALL-001": {
        "strategy": "mixed_sections"
    },

    "WSI-SPEC-001": {
        "strategy": "mixed_sections"
    },

    "WSI-SOLO-001": {
        "strategy": "mixed_sections"
    },

    "WSI-ADHESIVE-001": {
        "strategy": "mixed_sections"
    },

    "WSI-WOODFIBRE-001": {
        "strategy": "mixed_sections"
    },

    "WSI-DURO-001": {
        "strategy": "mixed_sections"
    },

    "WSI-MAINT-001": {
        "strategy": "mixed_sections"
    },

    "WSI-WARRANTY-001": {
        "strategy": "page"
    },

    "WSI-DETAILS-001": {
        "strategy": "detail_pages"
    },
}


PAGE_OVERRIDES = {

    ("WSI-WARRANTY-001", 1): {
        "page_role": "warranty_terms",
        "strategy": "page"
    },

    ("WSI-WARRANTY-001", 2): {
        "page_role": "warranty_terms",
        "strategy": "page"
    },

    ("WSI-DETAILS-001", 1): {
        "page_role": "cover",
        "strategy": "detail_pages",
        "retrieval_enabled": False
    },

    ("WSI-DETAILS-001", 2): {
        "page_role": "introduction",
        "strategy": "detail_pages",
        "retrieval_enabled": False
    },

    ("WSI-DETAILS-001", 3): {
        "page_role": "contents",
        "strategy": "detail_pages",
        "retrieval_enabled": False
    },

    ("WSI-DETAILS-001", 4): {
        "page_role": "system_image",
        "strategy": "detail_pages",
        "retrieval_enabled": False
    },

    ("WSI-DETAILS-001", 24): {
        "page_role": "publication_information",
        "strategy": "detail_pages",
        "retrieval_enabled": False
    },

    ("WSI-BDA-001", 1): {
        "page_role": "scope_and_description",
        "strategy": "page"
    },

    ("WSI-BDA-001", 2): {
        "page_role": "summary_and_contents",
        "strategy": "page",
        "retrieval_enabled": False
    },

    # Design Guide contents page
    ("WSI-DESIGN-001", 2): {
        "page_role": "contents",
        "retrieval_enabled": False
    },

    # Fire report
    ("WSI-FIRE-001", 1): {
        "page_role": "introduction",
        "strategy": "page",
        "retrieval_enabled": False
    },

    ("WSI-FIRE-001", 2): {
        "page_role": "product_description",
        "strategy": "fire_report"
    },

    ("WSI-FIRE-001", 3): {
        "page_role": "test_results",
        "strategy": "page"
    },

    ("WSI-FIRE-001", 4): {
        "page_role": "classification",
        "strategy": "fire_report"
    },

    ("WSI-FIRE-001", 5): {
        "page_role": "limitations",
        "strategy": "fire_report"
    },

    # BDA final supporting-information page
    ("WSI-BDA-001", 11): {
        "page_role": "supporting_information",
        "strategy": "numbered_sections"
    },
}
