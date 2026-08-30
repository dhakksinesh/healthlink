
import logging
import re

from app.security import mask_pii
from shared.schemas import HealthSummary

logger = logging.getLogger("healthlink.guardrails")




_DEFINITIVE_DIAGNOSIS_PATTERNS = [
    r"\byou (have|are (suffering from|diagnosed with))\b",
    r"\bthis (is|indicates) (a case of|that you have)\b",
    r"\bconfident(ly)? (diagnos|that you have)\b",
    r"\bdefinitive(ly)?\b.*\b(diagnos|condition)\b",
    r"\byour condition is\b",
]


_HARMFUL_PATTERNS = [
    r"\bdon['']?t (see|consult|visit) (a|the) doctor\b",
    r"\bstop taking your medication\b",
    r"\bself[- ]harm\b",
]


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b(?:\+?\d[\s-]?){9,15}\b")

def scan_text(text: str) -> list[str]:

    flags: list[str] = []

    if not text:
        return flags

    for pattern in _DEFINITIVE_DIAGNOSIS_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append("definitive_diagnosis_claim")
            break

    for pattern in _HARMFUL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            flags.append("harmful_advice")
            break

    if _EMAIL_RE.search(text) or _PHONE_RE.search(text):
        flags.append("pii_exposure")

    return flags

def soften_text(text: str) -> str:

    text = re.sub(
        r"\byou have\b", "your symptoms may be consistent with", text, flags=re.IGNORECASE
    )
    text = re.sub(
        r"\byou are (suffering from|diagnosed with)\b",
        "your symptoms may suggest",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\byour condition is\b", "your condition may be", text, flags=re.IGNORECASE
    )
    text = re.sub(
        r"\bthis (is|indicates) (a case of|that you have)\b",
        "this may be consistent with",
        text,
        flags=re.IGNORECASE,
    )
    return text

def scan_summary(summary: HealthSummary) -> list[str]:

    fields = [summary.summary, *summary.key_findings, *summary.recommended_actions]
    flags: list[str] = []
    for text in fields:
        flags.extend(scan_text(text))

    if not summary.disclaimer:
        flags.append("missing_disclaimer")

    return list(dict.fromkeys(flags))

def apply_guardrails(summary: HealthSummary) -> HealthSummary:

    flags = scan_summary(summary)

    if "definitive_diagnosis_claim" in flags:
        summary.summary = soften_text(summary.summary)
        summary.key_findings = [soften_text(f) for f in summary.key_findings]
        summary.recommended_actions = [soften_text(a) for a in summary.recommended_actions]
        logger.info("Guardrail: softened definitive-diagnosis language in summary")

    if "harmful_advice" in flags:
        summary.recommended_actions = [
            a for a in summary.recommended_actions if not any(
                re.search(p, a, re.IGNORECASE) for p in _HARMFUL_PATTERNS
            )
        ]
        logger.warning("Guardrail: removed harmful-advice phrasing from summary")

    if "pii_exposure" in flags:
        summary.summary = mask_pii(summary.summary)
        summary.key_findings = [mask_pii(f) for f in summary.key_findings]
        logger.warning("Guardrail: masked PII found in generated summary")

    if "missing_disclaimer" in flags:
        summary.disclaimer = (
            "This is not a medical diagnosis. Please consult with healthcare "
            "professionals for medical advice."
        )

    return summary
