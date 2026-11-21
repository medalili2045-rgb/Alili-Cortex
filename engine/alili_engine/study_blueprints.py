"""Evidence-aware learning blueprints that map open tools to AC specialist brains.

These are study plans, not claims that source material has already been ingested
or that any model has been trained. Each artifact/version still needs license,
provenance, security and quality review before use.
"""

_BLUEPRINTS = (
    {
        "blueprint_id": "foundation_models",
        "domain": "language_models",
        "title": "Foundation models and adaptation",
        "brain_ids": ["ac_reasoning", "ac_language", "ac_code"],
        "source_ids": ["hf_transformers", "hf_tokenizers", "hf_peft", "hf_trl", "pytorch", "google_gemma", "openai_gpt_oss", "deepseek_r1", "qwen"],
        "lessons": [
            {"lesson_id": "architecture", "objective": "Understand transformer blocks, attention, tokenization, context limits and model interfaces.", "study_actions": ["trace a small model forward pass", "compare tokenizer behavior", "map architecture components"], "deliverable": "architecture_map"},
            {"lesson_id": "adaptation", "objective": "Compare full fine-tuning, LoRA and other parameter-efficient methods; identify when each is appropriate.", "study_actions": ["inspect PEFT recipes", "compare trainable parameter counts", "design a small controlled experiment"], "deliverable": "adaptation_decision_record"},
            {"lesson_id": "post_training", "objective": "Understand supervised fine-tuning, preference optimization and reinforcement-learning post-training without confusing them with inference.", "study_actions": ["trace data-to-objective pipelines", "inspect TRL examples", "record failure modes"], "deliverable": "post_training_comparison"},
        ],
    },
    {
        "blueprint_id": "reasoning_math",
        "domain": "reasoning_and_math",
        "title": "Reasoning, mathematics and symbolic computation",
        "brain_ids": ["ac_reasoning", "ac_science"],
        "source_ids": ["deepseek_r1", "sympy", "scipy", "google_jax", "pytorch", "lm_eval"],
        "lessons": [
            {"lesson_id": "decomposition", "objective": "Decompose complex tasks into explicit subproblems, assumptions and verifiable intermediate results.", "study_actions": ["compare alternative derivations", "construct counterexamples", "test edge cases"], "deliverable": "reasoning_trace_spec"},
            {"lesson_id": "symbolic_numeric", "objective": "Choose symbolic, numerical or learned methods based on problem structure and error tolerance.", "study_actions": ["solve equivalent problems with SymPy and SciPy", "compare residuals", "check units and boundary conditions"], "deliverable": "method_selection_report"},
            {"lesson_id": "calibration", "objective": "Report uncertainty, detect unsupported steps and abstain when evidence is insufficient.", "study_actions": ["score held-out problems", "audit proofs", "measure calibration"], "deliverable": "calibration_eval"},
        ],
    },
    {
        "blueprint_id": "software_engineering",
        "domain": "software",
        "title": "Software engineering and secure coding",
        "brain_ids": ["ac_code", "ac_execution", "ac_reasoning"],
        "source_ids": ["pytorch", "hf_smolagents", "inspect_ai", "llama_cpp"],
        "lessons": [
            {"lesson_id": "architecture_testing", "objective": "Derive modular architecture, explicit contracts, deterministic tests and reproducible builds from mature projects.", "study_actions": ["map module boundaries", "write contract tests", "reproduce a documented bug fix"], "deliverable": "design_and_test_plan"},
            {"lesson_id": "secure_defaults", "objective": "Apply least privilege, input validation, safe deserialization, dependency pinning and fail-closed behavior.", "study_actions": ["review security advisories", "create threat models", "write regression tests"], "deliverable": "threat_model_and_regressions"},
            {"lesson_id": "debugging", "objective": "Diagnose faults from logs and minimal reproductions rather than guessing.", "study_actions": ["minimize failing cases", "bisect changes", "verify fixes against regression suites"], "deliverable": "reproducible_bug_report"},
        ],
    },
    {
        "blueprint_id": "agents_tools",
        "domain": "agents_and_automation",
        "title": "Agents, tools and controlled execution",
        "brain_ids": ["ac_execution", "ac_strategy", "ac_code"],
        "source_ids": ["hf_smolagents", "langchain", "llamaindex", "openai_gpt_oss", "inspect_ai"],
        "lessons": [
            {"lesson_id": "tool_contracts", "objective": "Design typed tool contracts with bounded inputs, explicit permissions and auditable outputs.", "study_actions": ["inspect tool schemas", "test malformed arguments", "separate proposal from execution"], "deliverable": "tool_contract_suite"},
            {"lesson_id": "planning_control", "objective": "Use plan-act-observe-verify loops with budgets, stop conditions and human approval for consequential actions.", "study_actions": ["simulate interrupted workflows", "test retry limits", "verify idempotency"], "deliverable": "safe_agent_policy"},
            {"lesson_id": "sandboxing", "objective": "Treat model output and retrieved content as untrusted; isolate execution and deny network or filesystem access by default.", "study_actions": ["build threat scenarios", "test permission denials", "record containment evidence"], "deliverable": "sandbox_acceptance_tests"},
        ],
    },
    {
        "blueprint_id": "knowledge_retrieval",
        "domain": "retrieval_and_memory",
        "title": "Knowledge retrieval, indexing and memory",
        "brain_ids": ["ac_memory", "ac_research"],
        "source_ids": ["meta_faiss", "qdrant", "chroma", "hf_sentence_transformers", "llamaindex", "haystack", "docling"],
        "lessons": [
            {"lesson_id": "document_pipeline", "objective": "Preserve document structure, metadata, page locations and source provenance during extraction.", "study_actions": ["compare parsing outputs", "test tables and scanned pages", "retain source spans"], "deliverable": "document_ingestion_eval"},
            {"lesson_id": "retrieval_quality", "objective": "Measure recall, precision, ranking quality and answer grounding across lexical, vector and hybrid retrieval.", "study_actions": ["build a labelled query set", "compare index strategies", "audit citations"], "deliverable": "retrieval_benchmark"},
            {"lesson_id": "memory_governance", "objective": "Track freshness, contradictions, provenance, retention and supersession rather than storing every claim as truth.", "study_actions": ["simulate conflicting sources", "detect stale facts", "test lifecycle transitions"], "deliverable": "memory_governance_tests"},
        ],
    },
    {
        "blueprint_id": "vision_documents",
        "domain": "vision_and_documents",
        "title": "Computer vision, OCR and document understanding",
        "brain_ids": ["ac_vision", "ac_research"],
        "source_ids": ["opencv", "meta_sam", "docling", "hf_transformers"],
        "lessons": [
            {"lesson_id": "visual_pipeline", "objective": "Understand image preprocessing, detection, segmentation and uncertainty-aware interpretation.", "study_actions": ["compare preprocessing choices", "evaluate segmentation masks", "test low-quality inputs"], "deliverable": "vision_eval_report"},
            {"lesson_id": "ocr_layout", "objective": "Extract text, tables and reading order while preserving coordinates and confidence.", "study_actions": ["test multilingual scans", "compare table reconstruction", "measure character and layout error"], "deliverable": "ocr_quality_suite"},
        ],
    },
    {
        "blueprint_id": "audio_speech",
        "domain": "audio",
        "title": "Speech, audio understanding and signal processing",
        "brain_ids": ["ac_media", "ac_language"],
        "source_ids": ["whisper", "librosa", "hf_transformers"],
        "lessons": [
            {"lesson_id": "signal_basics", "objective": "Understand sampling, framing, spectral features, noise and audio quality limits.", "study_actions": ["inspect waveform and spectrogram", "test resampling", "measure noise sensitivity"], "deliverable": "audio_preprocessing_report"},
            {"lesson_id": "speech_eval", "objective": "Evaluate transcription and translation with language-aware error metrics and careful handling of names and numbers.", "study_actions": ["build a diverse held-out set", "measure WER and targeted errors", "audit timestamps"], "deliverable": "speech_eval_suite"},
        ],
    },
    {
        "blueprint_id": "generative_media",
        "domain": "image_video_generation",
        "title": "Generative images and media pipelines",
        "brain_ids": ["ac_media", "ac_vision"],
        "source_ids": ["hf_diffusers", "meta_muse_glimmer", "opencv"],
        "lessons": [
            {"lesson_id": "generation_pipeline", "objective": "Understand diffusion pipelines, conditioning, schedulers, latent representations and reproducibility.", "study_actions": ["trace inference stages", "compare scheduler settings", "record seed and model version"], "deliverable": "generation_experiment_card"},
            {"lesson_id": "media_quality_rights", "objective": "Evaluate output quality, provenance, safety and asset/model usage rights.", "study_actions": ["apply a blinded quality rubric", "inspect model cards", "record provenance"], "deliverable": "media_review_record"},
        ],
    },
    {
        "blueprint_id": "science_engineering",
        "domain": "science_and_engineering",
        "title": "Scientific computing and engineering validation",
        "brain_ids": ["ac_science", "ac_reasoning"],
        "source_ids": ["scipy", "sympy", "google_jax", "pytorch"],
        "lessons": [
            {"lesson_id": "numerical_validity", "objective": "Use dimensional analysis, tolerances, convergence checks and uncertainty propagation.", "study_actions": ["compare analytic and numeric solutions", "test convergence", "audit units"], "deliverable": "numerical_validation_report"},
            {"lesson_id": "reproducibility", "objective": "Make experiments reproducible through fixed inputs, environment records, seeds and explicit assumptions.", "study_actions": ["rerun reference examples", "record environment", "compare independent implementations"], "deliverable": "reproducible_experiment"},
        ],
    },
    {
        "blueprint_id": "bio_chemistry",
        "domain": "biology_and_chemistry",
        "title": "Bioinformatics, chemistry and molecular simulation",
        "brain_ids": ["ac_science", "ac_research"],
        "source_ids": ["biopython", "rdkit", "openmm"],
        "lessons": [
            {"lesson_id": "biological_data", "objective": "Validate sequence formats, identifiers, annotations and biological provenance.", "study_actions": ["parse reference datasets", "check identifier consistency", "compare curated records"], "deliverable": "bioinformatics_validation"},
            {"lesson_id": "molecular_methods", "objective": "Understand molecular representations, descriptors and simulation assumptions without overstating predictive certainty.", "study_actions": ["inspect molecular encodings", "reproduce a documented descriptor", "audit simulation parameters"], "deliverable": "molecular_method_report"},
        ],
    },
    {
        "blueprint_id": "robotics_edge",
        "domain": "robotics_and_edge",
        "title": "Robotics, embodied agents and edge inference",
        "brain_ids": ["ac_execution", "ac_vision", "ac_science"],
        "source_ids": ["executorch", "llama_cpp", "opencv", "pytorch"],
        "lessons": [
            {"lesson_id": "robotics_interfaces", "objective": "Study sensor, actuator, message and control-loop boundaries with explicit safety states.", "study_actions": ["map message contracts", "simulate sensor faults", "test emergency stop paths"], "deliverable": "robotics_interface_spec"},
            {"lesson_id": "edge_constraints", "objective": "Optimize latency, memory, quantization and energy while measuring quality loss.", "study_actions": ["benchmark target hardware", "compare quantization levels", "test offline behavior"], "deliverable": "edge_performance_report"},
        ],
    },
    {
        "blueprint_id": "cad_3d_design",
        "domain": "cad_and_3d",
        "title": "CAD, 3D design and spatial workflows",
        "brain_ids": ["ac_science", "ac_media", "ac_execution"],
        "source_ids": ["blender", "freecad"],
        "lessons": [
            {"lesson_id": "geometry_constraints", "objective": "Represent geometry parametrically and validate dimensions, constraints and topology.", "study_actions": ["inspect parametric models", "test constraint changes", "check mesh validity"], "deliverable": "geometry_validation_suite"},
            {"lesson_id": "workflow_automation", "objective": "Automate repeatable design operations with checkpoints and reversible changes.", "study_actions": ["record reproducible workflows", "test invalid parameters", "compare exported artifacts"], "deliverable": "design_automation_spec"},
        ],
    },
    {
        "blueprint_id": "evaluation_security",
        "domain": "evaluation_and_security",
        "title": "Model evaluation, robustness and defensive security",
        "brain_ids": ["ac_reasoning", "ac_code", "ac_research", "ac_execution"],
        "source_ids": ["lm_eval", "inspect_ai", "hf_evaluate"],
        "lessons": [
            {"lesson_id": "benchmark_design", "objective": "Build held-out, contamination-aware evaluations and report task-level uncertainty.", "study_actions": ["define evaluation protocols", "test data leakage", "compare repeated runs"], "deliverable": "benchmark_protocol"},
            {"lesson_id": "security_review", "objective": "Track advisories, threat models, vulnerable versions and mitigations; never turn vulnerability research into unauthorized exploitation.", "study_actions": ["review official advisories", "map affected version ranges", "write defensive regression tests"], "deliverable": "security_advisory_record"},
            {"lesson_id": "robustness", "objective": "Test prompt injection, malformed inputs, data leakage and unsafe tool requests using controlled test fixtures.", "study_actions": ["create adversarial test cases", "verify isolation", "measure false positives and false negatives"], "deliverable": "robustness_test_report"},
        ],
    },
    {
        "blueprint_id": "persistent_agent_memory",
        "domain": "retrieval_and_memory",
        "title": "Persistent agent identity, memory and experiential consolidation",
        "brain_ids": ["ac_memory", "ac_research", "ac_strategy"],
        "source_ids": ["letta_code"],
        "lessons": [
            {"lesson_id": "agent_owned_memory", "objective": "Study durable agent-owned memory, identity boundaries and retrieval of prior experience without conflating memory with the active context window.", "study_actions": ["map memory layers and lifecycle", "compare in-context and on-demand memory", "design a compact memory index"], "deliverable": "persistent_memory_architecture"},
            {"lesson_id": "experience_consolidation", "objective": "Evaluate background reflection and consolidation while preserving provenance, contradiction handling and reviewable changes.", "study_actions": ["simulate duplicate and conflicting memories", "propose consolidation diffs", "test rollback and version history"], "deliverable": "memory_consolidation_eval"},
            {"lesson_id": "locality_and_privacy", "objective": "Separate local memory operation from hosted services and prevent secrets or sensitive data from entering durable memory.", "study_actions": ["trace local and cloud dependencies", "test secret redaction", "verify offline failure behavior"], "deliverable": "memory_privacy_and_locality_report"},
        ],
    },
    {
        "blueprint_id": "software_execution_agents",
        "domain": "software",
        "title": "Repository-level software agents and verified execution",
        "brain_ids": ["ac_execution", "ac_code", "ac_reasoning"],
        "source_ids": ["openhands_core"],
        "lessons": [
            {"lesson_id": "repository_workflow", "objective": "Study end-to-end issue-to-change workflows with explicit plans, repository inspection, bounded edits and evidence-backed completion.", "study_actions": ["trace issue-to-patch workflows", "record tool input/output contracts", "compare task completion evidence"], "deliverable": "repository_agent_workflow_spec"},
            {"lesson_id": "execution_isolation", "objective": "Design least-privilege execution with disposable workspaces, network restrictions, resource budgets and explicit approval gates.", "study_actions": ["inspect sandbox boundaries", "test filesystem and network denial", "simulate malicious repository instructions"], "deliverable": "execution_sandbox_acceptance_suite"},
            {"lesson_id": "test_and_repair", "objective": "Require reproducible tests, logs, regression checks and truthful reporting before accepting code changes.", "study_actions": ["reproduce seeded failures", "verify patches against regression tests", "measure false-success reports"], "deliverable": "verified_code_change_protocol"},
        ],
    })

def list_blueprints(*, brain_id=None, domain=None):
    """Return defensive copies filtered by specialist brain and/or domain."""
    if brain_id is not None and (not isinstance(brain_id, str) or not brain_id.strip()):
        raise ValueError("invalid_brain_id")
    if domain is not None and (not isinstance(domain, str) or not domain.strip()):
        raise ValueError("invalid_domain")
    results = []
    for item in _BLUEPRINTS:
        if brain_id and brain_id not in item["brain_ids"]:
            continue
        if domain and domain.lower() != item["domain"]:
            continue
        results.append({
            **item,
            "brain_ids": list(item["brain_ids"]),
            "source_ids": list(item["source_ids"]),
            "lessons": [dict(lesson, study_actions=list(lesson["study_actions"])) for lesson in item["lessons"]],
            "status": "study_plan_only_not_ingested",
        })
    return results
