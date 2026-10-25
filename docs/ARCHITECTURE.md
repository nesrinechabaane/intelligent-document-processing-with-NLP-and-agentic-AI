# Architecture & design decisions

## Data flow

```text
file ─► load_document ─► text ─► extract_document ─► ExtractedDocument
                                   (+ spaCy entities, optional)
                                         │
                                    validate(rules) ─► [Finding]
                                         │
                       DocumentAgent.run(doc, findings)
                         1. planner.plan()          → Plan(actions, notes)
                         2. _enforce_policy()       → guardrails
                         3. _execute() per action   → ActionRecord (retries)
                         4. _verify_and_recover()   → invariants checked
                                         │
                       render_report ─► ProcessingResult ─► reports/*.md|json
```

All stages exchange the typed Pydantic models of `models.py`, which are also the API response schema.

## Key decisions

**Rules first, models optional.** The extractor is deterministic and needs no download. This makes
the project reproducible, testable in CI and explainable (every finding carries its evidence). LLMs
and spaCy are additive.

**Separate *deciding* from *doing*.** The planner only returns a list of `PlannedAction`. Execution,
validation of arguments, retries and policy enforcement live in the agent. An LLM can therefore be
swapped in without being trusted with side effects.

**Guardrails beat prompts.** Invariants hold regardless of the planner:

* a critical finding always ends with a `create_ticket` call (added if missing);
* `archive_document` is always called exactly once, last, with a status derived from the findings;
* only registered tools with schema-valid arguments are executed;
* if the ticket still fails after retries, the agent queues a human review and records the failure.

**Error taxonomy.** `ToolError` (bad call) is permanent → recorded, not retried. Any other exception
is assumed transient → retried with exponential backoff (`IDP_MAX_RETRIES`, `IDP_RETRY_BACKOFF`).

**Prompt-injection surface.** The LLM planner receives a JSON summary built from extracted fields
and rule messages — never the document body. Free text that does reach it (rule messages) is
truncated. Even a manipulated answer can only select among the registered tools, and the guardrails
above still apply.

**Settings are an explicit immutable object** (`Settings`), not global state; the API key is excluded
from `repr`.

**One bad file never stops a batch** (`process_many`), and a crashing validation rule becomes a finding
instead of aborting verification.

## Extending

| I want to… | Do this |
|---|---|
| Add a verification rule | Write `def rule_x(doc) -> list[Finding]`, append to `DEFAULT_RULES` |
| Add a tool (Jira, e-mail…) | Create a `Tool(name, description, json_schema, handler)` and register it; teach the planner when to use it |
| Support a new unit | Add it to `UNITS` (`vocabulary.py`) and `UNIT_TO_REFERENCE` (`validation.py`) |
| Support a new language | Add labels/keywords to `vocabulary.py` and a spaCy model to `entities.MODELS` |
| Use another LLM provider | Implement `LLMClient.complete(system, prompt) -> str` and extend `build_llm` |
| Add ground truth | Put `<name>.expected.json` next to a document; run `idp evaluate <folder>` |

## Testing strategy

* Unit tests per module (extraction, validation, tools, planner, agent, config, ingestion).
* Failure injection: a flaky tool proves retries and backoff; a permanently failing tool proves recovery.
* LLM behaviour is tested with a fake client: valid answers, JSON wrapped in prose, malformed JSON,
  unknown tools, provider errors, and the "no raw text in the prompt" property.
* End-to-end tests on generated TXT / PDF / PNG (OCR) files; CLI tests with `click.testing`.
* API tests are skipped automatically when FastAPI is not installed.
* CI runs lint, type checking, tests and a quality gate on the benchmark F1.
