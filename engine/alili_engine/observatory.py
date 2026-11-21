"""AC's independent, free-first observatory for external AI capabilities.

This module studies public product documentation and capability patterns. It
never imports third-party weights, claims ownership, or enables paid providers.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone


DEFAULT_CAPABILITIES = (
    {
        "id": "google_ai_studio",
        "name": "Google AI Studio",
        "category": "app_building_and_model_experimentation",
        "url": "https://aistudio.google.com/",
        "capabilities": ["prompt_experimentation", "model_comparison", "multimodal_prototyping",
                        "app_building", "tool_and_function_calling", "api_workflows"],
        "study_focus": ["prototype_flow", "prompt_design", "evaluation", "exportable_app_patterns"],
        "access_note": "Product access and model/API quotas vary; verify before runtime use.",
    },
    {
        "id": "google_nano_banana",
        "name": "Google Nano Banana",
        "category": "image_generation_and_editing",
        "url": "https://deepmind.google/models/gemini-image/",
        "capabilities": ["instruction_following", "image_editing", "multi_image_fusion",
                        "visual_consistency", "text_rendering", "world_knowledge_grounding"],
        "study_focus": ["edit_instruction_patterns", "identity_consistency", "composition_control",
                        "multilingual_text_rendering", "visual_quality_evaluation"],
        "access_note": "Reference study does not grant model access; current Nano Banana API access may require a paid API key, so runtime use is excluded from the free-only path.",
    },
    {
        "id": "google_gemini",
        "name": "Google Gemini",
        "category": "multimodal_models_and_agents",
        "url": "https://ai.google.dev/gemini-api/docs",
        "capabilities": ["reasoning", "multimodal_input", "structured_output",
                        "tool_calling", "long_context", "live_interaction"],
        "study_focus": ["task_decomposition", "multimodal_routing", "tool_safety", "evaluation"],
        "access_note": "Model availability, free quota and billing requirements are model-specific.",
    },
    {
        "id": "github_copilot",
        "name": "GitHub Copilot",
        "category": "software_engineering_assistant",
        "url": "https://docs.github.com/en/copilot",
        "capabilities": ["inline_code_completion", "codebase_questions", "repository_context",
                        "multi_step_coding_agent", "code_review", "test_generation",
                        "issue_and_pull_request_workflows", "custom_instructions",
                        "agent_skills", "mcp_tool_integration", "terminal_and_ide_workflows"],
        "study_focus": ["repository_mapping", "change_planning", "patch_review",
                        "test_first_workflows", "secure_tool_execution", "agent_delegation",
                        "repository_instructions", "human_approval_gates"],
        "access_note": "Copilot Free exists, but feature availability depends on plan, client and policy; do not assume advanced agent features are free.",
    },
    {
        "id": "github_copilot_sdk",
        "name": "GitHub Copilot SDK",
        "category": "agent_development",
        "url": "https://github.com/github/copilot-sdk",
        "capabilities": ["agent_embedding", "tool_orchestration", "custom_copilot_workflows"],
        "study_focus": ["sdk_architecture", "session_lifecycle", "tool_contracts", "license_and_runtime_review"],
        "access_note": "Evaluate SDK maturity, license and service dependencies before adoption.",
    },
    {
        "id": "github_models",
        "name": "GitHub Models",
        "category": "model_catalog_and_evaluation",
        "url": "https://github.com/marketplace/models",
        "capabilities": ["model_discovery", "prompt_testing", "comparative_evaluation"],
        "study_focus": ["model_metadata", "rate_limits", "quota_policy", "evaluation_design"],
        "access_note": "Availability and quotas can change; no paid fallback is permitted.",
    },
    {
        "id": "openhands",
        "name": "OpenHands",
        "category": "software_engineering_agents",
        "url": "https://github.com/All-Hands-AI/OpenHands",
        "capabilities": ["repository_tasks", "sandboxed_execution", "agent_tools", "software_testing"],
        "study_focus": ["sandbox_boundaries", "task_planning", "execution_trace", "verification"],
        "access_note": "Prefer local/open-source components; inspect dependencies and license.",
    },
    {
        "id": "letta",
        "name": "Letta",
        "category": "agent_memory",
        "url": "https://github.com/letta-ai/letta",
        "capabilities": ["persistent_agent_memory", "memory_management", "agent_state"],
        "study_focus": ["memory_lifecycle", "retrieval", "state_versioning", "privacy_controls"],
        "access_note": "Study architecture separately from adopting its runtime.",
    },
    {
        "id": "huggingface_transformers",
        "name": "Hugging Face Transformers",
        "category": "open_model_runtime",
        "url": "https://github.com/huggingface/transformers",
        "capabilities": ["model_loading", "inference", "training_interfaces", "multimodal_models"],
        "study_focus": ["model_compatibility", "license_metadata", "hardware_requirements", "reproducibility"],
        "access_note": "Each model has its own license and hardware requirements.",
    },
    {
        "id": "huggingface_peft",
        "name": "Hugging Face PEFT",
        "category": "parameter_efficient_training",
        "url": "https://github.com/huggingface/peft",
        "capabilities": ["lora", "qlora_related_workflows", "adapter_training"],
        "study_focus": ["adapter_isolation", "training_preflight", "evaluation", "rollback"],
        "access_note": "Training requires compatible hardware and individually licensed base models.",
    },
    {
        "id": "pytorch",
        "name": "PyTorch",
        "category": "machine_learning_framework",
        "url": "https://github.com/pytorch/pytorch",
        "capabilities": ["tensor_computation", "model_training", "inference", "accelerator_support"],
        "study_focus": ["resource_profiling", "deterministic_experiments", "training_safety"],
        "access_note": "Open-source framework; hardware and deployment costs are separate.",
    },
    {
        "id": "comfyui",
        "name": "ComfyUI",
        "category": "generative_media_workflows",
        "url": "https://github.com/comfyanonymous/ComfyUI",
        "capabilities": ["node_graphs", "image_workflows", "model_composition", "local_generation"],
        "study_focus": ["workflow_graphs", "node_contracts", "model_provenance", "resource_limits"],
        "access_note": "Individual checkpoints and custom nodes have separate licenses and risks.",
    },
    {
        "id": "llamaindex",
        "name": "LlamaIndex",
        "category": "knowledge_retrieval",
        "url": "https://github.com/run-llama/llama_index",
        "capabilities": ["document_ingestion", "retrieval", "indexing", "agent_data_connectors"],
        "study_focus": ["source_provenance", "retrieval_quality", "chunking", "data_permissions"],
        "access_note": "Review package and connector licenses and optional hosted service requirements.",
    },
    {
        "id": "qdrant",
        "name": "Qdrant",
        "category": "vector_search",
        "url": "https://github.com/qdrant/qdrant",
        "capabilities": ["vector_search", "hybrid_retrieval", "metadata_filtering"],
        "study_focus": ["index_tradeoffs", "filter_security", "local_deployment"],
        "access_note": "Prefer self-hosted open-source deployment where suitable.",
    },
    {
        "id": "openai_gpt_oss",
        "name": "OpenAI gpt-oss",
        "category": "open_weight_models",
        "url": "https://github.com/openai/gpt-oss",
        "capabilities": ["open_weight_inference", "reasoning", "local_deployment"],
        "study_focus": ["weight_license", "hardware_fit", "benchmarking", "runtime_compatibility"],
        "access_note": "Check the exact model license and hardware needs; do not assume every OpenAI model is open-weight.",
    },
)


RESPONSE_STYLE_POLICY = {
    "id": "ac_clear_response_v1",
    "name": "AC Clear Intelligence & Response Style",
    "principles": [
        "Answer the actual question first; put the useful conclusion before background.",
        "Use plain, natural language and explain necessary technical terms briefly.",
        "Match answer length to the task; do not confuse brevity with missing essential detail.",
        "Avoid repetition, filler, performative complexity and unnecessary headings.",
        "Use examples only when they make the idea easier to understand.",
        "Ask one focused clarification only when an essential detail is missing.",
        "Separate verified facts, estimates and unknowns; never invent capabilities or results.",
        "For actions, state what was actually completed and what remains unverified.",
        "Offer deeper detail when the user asks or when safety and correctness require it.",
    ],
    "evaluation_boundary": "Structural clarity heuristics only; factual correctness and semantic quality require separate evaluation.",
}


class AICapabilityObservatory:
    """Catalog, study ledger and explainable response-style checks."""

    def __init__(self, database_path: str):
        self.database_path = database_path
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS ai_capability_studies (
                    study_id TEXT PRIMARY KEY,
                    capability_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    license_status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_ai_studies_capability ON ai_capability_studies(capability_id, created_at)")

    @staticmethod
    def catalog(query: str | None = None, category: str | None = None, limit: int = 100):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit_must_be_1_to_200")
        items = [dict(item) for item in DEFAULT_CAPABILITIES]
        if category:
            items = [item for item in items if item["category"] == category]
        if query:
            needle = query.strip().lower()
            if not needle:
                raise ValueError("query_must_not_be_blank")
            items = [item for item in items if needle in json.dumps(item, ensure_ascii=False).lower()]
        return items[:limit]

    @staticmethod
    def get_capability(capability_id: str):
        for item in DEFAULT_CAPABILITIES:
            if item["id"] == capability_id:
                return dict(item)
        return None

    def record_study(self, capability_id: str, title: str, notes: str, source_url: str):
        import hashlib
        if self.get_capability(capability_id) is None:
            raise ValueError("unknown_ai_capability")
        for value, field, maximum in ((title, "title", 240), (notes, "notes", 24000),
                                      (source_url, "source_url", 2048)):
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"invalid_{field}")
        item = {
            "study_id": "aistudy_" + uuid.uuid4().hex,
            "capability_id": capability_id,
            "title": title.strip(),
            "notes": notes.strip(),
            "source_url": source_url.strip(),
            "content_sha256": hashlib.sha256(notes.strip().encode("utf-8")).hexdigest(),
            "status": "quarantined",
            "license_status": "review_required",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._connect() as db:
            db.execute("""
                INSERT INTO ai_capability_studies
                (study_id, capability_id, title, notes, source_url, content_sha256,
                 status, license_status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(item.values()))
        return item

    def list_studies(self, capability_id: str | None = None, limit: int = 50):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("limit_must_be_1_to_200")
        with self._connect() as db:
            if capability_id:
                rows = db.execute(
                    "SELECT * FROM ai_capability_studies WHERE capability_id=? ORDER BY created_at DESC LIMIT ?",
                    (capability_id, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM ai_capability_studies ORDER BY created_at DESC LIMIT ?",
                    (limit,)).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def response_style_policy():
        return dict(RESPONSE_STYLE_POLICY)

    @staticmethod
    def evaluate_response(text: str):
        if not isinstance(text, str) or not text.strip():
            raise ValueError("response_must_not_be_empty")
        content = text.strip()
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        words = content.split()
        repeated_lines = len(lines) - len(set(lines))
        checks = {
            "non_empty": bool(content),
            "reasonable_sentence_length": all(len(sentence.split()) <= 45
                                               for sentence in content.replace("!", ".").replace("?", ".").split(".")
                                               if sentence.strip()),
            "limited_repetition": repeated_lines == 0,
            "no_excessive_length": len(words) <= 900,
            "structured_when_long": len(words) <= 180 or len(lines) >= 3,
        }
        score = round(sum(checks.values()) / len(checks), 2)
        suggestions = []
        if not checks["reasonable_sentence_length"]:
            suggestions.append("Break long sentences into shorter, clearer sentences.")
        if not checks["limited_repetition"]:
            suggestions.append("Remove repeated lines or restate each idea only once.")
        if not checks["no_excessive_length"]:
            suggestions.append("Lead with a short conclusion and move secondary detail behind it.")
        if not checks["structured_when_long"]:
            suggestions.append("Add short paragraphs or headings to make the long answer easier to scan.")
        return {
            "profile": "ac_clear_response_v1",
            "structural_score": score,
            "checks": checks,
            "suggestions": suggestions,
            "semantic_accuracy": "not_evaluated",
            "factual_grounding": "not_evaluated",
            "human_review_required": True,
        }
