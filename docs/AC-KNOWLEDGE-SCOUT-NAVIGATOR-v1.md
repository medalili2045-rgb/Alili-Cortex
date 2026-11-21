# AC Knowledge Scout Navigator v1

Navigator adds bounded discovery on top of the existing
`UniversalSourceConnector` and `KnowledgeScout`.

## How discovery works

1. A source must be registered and explicitly enabled in the Scout registry.
2. Its identifier must also exist in the curated AC ecosystem catalog.
3. The existing connector performs HTTPS-only retrieval, resolves and pins a
   public IP, revalidates redirects, limits redirects/time/response bytes, and
   accepts text-only content types.
4. Structural extraction selects headings and list items (or a small sentence
   fallback), skips fenced code blocks, deduplicates candidates, and caps the
   note at 2,400 characters.
5. The resulting short note is stored as a provenance-bearing quarantined
   proposal. No automatic publication or package installation occurs.

## API

Authenticated endpoint:

- `POST /v1/knowledge-scout/discover`

Example body:

```json
{
  "source_id": "hf_transformers",
  "artifact_url": "https://github.com/huggingface/transformers",
  "domain": "software",
  "brain_id": "code"
}
```

The source must first be registered in the Scout registry with a base URL
matching its curated ecosystem source, reviewed for terms, and explicitly
enabled with a public HTTPS terms-evidence URL.

## Boundaries

- Navigator only accesses the existing curated ecosystem catalog; it is not an
  unrestricted web crawler or general search engine.
- Structural extraction is not semantic fact verification and does not use an
  LLM. The resulting notes require human review and source/license checks.
- No paywall/login bypass, private network access, bulk copying, or code execution.
- This is on-demand discovery, not a 24/7 service. Scheduling and provider
  eligibility must be separately implemented and verified under the free-only,
  no-card, no-billing policy.
- Knowledge ingestion is retrieval/curation (RAG material), not model-weight training.
