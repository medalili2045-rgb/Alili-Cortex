"""Curated, license-aware catalog of public open ecosystem sources for AC.

Catalog entries are discovery targets, not endorsements or permission to copy/use
all artifacts. Model, dataset, code and documentation licenses must be reviewed
at the individual artifact/version before ingestion or training.
"""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EcosystemSource:
    source_id: str
    name: str
    organization: str
    url: str
    domains: tuple[str, ...]
    source_kind: str
    access_mode: str
    trust_class: str
    license_policy: str
    study_focus: tuple[str, ...]
    notes: str = ""

    def to_dict(self):
        value = asdict(self)
        value["domains"] = list(self.domains)
        value["study_focus"] = list(self.study_focus)
        value["adoption_status"] = "catalog_only_not_ingested"
        return value


# Official repositories and public research/data indexes selected as starting points.
# The catalog deliberately records license review as required; repository-level
# licenses do not automatically cover model weights, datasets, docs or dependencies.
_DEFAULT_SOURCES = (
    ("hf_transformers","Transformers","Hugging Face","https://github.com/huggingface/transformers",("language","vision","audio","multimodal","models"),"library","public_repo","official","verify_each_artifact",("architectures","tokenizers","model interfaces","examples")),
    ("hf_datasets","Datasets","Hugging Face","https://github.com/huggingface/datasets",("data","language","vision","audio","science"),"library","public_repo","official","verify_each_artifact",("dataset loaders","streaming","data validation","dataset cards")),
    ("hf_tokenizers","Tokenizers","Hugging Face","https://github.com/huggingface/tokenizers",("language","data"),"library","public_repo","official","verify_each_artifact",("tokenization","normalization","vocabulary")),
    ("hf_peft","PEFT","Hugging Face","https://github.com/huggingface/peft",("training","language","vision"),"library","public_repo","official","verify_each_artifact",("LoRA","adapter methods","parameter-efficient tuning")),
    ("hf_trl","TRL","Hugging Face","https://github.com/huggingface/trl",("training","alignment","language"),"library","public_repo","official","verify_each_artifact",("SFT","preference optimization","RL post-training")),
    ("hf_diffusers","Diffusers","Hugging Face","https://github.com/huggingface/diffusers",("image","video","audio","media"),"library","public_repo","official","verify_each_artifact",("diffusion","generation pipelines","fine-tuning")),
    ("hf_accelerate","Accelerate","Hugging Face","https://github.com/huggingface/accelerate",("training","compute"),"library","public_repo","official","verify_each_artifact",("distributed training","mixed precision","device placement")),
    ("hf_smolagents","smolagents","Hugging Face","https://github.com/huggingface/smolagents",("agents","automation","coding"),"library","public_repo","official","verify_each_artifact",("tool use","agent loops","sandbox integration")),
    ("hf_sentence_transformers","Sentence Transformers","Hugging Face","https://github.com/huggingface/sentence-transformers",("language","retrieval","search"),"library","public_repo","official","verify_each_artifact",("embeddings","reranking","semantic search")),
    ("hf_evaluate","Evaluate","Hugging Face","https://github.com/huggingface/evaluate",("evaluation","language","vision","audio"),"library","public_repo","official","verify_each_artifact",("metrics","comparative evaluation","reproducibility")),
    ("pytorch","PyTorch","PyTorch Foundation","https://github.com/pytorch/pytorch",("training","compute","science","vision"),"framework","public_repo","official","verify_each_artifact",("tensor computation","autograd","training","optimization")),
    ("torchtune","torchtune","Meta / PyTorch","https://github.com/meta-pytorch/torchtune",("training","language","multimodal"),"library","public_repo","official","verify_each_artifact",("fine-tuning recipes","model adaptation","training configs")),
    ("executorch","ExecuTorch","Meta / PyTorch","https://github.com/pytorch/executorch",("mobile","edge","inference"),"runtime","public_repo","official","verify_each_artifact",("on-device inference","quantization","deployment")),
    ("meta_faiss","Faiss","Meta AI Research","https://github.com/facebookresearch/faiss",("retrieval","search","data"),"library","public_repo","official","verify_each_artifact",("vector search","clustering","index evaluation")),
    ("meta_sam","Segment Anything","Meta AI Research","https://github.com/facebookresearch/segment-anything",("vision","image","media"),"model_and_code","public_repo","official","verify_code_and_checkpoint_separately",("segmentation","image annotation","visual reasoning")),
    ("google_jax","JAX","Google","https://github.com/jax-ml/jax",("training","compute","science","math"),"framework","public_repo","official","verify_each_artifact",("automatic differentiation","compilation","accelerator computation")),
    ("google_tensorflow","TensorFlow","Google","https://github.com/tensorflow/tensorflow",("training","compute","vision","audio"),"framework","public_repo","official","verify_each_artifact",("model training","deployment","data pipelines")),
    ("google_gemma","Gemma","Google DeepMind","https://github.com/google-deepmind/gemma",("language","models","multimodal"),"model_and_code","public_repo","official","model_terms_must_be_reviewed",("open-weight model research","inference","fine-tuning")),
    ("meta_muse_glimmer","Muse Glimmer","Meta AI","https://huggingface.co/blog/muse-glimmer",("language","vision","video","agents","multimodal","models"),"model_release","public_model_hub","official","verify_checkpoint_license_and_model_card",("local multimodal models","agentic use","video and image understanding")),
    ("openai_gpt_oss","gpt-oss","OpenAI","https://github.com/openai/gpt-oss",("language","reasoning","agents","models","inference"),"model_and_reference_tools","public_repo","official","Apache-2.0-plus-usage-policy-review",("open-weight reasoning","tool use","local inference","reference browser and python tools")),
    ("deepseek_r1","DeepSeek R1","DeepSeek","https://github.com/deepseek-ai/DeepSeek-R1",("language","reasoning","math","models"),"model_and_code","public_repo","official","model_terms_must_be_reviewed",("reasoning","distillation","training reports")),
    ("qwen","Qwen","Alibaba / Qwen Team","https://github.com/QwenLM",("language","code","vision","audio","models"),"model_family","public_repo","official","verify_each_model_card",("model architectures","multimodal methods","coding")),
    ("llama_cpp","llama.cpp","ggml-org","https://github.com/ggml-org/llama.cpp",("inference","edge","compute"),"runtime","public_repo","community","verify_each_artifact",("CPU inference","quantization","hardware backends")),
    ("vllm","vLLM","vLLM Project","https://github.com/vllm-project/vllm",("inference","serving","compute"),"runtime","public_repo","community","verify_each_artifact",("high-throughput inference","continuous batching","serving")),
    ("sglang","SGLang","SGLang Project","https://github.com/sgl-project/sglang",("inference","serving","agents"),"runtime","public_repo","community","verify_each_artifact",("structured generation","serving","agent execution")),
    ("ollama","Ollama","Ollama","https://github.com/ollama/ollama",("inference","local","edge"),"runtime","public_repo","official","verify_each_artifact",("local model management","model packaging","local API")),
    ("mlx","MLX","Apple","https://github.com/ml-explore/mlx",("compute","training","edge"),"framework","public_repo","official","verify_each_artifact",("Apple silicon","unified memory","local training")),
    ("docling","Docling","IBM","https://github.com/docling-project/docling",("documents","ocr","retrieval"),"library","public_repo","official","verify_each_artifact",("PDF parsing","document structure","tables","OCR")),
    ("llamaindex","LlamaIndex","LlamaIndex","https://github.com/run-llama/llama_index",("retrieval","agents","documents"),"framework","public_repo","community","verify_each_artifact",("RAG","connectors","document indexing")),
    ("langchain","LangChain","LangChain","https://github.com/langchain-ai/langchain",("agents","retrieval","automation"),"framework","public_repo","community","verify_each_artifact",("tool orchestration","retrieval","agent patterns")),
    ("haystack","Haystack","deepset","https://github.com/deepset-ai/haystack",("retrieval","documents","agents"),"framework","public_repo","community","verify_each_artifact",("search pipelines","RAG","evaluation")),
    ("qdrant","Qdrant","Qdrant","https://github.com/qdrant/qdrant",("retrieval","search","data"),"database","public_repo","official","verify_each_artifact",("vector database","filtering","hybrid search")),
    ("chroma","Chroma","Chroma","https://github.com/chroma-core/chroma",("retrieval","search","data"),"database","public_repo","official","verify_each_artifact",("embedding storage","retrieval","metadata filtering")),
    ("lm_eval","LM Evaluation Harness","EleutherAI","https://github.com/EleutherAI/lm-evaluation-harness",("evaluation","language","reasoning"),"evaluation","public_repo","community","verify_each_artifact",("benchmarking","task suites","reproducible evaluation")),
    ("inspect_ai","Inspect AI","UK AI Security Institute","https://github.com/UKGovernmentBEIS/inspect_ai",("evaluation","safety","agents"),"evaluation","public_repo","official","verify_each_artifact",("agent evaluations","security tests","scoring")),
    ("scipy","SciPy","SciPy Community","https://github.com/scipy/scipy",("science","math","engineering"),"library","public_repo","community","verify_each_artifact",("numerical methods","optimization","statistics")),
    ("sympy","SymPy","SymPy Development Team","https://github.com/sympy/sympy",("math","science","engineering"),"library","public_repo","community","verify_each_artifact",("symbolic mathematics","algebra","calculus")),
    ("scikit_learn","scikit-learn","scikit-learn","https://github.com/scikit-learn/scikit-learn",("data","science","statistics"),"library","public_repo","community","verify_each_artifact",("classical ML","preprocessing","model selection")),
    ("rdkit","RDKit","RDKit","https://github.com/rdkit/rdkit",("chemistry","science","biology"),"library","public_repo","community","verify_each_artifact",("cheminformatics","molecular descriptors","molecule processing")),
    ("biopython","Biopython","Biopython","https://github.com/biopython/biopython",("biology","science","medicine"),"library","public_repo","community","verify_each_artifact",("bioinformatics","sequence analysis","biological data")),
    ("openmm","OpenMM","OpenMM","https://github.com/openmm/openmm",("biology","chemistry","science"),"simulation","public_repo","community","verify_each_artifact",("molecular dynamics","simulation","biophysics")),
    ("opencv","OpenCV","OpenCV","https://github.com/opencv/opencv",("vision","image","video","robotics"),"library","public_repo","community","verify_each_artifact",("computer vision","image processing","video analysis")),
    ("whisper","Whisper","OpenAI","https://github.com/openai/whisper",("audio","language","media"),"model_and_code","public_repo","official","verify_code_and_weights_separately",("speech recognition","transcription","translation")),
    ("librosa","librosa","librosa","https://github.com/librosa/librosa",("audio","music","science"),"library","public_repo","community","verify_each_artifact",("audio analysis","features","music information retrieval")),
    ("blender","Blender","Blender Foundation","https://github.com/blender/blender",("3d","design","animation","engineering"),"application","public_repo","official","verify_each_artifact",("3D modeling","rendering","simulation","geometry")),
    ("freecad","FreeCAD","FreeCAD","https://github.com/FreeCAD/FreeCAD",("cad","engineering","design"),"application","public_repo","community","verify_each_artifact",("parametric CAD","mechanical design","geometry")),
    ("lerobot","LeRobot","Hugging Face","https://github.com/huggingface/lerobot",("robotics","vision","control"),"framework","public_repo","official","verify_each_artifact",("robot learning","imitation learning","robot datasets")),
    ("ros2","ROS 2","Open Robotics","https://github.com/ros2/ros2",("robotics","automation","engineering"),"framework","public_repo","community","verify_each_artifact",("robot middleware","simulation integration","robot applications")),
    ("letta_code","Letta Code","Letta","https://github.com/letta-ai/letta-code",("agents","memory","language","automation"),"agent_runtime","public_repo","official","Apache-2.0-code; exclude brand assets; verify dependencies and exact version",("persistent agent identity","git-backed memory filesystem","dreaming and memory consolidation","skills and subagents","local backend boundaries")),
    ("openhands_core","OpenHands","OpenHands","https://github.com/OpenHands/OpenHands",("agents","code","automation","evaluation"),"software_agent","public_repo","official","MIT outside separately licensed enterprise paths; inspect exact paths and dependencies",("repository-level coding agent","plan-act-observe-verify","sandboxed execution","tool permissions","test and repair loops")),
    ("openalex","OpenAlex","OurResearch","https://openalex.org",("research","science","education"),"research_index","public_api","community","check_api_terms_and_record_metadata",("scholarly works","authors","institutions","citations")),
    ("arxiv","arXiv","Cornell University","https://arxiv.org",("research","science","math","engineering"),"research_repository","public_api","official","check_article_license_individually",("preprints","papers","research metadata")),
    ("openml","OpenML","OpenML","https://www.openml.org",("data","science","statistics"),"dataset_hub","public_api","community","check_dataset_license_individually",("datasets","tasks","reproducible experiments")),
    ("europe_pmc","Europe PMC","EMBL-EBI","https://europepmc.org",("medicine","biology","science"),"research_index","public_api","official","check_full_text_license_individually",("biomedical literature","open access full text","metadata")),
    ("wikidata","Wikidata","Wikimedia Foundation","https://www.wikidata.org",("knowledge","geography","history","science"),"knowledge_graph","public_api","official","check_data_and_media_terms",("structured facts","entity relations","provenance")),
    ("unsloth","Unsloth","Unsloth AI","https://github.com/unslothai/unsloth",("training","models","language","vision"),"training_framework","public_repo","official","verify_model_dataset_and_dependency_terms",("memory-efficient fine-tuning","LoRA and QLoRA","training reproducibility")),
    ("llama_factory","LLaMA-Factory","hiyouga","https://github.com/hiyouga/LLaMA-Factory",("training","models","language","multimodal"),"training_framework","public_repo","community","verify_each_artifact",("supervised fine-tuning","preference optimization","multimodel training workflows")),
    ("deepspeed","DeepSpeed","Microsoft","https://github.com/microsoft/DeepSpeed",("training","compute","inference"),"training_framework","public_repo","official","verify_each_artifact",("distributed training","memory optimization","inference optimization")),
    ("cognee","Cognee","topoteretes","https://github.com/topoteretes/cognee",("agents","retrieval","data"),"knowledge_framework","public_repo","community","verify_each_artifact",("knowledge graph memory","data pipelines","retrieval and reasoning")),
    ("graphiti","Graphiti","getzep","https://github.com/getzep/graphiti",("agents","retrieval","data"),"knowledge_graph_framework","public_repo","community","verify_each_artifact",("temporal knowledge graphs","entity relationships","evolving agent memory")),
    ("ragflow","RAGFlow","InfiniFlow","https://github.com/infiniflow/ragflow",("retrieval","documents","search"),"rag_platform","public_repo","community","verify_each_artifact",("document parsing","grounded retrieval","citation-aware RAG")),
    ("comfyui","ComfyUI","ComfyUI","https://github.com/comfyanonymous/ComfyUI",("image","video","audio","media","automation"),"media_application","public_repo","community","verify_core_nodes_custom_nodes_models_and_workflows_separately",("node-based generative workflows","image and video pipelines","reproducible media graphs")),
    ("ffmpeg","FFmpeg","FFmpeg Project","https://github.com/FFmpeg/FFmpeg",("audio","video","media"),"media_framework","public_repo","official","review_build_configuration_and_external_codec_licenses",("media transcoding","audio video processing","stream and container handling")),
    ("piper_tts","Piper","OHF Voice","https://github.com/OHF-Voice/piper1-gpl",("audio","language","edge"),"speech_runtime","public_repo","community","review_gpl_code_and_each_voice_model_license_separately",("local text to speech","voice model packaging","offline speech synthesis")),
    ("sherpa_onnx","sherpa-onnx","k2-fsa","https://github.com/k2-fsa/sherpa-onnx",("audio","language","edge","inference"),"speech_runtime","public_repo","community","verify_each_artifact",("offline speech recognition","text to speech","keyword spotting")),
    ("krita","Krita","KDE","https://github.com/KDE/krita",("design","image","media"),"creative_application","public_repo","official","review_application_plugins_and_assets_separately",("digital painting","raster graphics","creative workflow automation")),
    ("n8n","n8n","n8n GmbH","https://github.com/n8n-io/n8n",("automation","agents","data"),"workflow_platform","public_repo","official","source_available_license_not_assumed_osi_open_source_review_terms",("workflow orchestration","service integrations","self-hosted automation")),
    ("playwright","Playwright","Microsoft","https://github.com/microsoft/playwright",("automation","code","evaluation"),"browser_automation_library","public_repo","official","verify_each_artifact",("browser automation","end-to-end testing","deterministic web interaction")),
    ("temporal","Temporal","Temporal Technologies","https://github.com/temporalio/temporal",("automation","compute","code"),"workflow_engine","public_repo","official","verify_each_artifact",("durable workflows","retries and recovery","long-running task orchestration")),
    ("langgraph","LangGraph","LangChain","https://github.com/langchain-ai/langgraph",("agents","automation","retrieval"),"agent_framework","public_repo","official","verify_each_artifact",("stateful agent graphs","human approval checkpoints","durable orchestration")),
    ("crewai","CrewAI","CrewAI","https://github.com/crewAIInc/crewAI",("agents","automation","code"),"multi_agent_framework","public_repo","official","verify_each_artifact",("role-based agent teams","task delegation","workflow orchestration")),
    ("goose","Goose","Block","https://github.com/block/goose",("agents","code","automation"),"agent_runtime","public_repo","official","verify_each_artifact_and_extension",("local-first agent workflows","tool integrations","developer automation")),
    ("browser_use","Browser Use","browser-use","https://github.com/browser-use/browser-use",("agents","automation","code"),"browser_agent_library","public_repo","community","verify_each_artifact",("browser agent interaction","web task automation","browser session controls")),
    ("jupyter","Jupyter","Project Jupyter","https://github.com/jupyter/notebook",("data","science","education","math"),"interactive_computing_application","public_repo","official","verify_each_artifact_and_notebook_content",("reproducible notebooks","interactive research","computational education")),
    ("duckdb","DuckDB","DuckDB Foundation","https://github.com/duckdb/duckdb",("data","science","statistics"),"analytical_database","public_repo","official","verify_each_artifact",("embedded analytics","SQL over local files","columnar data processing")),
    ("polars","Polars","pola.rs","https://github.com/pola-rs/polars",("data","science","statistics"),"dataframe_library","public_repo","community","verify_each_artifact",("lazy query optimization","columnar dataframes","large local datasets")),
    ("sagemath","SageMath","SageMath","https://github.com/sagemath/sage",("math","science","engineering"),"mathematics_platform","public_repo","community","review_component_licenses_and_optional_dependencies",("computer algebra","number theory","symbolic and numeric mathematics")),
    ("astropy","Astropy","Astropy Project","https://github.com/astropy/astropy",("science","math","data"),"scientific_library","public_repo","community","verify_each_artifact",("astronomy data","units and coordinates","scientific reproducibility")),
    ("openbabel","Open Babel","Open Babel","https://github.com/openbabel/openbabel",("chemistry","science","biology"),"scientific_library","public_repo","community","verify_each_artifact",("chemical file conversion","molecular formats","cheminformatics")),
    ("openscad","OpenSCAD","OpenSCAD","https://github.com/openscad/openscad",("cad","3d","engineering","design"),"cad_application","public_repo","community","verify_each_artifact",("script-based CAD","parametric geometry","reproducible 3D models")),
)

