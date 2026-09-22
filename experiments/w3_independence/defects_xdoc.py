"""Ground truth for `corpus_xdoc/` — 24 CROSS-DOCUMENT defects.

Why this corpus exists
----------------------
`document_long.md` (20 seeded defects) failed to create headroom against
`claude-opus-5`: 20/20 on the first call in all five repeats, so resampling could
not be measured there. The overnight conclusion was that the honest fix was a much
longer document — tens of pages — where attention cannot cover everything.

This takes a different route to the same goal. **Length is not the only thing that
outruns a single pass; combinatorics is.** Each defect here is a contradiction
between TWO of four documents, so finding them requires holding pairs in mind at
once. Four documents give 6 pairs; the work grows quadratically in corpus size
while the token count grows linearly. A model can read every document attentively
and still miss a conflict, because no single document is wrong.

Design rules, all deliberate:

1. **Every seeded defect is cross-document.** No defect can be found by reading one
   document in isolation. That is what makes this a different test rather than a
   longer one.
2. **Each document is internally consistent.** Phase durations sum to the stated
   programme length; the team roster sums to the stated headcount. So a
   single-document reading yields nothing, and any within-document finding is
   either a genuine bonus or matcher noise — counted and dumped either way.
3. **Distinctive fingerprints, chosen at authoring time, not fitted to output.**
   Each defect anchors on a number or term appearing nowhere else in the corpus
   (`Bengaluru`, `set-off`, `Annex 3`, `£250,000`, `99.9%`, `Saturday`). This is the
   methodological improvement `defects_long.py` introduced and it is kept.
4. **Both sides of a numeric conflict are accepted.** A model may report the clash
   from either document's point of view.

`rules` semantics are identical to run_w3.py and defects_long.py: a finding matches
when every regex in ANY ONE inner list hits the lowercased finding text.

Documents: 01_msa.md (MSA), 02_sow.md (SOW / Schedule 1), 03_dpa.md (DPA),
04_sla.md (SLA / Schedule 2).
"""

from __future__ import annotations

