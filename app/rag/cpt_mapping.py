"""CPT code to coverage category mapping for policy metadata filtering."""

# Coverage categories used in policy documents
COVERAGE_CATEGORIES = [
    "outpatient",
    "inpatient",
    "emergency",
    "diagnostic",
    "laboratory",
    "radiology",
    "surgery",
    "prescription",
    "preventive",
    "mental_health",
    "rehabilitation",
    "maternity",
    "dental",
    "vision",
]

# CPT code ranges mapped to coverage categories
# Based on AMA CPT code structure
CPT_CATEGORY_RANGES = {
    # Evaluation and Management (99201-99499)
    "outpatient": [
        (99201, 99215),  # Office visits
        (99241, 99245),  # Office consultations
        (99381, 99397),  # Preventive visits
        (99401, 99429),  # Counseling
    ],
    "inpatient": [
        (99221, 99223),  # Initial hospital care
        (99231, 99233),  # Subsequent hospital care
        (99238, 99239),  # Hospital discharge
        (99251, 99255),  # Inpatient consultations
        (99291, 99292),  # Critical care
    ],
    "emergency": [
        (99281, 99285),  # Emergency department
        (99288, 99288),  # Emergency physician direction
    ],
    # Anesthesia (00100-01999) and Surgery (10021-69990)
    "surgery": [
        (100, 1999),  # Anesthesia (CPT 00100-01999)
        (10021, 69990),  # Surgery codes
    ],
    # Radiology (70010-79999)
    "radiology": [
        (70010, 79999),  # Radiology procedures
    ],
    # Pathology and Laboratory (80047-89398)
    "laboratory": [
        (80047, 89398),  # Lab tests
    ],
    "diagnostic": [
        (90281, 90399),  # Immune globulins
        (91010, 91299),  # Gastroenterology
        (92002, 92499),  # Ophthalmology
        (92502, 92700),  # Otorhinolaryngology
        (93000, 93799),  # Cardiovascular
        (94002, 94799),  # Pulmonary
        (95004, 95199),  # Allergy testing
        (95250, 95251),  # Glucose monitoring
        (95800, 95999),  # Sleep studies, neurology
    ],
    # Medicine (90281-99607)
    "preventive": [
        (90460, 90474),  # Immunizations
        (96360, 96379),  # IV infusions
        (99381, 99397),  # Preventive medicine
    ],
    "mental_health": [
        (90785, 90899),  # Psychiatry
        (96101, 96155),  # Psychological testing
    ],
    "rehabilitation": [
        (97001, 97799),  # Physical therapy
        (97802, 97804),  # Medical nutrition
    ],
    "prescription": [
        (99605, 99607),  # Medication therapy management
    ],
    "maternity": [
        (59000, 59899),  # Maternity and delivery
    ],
}

# ICD-10 code prefixes mapped to categories
ICD10_CATEGORY_PREFIXES = {
    "outpatient": ["Z00", "Z01", "Z02"],  # General examination
    "inpatient": ["Z51"],  # Encounter for procedures
    "emergency": ["S", "T"],  # Injuries, poisoning
    "diagnostic": ["R"],  # Symptoms and signs
    "laboratory": ["Z01.1", "Z01.2", "Z01.3"],  # Lab encounters
    "radiology": ["Z01.0"],  # Imaging encounters
    "mental_health": ["F"],  # Mental disorders
    "maternity": ["O", "Z3"],  # Pregnancy, childbirth
    "preventive": ["Z23", "Z24", "Z25", "Z26", "Z27", "Z28"],  # Immunizations
}


def get_category_for_cpt(cpt_code: str) -> str | None:
    """Map a CPT code to a coverage category.

    Args:
        cpt_code: CPT procedure code (5-digit string)

    Returns:
        Coverage category string or None if not mapped
    """
    try:
        code_num = int(cpt_code)
    except (ValueError, TypeError):
        return None

    for category, ranges in CPT_CATEGORY_RANGES.items():
        for start, end in ranges:
            if start <= code_num <= end:
                return category

    return None