DOMAINS = (
    "agents","alignment","animation","audio","automation","biology","cad","chemistry",
    "code","compute","data","design","documents","3d","edge","education","engineering",
    "evaluation","geography","history","image","inference","language","math","media",
    "medicine","models","multimodal","music","robotics","safety","science","search",
    "statistics","training","video","vision"
)


class EcosystemRegistry:
    """Searchable metadata catalog; never downloads or executes a listed project."""

    def __init__(self, sources=None):
        entries = sources if sources is not None else self._defaults()
        self._sources = {}
        for source in entries:
            if source.source_id in self._sources:
                raise ValueError(f"duplicate_ecosystem_source:{source.source_id}")
            if not source.url.startswith(("https://", "http://")):
                raise ValueError(f"invalid_ecosystem_source_url:{source.source_id}")
            self._sources[source.source_id] = source

    @staticmethod
    def _defaults():
        return tuple(EcosystemSource(
            source_id=row[0], name=row[1], organization=row[2], url=row[3],
            domains=row[4], source_kind=row[5], access_mode=row[6],
            trust_class=row[7], license_policy=row[8], study_focus=row[9],
            notes="Public discovery target. Verify current maintenance, exact version, dependencies and artifact-specific terms before use."
        ) for row in _DEFAULT_SOURCES)

    def list(self, *, domain=None, query=None, limit=100):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("limit_must_be_between_1_and_500")
        if domain is not None and domain not in DOMAINS:
            raise ValueError("unknown_ecosystem_domain")
        needle = query.strip().casefold() if isinstance(query, str) else ""
        results = []
        for source in self._sources.values():
            if domain and domain not in source.domains:
                continue
            haystack = " ".join((source.source_id, source.name, source.organization,
                                 source.source_kind, *source.domains, *source.study_focus)).casefold()
            if needle and needle not in haystack:
                continue
            results.append(source.to_dict())
        return results[:limit]

    def get(self, source_id):
        source = self._sources.get(source_id) if isinstance(source_id, str) else None
        return source.to_dict() if source else None

    def policy(self):
        return {
            "mode": "hybrid_discovery_and_local_study",
            "execution": "metadata_and_documentation_study_only",
            "automatic_install": False,
            "automatic_code_execution": False,
            "automatic_weight_training": False,
            "paid_services": "prohibited",
            "network_policy": "public_sources_only; no paid API, credentialed SaaS, or hidden quota dependency",
            "stages": [
                {"id":"discover","description":"Discover official repositories, documentation, model cards, dataset cards, papers and release notes."},
                {"id":"identify","description":"Resolve exact project, version, owner, source URL, commit and artifact identity."},
                {"id":"license_gate","description":"Review code, model-weight, dataset, documentation and dependency licenses separately; quarantine unknown or incompatible terms."},
                {"id":"collect","description":"Collect metadata and permitted documentation/source text; never mirror an entire repository by default."},
                {"id":"parse","description":"Extract APIs, concepts, algorithms, examples, constraints, citations and version relationships."},
                {"id":"deduplicate","description":"Normalize, hash, deduplicate and retain source-level provenance and timestamps."},
                {"id":"study","description":"Create domain-specific concept maps, dependency graphs, worked examples and cross-source comparisons."},
                {"id":"verify","description":"Cross-check against independent sources, tests, benchmarks and versioned documentation."},
                {"id":"sandbox","description":"Try code or experiments only in isolated, resource-limited sandboxes with no secrets or production access."},
                {"id":"publish","description":"Share validated knowledge with AC brains; require review before production code, model-weight or policy changes."}
            ],
            "knowledge_quality": {
                "required_provenance": ["source_url","source_version_or_commit","retrieved_at","artifact_hash","license_review_status"],
                "confidence_inputs": ["source_authority","version_freshness","independent_agreement","test_results","benchmark_reproducibility"],
                "unknown_license_action": "quarantine",
                "conflicting_sources_action": "preserve_both_and_flag_for_review",
                "training_data_rule": "A public URL or downloadable file is not proof that it may be used for training."
            },
            "scope": list(DOMAINS),
            "catalog_size": len(self._sources),
            "current_ingestion_status": "catalog_only_no_external_content_ingested"
        }

    def summary(self):
        counts = {}
        for source in self._sources.values():
            for domain in source.domains:
                counts[domain] = counts.get(domain, 0) + 1
        return {"source_count": len(self._sources), "domains": counts,
                "catalog_status": "curated_seed_catalog",
                "content_ingested": False}
