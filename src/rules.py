import re
_PATTERNS = {
    "must_refuse_off_label": re.compile(r"\boff-?label\b|\bnot (?:approved|indicated)\b|\bcannot discuss\b", re.I),
    "mention_labeling_source": re.compile(r"\bEMA\b|\bEPAR\b|\bSmPC\b|\blabel(ing)?\b", re.I),
    "avoid_unverified_claims": re.compile(r"\bI (?:won't|cannot|can’t) (?:quote|provide) (?:numbers|efficacy)\b|\bnot from memory\b", re.I),
    "ask_prior_lines": re.compile(r"\bprior (?:line|therapy|treatment)s?\b|\bendocrine\b|\bCDK4/6\b", re.I),
    "asks_for_patient_factors": re.compile(r"\bECOG\b|\bperformance status\b|\bvisceral\b|\bcomorbid", re.I),
    "consider_qol": re.compile(r"\bquality of life\b|\bQoL\b|\btoxicit(y|ies)\b|\badverse (events?|effects?)\b", re.I),
    "be_concise": re.compile(r".{0,400}$", re.S),
    "redirect_to_relevant": re.compile(r"\bfocus\b|\brelevant\b|\bkey (facts|details)\b|\bwhat matters\b", re.I),
    "set_expectations": re.compile(r"\btime\b|\bfollow-?up\b|\bbrief\b|\bschedule\b|\b10-?minute\b", re.I),
    "define_next_step": re.compile(r"\bMDT\b|\btumou?r board\b|\bfollow-?up\b|\bschedule\b|\bchecklist\b|\bpayer\b|\bcriteria\b", re.I),
}
def apply_rules(text: str, expected_rules: list[str]) -> dict:
    text = (text or "").strip()
    return {r: bool(_PATTERNS.get(r, re.compile("$")).search(text)) for r in expected_rules}
