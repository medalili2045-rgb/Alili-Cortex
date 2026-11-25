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

## Multimodal data: images and video are first-class

Vayron's data program must not be text-only. Images and videos are part of the target training and evaluation scope, alongside text. They must have their own ingestion pipeline and provenance records; they must not be forced through the current text-only `train_text` path.

### Images
- Image-text pairs: captions, descriptions, visual question answering, OCR/document understanding, charts, diagrams, scientific figures, and object/scene descriptions.
- Image-only material may be used only where the source license and intended training use permit it; preserve annotations and source metadata.
- Preprocessing: verify file type, decode safely, reject corrupt files, normalize orientation, record dimensions, detect duplicates and near-duplicates, and create controlled-resolution derivatives.
- Filter personal/private images, exposed personal data, sensitive documents, non-consensual intimate imagery, and unsafe or disallowed content. Apply appropriate safeguards to faces and biometric data.
- Keep the original asset reference and checksum; store derived crops/resizes as reproducible transformations, not replacements for provenance.

### Video
- Video-text pairs: licensed clips with captions, subtitles, transcripts, scene descriptions, instructional steps, and temporal question-answer annotations.
- Process videos as time-based sequences: validate codecs and duration, sample frames at documented intervals or scene boundaries, retain timestamps, and preserve audio/subtitle alignment when separately licensed.
- Deduplicate both complete videos and sampled frames. Avoid treating repeated adjacent frames as independent examples.
- Store clip-level and frame-level provenance, license, timestamps, transformations, and source identifiers. A frame extracted from a video inherits the relevant source rights; extraction does not make it public domain.
- Do not ingest streaming-platform videos or scraped social-media clips merely because they are publicly viewable. Require an explicit compatible license or documented permission.

### Multimodal architecture required
1. Separate image and video manifests with per-asset license/provenance checks and checksums.
2. A safe, bounded-memory media downloader and decoder; no unbounded downloads into Colab.
3. Image preprocessing and video frame/scene sampling pipelines with reproducible configs.
4. Aligned examples that connect media assets to captions, questions, answers, timestamps, and text context.
5. A vision encoder and a temporal video pathway, plus a tested connector into the language model. The current small text-only model does not yet provide these capabilities.
6. Separate image, video, OCR, visual QA, and temporal understanding evaluation suites.
7. A staged training plan: validate data and encoders on small permitted samples first, then scale only with adequate compute and storage.

### Multimodal source discovery policy
Discover image and video datasets broadly, including scientific, educational, public-domain, government, cultural-heritage, and openly licensed repositories. Approve each dataset only after checking its actual license, asset-level restrictions where available, attribution obligations, privacy/safety constraints, download terms, and whether model training is permitted. Dataset names or public URLs alone are not approval.

## Updated current status
- Image/video source audit: not started.
- Image/video downloads: not started.
- Vision encoder and video pathway: not implemented.
- Multimodal training: not started.
