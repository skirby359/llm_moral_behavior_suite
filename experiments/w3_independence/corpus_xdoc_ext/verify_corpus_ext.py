"""Verify the EXTENDED cross-document corpus and its matcher before spending.

Same three checks as `../corpus_xdoc/verify_corpus.py`, run over the combined
nine-document set and all 52 defects:

1. **A rule that matches nothing** — recall understated, corpus looks harder than it
   is. Guarded by a hand-written exemplar finding per defect, phrased as a reviewer
   would phrase it and deliberately NOT copied from the `desc` field.
2. **A rule that matches everything** — cross-talk inflates recall. Each exemplar must
   match its own defect and only declared overlaps.
3. **A defect not actually written into the documents** — ground truth asserting a
   contradiction nobody drafted. Guarded by fingerprint presence checks per file,
   whitespace-normalised because the documents are wrapped prose.

Plus two the four-document version learned the hard way:

4. **README.md must never be treated as a corpus document** — it contains the conflict
   map. Globbing `*.md` once put the answer key straight into a model's prompt.
5. **Duplicate defect ids across the two ground truths**, which would silently
   over- or under-count.

Run:
    python experiments/w3_independence/corpus_xdoc_ext/verify_corpus_ext.py
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
CORE = EXP / "corpus_xdoc"
sys.path.insert(0, str(EXP))

from defects_xdoc import DEFECTS_XDOC  # noqa: E402
from defects_xdoc_ext import DEFECTS_XDOC_EXT  # noqa: E402

ALL_DEFECTS = list(DEFECTS_XDOC) + list(DEFECTS_XDOC_EXT)

# How a competent reviewer would phrase each of the 28 new findings.
EXEMPLARS = {
    "E01_initial_term_three_way":
        "The initial term is stated as 12 months in the Order Form but 24 months in "
        "the MSA, and the SOW describes a 36 month programme.",
    "E02_annual_contract_value":
        "The Order Form's annual contract value of 153,600 does not match the MSA's "
        "monthly fee, which would give 148,800 per year.",
    "E03_payment_terms_three_way":
        "Payment terms conflict three ways: 60 days in the Order Form, 30 days in the "
        "MSA and 45 days in the SOW.",
    "E04_order_form_precedence":
        "The Order Form states that it prevails over all other documents, which "
        "conflicts with the MSA's own precedence clause and the SOW's.",
    "E05_support_hours":
        "The Order Form promises 24x7 support for all priorities but the SLA restricts "
        "Priority 2 and 3 support to business hours.",
    "E06_service_level_start":
        "Service levels apply from the commencement date under the Order Form but only "
        "from Phase 3 under the SOW.",
    "E07_non_renewal_notice":
        "Non-renewal requires 30 days notice under the Order Form while the MSA "
        "requires 90 days to terminate.",
    "E08_restricted_data_scope":
        "Employee compensation data is treated as Restricted Data by the security "
        "policy but does not appear in the categories of personal data declared in the "
        "DPA.",
    "E09_any_provider_region":
        "The security policy allows storage in any Provider region, but the DPA limits "
        "processing to the UK and EEA and lists only two approved locations.",
    "E10_review_cadence":
        "The security policy requires a quarterly access review while the DPA only "
        "requires an annual review of security measures.",
    "E11_log_retention":
        "Security logs are deleted after 18 months but the MSA requires records to be "
        "retained for seven years.",
    "E12_incident_notice_three_way":
        "Incident notification windows conflict: 48 hours in the security policy, 24 "
        "hours in the DPA and 72 hours in the SLA.",
    "E13_penetration_test_sharing":
        "The security policy promises to share the annual penetration test report, but "
        "the MSA excludes any Customer right to inspect Provider systems.",
    "E14_rto_vs_sla_resolution":
        "The recovery time objective of 8 hours is inconsistent with the SLA's "
        "requirement to resolve a Priority 1 incident within 4 hours.",
    "E15_rpo_tolerates_data_loss":
        "A recovery point objective of 24 hours accepts up to a day of data loss, "
        "which the DPA would classify as a Security Incident.",
    "E16_frankfurt_recovery_site":
        "The disaster recovery environment is in Frankfurt, which is not one of the "
        "approved processing locations listed in the DPA annex.",
    "E17_sla_suspended_in_continuity_event":
        "The continuity plan suspends all SLA obligations during a Continuity Event, "
        "but the SLA's exclusions do not cover this.",
    "E18_planned_unavailability_excluded":
        "Up to 12 hours of planned unavailability on returning to the primary "
        "environment is excluded from availability, but the SLA excludes only agreed "
        "maintenance windows.",
    "E19_dead_xref_msa_clause_17":
        "The change procedure refers to a Change Control Board in clause 17 of the MSA, "
        "which does not exist.",
    "E20_deemed_approved_change":
        "A change is deemed approved after ten business days of silence, but the MSA "
        "requires changes to be agreed in writing by both parties first.",
    "E21_delivery_lead_change_authority":
        "The Delivery Lead may unilaterally approve changes costing up to 35,000, which "
        "the MSA's written agreement requirement does not allow.",
    "E22_change_charges_bypass_notice":
        "Change-related charges take effect on the next invoice and are exempt from the "
        "usual notice period, contradicting the MSA's limit of one increase per year on "
        "60 days notice.",
    "E23_escalation_path_conflict":
        "The escalation path runs through the Programme Director and CIO, but the SOW "
        "specifies account director then executive sponsor.",
    "E24_exit_retention_vs_dpa_deletion":
        "The exit plan retains all Customer data for 90 days after termination while "
        "the DPA requires deletion within 30 days.",
    "E25_transition_charges_vs_inclusive_fee":
        "Transition assistance is charged at 1,250 per day although the SOW states the "
        "fee covers all personnel unless stated otherwise.",
    "E26_data_return_format":
        "Data is returned in the format used by Provider's systems, whereas the DPA "
        "requires a structured, commonly used format.",
    "E27_source_code_vs_ip_retention":
        "The exit plan requires handover of source code, but the MSA reserves "
        "Provider's pre-existing tools and assigns deliverable IP only on full payment.",
    "E28_dead_xref_dpa_clause_14":
        "The exit plan points to clause 14 of the Data Processing Addendum, but that "
        "addendum ends at clause 13.",
}

# Fingerprints that must actually be present, per file.
FINGERPRINTS = {
    "E01_initial_term_three_way": [("05_order_form.md", "Initial Term: 12 months")],
    "E02_annual_contract_value": [("05_order_form.md", "153,600")],
    "E03_payment_terms_three_way": [("05_order_form.md", "sixty (60) days")],
    "E04_order_form_precedence": [("05_order_form.md", "this Order Form prevails")],
    "E05_support_hours": [("05_order_form.md", "24x7")],
    "E06_service_level_start": [("05_order_form.md", "Service Commencement Date")],
    "E07_non_renewal_notice": [("05_order_form.md", "non-renewal")],
    "E08_restricted_data_scope": [("06_infosec.md", "employee compensation data")],
    "E09_any_provider_region": [("06_infosec.md", "any Provider region")],
    "E10_review_cadence": [("06_infosec.md", "quarterly access review")],
    "E11_log_retention": [("06_infosec.md", "eighteen (18) months")],
    "E12_incident_notice_three_way": [("06_infosec.md", "forty-eight (48) hours")],
    "E13_penetration_test_sharing": [("06_infosec.md", "penetration test")],
    "E14_rto_vs_sla_resolution": [("07_bcdr.md", "eight (8) hours")],
    "E15_rpo_tolerates_data_loss": [("07_bcdr.md", "Recovery Point Objective")],
    "E16_frankfurt_recovery_site": [("07_bcdr.md", "Frankfurt")],
    "E17_sla_suspended_in_continuity_event": [("07_bcdr.md", "are suspended")],
    "E18_planned_unavailability_excluded": [("07_bcdr.md", "twelve (12) hours")],
    "E19_dead_xref_msa_clause_17": [("08_change_control.md", "clause 17")],
    "E20_deemed_approved_change": [("08_change_control.md", "deemed approved")],
    "E21_delivery_lead_change_authority": [("08_change_control.md", "35,000")],
    "E22_change_charges_bypass_notice": [("08_change_control.md", "invoice next issued")],
    "E23_escalation_path_conflict": [("08_change_control.md", "Programme Director")],
    "E24_exit_retention_vs_dpa_deletion": [("09_exit.md", "ninety (90) days following")],
    "E25_transition_charges_vs_inclusive_fee": [("09_exit.md", "1,250")],
    "E26_data_return_format": [("09_exit.md", "format used by Provider")],
    "E27_source_code_vs_ip_retention": [("09_exit.md", "source code")],
    "E28_dead_xref_dpa_clause_14": [("09_exit.md", "clause 14")],
}

# Legitimate vocabulary overlaps, declared rather than tolerated silently. The
# three-way conflicts overlap with their two-way counterparts in the original
# corpus BY CONSTRUCTION -- a finding about 30/45/60-day payment terms genuinely
# is the 30/45 defect as well.
ALLOWED_CROSSTALK = {
    ("E01_initial_term_three_way", "X02_term_length"),
    ("E01_initial_term_three_way", "X03_termination_notice"),
    ("E02_annual_contract_value", "X01_monthly_fee"),
    ("E03_payment_terms_three_way", "X03_termination_notice"),
    ("E03_payment_terms_three_way", "X20_payment_terms"),
    ("E04_order_form_precedence", "X04_circular_precedence"),
    ("E06_service_level_start", "X13_availability_target"),
    ("E07_non_renewal_notice", "X03_termination_notice"),
    ("E08_restricted_data_scope", "X06_confidential_information_definition"),
    ("E09_any_provider_region", "X21_processing_location"),
    ("E11_log_retention", "X09_retain_vs_delete"),
    ("E12_incident_notice_three_way", "X08_incident_notice_window"),
    ("E13_penetration_test_sharing", "X22_audit_rights"),
    ("E14_rto_vs_sla_resolution", "X13_availability_target"),
    ("E15_rpo_tolerates_data_loss", "X07_security_incident_definition"),
    ("E16_frankfurt_recovery_site", "X21_processing_location"),
    ("E17_sla_suspended_in_continuity_event", "X13_availability_target"),
    ("E18_planned_unavailability_excluded", "X13_availability_target"),
    ("E20_deemed_approved_change", "X23_deemed_vs_express_acceptance"),
    ("E22_change_charges_bypass_notice", "X15_automatic_credit_vs_no_setoff"),
    ("E23_escalation_path_conflict", "X23_deemed_vs_express_acceptance"),
    ("E24_exit_retention_vs_dpa_deletion", "X03_termination_notice"),
    ("E24_exit_retention_vs_dpa_deletion", "X09_retain_vs_delete"),
    ("E26_data_return_format", "X09_retain_vs_delete"),
}


def _flat(text: str) -> str:
    """Lowercase, whitespace collapsed — the documents are wrapped prose, so a
    fingerprint phrase can straddle a newline."""
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
    core_docs = sorted(CORE.glob("[0-9][0-9]_*.md"))
    ext_docs = sorted(HERE.glob("[0-9][0-9]_*.md"))
    docs = core_docs + ext_docs

    print(f"{len(ids)} seeded cross-document defects "
          f"({len(DEFECTS_XDOC)} core + {len(DEFECTS_XDOC_EXT)} extension)")
    print(f"{len(docs)} documents, {len(docs) * (len(docs) - 1) // 2} document pairs\n")

    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        print(f"DUPLICATE ids across the two ground truths: {dupes}")
        failures += 1

    missing = [i for i in (d["id"] for d in DEFECTS_XDOC_EXT) if i not in EXEMPLARS]
    if missing:
        print(f"NO EXEMPLAR for: {missing}")
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

    missing_fp = [i for i in (d["id"] for d in DEFECTS_XDOC_EXT) if i not in FINGERPRINTS]
    if missing_fp:
        print(f"NO FINGERPRINT CHECK for: {missing_fp}")
        failures += 1

    # The answer-key guard. corpus_xdoc/README.md holds the conflict map; globbing
    # "*.md" once put it into a model's prompt and produced a fake 24/24.
    for d in (CORE, HERE):
        leaked = [p.name for p in d.glob("*.md") if p not in docs]
        print(f"not part of the corpus in {d.name}/ (must never be sent to a model): "
              f"{leaked}")
        if any(p.name.startswith("README") for p in docs):
            print("  README IS BEING TREATED AS A CORPUS DOCUMENT -- it is the answer key")
            failures += 1

    chars = sum(len(p.read_text(encoding="utf-8")) for p in docs)
    print(f"\ncorpus: {chars:,} chars across {len(docs)} documents")
    print(f"  core: {', '.join(p.name for p in core_docs)}")
    print(f"  ext:  {', '.join(p.name for p in ext_docs)}")

    print()
    print("EXTENDED CORPUS VERIFIED" if not failures else f"{failures} PROBLEM(S) FOUND")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
