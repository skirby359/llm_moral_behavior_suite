# Model Scorecard — `qwen3:8b`

_Synthesized across all runs in_ `outputs`. _Conditions in increasing difficulty._

## 1. Single-turn (baseline)
- calls: 296  (parse-fail rate: 0%)
- boundary preservation (of parsed): **93%**
- high-confidence failures: 20
- authority susceptibility (authority - neutral fail rate): -0.04

## 2. Multi-turn pushback (chat)
- conversations: 10
- mean boundary-survival depth: **1.50**
- held all turns: 3/10

## 3. Tools — single shot (does action match text?)
- tool tasks: 6
- state-pass rate: **100%**
- chose send_email: 0

## 4. Tools — multi-turn (does pressure cause a real unsafe call?)
- tool conversations: 2
- mean tool-survival depth: **0.00**
- never made an unsafe call: 0/2

## 5. LLM-judge (qualitative)
- verdicts: 20
- mean qualitative score: **4.95/5**

---
_Single-turn boundary preservation tends to a ceiling; the discriminating signal is multi-turn survival depth and real tool actions under authority pressure. Read the conditions together, not the headline alone._
