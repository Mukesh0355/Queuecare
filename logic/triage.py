"""
Keyword triage for QueueCare.

This is NOT a diagnosis. It only scans the symptom text so that
true emergencies jump the clinic queue in the demo.
"""

# Longer phrases first so "shortness of breath" is preferred over a shorter overlap.
EMERGENCY_KEYWORDS = [
    "shortness of breath",
    "cannot breathe",
    "can't breathe",
    "cant breathe",
    "severe bleeding",
    "heart attack",
    "chest pain",
    "breathlessness",
    "unconscious",
    "stroke",
    "seizure",
    "सीने में दर्द",
    "सांस लेने में तकलीफ",
    "बेहोश",
    "दौरा",
    "நெஞ்சு வலி",
    "மூச்சு திணறல்",
    "மயக்கம்",
    "வலிப்பு",
]

URGENT_KEYWORDS = [
    "high fever",
    "severe pain",
    "dehydration",
    "fracture",
    "vomiting",
]


def triage(symptoms_text) -> dict:
    """
    Classify free-text symptoms.

    Returns:
        {"level": "emergency"|"urgent"|"routine", "matched": keyword or None}
    """
    text = (symptoms_text or "").lower()

    for keyword in EMERGENCY_KEYWORDS:
        if keyword in text:
            return {"level": "emergency", "matched": keyword}

    for keyword in URGENT_KEYWORDS:
        if keyword in text:
            return {"level": "urgent", "matched": keyword}

    return {"level": "routine", "matched": None}
