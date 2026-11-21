# AC Knowledge Scout Expansion v2

## Expanded scope

The Scout taxonomy now includes software and AI, mathematics, natural and applied sciences, medicine and biology, chemistry, physics, astronomy, engineering, robotics, electronics, materials, aerospace, energy, agriculture, climate and environment, geography, history, languages, humanities, economics, law, public policy, business, operations, accessibility, standards and open data.

Admissible source classes include official documentation, standards bodies, government open data, academic repositories, open-access research, security advisories, public repositories, open-source projects and open courseware. Every source still requires registration, terms review, evidence and explicit activation.

## Evidence evaluator

KnowledgeEvidenceEvaluator provides deterministic review triage using source-class weights, distinct host count, retrieval recency, evidence count and conflicting values for a normalized claim key. It does not infer semantic equivalence, verify truth, assess research methodology or establish legal safety. A high score only prioritizes human review. Conflicts force expert review. Every result says truth_verified=false, human_review_required, and no automatic publication or training.

## Safety and operation

- HTTPS-only credential-free evidence URLs, port 443 only.
- Maximum 100 evidence records per evaluation; timezone-aware timestamps.
- Existing catalog-bound connector, DNS pinning, redirect revalidation, byte caps and timeouts remain mandatory for retrieval.
- No unrestricted crawling, login/paywall bypass, bulk mirroring, package installation, code execution or model-weight training.
- Knowledge remains quarantined pending review.
- No 24/7 uptime claim; scheduling is separate and subject to free/no-card/no-billing eligibility.