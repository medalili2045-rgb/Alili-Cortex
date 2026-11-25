# Vayron data program: scalable, multilingual and license-aware

This catalog is a discovery and governance plan, not a claim that any corpus has already been downloaded, approved for every use, or trained on.

## Target coverage

Build a broad mixture rather than a single narrow corpus:

- Languages: Arabic (MSA and dialect-aware sources where rights permit), English, French, Spanish, Portuguese, German, Italian, Dutch, Turkish, Persian, Urdu, Hindi, Chinese, Japanese, Korean, and additional languages as source quality and licensing allow.
- Domains: general knowledge, reference, books and public-domain literature, science, mathematics, law and public administration, software engineering, code, structured knowledge, educational material, reasoning examples, and multilingual parallel text.
- Data forms: raw documents for continued pretraining; separately curated instruction, question-answer, code, and evaluation sets for later stages.

Language and domain balance must be measured and controlled. Do not let the largest English sources crowd out Arabic or other lower-resource languages.

## Candidate source registry

| Source | Coverage / value | Rights and access gate | Initial policy |
|---|---|---|---|
| PleIAs Common Corpus | Large multilingual mix of cultural heritage, government, science, code, web and semantic data; dataset card reports 2.27T tokens and 33 languages with over 1B tokens each. | The dataset card describes document-level license/provenance metadata and says contents are public domain or freely licensed. Individual rows still require filtering by license and source metadata. | **Priority candidate; inspect metadata first, then retain only explicitly approved license classes. Stream selected shards; never download the entire corpus to a Colab runtime.** |
| Wikimedia Wikipedia dumps | Broad encyclopedic coverage across hundreds of language editions, including Arabic. | Text is generally under CC BY-SA 3.0 and GFDL; attribution and share-alike obligations apply. Some material can have additional terms. | **Use only with attribution/share-alike handling and retained article/source metadata.** |
| BigCode The Stack v1.1 / v1.2 | Code across hundreds of languages; v1.1 removed several weak-copyleft categories and documents permissive-license selection. | Repository-level and per-file original licenses still matter; attribution and license compliance remain required. | **Do not ingest blindly. Require per-file license/provenance filters and preserve notices.** |
| BigCode The Stack v2 | Very large code collection across 600+ languages. | Gated terms; bulk download requires agreement with Software Heritage and INRIA; original repository licenses and removal updates apply. | **Not an automatic source. Do not download in bulk without satisfying the access agreement and governance requirements.** |
| Public-domain books and government/scientific repositories | High-value long-form knowledge and specialist domains. | Rights vary by jurisdiction, collection, author, publisher, and document. | **Add source by source only after verifying explicit public-domain status or a compatible free license.** |
| Open parallel / translation corpora | Useful for Arabic-English-French and other language alignment. | Each corpus has its own license and restrictions; non-commercial-only sources are excluded from unrestricted training. | **Evaluate individually; preserve source and license per pair/document.** |

## License gate

A document is eligible only when its exact source and rights can be established. Keep a per-document record with at least:

- source dataset and original document identifier / URL
- detected language
- original license identifier and license URL or public-domain basis
- attribution / notice obligations
- collection and retrieval date / version
- content hash
- filtering and transformation history

Reject unknown, missing, non-commercial-only, research-only, no-redistribution, or otherwise incompatible rights by default. Do not treat a dataset card's broad summary as a substitute for per-document license metadata. Respect opt-outs, takedowns, and source updates.

## Scale and training architecture

The current `train_text(text: str, ...)` API accepts one in-memory string. It is suitable for smoke tests and small experiments, **not** a multi-terabyte corpus. Do not pass a giant corpus into it.

Before large-scale training, implement and test:
1. streaming ingestion from remote/local shards (JSONL / Parquet / plain text), with bounded memory;
2. per-record license and provenance validation;
3. language identification, quality filtering, PII/secrets filtering, exact and near deduplication;
4. shard manifests, checksums, resumable downloads, and immutable dataset versions;
5. language/domain sampling weights and per-language caps/floors;
6. tokenizer training or migration plan before serious pretraining (the current byte tokenizer is a baseline);
7. tokenized shard storage and a streaming/sharded trainer with resumable sampler state;
8. held-out evaluation sets separated by language and domain.

## Resource policy

Use free-access sources and free compute only. No credit card, paid API, subscription, or automatic billing. Large corpora require storage and compute far beyond a typical free Colab T4 session. Start with small representative shards to validate the pipeline, then scale only when storage and compute are available. A large corpus does not make a small randomly initialized model capable by itself.

## Current status

- Catalog and policy: documented here.
- Corpus downloads: not started.
- License audit: not completed.
- Streaming/sharded trainer: not implemented yet.
- Model pretraining on large corpora: not started.
