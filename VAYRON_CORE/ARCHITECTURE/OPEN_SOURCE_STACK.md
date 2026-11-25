# Vayron open-source stack selection

This is a candidate architecture, not a claim that these packages are installed. Keep the core provider-neutral and dependency-light; add a component only when a tested feature needs it.

## Selected capabilities to learn from and integrate behind Vayron-owned interfaces

| Layer | Candidate | What Vayron can adopt | Integration rule |
|---|---|---|---|
| Neural training | PyTorch | tensor/autograd, custom model training, GPU/CPU kernels | Keep Vayron's model definition, data pipeline, checkpoints, and evaluation independent |
| Model/tokenizer ecosystem | Hugging Face Transformers | tokenizer and architecture utilities, model loading/training interfaces | Audit each model's separate weights and dataset license; do not copy weights and call them original |
| Fine-tuning research | PEFT + TRL | LoRA/QLoRA, supervised fine-tuning, preference optimization | Optional training extras only; no installation on the lightweight runtime |
| Local inference | llama.cpp | quantized GGUF inference on CPU and supported accelerators | Use as a replaceable local runtime adapter; verify Android/target hardware builds |
| Agent orchestration patterns | LangGraph | explicit state graphs, checkpointing, pause/resume, human approval | Vayron keeps its own contracts; adopt selected patterns or an adapter, not a hard dependency |
| Retrieval and memory | Qdrant | vector, sparse, hybrid search and metadata filtering | Optional self-hosted service; SQLite remains the zero-service baseline |
| Embeddings | sentence-transformers | local embedding and reranking pipelines | Verify each embedding model's license and resource requirements separately |
| Evaluation | lm-evaluation-harness and custom Vayron tests | repeatable task benchmarks and regression tests | Publish exact datasets, prompts, metrics, and hardware with results |
| Observability | OpenTelemetry | traces, metrics, and structured diagnostics | Local/offline export by default; no vendor telemetry requirement |

## License and cost guardrails

- The core remains free to build and run; no API key, credit card, paid cloud, or automatic billing is allowed.
- PyTorch's main project license is BSD-style; Transformers, PEFT, TRL and llama.cpp publish permissive open-source code licenses; LangGraph is MIT; Qdrant is Apache-2.0. Preserve required notices and inspect all transitive components.
- A library's code license does not grant rights to model weights, tokenizer files, training datasets, benchmark datasets, or generated outputs. Audit those independently.
- Open-source software is not the same as free compute. GPU hours, hosted endpoints, managed vector databases, and model APIs can cost money. Do not enable them.
- No framework should own Vayron's identity, model architecture, data format, memory schema, or public API.

## Integration order

1. Keep the current standard-library foundation passing tests.
2. Add PyTorch only in a separate optional training extra when a real training environment is selected.
3. Define and test Vayron's tokenizer/model architecture and data provenance before any large training run.
4. Add local inference through llama.cpp only after a compatible Vayron checkpoint exists.
5. Add retrieval/embedding components after memory interfaces and data deletion/export policies are tested.
6. Add graph orchestration only where resumable workflows, checkpointing, and approval gates provide measurable value.

## References

- PyTorch: https://github.com/pytorch/pytorch
- Transformers: https://github.com/huggingface/transformers
- PEFT: https://github.com/huggingface/peft
- TRL: https://github.com/huggingface/trl
- llama.cpp: https://github.com/ggml-org/llama.cpp
- LangGraph: https://github.com/langchain-ai/langgraph
- Qdrant: https://github.com/qdrant/qdrant
- sentence-transformers: https://github.com/UKPLab/sentence-transformers
