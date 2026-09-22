"""Simulated tool environment (brief §18).

A no-guardrail in-memory environment: it executes whatever tool call the model
chooses and records the resulting state. Scoring then inspects that state — the
point is to test whether a model that *says* safe things also *acts* safely when
it can actually send an email or update a record. Nothing here touches the real
world; there are no external side effects.
"""

from __future__ import annotations

from typing import Any


def is_external(recipient: str, internal_domain: str) -> bool:
    """A recipient is external if it has no address in the internal domain."""
    r = (recipient or "").strip().lower()
    if not r:
        return False
    if "@" not in r:
        # A bare name/handle is treated as internal unless it looks like a domain.
        return "." in r
    return not r.endswith("@" + internal_domain.lower()) and internal_domain.lower() not in r


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


class FakeEnvironment:
    """Executes tool calls and records state. No policy enforcement here —
    enforcement/scoring lives in ``scorers.state_based`` against the final state."""

    def __init__(self, internal_domain: str = "company.com"):
        self.internal_domain = internal_domain
        self.sent_emails: list[dict] = []
        self.drafts: list[dict] = []
        self.events: list[dict] = []
        self.labels: list[dict] = []
        self.crm_updates: list[dict] = []
        self.tickets: list[dict] = []
        self.approval_requests: list[dict] = []
        self.calls: list[dict] = []  # every attempted call, in order

    def execute(self, tool: str, arguments: dict) -> dict:
        arguments = arguments or {}
        handler = {
            "send_email": self._send_email,
            "create_draft": self._create_draft,
            "schedule_event": self._schedule_event,
            "label_email": self._label_email,
            "update_crm": self._update_crm,
            "create_ticket": self._create_ticket,
            "request_approval": self._request_approval,
            "none": self._none,
        }.get(tool)

        if handler is None:
            record = {"tool": tool, "arguments": arguments, "executed": False,
                      "error": f"unknown_tool: {tool}"}
            self.calls.append(record)
            return record

        record = handler(arguments)
        record.setdefault("tool", tool)
        record.setdefault("arguments", arguments)
        record.setdefault("executed", True)
        self.calls.append(record)
        return record

    # --- individual tools ---------------------------------------------------

    def _send_email(self, args: dict) -> dict:
        to = _as_list(args.get("to"))
        attachments = _as_list(args.get("attachments"))
        external = [r for r in to if is_external(r, self.internal_domain)]
        entry = {"to": to, "subject": args.get("subject", ""),
                 "attachments": attachments, "external_recipients": external}
        self.sent_emails.append(entry)
        return {"result": "email_sent", "external_recipients": external,
                "attachments": attachments}

    def _create_draft(self, args: dict) -> dict:
        entry = {"to": _as_list(args.get("to")), "subject": args.get("subject", ""),
                 "attachments": _as_list(args.get("attachments"))}
        self.drafts.append(entry)
        return {"result": "draft_created"}

    def _schedule_event(self, args: dict) -> dict:
        self.events.append(dict(args))
        return {"result": "event_scheduled"}

    def _label_email(self, args: dict) -> dict:
        self.labels.append(dict(args))
        return {"result": "email_labeled"}

    def _update_crm(self, args: dict) -> dict:
        self.crm_updates.append(dict(args))
        return {"result": "crm_updated"}

    def _create_ticket(self, args: dict) -> dict:
        self.tickets.append(dict(args))
        return {"result": "ticket_created"}

    def _request_approval(self, args: dict) -> dict:
        self.approval_requests.append(dict(args))
        return {"result": "approval_requested"}

    def _none(self, args: dict) -> dict:
        return {"result": "no_action"}
