"""Ground truth for `document_long.md` — 20 seeded defects.

Purpose: `document.md` has 8 defects and `claude-opus-5` scores 8/8 on a single
call, so it is a ceiling that cannot discriminate resampling behaviour on a
frontier model (see FINDINGS.md, "the ground truth was a ceiling"). This document
is ~5x longer with 20 defects, giving headroom for partial recall — and it tests
the standing caveat that a 30-line document may suppress the differential
attention a long corpus would produce.

Matcher design: every defect is given a DISTINCTIVE FINGERPRINT — a number or term
that appears nowhere else in the document — so `rules` can anchor on it with
minimal cross-talk. Fingerprints were chosen at authoring time, not fitted to
model output, which is the main methodological improvement over the 8-defect set.

`rules` semantics are identical to run_w3.py: a finding matches when every regex
in ANY ONE inner list hits the lowercased finding text.
"""

from __future__ import annotations

DEFECTS_LONG = [
    # ---------------------------------------------------------------- obvious
    {
        "id": "L01_annual_fee_arithmetic",
        "grade": "obvious",
        "desc": "3.3 says annual Fee $58,000 'representing twelve monthly payments'; "
                "12 x $4,750 = $57,000",
        "rules": [[r"(58,?000|57,?000)"]],
    },
    {
        "id": "L02_uptime_arithmetic",
        "grade": "obvious",
        "desc": "5.3 equates 99.5% monthly availability with 'no more than 3 hours' "
                "downtime; 0.5% of a 30-day month is ~3.6 hours",
        "rules": [[r"(99\.5|three \(3\) hours|3 hours|3\.6)", r"(availab|uptime|downtime|unavail)"]],
    },
    {
        "id": "L03_appendix_a_total",
        "grade": "obvious",
        "desc": "Appendix A line items total $4,690 but 3.2 states a monthly Fee of $4,750",
        "rules": [[r"(4,?690)"]],
    },
    # ----------------------------------------------------------------- medium
    {
        "id": "L04_dead_section_ref",
        "grade": "medium",
        "desc": "2.4 refers to a change control procedure in Section 9; document ends at Section 8",
        "rules": [[r"(section 9|sec\.? ?9|§ ?9)"]],
    },
    {
        "id": "L05_dead_appendix_ref",
        "grade": "medium",
        "desc": "4.6 refers to Appendix C; only Appendices A and B exist",
        "rules": [[r"appendix c"]],
    },
    {
        "id": "L06_circular_confidential",
        "grade": "medium",
        "desc": "1.3 defines Confidential Information as information that is confidential",
        "rules": [[
            r"(confidential information|\b1\.3\b)",
            r"(circular|tautolog|defines? itself|self-referential|no (real|substantive) definition|vacuous|meaningless)",
        ]],
    },
    {
        "id": "L07_payment_term_contradiction",
        "grade": "medium",
        "desc": "3.5 gives 45 days for invoices over $10,000; 3.6 says the 30-day term "
                "applies to all invoices without exception",
        "rules": [[
            r"(forty-five|45|3\.5|3\.6)",
            r"(contradict|conflict|inconsist|without exception|no exception|irreconcil|incompat)",
        ]],
    },
    {
        "id": "L08_breach_notice_conflict",
        "grade": "medium",
        "desc": "4.5 requires notification within 72 hours; 4.7 requires it within "
                "3 Business Days — different and potentially much longer deadlines",
        "rules": [[
            r"(72|seventy-two|three \(3\) business days|3 business days)",
            r"(contradict|conflict|inconsist|differ|two different|incompat|longer)",
        ]],
    },
    {
        "id": "L09_governing_law_venue",
        "grade": "medium",
        "desc": "8.3 makes the Agreement governed by Washington law; 8.4 gives Delaware "
                "courts exclusive jurisdiction applying Delaware law",
        "rules": [[r"(washington|delaware)", r"(governing law|jurisdiction|venue|conflict|contradict|inconsist)"]],
    },
    {
        "id": "L10_undefined_data_steward",
        "grade": "medium",
        "desc": "4.4 assigns record-keeping duties to 'the Data Steward', a role never "
                "defined or allocated to either party",
        "rules": [[r"data steward"]],
    },
    {
        "id": "L11_undefined_restricted_data",
        "grade": "medium",
        "desc": "4.2 restricts transfer of 'Restricted Data'; the term is never defined "
                "(Section 1 defines Personal Data, not Restricted Data)",
        "rules": [[r"restricted data"]],
    },
    {
        "id": "L12_undefined_territory",
        "grade": "medium",
        "desc": "'Territory' is load-bearing in 1.5 and 4.2 but never defined",
        "rules": [[r"territory"]],
    },
    # ----------------------------------------------------------------- subtle
    {
        "id": "L13_undefined_effective_date",
        "grade": "subtle",
        "desc": "The Agreement takes effect on the 'Effective Date', never defined; 6.1 "
                "defers to the prior MSA's definition while 8.1 supersedes that MSA, and "
                "8.1 separately fixes 1 January 2027 — circular and conflicting",
        "rules": [
            [r"effective date", r"(undefined|not defined|never defined|no definition|circular|supersed)"],
            [r"(prior master services|prior msa)", r"(supersed|circular|conflict|contradict)"],
        ],
    },
    {
        "id": "L14_unreachable_credit_tier",
        "grade": "subtle",
        "desc": "5.4 offers a 25% service credit below 95% availability, but 5.5 caps "
                "aggregate monthly credits at 10% — the 25% tier can never be paid",
        "rules": [[r"(25%|25 percent)", r"(cap|10%|exceed|unreachable|never|cannot|illusory|meaningless)"]],
    },
    {
        "id": "L15_liability_cap_contradiction",
        "grade": "subtle",
        "desc": "7.3 disapplies the liability cap for negligent Security Incidents while "
                "7.4 says the cap applies notwithstanding any other provision",
        "rules": [[r"(7\.3|7\.4|notwithstanding)", r"(contradict|conflict|inconsist|circular|cancel|negat|irreconcil)"]],
    },
    {
        "id": "L16_survival_omits_liability",
        "grade": "subtle",
        "desc": "7.5 states Section 7 survives termination; 6.6 lists surviving sections "
                "as 1, 4 and 8 only — omitting 7",
        "rules": [[r"(6\.6|7\.5|surviv)", r"(omit|contradict|conflict|inconsist|does not (include|list)|missing|exclud)"]],
    },
    {
        "id": "L17_notice_period_conflict",
        "grade": "subtle",
        "desc": "6.4 permits immediate termination for uncured material breach while 6.5 "
                "says the 60-day notice period may not be shortened",
        "rules": [[r"(6\.4|6\.5|immediat|shorten)", r"(contradict|conflict|inconsist|irreconcil|incompat|override)"]],
    },
    {
        "id": "L18_business_hours_vs_hours",
        "grade": "subtle",
        "desc": "5.2 promises response within 4 Business Hours; Appendix A item A-3 "
                "describes the same tier as '4 hour response' — different obligations",
        "rules": [[r"(business hours|a-3|4 hour)", r"(differ|inconsist|conflict|contradict|calendar|ambig|not the same)"]],
    },
    {
        "id": "L19_reserved_line_item",
        "grade": "subtle",
        "desc": "Appendix A item A-5 is 'Reserved' with no description or charge, yet 2.1 "
                "defines scope by reference to the Appendix A list",
        "rules": [[r"(reserved|a-5)"]],
    },
    {
        "id": "L20_unused_subprocessor_definition",
        "grade": "subtle",
        "desc": "1.7 defines 'Permitted Subprocessor' but the term is never used; 4.8 "
                "addresses subprocessors without reference to the defined term",
        "rules": [[
            r"(permitted subprocessor|\b1\.7\b)",
            r"(never used|not used|unused|no.{0,12}reference|orphan|redundant|superfluous|4\.8)",
        ]],
    },
]

assert len({d["id"] for d in DEFECTS_LONG}) == len(DEFECTS_LONG), "duplicate defect id"
