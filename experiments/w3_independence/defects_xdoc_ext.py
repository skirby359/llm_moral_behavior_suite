"""Ground truth for the EXTENDED cross-document corpus — 28 further defects.

The four-document corpus (`corpus_xdoc/`, 24 defects, 6 document pairs) failed to
create headroom against `claude-opus-5`: 24/24 on the first call. The diagnosis in
FINDINGS.md was that the pair count needed to grow again, and that this is cheap —
pairs grow quadratically in documents while authoring cost grows linearly.

This adds five documents (`corpus_xdoc_ext/`), taking the set to **nine documents and
36 pairs**, with 28 further conflicts on top of the original 24 — **52 seeded
cross-document defects total**.

The five new documents are the ones a real contract set of this shape would actually
contain, which is what makes the conflicts plausible rather than contrived:

    05_order_form.md      Order Form (commercial terms)
    06_infosec.md         Information Security Policy (Schedule 3)
    07_bcdr.md            Business Continuity and DR Plan (Schedule 4)
    08_change_control.md  Change Control Procedure (Schedule 5)
    09_exit.md            Exit and Transition Plan (Schedule 6)

Same design rules as `defects_xdoc.py`, and they are load-bearing:

1. **Every defect spans two documents.** At least one is always a new document, and
   several are new-to-new. None can be found by reading one document alone.
2. **Each document is internally consistent.** The Order Form's £153,600 annual value
   really is 12 x £12,800; the exit milestones really do fit inside the six-month
   transition period. So a single-document reading yields nothing.
3. **Fingerprints chosen at authoring time and checked for uniqueness across all nine
   documents** — `Frankfurt`, `35,000`, `1,250`, `153,600`, `24x7`, `penetration
   test`, `deemed approved`, `Programme Director`, `Restricted Data`, `clause 14`,
   `clause 17`.
4. **Not every cross-reference is a defect.** `08_change_control.md` cl. 7.2 points at
   the rate in the Exit and Transition Plan, which genuinely exists at 09_exit cl.
   3.2. A corpus where every reference is broken would teach a model to flag
   references rather than check them.

Three-way conflicts are deliberate and are seeded as single defects, because a
reviewer reports them as one problem: payment terms are 30 / 45 / 60 days across
MSA / SOW / Order Form, the term is 24 / 36 / 12 months, and incident notification
is 24 / 72 / 48 hours across DPA / SLA / InfoSec.
"""

from __future__ import annotations

