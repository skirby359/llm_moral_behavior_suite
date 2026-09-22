"""Verify the FIFTEEN-document corpus and its matcher before spending.

Runs the same checks as the earlier verifiers over the whole 87-defect set:

1. **A rule that matches nothing** — recall understated, corpus looks harder than it
   is. Guarded by a hand-written exemplar per new defect, phrased as a reviewer would
   phrase it and deliberately NOT copied from the `desc` field.
2. **A rule that matches everything** — cross-talk inflates recall. Each exemplar must
   match its own defect and only declared overlaps.
3. **A defect not actually written into the documents** — ground truth asserting a
   contradiction nobody drafted. Fingerprint presence per file, whitespace-normalised
   because the documents are wrapped prose.
4. **README treated as a corpus document** — it holds the conflict map. Globbing
   `*.md` once put an answer key straight into a model's prompt.
5. **Duplicate defect ids** across the three ground truths.

Run:
    python experiments/w3_independence/corpus_xdoc_ext2/verify_corpus_ext2.py
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
CORE = EXP / "corpus_xdoc"
EXT1 = EXP / "corpus_xdoc_ext"
sys.path.insert(0, str(EXP))

from defects_xdoc import DEFECTS_XDOC  # noqa: E402
from defects_xdoc_ext import DEFECTS_XDOC_EXT  # noqa: E402
from defects_xdoc_ext2 import DEFECTS_XDOC_EXT2  # noqa: E402

ALL_DEFECTS = list(DEFECTS_XDOC) + list(DEFECTS_XDOC_EXT) + list(DEFECTS_XDOC_EXT2)

EXEMPLARS = {
    "Z01_fourth_monthly_charge":
        "The pricing schedule states a recurring monthly charge of 13,100, a fourth "
        "figure alongside the MSA, SOW and Order Form.",
    "Z02_invoiced_in_advance":
        "The pricing schedule invoices monthly in advance while the MSA and SOW both "
        "invoice monthly in arrears.",
    "Z03_rate_fixed_vs_cpi_increase":
        "Charges are fixed for the initial term with no indexation, but the MSA permits "
        "a CPI increase once a year.",
    "Z04_day_rate_three_way":
        "The standard day rate is 1,450 in the pricing schedule but transition "
        "assistance is charged at a different rate in the exit plan.",
    "Z05_service_credit_cap_three_way":
        "Service credits are capped at five per cent of the monthly charge here, but "
        "at ten per cent in the SLA and twenty-five in the SOW.",
    "Z06_credit_base_differs":
        "Credits are capped against the recurring charge in pricing but against the "
        "Fee in the SLA, so the same percentage yields a different amount.",
    "Z07_invoice_query_window":
        "Invoice queries must be raised within 10 Business Days although payment is not "
        "due for 30 or 60 days, so the dispute window closes before payment falls due.",
    "Z08_immediate_suspension_vs_cure_period":
        "The acceptable use policy permits Provider to suspend the Services immediately "
        "without notice, but the MSA gives fifteen days to remedy a material breach.",
    "Z09_no_monitoring_vs_continuous_monitoring":
        "The acceptable use policy states Provider does not monitor content while the "
        "security policy commits to continuous monitoring.",
    "Z10_under_16_vs_retail_customers":
        "Personal data of anyone under 16 is prohibited, but the DPA names retail "
        "customers as data subjects with no age exclusion.",
    "Z11_card_data_prohibited_but_tokenised":
        "Storing payment card numbers is prohibited yet a payment tokenisation "
        "subprocessor is engaged.",
    "Z12_law_enforcement_disclosure":
        "Provider may disclose Customer content to law enforcement without telling "
        "Customer, contradicting the DPA's documented-instructions rule.",
    "Z13_unilateral_policy_amendment":
        "Provider may amend the policy unilaterally on 30 days notice with continued "
        "use deemed acceptance, but the MSA requires changes agreed in writing.",
    "Z14_singapore_subprocessor":
        "A subprocessor processes in Singapore, outside the UK and EEA that the DPA "
        "restricts processing to.",
    "Z15_objection_right_vs_prior_consent":
        "New subprocessors may be added with only a right to object, whereas the DPA "
        "requires prior written consent to that specific subprocessor.",
    "Z16_immediate_replacement_no_consent":
        "A subprocessor may be replaced immediately with notice afterwards, with no "
        "consent at all.",
    "Z17_annex_2_identity_collision":
        "This schedule calls itself Annex 2 to the Data Processing Addendum, but the "
        "DPA's Annex 2 is the approved processing location list.",
    "Z18_transfer_mechanism_scope":
        "Transfer safeguards are required only for subprocessors outside the United "
        "Kingdom, a narrower trigger than the DPA's UK and EEA restriction.",
    "Z19_acceptance_criteria_location":
        "Exhibit A declares itself the sole source of acceptance criteria while the MSA "
        "points elsewhere for the acceptance criteria.",
    "Z20_acceptance_certificate_vs_deemed":
        "Acceptance requires a signed acceptance certificate and silence does not "
        "constitute acceptance, but the SOW deems deliverables accepted after five days.",
    "Z21_two_sources_of_deliverables":
        "Deliverables are listed in Exhibit A but the SOW says they are whatever is in "
        "the phase plan kept by the delivery lead.",
    "Z22_material_defect_vs_priority_1":
        "A Material Defect is defined here but the SLA uses a separate Priority 1 to 3 "
        "severity scheme and nothing maps between them.",
    "Z23_warranty_period_conflict":
        "Deliverables are warranted for 180 days from acceptance here but for ninety "
        "days in the MSA.",
    "Z24_substitution_notice_vs_prior_agreement":
        "Key personnel may be substituted on 10 Business Days notice, but the SOW "
        "forbids substitution without Customer's prior written agreement.",
    "Z25_delivery_lead_location":
        "The Delivery Lead is based in London here while the SOW places the delivery "
        "team in Bengaluru.",
    "Z26_engineer_rate_vs_standard_rate":
        "Engineers are charged at 1,100 per day, but the pricing schedule states a "
        "single standard rate for every role.",
    "Z27_key_personnel_count":
        "Four key personnel roles are named here whereas the SOW commits an eleven "
        "person team and never says which are key.",
    "Z28_glossary_precedence_fourth_claim":
        "The glossary states its definitions prevail over the same term elsewhere, a "
        "fourth document claiming precedence.",
    "Z29_glossary_business_day_third_definition":
        "Business Day is defined as Monday to Friday including public holidays here, a "
        "third and different definition.",
    "Z30_glossary_agreement_includes_order_form":
        "The glossary says the Agreement includes the Order Form, but the MSA's own "
        "definition covers only schedules and addenda.",
    "Z31_glossary_deliverable_any_output":
        "Deliverable is defined as any output of the Services, far broader than the "
        "MSA's definition, which matters because IP in Deliverables is assigned.",
    "Z32_glossary_fee_includes_expenses":
        "The glossary's Fee includes expenses, while the SOW and pricing schedule treat "
        "expenses as reimbursed outside the Fee.",
    "Z33_glossary_security_incident_third_definition":
        "Security Incident is defined as any event affecting confidentiality, integrity "
        "or availability, a third definition of the term.",
    "Z34_glossary_personal_data_uk_only":
        "Personal Data is defined by reference to the UK GDPR alone although the DPA is "
        "governed by Irish law and covers every territory served.",
    "Z35_glossary_services_includes_support":
        "The glossary's Services includes the support services, together with what a "
        "statement of work describes, which is broader than the MSA definition.",
}

FINGERPRINTS = {
    "Z01_fourth_monthly_charge": [("10_pricing.md", "13,100")],
    "Z02_invoiced_in_advance": [("10_pricing.md", "monthly in advance")],
    "Z03_rate_fixed_vs_cpi_increase": [("10_pricing.md", "fixed for the initial term")],
    "Z04_day_rate_three_way": [("10_pricing.md", "1,450")],
    "Z05_service_credit_cap_three_way": [("10_pricing.md", "five per cent (5%)")],
    "Z06_credit_base_differs": [("10_pricing.md", "recurring monthly charge")],
    "Z07_invoice_query_window": [("10_pricing.md", "ten (10) Business Days")],
    "Z08_immediate_suspension_vs_cure_period":
        [("11_acceptable_use.md", "suspend the Services immediately")],
    "Z09_no_monitoring_vs_continuous_monitoring":
        [("11_acceptable_use.md", "does not monitor")],
    "Z10_under_16_vs_retail_customers": [("11_acceptable_use.md", "under 16")],
    "Z11_card_data_prohibited_but_tokenised":
        [("11_acceptable_use.md", "payment card"), ("12_subprocessors.md", "tokenisation")],
    "Z12_law_enforcement_disclosure": [("11_acceptable_use.md", "law enforcement")],
    "Z13_unilateral_policy_amendment": [("11_acceptable_use.md", "amend this Policy")],
    "Z14_singapore_subprocessor": [("12_subprocessors.md", "Singapore")],
    "Z15_objection_right_vs_prior_consent": [("12_subprocessors.md", "right to object")],
    "Z16_immediate_replacement_no_consent":
        [("12_subprocessors.md", "replace a Subprocessor immediately")],
    "Z17_annex_2_identity_collision":
        [("12_subprocessors.md", "Annex 2 to the Data Processing Addendum")],
    "Z18_transfer_mechanism_scope":
        [("12_subprocessors.md", "outside the United Kingdom")],
    "Z19_acceptance_criteria_location":
        [("13_exhibit_a_acceptance.md", "sole source of the acceptance criteria")],
    "Z20_acceptance_certificate_vs_deemed":
        [("13_exhibit_a_acceptance.md", "acceptance certificate")],
    "Z21_two_sources_of_deliverables": [("13_exhibit_a_acceptance.md", "Deliverable")],
    "Z22_material_defect_vs_priority_1":
        [("13_exhibit_a_acceptance.md", "Material Defect")],
    "Z23_warranty_period_conflict":
        [("13_exhibit_a_acceptance.md", "one hundred and eighty (180) days")],
    "Z24_substitution_notice_vs_prior_agreement":
        [("14_exhibit_b_personnel.md", "ten (10) Business Days")],
    "Z25_delivery_lead_location": [("14_exhibit_b_personnel.md", "London")],
    "Z26_engineer_rate_vs_standard_rate": [("14_exhibit_b_personnel.md", "1,100")],
    "Z27_key_personnel_count": [("14_exhibit_b_personnel.md", "Key Personnel")],
    "Z28_glossary_precedence_fourth_claim":
        [("15_glossary.md", "definitions in this Glossary prevail")],
    "Z29_glossary_business_day_third_definition":
        [("15_glossary.md", "including public holidays")],
    "Z30_glossary_agreement_includes_order_form": [("15_glossary.md", "the Order Form")],
    "Z31_glossary_deliverable_any_output":
        [("15_glossary.md", "any output of the Services")],
    "Z32_glossary_fee_includes_expenses": [("15_glossary.md", "including recurring")],
    "Z33_glossary_security_incident_third_definition":
        [("15_glossary.md", "confidentiality, integrity")],
    "Z34_glossary_personal_data_uk_only":
        [("15_glossary.md", "UK General Data Protection Regulation")],
    "Z35_glossary_services_includes_support":
        [("15_glossary.md", "support services described in the Service Level")],
}

# Legitimate overlaps. Multi-way conflicts subsume their two-way ancestors BY
# CONSTRUCTION -- a finding about a 5%/10%/25% credit cap genuinely is the 10%/25%
# defect too -- so those are declared rather than engineered away.
ALLOWED_CROSSTALK = {
    ("Z01_fourth_monthly_charge", "X01_monthly_fee"),
    ("Z01_fourth_monthly_charge", "E02_annual_contract_value"),
    ("Z02_invoiced_in_advance", "X20_payment_terms"),
    ("Z03_rate_fixed_vs_cpi_increase", "E22_change_charges_bypass_notice"),
    ("Z04_day_rate_three_way", "E25_transition_charges_vs_inclusive_fee"),
    ("Z05_service_credit_cap_three_way", "X14_service_credit_cap"),
    ("Z05_service_credit_cap_three_way", "X13_availability_target"),
    ("Z06_credit_base_differs", "X14_service_credit_cap"),
    ("Z06_credit_base_differs", "X15_automatic_credit_vs_no_setoff"),
    ("Z06_credit_base_differs", "E22_change_charges_bypass_notice"),
    ("Z07_invoice_query_window", "X20_payment_terms"),
    ("Z07_invoice_query_window", "E03_payment_terms_three_way"),
    ("Z08_immediate_suspension_vs_cure_period", "E17_sla_suspended_in_continuity_event"),
    ("Z09_no_monitoring_vs_continuous_monitoring", "E10_review_cadence"),
    ("Z11_card_data_prohibited_but_tokenised", "E08_restricted_data_scope"),
    ("Z13_unilateral_policy_amendment", "E15_rpo_tolerates_data_loss"),
    # "continued use deemed acceptance" genuinely touches the deemed-vs-express
    # acceptance theme; the overlap is real rather than an artefact.
    ("Z13_unilateral_policy_amendment", "X23_deemed_vs_express_acceptance"),
    ("Z14_singapore_subprocessor", "X21_processing_location"),
    ("Z14_singapore_subprocessor", "E09_any_provider_region"),
    ("Z15_objection_right_vs_prior_consent", "X10_subprocessor_consent"),
    ("Z16_immediate_replacement_no_consent", "X10_subprocessor_consent"),
    ("Z17_annex_2_identity_collision", "X18_dead_xref_to_dpa_annex"),
    ("Z17_annex_2_identity_collision", "X21_processing_location"),
    ("Z18_transfer_mechanism_scope", "X21_processing_location"),
    ("Z18_transfer_mechanism_scope", "E09_any_provider_region"),
    ("Z19_acceptance_criteria_location", "X17_dead_xref_to_sow"),
    ("Z19_acceptance_criteria_location", "X23_deemed_vs_express_acceptance"),
    ("Z20_acceptance_certificate_vs_deemed", "X23_deemed_vs_express_acceptance"),
    ("Z20_acceptance_certificate_vs_deemed", "E20_deemed_approved_change"),
    ("Z21_two_sources_of_deliverables", "X23_deemed_vs_express_acceptance"),
    ("Z23_warranty_period_conflict", "X03_termination_notice"),
    ("Z24_substitution_notice_vs_prior_agreement", "E24_exit_retention_vs_dpa_deletion"),
    ("Z25_delivery_lead_location", "X21_processing_location"),
    ("Z26_engineer_rate_vs_standard_rate", "Z04_day_rate_three_way"),
    ("Z27_key_personnel_count", "E01_initial_term_three_way"),
    ("Z28_glossary_precedence_fourth_claim", "X04_circular_precedence"),
    ("Z28_glossary_precedence_fourth_claim", "E04_order_form_precedence"),
    ("Z29_glossary_business_day_third_definition", "X05_business_day_definition"),
    ("Z30_glossary_agreement_includes_order_form", "E04_order_form_precedence"),
    ("Z31_glossary_deliverable_any_output", "X23_deemed_vs_express_acceptance"),
    ("Z32_glossary_fee_includes_expenses", "E25_transition_charges_vs_inclusive_fee"),
    ("Z33_glossary_security_incident_third_definition", "X07_security_incident_definition"),
    ("Z34_glossary_personal_data_uk_only", "X16_governing_law"),
    ("Z35_glossary_services_includes_support", "E06_service_level_start"),
}


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def match_ids(text: str) -> set[str]:
    low = text.lower()
    return {
        d["id"]
        for d in ALL_DEFECTS
        if any(all(re.search(p, low) for p in rule) for rule in d["rules"])
    }


def main() -> int:
    failures = 0
    ids = [d["id"] for d in ALL_DEFECTS]
    docs = (sorted(CORE.glob("[0-9][0-9]_*.md"))
            + sorted(EXT1.glob("[0-9][0-9]_*.md"))
            + sorted(HERE.glob("[0-9][0-9]_*.md")))

    print(f"{len(ids)} seeded cross-document defects "
          f"({len(DEFECTS_XDOC)} + {len(DEFECTS_XDOC_EXT)} + {len(DEFECTS_XDOC_EXT2)})")
    print(f"{len(docs)} documents, {len(docs) * (len(docs) - 1) // 2} document pairs\n")

    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        print(f"DUPLICATE ids across the three ground truths: {dupes}")
        failures += 1

    new_ids = [d["id"] for d in DEFECTS_XDOC_EXT2]
    for missing, what in ((set(new_ids) - set(EXEMPLARS), "EXEMPLAR"),
                          (set(new_ids) - set(FINGERPRINTS), "FINGERPRINT CHECK")):
        if missing:
            print(f"NO {what} for: {sorted(missing)}")
            failures += 1

    for defect_id, text in EXEMPLARS.items():
        hits = match_ids(text)
        if defect_id not in hits:
            print(f"  MISS  {defect_id}: its own exemplar does not match its rules")
            print(f"        {text}")
            failures += 1
        extra = {h for h in hits - {defect_id} if (defect_id, h) not in ALLOWED_CROSSTALK}
        if extra:
            print(f"  CROSSTALK  {defect_id} also matched {sorted(extra)}")
            failures += 1

    for defect_id, expectations in FINGERPRINTS.items():
        for filename, needle in expectations:
            path = HERE / filename
            if not path.exists():
                print(f"  MISSING FILE  {filename} (for {defect_id})")
                failures += 1
                continue
            if _flat(needle) not in _flat(path.read_text(encoding="utf-8")):
                print(f"  ABSENT  {defect_id}: {needle!r} not in {filename}")
                failures += 1

    for d in (CORE, EXT1, HERE):
        leaked = [p.name for p in d.glob("*.md") if p not in docs]
        if leaked:
            print(f"not a corpus document in {d.name}/ (never send to a model): {leaked}")
    if any(p.name.startswith("README") for p in docs):
        print("  README IS BEING TREATED AS A CORPUS DOCUMENT -- it is the answer key")
        failures += 1

    chars = sum(len(p.read_text(encoding="utf-8")) for p in docs)
    print(f"\ncorpus: {chars:,} chars across {len(docs)} documents")
    for p in docs:
        print(f"    {p.parent.name}/{p.name}")

    print()
    print("15-DOCUMENT CORPUS VERIFIED" if not failures else f"{failures} PROBLEM(S) FOUND")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
