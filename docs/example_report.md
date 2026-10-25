# Processing report — INS-2026-0207

**Status:** 🔴 CRITICAL  
**Findings:** 1 critical, 1 warning, 0 info  
**Extraction confidence:** 100%

## Document

| Field | Value |
|---|---|
| Source | inspection_report_fr.txt |
| Title | Rapport d'inspection |
| Type | inspection_report |
| Language | fr |
| Document ID | INS-2026-0207 |
| Date | 2026-10-12 |
| Equipment | Compresseur à vis CV-12 |
| Manufacturer | AirTech SA |
| Standards | ISO 1217, EN 60204-1 |

## Extracted measurements

| Name | Parameter | Kind | Value | Unit |
|---|---|---|---|---|
| Pression mesurée | pressure | measured | 11.5 | bar |
| Pression maximale | pressure | max | 13.0 | bar |
| Température mesurée | temperature | measured | 88.0 | °C |
| Température maximale | temperature | max | 85.0 | °C |
| Vibration | vibration | measured | 4.2 | mm/s |

## Verification findings

| Severity | Rule | Message | Evidence |
|---|---|---|---|
| critical | limits | Température mesurée (88.0 °C) exceeds Température maximale (85.0 °C) | - Température mesurée : 88 °C \| - Température maximale : 85 °C |
| warning | reported_issue | Anomaly reported in document | Fuite d'huile constatée au niveau du joint d'arbre. |

## Actions triggered by the agent

| Tool | Result | Attempts | OK |
|---|---|---|---|
| create_ticket | ticket TCK-D83E6327 created (TCK-D83E6327.json) | 1 | yes |
| send_alert | alert sent to 'maintenance' (simulated outbox) | 1 | yes |
| request_human_review | document queued for human review | 1 | yes |
| archive_document | document archived with status 'needs_attention' | 1 | yes |
