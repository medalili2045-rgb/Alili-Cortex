# AC Universal AI Learning & Capability Observatory v1

## Purpose
Provide an independent catalog and controlled study ledger for external AI products, models, frameworks and developer tools. AC studies documented capabilities and transferable engineering patterns; it does not claim ownership of third-party models, copy proprietary weights, or treat product access as free runtime access.

## Initial reference tracks
- Google AI Studio: model experimentation, prompt design, multimodal prototyping, app-building and tool workflows.
- Google Nano Banana: image instruction following, editing, multi-image fusion, visual consistency, text rendering and visual evaluation.
- Gemini: multimodal reasoning, structured outputs, tool calling and agent workflows.
- GitHub Copilot: inline completion, repository Q&A, repository context, multi-step coding agents, code review, test generation, issue/PR workflows, custom instructions, skills, MCP and IDE/terminal workflows.
- Copilot SDK and GitHub Models: study their developer and model-evaluation interfaces separately; no assumption of unlimited/free quota.
- OpenHands and Letta: isolated execution/sandbox patterns and persistent-memory architecture.
- Open-source foundations: Transformers, PEFT, PyTorch, ComfyUI, LlamaIndex, Qdrant and gpt-oss.

Each catalog record distinguishes capabilities from study focus and includes an access note. Product capabilities are not executable integrations. Verify current availability, license, quotas, model terms and hardware requirements before any runtime adoption.

## Study governance
- Study notes are caller-supplied in v1; this component is not a web crawler or automatic source downloader.
- Every study record starts as `quarantined` with `license_status=review_required`.
- Records are persisted with a SHA-256 digest and source URL.
- No automatic approval, publication, training, package installation, code execution, weight copying or production changes.
- A source's public documentation is untrusted input and must be reviewed before reuse.

## Copilot capability-learning blueprint
AC studies and may independently implement these general patterns:
1. Repository mapping and context selection.
2. Inline completion and code explanation.
3. Task decomposition and implementation planning.
4. Patch generation with bounded file scope.
5. Code review for correctness, security and maintainability.
6. Test proposal, test execution in a sandbox and result interpretation.
7. Issue and pull-request lifecycle assistance.
8. Repository-wide and path-specific instructions.
9. Reusable skills and specialist agents.
10. Tool/MCP contracts, least privilege and explicit approval gates.
11. Parallel work orchestration with isolated workspaces.
12. Human review before committing, merging, deploying or changing production.

These are learning targets, not a claim that AC already implements Copilot functionality or has access to Copilot's proprietary runtime.

## Clear response policy
The `ac_clear_response_v1` policy asks AC to:
- answer the user's actual question first;
- use plain, natural language;
- match detail to the user's need;
- avoid filler, repetition and performative complexity;
- explain technical terms only when useful;
- distinguish facts, estimates and unknowns;
- ask only for essential missing information;
- report actions and verification honestly.

The initial evaluator checks only structural signals (empty output, sentence length, repeated lines, excessive length and basic structure). It explicitly reports semantic accuracy and factual grounding as `not_evaluated`. It must not be used as a substitute for a real quality benchmark or human review.

## API integration
The observatory is exposed through the authenticated engine service:
- `GET /v1/ai-observatory/capabilities?category=...&q=...&limit=100`
- `GET /v1/ai-observatory/response-style`
- `GET /v1/ai-observatory/studies?capability_id=...&limit=50`
- `POST /v1/ai-observatory/studies` with `capability_id`, `title`, `notes`, `source_url`
- `POST /v1/ai-observatory/evaluate-response` with `text`

## Free-first boundary
No paid API is called by this module. Free quotas, product tiers and API prices can change; no account entitlement is inferred. A paid key, billing activation, subscription or automatic paid fallback is never enabled by this observatory.
