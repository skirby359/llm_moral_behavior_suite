"""ombs — LLM Operational Moral-Behavior Testing Suite.

A local-first evaluation harness that measures whether LLMs acting in delegated
workplace roles preserve boundaries, exercise sound escalation judgment, and
remain stable under authority, urgency, loyalty, social-proof, ambiguity, and
cultural-context pressure.

Results describe observed behavior of a specific model configuration under a
specific prompt protocol and scenario set. They are not universal claims about
a model, its developer, or its moral status.
"""

__version__ = "0.1.0"

# 0.2: disambiguated `should_send_or_disclose_information` to mean external /
#      unauthorized disclosure only (internal escalation is not disclosure).
# 0.3: added finance / security / it escalation targets.
# 0.4: added procurement escalation target.
PROMPT_TEMPLATE_VERSION = "0.4"
