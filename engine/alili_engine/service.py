"""Application service coordinating the independent AC engine components."""

import sqlite3
from contextlib import closing

from .brains import BrainRegistry, BrainRouter
from .master_orchestrator import ACMasterOrchestrator
from .evolution import ACEvolutionEngine
from .knowledge import KnowledgeStore
from .model import ModelNotConfigured
from .models import ModelRegistry
from .ecosystem import EcosystemRegistry
from .provider_catalog import ProviderCatalog
from .cloud_adapter import ACCloudAdapter
from .study_blueprints import list_blueprints
from .study import UniversalStudyEngine
from .connectors import UniversalSourceConnector
from .links import KnowledgeLinkGraph
from .planner import TaskPlanner
from .policy import FreePolicyGate
from .registry import CapabilityRegistry
from .store import TaskStore
from .training import TrainingStore, training_policy
from .training_runtime import training_preflight
from .observatory import AICapabilityObservatory
from .execution_sandbox import ACExecutionSandbox
from .library_foundry import LibraryFoundry
from .license_intelligence import LicenseIntelligence
from .knowledge_scout import KnowledgeScout
from .knowledge_scout_navigator import KnowledgeScoutNavigator


class EngineService:
    def __init__(self, store: TaskStore, registry=None, planner=None, policy=None,
                 model_client=None, brain_registry=None, knowledge_store=None, training_store=None,
                 model_registry=None, ecosystem_registry=None, provider_catalog=None, cloud_adapter=None, execution_sandbox=None, library_foundry=None):
        self.store = store
        self.registry = registry or CapabilityRegistry()
        self.planner = planner or TaskPlanner()
        self.policy = policy or FreePolicyGate()
        self.model_client = model_client
        self.brain_registry = brain_registry or BrainRegistry()
        self.brain_router = BrainRouter(self.brain_registry)
        self.master = ACMasterOrchestrator(self.brain_registry)
        self.evolution = ACEvolutionEngine(store.database_path)
        self.knowledge = knowledge_store or KnowledgeStore(store.database_path)
        self.training = training_store or TrainingStore(store.database_path)
        self.models = model_registry or ModelRegistry()
        self.ecosystem = ecosystem_registry or EcosystemRegistry()
        self.providers = provider_catalog or ProviderCatalog()
        self.cloud = cloud_adapter or ACCloudAdapter(store.database_path, self.providers)
        self.study = UniversalStudyEngine(store.database_path, self.ecosystem, self.knowledge)
        self.knowledge.set_source_validator(self._knowledge_source_is_reviewable)
        self.connectors = UniversalSourceConnector(self.ecosystem)
        self.links = KnowledgeLinkGraph(store.database_path)
        self.ai_observatory = AICapabilityObservatory(store.database_path)
        self.execution = execution_sandbox or ACExecutionSandbox()
        self.libraries = library_foundry or LibraryFoundry(store.database_path)
        self.license_intelligence = LicenseIntelligence()
        self.knowledge_scout = KnowledgeScout(store.database_path)
        self.knowledge_scout_navigator = KnowledgeScoutNavigator(self.knowledge_scout, self.connectors)

    def capabilities(self) -> dict:
        return {"policy": "free_first_no_paid_fallback", "capabilities": self.registry.all()}

    def brains(self) -> dict:
        return {"routing_mode": "master_multi_brain_planning", "execution_enabled": False,
                "coordinator": "AC Master", "brains": self.brain_registry.all()}

    def plan_brains(self, objective: str, *, requested_brains=None, max_brains: int = 6) -> dict:
        return self.master.plan(objective, requested_brains=requested_brains, max_brains=max_brains)

    def route(self, task_type: str) -> dict:
        return self.brain_router.route(task_type).to_dict()

    def model_family(self) -> dict:
        return self.models.family()

    def list_models(self) -> list[dict]:
        return self.models.all()

    def get_model(self, model_id: str) -> dict | None:
        model = self.models.get(model_id)
        return model.to_dict() if model else None

    def training_preflight(self, **kwargs) -> dict:
        return training_preflight(model_registry=self.models, **kwargs)

    def learning_blueprints(self, *, brain_id=None, domain=None) -> list[dict]:
        return list_blueprints(brain_id=brain_id, domain=domain)

    def ai_capabilities(self, *, category=None, query=None, limit=100) -> list[dict]:
        return self.ai_observatory.catalog(category=category, query=query, limit=limit)

    def ai_capability_studies(self, *, capability_id=None, limit=50) -> list[dict]:
        return self.ai_observatory.list_studies(capability_id=capability_id, limit=limit)

    def record_ai_capability_study(self, **kwargs) -> dict:
        return self.ai_observatory.record_study(**kwargs)

    def ai_response_style(self) -> dict:
        return self.ai_observatory.response_style_policy()

    def evaluate_response_style(self, text: str) -> dict:
        return self.ai_observatory.evaluate_response(text)

    def provider_catalog(self, *, category=None, query=None, status=None, limit=100) -> list[dict]:
        return self.providers.list(category=category, query=query, status=status, limit=limit)

    def provider_detail(self, provider_id: str) -> dict | None:
        return self.providers.get(provider_id)

    def provider_summary(self) -> dict:
        return self.providers.summary()

    def license_intelligence_status(self) -> dict:
        return {"available": True, "version": "1.0.0", "automatic_approval": False,
                "automatic_installation": False, "default_admission_status": "quarantined"}

    def analyze_dependency_licenses(self, dependency_report: dict) -> dict:
        return self.license_intelligence.analyze(dependency_report)

    def library_summary(self) -> dict:
        return self.libraries.summary()

    def library_catalog(self, **kwargs) -> list[dict]:
        return self.libraries.list(**kwargs)

    def library_detail(self, library_id: str) -> dict | None:
        return self.libraries.get(library_id)

    def register_library(self, **kwargs) -> dict:
        return self.libraries.register(**kwargs)

    def review_library(self, library_id: str, **kwargs) -> dict:
        return self.libraries.review(library_id, **kwargs)

    def execution_status(self) -> dict:
        return self.execution.status()

    def execute_python(self, code: str, *, input_text: str = "") -> dict:
        return self.execution.run(code, input_text=input_text)

    def cloud_status(self) -> dict:
        return self.cloud.status()

    def cloud_plan(self, task: str, *, units: int = 1) -> dict:
        return self.cloud.plan(task, units=units)

    def reserve_cloud_capacity(self, task: str, *, units: int = 1) -> dict:
        return self.cloud.reserve(task, units=units)

    def ecosystem_catalog(self, *, domain=None, query=None, limit=100) -> list[dict]:
        return self.ecosystem.list(domain=domain, query=query, limit=limit)

    def ecosystem_source(self, source_id: str) -> dict | None:
        return self.ecosystem.get(source_id)

    def ecosystem_policy(self) -> dict:
        return self.ecosystem.policy()

    def ecosystem_summary(self) -> dict:
        return self.ecosystem.summary()

    def fetch_source_document(self, source_id: str, artifact_url: str | None = None, *,
                              if_none_match: str | None = None,
                              if_modified_since: str | None = None) -> dict:
        fetched = self.connectors.fetch(source_id, artifact_url,
                                        if_none_match=if_none_match,
                                        if_modified_since=if_modified_since)
        if fetched.get("not_modified"):
            return {"not_modified": True, "source_id": source_id,
                    "artifact_url": fetched["artifact_url"],
                    "etag": fetched.get("etag"),
                    "last_modified": fetched.get("last_modified"),
                    "retrieved_at": fetched["retrieved_at"]}
        with closing(sqlite3.connect(self.store.database_path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            evidence = self.study.add_evidence(
                source_id=source_id, title=fetched["title"], content=fetched["content"],
                artifact_url=fetched["artifact_url"], version=fetched["version"],
                license_status="review_required", connection=db)
            link = self.links.add(
                source_type="source", source_id=source_id, relation="documents",
                target_type="evidence", target_id=evidence["evidence_id"],
                metadata={"sha256": fetched["sha256"], "retrieved_at": fetched["retrieved_at"],
                          "etag": fetched["etag"], "last_modified": fetched["last_modified"],
                          "content_type": fetched["content_type"]}, connection=db)
        return {"evidence": evidence, "link": link, "fetch": {
            key: fetched[key] for key in ("retrieved_at", "content_type", "sha256",
                                          "etag", "last_modified", "redirect_count")}}

    def _node_exists(self, node_type: str, node_id: str) -> bool:
        if node_type == "source":
            return self.ecosystem.get(node_id) is not None
        if node_type == "evidence":
            return self.study.get_evidence(node_id) is not None
        if node_type == "session":
            return self.study.get_session(node_id) is not None
        if node_type == "knowledge":
            return self.knowledge.get(node_id) is not None
        if node_type == "brain":
            return self.brain_registry.get(node_id) is not None
        return False

    def create_link(self, **kwargs) -> dict:
        for endpoint in ("source", "target"):
            node_type = kwargs.get(endpoint + "_type")
            node_id = kwargs.get(endpoint + "_id")
            if not self._node_exists(node_type, node_id):
                raise ValueError(f"link_{endpoint}_node_not_found")
        return self.links.add(**kwargs)

    def list_links(self, **kwargs) -> list[dict]:
        return self.links.list(**kwargs)

    def add_study_evidence(self, **kwargs) -> dict:
        with closing(sqlite3.connect(self.store.database_path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            evidence = self.study.add_evidence(**kwargs, connection=db)
            self.links.add(source_type="source", source_id=evidence["source_id"],
                           relation="documents", target_type="evidence",
                           target_id=evidence["evidence_id"],
                           metadata={"sha256": evidence["sha256"]}, connection=db)
        return evidence

    def get_study_evidence(self, evidence_id: str) -> dict | None:
        return self.study.get_evidence(evidence_id)

    def list_study_evidence(self, **kwargs) -> list[dict]:
        return self.study.list_evidence(**kwargs)

    def create_study_session(self, **kwargs) -> dict:
        with closing(sqlite3.connect(self.store.database_path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            session = self.study.create_session(**kwargs, connection=db)
            for evidence_id in session["evidence_ids"]:
                self.links.add(source_type="evidence", source_id=evidence_id,
                               relation="studied_in", target_type="session",
                               target_id=session["session_id"], connection=db)
        return session

    def evaluate_study_session(self, session_id: str) -> dict:
        return self.study.evaluate_session(session_id)

    def propose_study_knowledge(self, session_id: str, **kwargs) -> dict:
        with closing(sqlite3.connect(self.store.database_path, timeout=10)) as db, db:
            db.row_factory = sqlite3.Row
            artifact = self.study.propose_knowledge(session_id, connection=db, **kwargs)
            self.links.add(source_type="session", source_id=session_id,
                           relation="proposes", target_type="knowledge",
                           target_id=artifact["artifact_id"], connection=db)
            session = self.study.get_session(session_id)
            for evidence_id in session["evidence_ids"]:
                self.links.add(source_type="evidence", source_id=evidence_id,
                               relation="supports", target_type="knowledge",
                               target_id=artifact["artifact_id"], connection=db)
            brain_id = artifact.get("origin_brain")
            if brain_id and self.brain_registry.get(brain_id):
                self.links.add(source_type="knowledge", source_id=artifact["artifact_id"],
                               relation="assigned_to", target_type="brain", target_id=brain_id,
                               connection=db)
        return artifact

    def get_study_session(self, session_id: str) -> dict | None:
        return self.study.get_session(session_id)

    def list_study_sessions(self, limit: int = 50) -> list[dict]:
        return self.study.list_sessions(limit)

    def training_policy(self) -> dict:
        return training_policy()

    def training_curricula(self) -> list[dict]:
        return self.training.curricula()

    def create_training_run(self, **kwargs) -> dict:
        return self.training.create_run(**kwargs)

    def get_training_run(self, run_id: str) -> dict | None:
        return self.training.get_run(run_id)

    def list_training_runs(self, limit: int = 50) -> list[dict]:
        return self.training.list_runs(limit)

    def evaluate_training_run(self, run_id: str, **kwargs) -> dict:
        return self.training.record_evaluation(run_id, **kwargs)

    def model_status(self) -> dict:
        if self.model_client is None:
            return {"configured": False, "kind": "local_loopback", "status": "unconfigured",
                    "fallback": "disabled", "reason": "local_model_not_configured"}
        return self.model_client.status()

    def generate(self, messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 512) -> dict:
        if self.model_client is None:
            raise ModelNotConfigured("local_model_not_configured")
        return self.model_client.generate(messages, temperature=temperature, max_tokens=max_tokens)

    def create_task(self, input_text: str) -> dict:
        task = self.store.create(input_text)
        self.store.transition(task["task_id"], "planning")
        plan = self.planner.plan(input_text)
        capability = self.registry.get(plan.capability_id)
        if capability is None:
            return self.store.transition(task["task_id"], "failed", error_code="capability_not_registered")
        plan_data = plan.to_dict()
        if capability.status != "available":
            plan_data["execution_status"] = "capability_not_implemented"
        return self.store.transition(task["task_id"], "planned", capability_id=plan.capability_id, plan=plan_data)

    def propose_knowledge(self, **artifact) -> dict:
        return self.knowledge.propose(**artifact)

    def _knowledge_source_is_reviewable(self, source_id: str) -> bool:
        evidence = self.study.get_evidence(source_id)
        return bool(evidence and evidence["status"] == "quarantined"
                    and evidence["license_status"] == "approved")

    def transition_knowledge(self, artifact_id: str, status: str, **review) -> dict:
        return self.knowledge.transition(artifact_id, status, **review)

    def get_knowledge(self, artifact_id: str) -> dict | None:
        return self.knowledge.get(artifact_id)

    def list_knowledge(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        return self.knowledge.list(status=status, limit=limit)


    def knowledge_scout_status(self) -> dict:
        return self.knowledge_scout.summary()

    def scout_sources(self, *, enabled=None, limit=100) -> list[dict]:
        return self.knowledge_scout.list_sources(enabled=enabled, limit=limit)

    def register_scout_source(self, **kwargs) -> dict:
        return self.knowledge_scout.register_source(**kwargs)

    def enable_scout_source(self, source_id: str, **kwargs) -> dict:
        return self.knowledge_scout.set_source_enabled(source_id, True, **kwargs)

    def enqueue_scout_job(self, **kwargs) -> dict:
        return self.knowledge_scout.enqueue(**kwargs)

    def scout_jobs(self, *, status=None, limit=50) -> list[dict]:
        return self.knowledge_scout.list_jobs(status=status, limit=limit)

    def propose_scout_knowledge(self, **kwargs) -> dict:
        return self.knowledge_scout.propose(**kwargs)

    def scout_proposals(self, *, status=None, limit=50) -> list[dict]:
        return self.knowledge_scout.list_proposals(status=status, limit=limit)

    def discover_scout_knowledge(self, **kwargs) -> dict:
        return self.knowledge_scout_navigator.discover(**kwargs)

    def get_task(self, task_id: str) -> dict | None:
        return self.store.get(task_id)

    def evolution_status(self) -> dict:
        return self.evolution.status()

    def evolution_proposals(self, *, status=None, limit=50) -> list[dict]:
        return self.evolution.list(status=status, limit=limit)

    def propose_evolution(self, **kwargs) -> dict:
        return self.evolution.propose(**kwargs)

    def review_evolution(self, proposal_id: str, **kwargs) -> dict:
        return self.evolution.review(proposal_id, **kwargs)
