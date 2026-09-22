"""Verify the cross-document corpus and its matcher before spending on a run.

Three failure modes this catches, all of which would masquerade as results:

1. **A rule that matches nothing.** Recall would be understated and the corpus
   would look harder than it is. Checked with a hand-written exemplar finding per
   defect: the phrasing a competent reviewer would actually use.
2. **A rule that matches everything.** Cross-talk inflates recall. Each exemplar is
   required to match its OWN defect and no more than a declared handful of others.
3. **A defect not actually present in the corpus.** Ground truth claiming a
   contradiction the documents do not contain. Checked by asserting each defect's
   fingerprint strings appear in the expected files.

Run:
    python experiments/w3_independence/corpus_xdoc/verify_corpus.py
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from defects_xdoc import DEFECTS_XDOC  # noqa: E402

# How a competent reviewer would phrase each finding. Deliberately NOT copied from
# the `desc` field -- if the exemplars were the descriptions, this would only prove
# the rules match their own prose.
EXEMPLARS = {
    "X01_monthly_fee":
        "The MSA states a monthly fee of GBP 12,400 but the SOW states GBP 12,800.",
    "X02_term_length":
        "The MSA initial term is 24 months while the SOW describes a 36 month programme.",
    "X03_termination_notice":
        "Notice to terminate for convenience is ninety days under the MSA and thirty "
        "days under the SOW.",
    "X08_incident_notice_window":
        "The DPA requires notification within 24 hours; the SLA allows seventy-two hours.",
    "X11_liability_cap":
        "Liability is capped at 12 months of fees in the MSA but at GBP 250,000 in the SOW.",
    "X13_availability_target":
        "Availability must be 99.9% under the SLA but only 99.5% under the SOW.",
    "X14_service_credit_cap":
        "Service credits are limited to 10% of the monthly fee in the SLA but "
        "twenty-five per cent in the SOW.",
    "X20_payment_terms":
        "Invoices are payable in 30 days under the MSA and forty-five days under the SOW.",
    "X24_insurance_limit":
        "Professional indemnity insurance is required at 5,000,000 in the MSA and "
        "2,000,000 in the SOW.",
    "X05_business_day_definition":
        "Business Day is defined as Monday to Friday in the MSA but Monday to Saturday "
        "in the SLA.",
    "X06_confidential_information_definition":
        "The MSA requires information to be marked confidential, but the DPA treats "
        "personal data as confidential whether or not marked.",
    "X07_security_incident_definition":
        "Security Incident is defined more narrowly in the SLA, requiring confirmed "
        "access and data loss, than in the DPA.",
    "X10_subprocessor_consent":
        "The MSA allows subcontracting without consent while the DPA requires prior "
        "written consent for each Subprocessor.",
    "X16_governing_law":
        "The MSA is governed by England and Wales but the DPA specifies the Republic "
        "of Ireland.",
    "X17_dead_xref_to_sow":
        "The MSA refers to acceptance criteria in Schedule 1 Section 12, which does not "
        "exist.",
    "X18_dead_xref_to_dpa_annex":
        "The SLA refers to Annex 3 of the Data Processing Addendum, but the DPA has only "
        "two annexes.",
    "X19_start_date_precedes_msa":
        "The programme commences 1 March 2027, before the MSA effective date of 1 April "
        "2027.",
    "X21_processing_location":
        "The DPA restricts processing to the UK and EEA but the delivery team is located "
        "in Bengaluru.",
    "X04_circular_precedence":
        "Precedence is circular: the MSA says it prevails over any Schedule and the SOW "
        "says it prevails over the MSA, so each contradicts the other.",
    "X09_retain_vs_delete":
        "The MSA requires records to be retained for seven years after termination while "
        "the DPA requires personal data to be deleted within thirty days.",
    "X12_liability_carveout_collision":
        "The DPA disapplies the liability cap for data protection breaches while the MSA "
        "applies it notwithstanding any addendum.",
    "X15_automatic_credit_vs_no_setoff":
        "Service credits are applied automatically to the next invoice, but the MSA "
        "prohibits any set-off or deduction without written agreement.",
    "X22_audit_rights":
        "The MSA limits assurance to a SOC 2 report and excludes any further audit, but "
        "the DPA grants an annual on-site audit.",
    "X23_deemed_vs_express_acceptance":
        "Deliverables are deemed accepted after five business days in the SOW, but the "
        "MSA requires express written acceptance.",
}

# Fingerprint strings that MUST appear in the corpus, per defect, with the file
# each is expected in. Guards against ground truth for a contradiction that was
# never actually written into the documents.
FINGERPRINTS = {
    "X01_monthly_fee": [("01_msa.md", "12,400"), ("02_sow.md", "12,800")],
    "X02_term_length": [("01_msa.md", "twenty-four (24) months"),
                        ("02_sow.md", "thirty-six (36) month")],
    "X03_termination_notice": [("01_msa.md", "ninety (90) days"),
                               ("02_sow.md", "thirty (30) days")],
    "X08_incident_notice_window": [("03_dpa.md", "twenty-four (24) hours"),
                                   ("04_sla.md", "seventy-two (72) hours")],
    "X11_liability_cap": [("02_sow.md", "250,000")],
    "X13_availability_target": [("04_sla.md", "99.9%"), ("02_sow.md", "99.5%")],
    "X14_service_credit_cap": [("04_sla.md", "ten per cent (10%)"),
                               ("02_sow.md", "twenty-five per cent (25%)")],
    "X20_payment_terms": [("01_msa.md", "thirty (30) days"),
                          ("02_sow.md", "forty-five (45) days")],
    "X24_insurance_limit": [("01_msa.md", "5,000,000"), ("02_sow.md", "2,000,000")],
    "X05_business_day_definition": [("01_msa.md", "Monday to Friday"),
                                    ("04_sla.md", "Monday to Saturday")],
    "X06_confidential_information_definition": [("01_msa.md", "marked as confidential"),
                                                ("03_dpa.md", "whether or not marked")],
    "X07_security_incident_definition": [("03_dpa.md", "unauthorised or unlawful access"),
                                         ("04_sla.md", "confirmed unauthorised access")],
    "X10_subprocessor_consent": [("01_msa.md", "without the prior consent"),
                                 ("03_dpa.md", "prior written consent")],
    "X16_governing_law": [("01_msa.md", "England and Wales"),
                          ("03_dpa.md", "Republic of Ireland")],
    "X17_dead_xref_to_sow": [("01_msa.md", "Schedule 1, Section 12")],
    "X18_dead_xref_to_dpa_annex": [("04_sla.md", "Annex 3")],
    "X19_start_date_precedes_msa": [("01_msa.md", "1 April 2027"),
                                    ("02_sow.md", "1 March 2027")],
    "X21_processing_location": [("03_dpa.md", "European Economic Area"),
                                ("02_sow.md", "Bengaluru")],
    "X04_circular_precedence": [("01_msa.md", "this Agreement prevails"),
                                ("02_sow.md", "this Statement of Work prevails")],
    "X09_retain_vs_delete": [("01_msa.md", "seven (7) years"),
                             ("03_dpa.md", "within thirty (30) days")],
    "X12_liability_carveout_collision": [("01_msa.md", "notwithstanding any other provision"),
                                         ("03_dpa.md", "No limitation or exclusion")],
    "X15_automatic_credit_vs_no_setoff": [("01_msa.md", "set-off"),
                                          ("04_sla.md", "automatically")],
    "X22_audit_rights": [("01_msa.md", "SOC 2"), ("03_dpa.md", "may audit")],
    "X23_deemed_vs_express_acceptance": [("01_msa.md", "expressly and in writing"),
                                         ("02_sow.md", "deemed accepted")],
}

# Defects whose vocabulary legitimately overlaps, so an exemplar for one may also
# match the other. Declared explicitly rather than tolerated silently.
ALLOWED_CROSSTALK = {
    ("X03_termination_notice", "X20_payment_terms"),
    ("X20_payment_terms", "X03_termination_notice"),
    ("X09_retain_vs_delete", "X03_termination_notice"),
    ("X13_availability_target", "X14_service_credit_cap"),
    ("X14_service_credit_cap", "X13_availability_target"),
    ("X02_term_length", "X03_termination_notice"),
}


def match_ids(text: str) -> set[str]:
    low = text.lower()
    return {
        d["id"]
        for d in DEFECTS_XDOC
        if any(all(re.search(p, low) for p in rule) for rule in d["rules"])
    }


def _flat(text: str) -> str:
    """Lowercase with runs of whitespace collapsed to single spaces.

    The documents are wrapped prose, so a fingerprint phrase like "prior written
    consent" can straddle a newline. Comparing raw text reported two defects as
    absent from documents that plainly contained them -- a bug in this checker, not
    in the corpus.
    """
    return re.sub(r"\s+", " ", text).lower()


def main() -> int:
    failures = 0
    ids = [d["id"] for d in DEFECTS_XDOC]
    print(f"{len(ids)} seeded cross-document defects\n")

    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        print(f"DUPLICATE ids: {sorted(dupes)}")
        failures += 1

    # 1 + 2 -- every exemplar matches its own defect, and not the world.
    missing_exemplar = [i for i in ids if i not in EXEMPLARS]
    if missing_exemplar:
        print(f"NO EXEMPLAR for: {missing_exemplar}")
        failures += 1

    for defect_id, text in EXEMPLARS.items():
        hits = match_ids(text)
        if defect_id not in hits:
            print(f"  MISS  {defect_id}: its own exemplar does not match its rules")
            print(f"        exemplar: {text}")
            failures += 1
        extra = {
            h for h in hits - {defect_id} if (defect_id, h) not in ALLOWED_CROSSTALK
        }
        if extra:
            print(f"  CROSSTALK  {defect_id} exemplar also matched {sorted(extra)}")
            failures += 1

    # 3 -- the contradiction is actually written into the documents.
    for defect_id, expectations in FINGERPRINTS.items():
        for filename, needle in expectations:
            path = HERE / filename
            if not path.exists():
                print(f"  MISSING FILE  {filename} (for {defect_id})")
                failures += 1
                continue
            if _flat(needle) not in _flat(path.read_text(encoding="utf-8")):
                print(f"  ABSENT  {defect_id}: {needle!r} not found in {filename}")
                failures += 1

    missing_fp = [i for i in ids if i not in FINGERPRINTS]
    if missing_fp:
        print(f"NO FINGERPRINT CHECK for: {missing_fp}")
        failures += 1

    # NN_*.md only -- README.md lives in this directory and contains the full
    # conflict map. Globbing "*.md" put the answer key into the model's prompt once
    # already (see run_w3.py, --doc xdoc). Asserted here so the mistake cannot come
    # back quietly in either place.
    docs = sorted(HERE.glob("[0-9][0-9]_*.md"))
    leaked = [p.name for p in HERE.glob("*.md") if p not in docs]
    chars = sum(len(p.read_text(encoding="utf-8")) for p in docs)
    print(f"\ncorpus: {len(docs)} documents ({', '.join(p.name for p in docs)}), "
          f"{chars:,} chars, {len(docs) * (len(docs) - 1) // 2} document pairs to check")
    print(f"not part of the corpus (must never be sent to a model): {leaked}")
    if any(d.name.startswith("README") for d in docs):
        print("  README.md IS BEING TREATED AS A CORPUS DOCUMENT -- it is the answer key")
        failures += 1

    print()
    print("CORPUS VERIFIED" if not failures else f"{failures} PROBLEM(S) FOUND")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