def get_category_for_icd10(icd_code: str) -> str | None:
    """Map an ICD-10 code to a coverage category.

    Args:
        icd_code: ICD-10 diagnosis code

    Returns:
        Coverage category string or None if not mapped
    """
    if not icd_code:
        return None

    icd_upper = icd_code.upper().strip()

    for category, prefixes in ICD10_CATEGORY_PREFIXES.items():
        for prefix in prefixes:
            if icd_upper.startswith(prefix):
                return category

    return None


def get_categories_for_codes(
    cpt_codes: list[str] | None = None,
    icd_codes: list[str] | None = None,
) -> list[str]:
    """Get all coverage categories for a set of medical codes.

    Args:
        cpt_codes: List of CPT procedure codes
        icd_codes: List of ICD-10 diagnosis codes

    Returns:
        List of unique coverage categories
    """
    categories = set()

    for code in (cpt_codes or []):
        cat = get_category_for_cpt(code)
        if cat:
            categories.add(cat)

    for code in (icd_codes or []):
        cat = get_category_for_icd10(code)
        if cat:
            categories.add(cat)

    return list(categories)


def get_category_keywords() -> dict[str, list[str]]:
    """Get keywords for detecting coverage categories in policy text.

    Used during policy ingestion to tag chunks with categories.

    Returns:
        Dict mapping category to list of keywords
    """
    return {
        "outpatient": [
            "outpatient", "office visit", "consultation", "clinic",
            "ambulatory", "day care", "doctor visit", "physician visit",
        ],
        "inpatient": [
            "inpatient", "hospitalization", "hospital stay", "admission",
            "room charges", "icu", "intensive care", "hospital room",
            "bed charges", "nursing care",
        ],
        "emergency": [
            "emergency", "accident", "urgent care", "trauma",
            "emergency room", "er visit", "ambulance",
        ],
        "diagnostic": [
            "diagnostic", "diagnosis", "test", "examination",
            "screening", "assessment", "evaluation",
        ],
        "laboratory": [
            "laboratory", "lab test", "blood test", "pathology",
            "urine test", "biopsy", "culture", "specimen",
        ],
        "radiology": [
            "radiology", "x-ray", "xray", "mri", "ct scan", "ultrasound",
            "imaging", "scan", "mammogram", "pet scan",
        ],
        "surgery": [
            "surgery", "surgical", "operation", "procedure",
            "anesthesia", "transplant", "implant",
        ],
        "prescription": [
            "prescription", "medication", "drug", "pharmacy",
            "medicine", "pharmaceutical", "formulary",
        ],
        "preventive": [
            "preventive", "prevention", "wellness", "vaccination",
            "immunization", "health checkup", "annual physical",
            "screening", "prophylactic",
        ],
        "mental_health": [
            "mental health", "psychiatric", "psychology", "counseling",
            "therapy", "behavioral health", "substance abuse",
            "addiction", "depression", "anxiety",
        ],
        "rehabilitation": [
            "rehabilitation", "physical therapy", "occupational therapy",
            "speech therapy", "rehab", "physiotherapy",
        ],
        "maternity": [
            "maternity", "pregnancy", "prenatal", "postnatal",
            "childbirth", "delivery", "obstetric", "newborn",
        ],
        "dental": [
            "dental", "dentist", "teeth", "oral", "orthodontic",
        ],
        "vision": [
            "vision", "eye", "optical", "ophthalmology", "optometry",
            "glasses", "contact lens",
        ],
    }


def detect_categories_in_text(text: str) -> list[str]:
    """Detect coverage categories mentioned in policy text.

    Used during policy ingestion to auto-tag chunks.

    Args:
        text: Policy document text

    Returns:
        List of detected category names
    """
    text_lower = text.lower()
    categories = set()

    for category, keywords in get_category_keywords().items():
        for keyword in keywords:
            if keyword in text_lower:
                categories.add(category)
                break  # One match per category is enough

    return list(categories)