DEFECTS_XDOC_EXT = [
    # =================================================================== 05 ORDER FORM
    {
        "id": "E01_initial_term_three_way",
        "grade": "obvious",
        "pair": "Order Form 1.2 vs MSA 3.1 vs SOW 2.1",
        "desc": "Initial term is 12 months (Order Form), 24 months (MSA) and a "
                "36-month programme (SOW) — a three-way conflict",
        "rules": [
            [r"initial term", r"\b(12|twelve)\b"],
            [r"\b(12|twelve)\b", r"\b(24|twenty-four)\b", r"(term|month)"],
        ],
    },
    {
        "id": "E02_annual_contract_value",
        "grade": "obvious",
        "pair": "Order Form 1.4 vs MSA 4.1",
        "desc": "Order Form's GBP 153,600 annual value equals 12 x the SOW's 12,800, "
                "not 12 x the MSA's 12,400 (148,800)",
        "rules": [[r"153[,.\s]?600"], [r"148[,.\s]?800"]],
    },
    {
        "id": "E03_payment_terms_three_way",
        "grade": "obvious",
        "pair": "Order Form 1.6 vs MSA 4.3 vs SOW 5.3",
        "desc": "Payment terms are 60 days (Order Form), 30 days (MSA) and 45 days "
                "(SOW)",
        # Tightened after verify_corpus_ext.py flagged cross-talk: the first version
        # was `60` plus any of payment/invoice/terms, which also fired on E22's
        # "60 days notice ... next invoice". Payment-terms language is now required.
        "rules": [[
            r"\b(60|sixty)\b",
            r"(payment term|payable within|days (of|from) (receipt|invoice|the date)|\bnet\b)",
        ]],
    },
    {
        "id": "E04_order_form_precedence",
        "grade": "subtle",
        "pair": "Order Form 2.1-2.2 vs MSA 14.2 vs SOW 1.2",
        "desc": "A THIRD precedence rule: the Order Form ranks itself above the MSA, "
                "which ranks itself above every Schedule, while the SOW ranks itself "
                "above the MSA. Three documents each claim primacy",
        # `priority` alone was too broad: verify_corpus_ext.py caught it firing on
        # E05's "Priority 2 and 3 support", which is incident priority, not
        # document precedence. Only precedence senses now.
        "rules": [[
            r"order form",
            r"(prevail|preceden|order of priority|ranks? (above|higher|first))",
        ]],
    },
    {
        "id": "E05_support_hours",
        "grade": "medium",
        "pair": "Order Form 3.1 vs SLA 2.2",
        "desc": "Order Form promises 24x7 support for all priorities; the SLA limits "
                "Priority 2 and 3 support to 08:00-18:00 on Business Days",
        "rules": [
            [r"24\s*[x*/×]\s*7"],
            [r"(around the clock|24 hours a day)", r"(priority|support)"],
        ],
    },
    {
        "id": "E06_service_level_start",
        "grade": "medium",
        "pair": "Order Form 3.3 vs SOW 7.1",
        "desc": "Order Form applies service levels from the Service Commencement Date; "
                "the SOW applies them only from the start of Phase 3, month 19",
        "rules": [[r"phase 3", r"(commencement|order form|service level|apply)"]],
    },
    {
        "id": "E07_non_renewal_notice",
        "grade": "subtle",
        "pair": "Order Form 6.2 vs MSA 3.3",
        "desc": "Order Form requires 30 days' notice of non-renewal; the MSA requires "
                "90 days' notice to terminate for convenience, so the Order Form can "
                "lapse while the MSA cannot yet be ended",
        "rules": [[r"non-?renewal", r"\b(30|thirty|90|ninety)\b"]],
    },
    # ============================================================ 06 INFORMATION SECURITY
    {
        "id": "E08_restricted_data_scope",
        "grade": "medium",
        "pair": "InfoSec 1.2 vs DPA 3.3 / Annex 1",
        "desc": "InfoSec classes employee compensation data as Restricted Data, but the "
                "DPA's declared categories of personal data are only contact details, "
                "transaction records and loyalty identifiers",
        "rules": [
            [r"restricted data", r"(compensation|categor|scope|not |conflict|inconsist)"],
            [r"compensation", r"(categor|annex 1|data processing addendum|dpa)"],
        ],
    },
    {
        "id": "E09_any_provider_region",
        "grade": "obvious",
        "pair": "InfoSec 2.1 vs DPA 4.1 / Annex 2",
        "desc": "InfoSec permits storage in any Provider region with equivalent "
                "controls; the DPA restricts processing to the UK and EEA and lists "
                "only London and Dublin",
        "rules": [
            [r"any provider region"],
            [r"region", r"(uk|eea|european economic|annex 2)"],
        ],
    },
    {
        "id": "E10_review_cadence",
        "grade": "subtle",
        "pair": "InfoSec 4.3 vs DPA 7.3",
        "desc": "InfoSec requires a quarterly access review; the DPA requires the "
                "security measures to be reviewed only annually",
        "rules": [
            [r"quarterly access review"],
            [r"quarterly", r"annual", r"review"],
        ],
    },
    {
        "id": "E11_log_retention",
        "grade": "medium",
        "pair": "InfoSec 5.2 vs MSA 12.4",
        "desc": "InfoSec deletes security logs after 18 months; the MSA requires all "
                "records relating to the Agreement to be retained for 7 years",
        "rules": [[r"\b(18|eighteen)\b", r"month"]],
    },
    {
        "id": "E12_incident_notice_three_way",
        "grade": "obvious",
        "pair": "InfoSec 6.1 vs DPA 6.1 vs SLA 7.3",
        "desc": "Incident notification is 48 hours (InfoSec), 24 hours (DPA) and 72 "
                "hours (SLA) — and InfoSec starts the clock at confirmation while the "
                "DPA starts it at awareness",
        "rules": [[r"\b(48|forty-eight)\b"]],
    },
    {
        "id": "E13_penetration_test_sharing",
        "grade": "medium",
        "pair": "InfoSec 7.1-7.3 vs MSA 10.2",
        "desc": "InfoSec shares penetration test reports and lets Customer nominate a "
                "target system; MSA 10.2 gives Customer no right beyond a SOC 2 report "
                "and no right to inspect systems",
        "rules": [[r"penetration test"]],
    },
    # ================================================= 07 BUSINESS CONTINUITY / DR
    {
        "id": "E14_rto_vs_sla_resolution",
        "grade": "obvious",
        "pair": "BCDR 2.1 vs SLA 5.1",
        "desc": "BCDR sets an 8-hour Recovery Time Objective; the SLA requires "
                "Priority 1 Resolution within 4 hours, and a Security Incident is "
                "treated as Priority 1",
        "rules": [
            [r"(recovery time objective|\brto\b)"],
            [r"\b(8|eight)\b", r"\b(4|four)\b", r"hour"],
        ],
    },
    {
        "id": "E15_rpo_tolerates_data_loss",
        "grade": "subtle",
        "pair": "BCDR 2.2 vs DPA 1.6 / 7.1",
        "desc": "A 24-hour Recovery Point Objective designs in up to a day of data "
                "loss, while the DPA defines any loss of Customer Personal Data as a "
                "Security Incident requiring notification",
        "rules": [
            [r"(recovery point objective|\brpo\b)"],
            [r"data loss", r"(security incident|dpa|data processing)"],
        ],
    },
    {
        "id": "E16_frankfurt_recovery_site",
        "grade": "medium",
        "pair": "BCDR 3.1 vs DPA Annex 2",
        "desc": "The recovery environment is in Frankfurt, which is inside the EEA and "
                "so satisfies DPA 4.1, but is NOT among the approved processing "
                "locations listed in DPA Annex 2 (London and Dublin only)",
        "rules": [[r"frankfurt"]],
    },
    {
        "id": "E17_sla_suspended_in_continuity_event",
        "grade": "medium",
        "pair": "BCDR 5.1 vs SLA 9",
        "desc": "BCDR suspends every SLA obligation for the duration of a Continuity "
                "Event; the SLA's own exclusions list does not include continuity "
                "events, so availability would still be measured against 99.9%",
        "rules": [[r"continuity event", r"(suspend|service level|\bsla\b|exclusion)"]],
    },
    {
        "id": "E18_planned_unavailability_excluded",
        "grade": "subtle",
        "pair": "BCDR 5.2-5.3 vs SLA 3.3-3.4",
        "desc": "BCDR excludes up to 12 hours of planned unavailability on returning to "
                "the primary environment; the SLA excludes only AGREED maintenance "
                "windows, which require 5 Business Days' notice",
        "rules": [
            [r"\b(12|twelve)\b", r"hour", r"(planned|unavailab|primary|return)"],
            [r"planned unavailab"],
        ],
    },
    # ==================================================== 08 CHANGE CONTROL PROCEDURE
    {
        "id": "E19_dead_xref_msa_clause_17",
        "grade": "medium",
        "pair": "Change Control 4.1 vs MSA (ends at 16)",
        "desc": "Change Control submits changes to a 'Change Control Board described in "
                "the Master Services Agreement, clause 17'; the MSA ends at clause 16 "
                "and describes no such board",
        "rules": [[r"(clause|section|§)\s*17"], [r"change control board"]],
    },
    {
        "id": "E20_deemed_approved_change",
        "grade": "obvious",
        "pair": "Change Control 4.2 vs MSA 2.4",
        "desc": "A change is deemed approved after 10 Business Days of Customer "
                "silence; MSA 2.4 requires every change to be agreed in writing by "
                "both parties BEFORE implementation",
        "rules": [[r"deemed approv"]],
    },
    {
        "id": "E21_delivery_lead_change_authority",
        "grade": "medium",
        "pair": "Change Control 4.3 vs MSA 2.4",
        "desc": "Provider's Delivery Lead may approve changes up to GBP 35,000 with no "
                "reference to Customer, which MSA 2.4's written-agreement requirement "
                "does not permit",
        "rules": [[r"35[,.\s]?000"]],
    },
    {
        "id": "E22_change_charges_bypass_notice",
        "grade": "subtle",
        "pair": "Change Control 5.1/5.3 vs MSA 4.4",
        "desc": "Change-related charges apply from the next invoice and are declared "
                "exempt from ordinary charge-increase notice; MSA 4.4 allows an "
                "increase only once in 12 months on 60 days' notice",
        "rules": [
            [r"(change-related|revised charge|next invoice|next issued)",
             r"(notice|once in any|4\.4|increase)"],
        ],
    },
    {
        "id": "E23_escalation_path_conflict",
        "grade": "medium",
        "pair": "Change Control 8.1 vs SOW 8.3",
        "desc": "Change Control escalates Delivery Lead -> Programme Director -> Chief "
                "Information Officer; the SOW escalates delivery lead -> account "
                "director -> executive sponsor",
        "rules": [
            [r"programme director|program director"],
            [r"escalat", r"(account director|executive sponsor)"],
        ],
    },
    # ==================================================== 09 EXIT AND TRANSITION PLAN
    {
        "id": "E24_exit_retention_vs_dpa_deletion",
        "grade": "obvious",
        "pair": "Exit 2.3 vs DPA 8.2",
        "desc": "Exit Plan retains all Customer data for 90 days after termination; the "
                "DPA requires all Customer Personal Data deleted within 30 days",
        "rules": [
            [r"\b(90|ninety)\b", r"(retain|retention)", r"(delet|30|thirty)"],
            [r"\b(90|ninety)\b", r"(transition|exit)", r"(delet|dpa|data processing)"],
        ],
    },
    {
        "id": "E25_transition_charges_vs_inclusive_fee",
        "grade": "medium",
        "pair": "Exit 3.2 vs SOW 5.2",
        "desc": "Transition assistance is chargeable at GBP 1,250 per person per day, "
                "but the SOW states the Fee covers all personnel unless expressly "
                "stated otherwise",
        "rules": [[r"1[,.\s]?250"]],
    },
    {
        "id": "E26_data_return_format",
        "grade": "subtle",
        "pair": "Exit 4.1(a) vs DPA 8.1",
        "desc": "Exit returns data 'in the format used by Provider's systems'; the DPA "
                "requires a structured, commonly used format",
        "rules": [
            [r"format used by provider"],
            [r"format", r"(structured|commonly used)"],
        ],
    },
    {
        "id": "E27_source_code_vs_ip_retention",
        "grade": "medium",
        "pair": "Exit 4.1(b) vs MSA 7.2-7.3",
        "desc": "Exit requires handover of all Deliverables including source code and "
                "build scripts; the MSA assigns Deliverable IP only on payment in full "
                "and expressly reserves Provider's pre-existing tools and methods",
        "rules": [[r"source code"]],
    },
    {
        "id": "E28_dead_xref_dpa_clause_14",
        "grade": "medium",
        "pair": "Exit 5.3 vs DPA (ends at 13)",
        "desc": "Exit points to 'the Data Processing Addendum, clause 14' for personal "
                "data obligations; the DPA ends at clause 13",
        "rules": [[r"(clause|section|§)\s*14"]],
    },
]
