import re

_PATTERNS = {
    # Compliance
    "must_refuse_off_label": re.compile(r"\boff-?label\b|\bnot (?:approved|indicated)\b|\b(can'?t|cannot) discuss\b", re.I),
    "mention_labeling_source": re.compile(r"\bEMA\b|\bEPAR\b|\bSmPC\b|\blabel(?:ing)?\b", re.I),
    "label_citation": re.compile(r"\bEMA\b|\bEPAR\b|\bSmPC\b|\blabel(?:ing)?\b", re.I),
    "avoid_unverified_claims": re.compile(r"\bI (?:won'?t|can'?t|cannot) (?:quote|provide) (?:numbers|efficacy)\b|\bnot from memory\b", re.I),

    # Clinical realism
    "ask_prior_lines": re.compile(r"\bprior (?:line|therapy|treatment)s?\b|\bendocrine\b|\bCDK4/6\b", re.I),
    "asks_for_patient_factors": re.compile(r"\bECOG\b|\bperformance status\b|\bPS\b|\bvisceral\b|\bcomorbid", re.I),
    "consider_qol": re.compile(r"\bquality of life\b|\bQoL\b|\btoxicit(y|ies)\b|\badverse (events?|effects?)\b", re.I),
    "monitoring_supportive_care": re.compile(r"\bmonitor(?:ing)?\b|\bCBC\b|\bLFTs?\b|\bsupportive care\b|\bpre-?med|\bantiemetic", re.I),
    "sequencing_endocrine_bias": re.compile(r"\bendocrine\b.*\b(sequence|first|before)\b|\bprefer\b.*\bendocrine\b|ADC.*\b(uncertain|hesitan)", re.I),
    "evidence_uncertainty": re.compile(r"\b(on-?label profile|depends|context|consider|uncertain|uncertainty)\b", re.I),

    # Experience
    "brevity_80w": re.compile(r"^(?:\W*\w+\W+){0,80}\w+\W*$", re.S),
    "redirect_to_relevant": re.compile(r"\b(focus|relevant|what matters|keep this brief|on-?label)\b", re.I),
    "set_expectations": re.compile(r"\b(time|brief|schedule|follow-?up|10-?minute)\b", re.I),

    # Sales training
    "define_next_step": re.compile(r"\b(MDT|tumou?r board|follow-?up|schedule|checklist|payer)\b", re.I),
    "one_next_step": re.compile(r"\b(MDT|tumou?r board|payer|checklist|follow-?up)\b", re.I),
}

def apply_rules(text: str, expected_rules: list[str]) -> dict:
    text = (text or "").strip()
    out = {}
    for r in expected_rules:
        pat = _PATTERNS.get(r)
        out[r] = bool(pat.search(text)) if pat else False
    return out