DEFECTS_XDOC = [
    # ------------------------------------------------------------------ obvious
    # Bare numeric clashes with unique fingerprints. Easy IF both documents are
    # being held at once, invisible otherwise.
    {
        "id": "X01_monthly_fee",
        "grade": "obvious",
        "pair": "MSA 4.1 vs SOW 5.1",
        "desc": "MSA sets the monthly Fee at GBP 12,400; SOW sets it at GBP 12,800",
        "rules": [[r"12[,.\s]?400"], [r"12[,.\s]?800"]],
    },
    {
        "id": "X02_term_length",
        "grade": "obvious",
        "pair": "MSA 3.1 vs SOW 2.1",
        "desc": "MSA initial term is 24 months; the SOW programme it governs runs 36 months",
        "rules": [[r"(36|thirty-six)", r"(month|term|programme|program)"]],
    },
    {
        "id": "X03_termination_notice",
        "grade": "obvious",
        "pair": "MSA 3.3 vs SOW 2.3",
        "desc": "Convenience-termination notice is 90 days in the MSA and 30 days in the SOW",
        "rules": [[r"(90|ninety|30|thirty)", r"(terminat|notice period|convenience)"]],
    },
    {
        "id": "X08_incident_notice_window",
        "grade": "obvious",
        "pair": "DPA 6.1 vs SLA 7.3",
        "desc": "Security Incident notification is within 24 hours (DPA) and 72 hours (SLA)",
        "rules": [[r"(72|seventy-two)"]],
    },
    {
        "id": "X11_liability_cap",
        "grade": "obvious",
        "pair": "MSA 13.1 vs SOW 9.2",
        "desc": "Liability cap is 12 months' fees in the MSA and a fixed GBP 250,000 in the SOW",
        "rules": [[r"250[,.\s]?000"]],
    },
    {
        "id": "X13_availability_target",
        "grade": "obvious",
        "pair": "SLA 3.1 vs SOW 7.2",
        "desc": "Monthly availability target is 99.9% in the SLA and 99.5% in the SOW",
        "rules": [[r"99\.9"], [r"99\.5", r"(99\.9|conflict|differ|inconsist)"]],
    },
    {
        "id": "X14_service_credit_cap",
        "grade": "obvious",
        "pair": "SLA 4.2 vs SOW 7.4",
        "desc": "Service credits are capped at 10% of the monthly Fee (SLA) and 25% (SOW)",
        "rules": [[r"(25|twenty-five)\s*(per cent|percent|%)"], [r"credit", r"(10%|ten per cent)"]],
    },
    {
        "id": "X20_payment_terms",
        "grade": "obvious",
        "pair": "MSA 4.3 vs SOW 5.3",
        "desc": "Payment terms are 30 days in the MSA and 45 days in the SOW",
        # ANCHORED 2026-08-04. This was `(45|forty-five)` with no word boundary, so it
        # matched the "45" inside any longer number -- caught when the 15-document
        # corpus introduced a £1,450 day rate and this rule claimed it. Harmless on the
        # 4- and 9-document corpora (verified by re-deriving their stored findings with
        # the anchored rule: no figure moved), but wrong, and the class of bug is worth
        # naming: a bare two-digit alternative is a substring match, not a number match.
        "rules": [[r"\b(45|forty-five)\b"]],
    },
    {
        "id": "X24_insurance_limit",
        "grade": "obvious",
        "pair": "MSA 16.1 vs SOW 9.4",
        "desc": "Professional indemnity cover is GBP 5,000,000 (MSA) and GBP 2,000,000 (SOW)",
        "rules": [[r"(5[,.\s]?000[,.\s]?000|2[,.\s]?000[,.\s]?000)", r"(insur|indemnity cover|professional indemnity)"]],
    },
    # ------------------------------------------------------------------- medium
    # Definitional and referential clashes. Require noticing that a term is
    # defined twice, in different documents, differently.
    {
        "id": "X05_business_day_definition",
        "grade": "medium",
        "pair": "MSA 1.2 vs SLA 1.1",
        "desc": "'Business Day' is Mon-Fri / England and Wales holidays (MSA) and "
                "Mon-Sat / US federal holidays (SLA)",
        "rules": [[r"saturday"], [r"business day", r"(us federal|united states federal)"]],
    },
    {
        "id": "X06_confidential_information_definition",
        "grade": "medium",
        "pair": "MSA 11.1 vs DPA 1.4",
        "desc": "MSA requires Confidential Information to be marked in writing; the DPA "
                "makes all Customer Personal Data confidential whether or not marked",
        "rules": [[r"whether or not marked"], [r"confidential", r"(marked|marking)"]],
    },
    {
        "id": "X07_security_incident_definition",
        "grade": "medium",
        "pair": "DPA 1.6 vs SLA 7.1",
        "desc": "'Security Incident' is any unauthorised access (DPA) but only CONFIRMED "
                "access causing loss or corruption (SLA) — the SLA definition is narrower",
        "rules": [[r"security incident", r"(defin|confirmed|narrow|broader|two different|inconsist|conflict)"]],
    },
    {
        "id": "X10_subprocessor_consent",
        "grade": "medium",
        "pair": "MSA 9.3 vs DPA 5.1",
        "desc": "MSA permits subcontracting without consent; DPA requires prior written "
                "consent to each Subprocessor",
        "rules": [[r"(subprocessor|sub-processor|subcontract)", r"consent"]],
    },
    {
        "id": "X16_governing_law",
        "grade": "medium",
        "pair": "MSA 15.1 vs DPA 13.2",
        "desc": "MSA is governed by England and Wales; the DPA specifies the Republic of Ireland",
        "rules": [[r"republic of ireland"], [r"governing law", r"(ireland|irish)"]],
    },
    {
        "id": "X17_dead_xref_to_sow",
        "grade": "medium",
        "pair": "MSA 6.2 vs SOW (ends at s.10)",
        "desc": "MSA 6.2 points to acceptance criteria in 'Schedule 1, Section 12'; the SOW "
                "ends at Section 10",
        "rules": [[r"section 12"]],
    },
    {
        "id": "X18_dead_xref_to_dpa_annex",
        "grade": "medium",
        "pair": "SLA 7.4 vs DPA (Annexes 1-2)",
        "desc": "SLA 7.4 points to 'Annex 3' of the DPA; the DPA has only Annexes 1 and 2",
        "rules": [[r"annex 3"]],
    },
    {
        "id": "X19_start_date_precedes_msa",
        "grade": "medium",
        "pair": "MSA Effective Date vs SOW 2.2",
        "desc": "The SOW programme commences 1 March 2027, a month BEFORE the MSA's "
                "1 April 2027 Effective Date under which the SOW is issued",
        "rules": [[r"(1 march 2027|march 2027|1 april 2027|april 2027)", r"(commenc|effective date|before|precede|start)"]],
    },
    {
        "id": "X21_processing_location",
        "grade": "medium",
        "pair": "DPA 4.1/Annex 2 vs SOW 3.4",
        "desc": "DPA restricts processing to the UK and EEA and lists only London and Dublin; "
                "the SOW places the delivery team in Bengaluru, India",
        "rules": [[r"bengaluru"], [r"(india|outside the (uk|eea))", r"(process|transfer|location)"]],
    },
    # ------------------------------------------------------------------- subtle
    # Structural conflicts: each document is coherent, the pair is not resolvable.
    {
        "id": "X04_circular_precedence",
        "grade": "subtle",
        "pair": "MSA 14.2 vs SOW 1.2",
        "desc": "MSA 14.2 says the MSA prevails over any Schedule; SOW 1.2 says the SOW "
                "prevails over the MSA. Precedence is circular and unresolvable",
        "rules": [[r"(prevail|preceden|takes priority|order of priority)",
                   r"(circular|conflict|contradict|inconsist|both|each other|mutual)"]],
    },
    {
        "id": "X09_retain_vs_delete",
        "grade": "subtle",
        "pair": "MSA 12.4 vs DPA 8.2",
        "desc": "MSA requires all records and data to be retained for 7 years after "
                "termination; DPA requires all Customer Personal Data deleted within 30 days",
        "rules": [[r"(seven \(7\) years|7 years|seven years)"],
                  [r"(delet|destroy)", r"(retain|retention)"]],
    },
    {
        "id": "X12_liability_carveout_collision",
        "grade": "subtle",
        "pair": "MSA 13.3 vs DPA 11.1",
        "desc": "DPA 11.1 disapplies every liability limit in the Agreement for data "
                "protection breaches; MSA 13.3 applies the cap notwithstanding any other "
                "provision of any Addendum. Each purports to override the other",
        "rules": [[r"notwithstanding"],
                  [r"(cap|limit)", r"(data protection|dpa|addendum)", r"(override|conflict|contradict|disappl)"]],
    },
    {
        "id": "X15_automatic_credit_vs_no_setoff",
        "grade": "subtle",
        "pair": "MSA 4.5 vs SLA 4.1",
        "desc": "SLA 4.1 requires service credits to be applied automatically to the next "
                "invoice; MSA 4.5 forbids any deduction or set-off without Provider's "
                "written agreement",
        "rules": [[r"set-?off"], [r"credit", r"(deduct|withhold)", r"(invoice|payment)"]],
    },
    {
        "id": "X22_audit_rights",
        "grade": "subtle",
        "pair": "MSA 10.2 vs DPA 9.1",
        "desc": "MSA 10.2 gives Customer no audit right beyond receiving a SOC 2 report; "
                "DPA 9.1 grants an annual on-site audit including inspection of systems",
        "rules": [[r"soc ?2"], [r"audit", r"(no further|no right|conflict|contradict|inconsist)"]],
    },
    {
        "id": "X23_deemed_vs_express_acceptance",
        "grade": "subtle",
        "pair": "MSA 6.1 vs SOW 6.3",
        "desc": "MSA 6.1 requires express written acceptance of every Deliverable; SOW 6.3 "
                "deems a Deliverable accepted after five Business Days of silence",
        "rules": [[r"deemed accept"], [r"accept", r"(express|in writing|silence|no response)"]],
    },
]
