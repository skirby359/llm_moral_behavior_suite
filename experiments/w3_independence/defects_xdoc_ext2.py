"""Ground truth for the SECOND cross-document extension — 30 further defects.

The nine-document set finally put `claude-opus-5` below ceiling (49/52 on call 1,
gain 4.50 +/- 2.12 over k=8). But 49/52 is thin: the whole resampling curve had to be
measured in the last three defects, and the gain's sd of 2.12 on n=2 says the
magnitude is not pinned down.

This adds six documents, taking the set to **fifteen documents, 105 pairs and 82
seeded cross-document defects**:

    10_pricing.md                 Pricing and Rate Card (Schedule 7)
    11_acceptable_use.md          Acceptable Use Policy (Schedule 8)
    12_subprocessors.md           Approved Subprocessor List (Schedule 9)
    13_exhibit_a_acceptance.md    Deliverables and Acceptance Criteria (Exhibit A)
    14_exhibit_b_personnel.md     Key Personnel and Role Rates (Exhibit B)
    15_glossary.md                Glossary of Defined Terms (Schedule 10)

**The Glossary is the sharpest instrument here.** A document that redefines terms the
other fourteen already define makes a whole class of conflicts that cannot be found
without holding two definitions side by side — and it is realistic, because contract
sets accumulate glossaries exactly this way. Eight defects come from it alone,
including a *fourth* precedence claim and a definition of "Agreement" that resolves an
ambiguity the MSA left open, in the wrong direction.

Design rules unchanged from the earlier ground truths, and still load-bearing:

1. **Every defect spans two documents.** At least one is always a new document.
2. **Each document is internally consistent.** Exhibit B's rate table agrees with
   itself; the Pricing volume band and per-transaction rate are coherent.
3. **Fingerprints chosen at authoring time, checked unique across all fifteen
   documents** -- `13,100`, `1,450`, `1,100`, `Kestrel`, `Singapore`, `tokenisation`,
   `under 16`, `law enforcement`, `Material Defect`, `acceptance certificate`,
   `including public holidays`, `any output of the Services`.
4. **Not every cross-reference is broken.** Exhibit B cl. 5.1 points at vetting in the
   Information Security Policy, which genuinely exists at 06_infosec cl. 8.1; the
   Pricing rate card's deferral to Exhibit B (cl. 2.4) is honoured by Exhibit B cl. 3.
5. **Escalating multi-way conflicts are single defects.** The day rate is now
   £1,250 / £1,450 / £1,100 across three documents; service credits are capped at
   10% / 25% / 5% across three; "Business Day" has three definitions; "Security
   Incident" has three.
"""

from __future__ import annotations

DEFECTS_XDOC_EXT2 = [
    # ================================================================== 10 PRICING
    {
        "id": "Z01_fourth_monthly_charge",
        "grade": "obvious",
        "pair": "Pricing 1.1 vs MSA 4.1 / SOW 5.1 / Order Form 1.4",
        "desc": "A FOURTH monthly figure: £13,100 recurring, against the MSA's £12,400, "
                "the SOW's £12,800 and the Order Form's £153,600 a year",
        "rules": [[r"13[,.\s]?100"]],
    },
    {
        "id": "Z02_invoiced_in_advance",
        "grade": "obvious",
        "pair": "Pricing 1.2 vs MSA 4.3 / SOW 5.3",
        "desc": "Pricing invoices monthly IN ADVANCE; both the MSA and the SOW invoice "
                "monthly in arrears",
        "rules": [[r"in advance", r"(arrears|invoic|month)"]],
    },
    {
        "id": "Z03_rate_fixed_vs_cpi_increase",
        "grade": "medium",
        "pair": "Pricing 1.3 vs MSA 4.4",
        "desc": "Pricing fixes the recurring charge for the initial term with no "
                "indexation; MSA 4.4 lets Provider raise the Fee once in any 12 months "
                "in line with CPI",
        "rules": [
            [r"fixed for the initial term"],
            [r"(indexation|cpi|consumer prices)", r"(fixed|increase|not subject)"],
        ],
    },
    {
        "id": "Z04_day_rate_three_way",
        "grade": "obvious",
        "pair": "Pricing 2.1 vs Exit 3.2 vs Exhibit B 3",
        "desc": "The day rate is £1,450 standard (Pricing), £1,250 for transition "
                "assistance (Exit) and role-dependent £950-£1,450 (Exhibit B)",
        "rules": [[r"1[,.\s]?450"]],
    },
    {
        "id": "Z05_service_credit_cap_three_way",
        "grade": "obvious",
        "pair": "Pricing 4.2 vs SLA 4.2 vs SOW 7.4",
        "desc": "Service credits are capped at 5% (Pricing), 10% (SLA) and 25% (SOW) of "
                "the monthly charge",
        "rules": [[r"(5|five)\s*(per cent|percent|%)", r"credit"]],
    },
    {
        "id": "Z06_credit_base_differs",
        "grade": "subtle",
        "pair": "Pricing 4.2 vs SLA 4.2",
        "desc": "Pricing caps credits against the RECURRING CHARGE (£13,100) while the "
                "SLA caps them against the monthly FEE, which the MSA defines as "
                "£12,400 — the same percentage yields different money",
        "rules": [[r"(recurring (monthly )?charge|recurring invoice)", r"(fee|credit|cap)"]],
    },
    {
        "id": "Z07_invoice_query_window",
        "grade": "subtle",
        "pair": "Pricing 6.3 vs MSA 4.3 / Order Form 1.6",
        "desc": "Queries must be raised within 10 Business Days, but payment falls due "
                "in 30 days (MSA) or 60 (Order Form) — and only UNDISPUTED invoices are "
                "payable, so the dispute window closes long before payment is due",
        "rules": [[r"(quer|disput)", r"(10|ten)", r"business day"]],
    },
    # ============================================================ 11 ACCEPTABLE USE
    {
        "id": "Z08_immediate_suspension_vs_cure_period",
        "grade": "obvious",
        "pair": "AUP 5.1 vs MSA 3.4",
        "desc": "The AUP allows immediate suspension without notice on a reasonable "
                "belief of breach; MSA 3.4 gives 15 days to remedy a material breach",
        "rules": [
            [r"suspend the services immediately"],
            [r"(suspend|suspension)", r"(without (prior )?notice|immediat)", r"(15|fifteen|cure|remedy)"],
        ],
    },
    {
        "id": "Z09_no_monitoring_vs_continuous_monitoring",
        "grade": "medium",
        "pair": "AUP 4.1 vs InfoSec 5.3",
        "desc": "The AUP says Provider does not monitor content; the Information "
                "Security Policy says Provider operates continuous monitoring for "
                "anomalous access",
        "rules": [
            [r"does not monitor"],
            [r"monitor", r"(continuous|anomalous)"],
        ],
    },
    {
        "id": "Z10_under_16_vs_retail_customers",
        "grade": "subtle",
        "pair": "AUP 3.1 vs DPA 3.2",
        "desc": "The AUP forbids storing personal data of anyone under 16; the DPA "
                "declares the data subjects to be Customer's retail customers, with no "
                "age exclusion anywhere",
        "rules": [[r"under 16|under sixteen"]],
    },
    {
        "id": "Z11_card_data_prohibited_but_tokenised",
        "grade": "medium",
        "pair": "AUP 3.2 vs Subprocessors 2 / InfoSec 1.2",
        "desc": "The AUP forbids storing payment card numbers, yet a payment "
                "tokenisation subprocessor is engaged and InfoSec classes payment card "
                "data as Restricted Data held on the platform",
        "rules": [[r"tokenisation|tokenization"], [r"payment card", r"(prohibit|forbid|not store|conflict)"]],
    },
    {
        "id": "Z12_law_enforcement_disclosure",
        "grade": "obvious",
        "pair": "AUP 6.1-6.2 vs DPA 2.2 / 6.3",
        "desc": "The AUP lets Provider disclose Customer content to law enforcement "
                "without notifying Customer; the DPA permits processing only on "
                "Customer's documented instructions",
        "rules": [[r"law enforcement"]],
    },
    {
        "id": "Z13_unilateral_policy_amendment",
        "grade": "medium",
        "pair": "AUP 8.1 vs MSA 2.4 / Change Control",
        "desc": "Provider may amend the AUP unilaterally on 30 days' notice, with "
                "continued use deemed acceptance; MSA 2.4 requires changes to be agreed "
                "in writing by both parties",
        "rules": [[r"(amend|change)", r"(this policy|the policy)", r"(30|thirty)"]],
    },
    # ============================================================= 12 SUBPROCESSORS
    {
        "id": "Z14_singapore_subprocessor",
        "grade": "obvious",
        "pair": "Subprocessors 2 vs DPA 4.1",
        "desc": "Kestrel Analytics Pte Ltd processes in Singapore, outside the UK and "
                "EEA, which DPA 4.1 forbids without prior written authorisation",
        "rules": [[r"singapore"], [r"kestrel"]],
    },
    {
        "id": "Z15_objection_right_vs_prior_consent",
        "grade": "obvious",
        "pair": "Subprocessors 3.1-3.2 vs DPA 5.1",
        "desc": "New Subprocessors may be added on 30 days' notice with a right to "
                "object; DPA 5.1 requires Customer's prior written CONSENT to each one",
        "rules": [
            [r"right to object"],
            [r"(object|notice)", r"(prior written consent|consent to that specific)"],
        ],
    },
    {
        "id": "Z16_immediate_replacement_no_consent",
        "grade": "medium",
        "pair": "Subprocessors 3.4 vs DPA 5.1",
        "desc": "Provider may replace a Subprocessor immediately with notice afterwards "
                "where needed for security or continuity — no consent, and no carve-out "
                "for this in the DPA",
        "rules": [[r"(replace|substitut)", r"immediat", r"(subprocessor|sub-processor)"]],
    },
    {
        "id": "Z17_annex_2_identity_collision",
        "grade": "subtle",
        "pair": "Subprocessors header vs DPA 4.3 / Annex 2",
        "desc": "This Schedule declares itself 'Annex 2 to the Data Processing "
                "Addendum', but the DPA's Annex 2 is the approved processing LOCATIONS "
                "list — two different documents claim the same annex",
        "rules": [
            [r"annex 2", r"(subprocessor|sub-processor|two different|collision|same annex|location)"],
        ],
    },
    {
        "id": "Z18_transfer_mechanism_scope",
        "grade": "subtle",
        "pair": "Subprocessors 5.1 vs DPA 4.1",
        "desc": "Transfer safeguards are required only where a Subprocessor is outside "
                "the UNITED KINGDOM; the DPA's restriction is the UK *and* the EEA, so "
                "an EEA subprocessor falls through the gap",
        # `gap` unanchored matched inside "Sin-GAP-ore", so the Singapore exemplar
        # claimed this defect too. Word-bounded now. Same class of bug as the
        # unanchored `45` in defects_xdoc.py: a short alternative is a substring
        # match unless you say otherwise.
        "rules": [
            [r"outside the united kingdom"],
            [r"(uk|united kingdom)", r"eea", r"(\bgap\b|\bonly\b|narrower|inconsist)"],
        ],
    },
    # ======================================================= 13 EXHIBIT A ACCEPTANCE
    {
        "id": "Z19_acceptance_criteria_location",
        "grade": "medium",
        "pair": "Exhibit A 1.2 vs MSA 6.2",
        "desc": "Exhibit A declares itself the SOLE source of acceptance criteria, "
                "while MSA 6.2 directs Customer to criteria 'in Schedule 1, Section 12'",
        "rules": [[r"(exhibit a|sole source)", r"acceptance criteria"]],
    },
    {
        "id": "Z20_acceptance_certificate_vs_deemed",
        "grade": "obvious",
        "pair": "Exhibit A 5.2-5.3 vs SOW 6.3",
        "desc": "Exhibit A requires a signed acceptance certificate within 15 Business "
                "Days and says silence is not acceptance; SOW 6.3 deems a Deliverable "
                "accepted after 5 Business Days of silence",
        "rules": [
            [r"acceptance certificate"],
            [r"silence", r"(not|does not) constitute acceptance"],
        ],
    },
    {
        "id": "Z21_two_sources_of_deliverables",
        "grade": "medium",
        "pair": "Exhibit A 2 vs SOW 6.1",
        "desc": "Exhibit A lists seven named Deliverables; SOW 6.1 says the Deliverables "
                "are whatever is in the phase plan maintained by Provider's delivery "
                "lead — two sources of truth",
        "rules": [[r"phase plan", r"(exhibit a|seven|d1|listed|two source)"]],
    },
    {
        "id": "Z22_material_defect_vs_priority_1",
        "grade": "subtle",
        "pair": "Exhibit A 4.1 vs SLA 1.3",
        "desc": "Exhibit A grades defects as Material / Minor; the SLA grades incidents "
                "Priority 1-3 with a different threshold. Nothing maps one to the other",
        "rules": [[r"material defect"]],
    },
    {
        "id": "Z23_warranty_period_conflict",
        "grade": "obvious",
        "pair": "Exhibit A 7.1 vs MSA 8.2",
        "desc": "Exhibit A warrants Deliverables for 180 days from acceptance; MSA 8.2 "
                "warrants them for 90 days",
        "rules": [[r"(180|one hundred and eighty)"]],
    },
    # ======================================================== 14 EXHIBIT B PERSONNEL
    {
        "id": "Z24_substitution_notice_vs_prior_agreement",
        "grade": "obvious",
        "pair": "Exhibit B 2.1 vs SOW 3.5",
        "desc": "Exhibit B allows substitution of Key Personnel on 10 Business Days' "
                "notice; SOW 3.5 forbids substituting named key personnel without "
                "Customer's prior written agreement",
        "rules": [[r"substitut", r"(10|ten)", r"(business day|notice)"]],
    },
    {
        "id": "Z25_delivery_lead_location",
        "grade": "medium",
        "pair": "Exhibit B 1 vs SOW 3.4",
        "desc": "Exhibit B bases the Delivery Lead and Lead Solution Architect in "
                "London; SOW 3.4 states the delivery team operates from Bengaluru",
        "rules": [[r"london", r"(bengaluru|delivery lead|based)"]],
    },
    {
        "id": "Z26_engineer_rate_vs_standard_rate",
        "grade": "medium",
        "pair": "Exhibit B 3 vs Pricing 2.1",
        "desc": "Exhibit B prices Engineers at £1,100 and Business Analysts at £950; "
                "Pricing 2.1 states a standard rate of £1,450 for every role",
        "rules": [[r"1[,.\s]?100"], [r"\b950\b"]],
    },
    {
        "id": "Z27_key_personnel_count",
        "grade": "subtle",
        "pair": "Exhibit B 1 vs SOW 3.1-3.2",
        "desc": "Exhibit B names four Key Personnel roles including a Second Solution "
                "Architect and Test Lead; the SOW's eleven-person team has one delivery "
                "lead, two architects, six engineers, one test lead and one BA, and does "
                "not identify which are 'key'",
        "rules": [[r"key personnel", r"(four|11|eleven|team|does not|which)"]],
    },
    # ================================================================= 15 GLOSSARY
    {
        "id": "Z28_glossary_precedence_fourth_claim",
        "grade": "obvious",
        "pair": "Glossary 1.2 vs MSA 14.2 / SOW 1.2 / Order Form 2.2",
        "desc": "A FOURTH precedence claim: Glossary definitions prevail over the same "
                "term defined anywhere else, on top of the MSA, SOW and Order Form each "
                "claiming primacy",
        "rules": [
            [r"(glossary|definitions in this)", r"prevail"],
            [r"(fourth|four)", r"(preceden|prevail)"],
        ],
    },
    {
        "id": "Z29_glossary_business_day_third_definition",
        "grade": "obvious",
        "pair": "Glossary vs MSA 1.2 vs SLA 1.1",
        "desc": "A THIRD 'Business Day': Mon-Fri INCLUDING public holidays (Glossary), "
                "Mon-Fri excluding England and Wales holidays (MSA), Mon-Sat excluding "
                "US federal holidays (SLA)",
        "rules": [[r"including public holidays"]],
    },
    {
        "id": "Z30_glossary_agreement_includes_order_form",
        "grade": "subtle",
        "pair": "Glossary vs MSA 1.1 / 1.6",
        "desc": "The Glossary's 'Agreement' expressly includes the Order Form; MSA 1.1 "
                "defines it as the MSA plus Schedules and Addenda, and the Order Form is "
                "neither on MSA 1.6's definition — so the two documents disagree about "
                "what the contract even consists of",
        "rules": [
            [r"agreement", r"order form", r"(includ|part of|definition|1\.1)"],
        ],
    },
    {
        "id": "Z31_glossary_deliverable_any_output",
        "grade": "medium",
        "pair": "Glossary vs MSA 1.3 / Exhibit A 2",
        "desc": "The Glossary defines 'Deliverable' as ANY output of the Services "
                "whether or not identified as one; MSA 1.3 requires identification in a "
                "Statement of Work. With MSA 7.2 assigning IP in Deliverables, the "
                "broader definition silently transfers far more IP",
        "rules": [[r"any output of the services"]],
    },
    {
        "id": "Z32_glossary_fee_includes_expenses",
        "grade": "medium",
        "pair": "Glossary vs MSA 1.4 / SOW 5.4 / Pricing 3",
        "desc": "The Glossary's 'Fee' includes expenses; SOW 5.4 and Pricing 3 treat "
                "expenses as reimbursed outside the Fee, and the liability cap in MSA "
                "13.1 is measured in Fees",
        "rules": [[r"fee", r"(includ|including)", r"expense"]],
    },
    {
        "id": "Z33_glossary_security_incident_third_definition",
        "grade": "obvious",
        "pair": "Glossary vs DPA 1.6 vs SLA 7.1",
        "desc": "A THIRD 'Security Incident': any event affecting confidentiality, "
                "integrity or availability (Glossary), any unauthorised access to "
                "personal data (DPA), confirmed access causing loss (SLA)",
        "rules": [[r"confidentiality, integrity"]],
    },
    {
        "id": "Z34_glossary_personal_data_uk_only",
        "grade": "subtle",
        "pair": "Glossary vs DPA 1.2 / 13.2",
        "desc": "The Glossary defines Personal Data by reference to the UK GDPR alone, "
                "while the DPA's Data Protection Law covers every territory where the "
                "Services are provided and the DPA is governed by Irish law",
        "rules": [[r"uk (general data protection|gdpr)"]],
    },
    {
        "id": "Z35_glossary_services_includes_support",
        "grade": "subtle",
        "pair": "Glossary vs MSA 1.5",
        "desc": "The Glossary's 'Services' includes the support services in the SLA; MSA "
                "1.5 limits Services to what a Statement of Work describes, which "
                "changes what the SOW's inclusive-Fee and liability provisions cover",
        "rules": [[r"services", r"(support services|service level and support)", r"(includ|together with|definition)"]],
    },
]
