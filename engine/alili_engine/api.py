"""Authenticated standard-library HTTP API for the independent AC engine."""

import hmac
import json
import logging
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .model import LocalModelClient, LocalModelError, ModelNotConfigured
from .service import EngineService
from .store import TaskStore
from .execution_sandbox import ExecutionRejected

MAX_BODY_BYTES = 128 * 1024
MAX_INPUT_CHARS = 16_000
MAX_CONCURRENT_REQUESTS = 16
REQUEST_TIMEOUT_SECONDS = 15
LOGGER = logging.getLogger(__name__)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    """Threaded server with a hard cap on active request handlers."""

    daemon_threads = True
    block_on_close = False
    request_queue_size = 32

    def __init__(self, *args, max_workers=MAX_CONCURRENT_REQUESTS, **kwargs):
        super().__init__(*args, **kwargs)
        self._request_slots = threading.BoundedSemaphore(max_workers)

    def process_request(self, request, client_address):
        if not self._request_slots.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\nRetry-After: 1\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


def build_service() -> EngineService:
    db_path = os.environ.get("ALILI_ENGINE_DB_PATH", "./data/jobs.sqlite3")
    model_url = os.environ.get("ALILI_LOCAL_MODEL_URL", "").strip()
    model_client = None
    if model_url:
        model_client = LocalModelClient(
            model_url, model_name=os.environ.get("ALILI_LOCAL_MODEL_NAME", "local-model"),
            timeout=float(os.environ.get("ALILI_LOCAL_MODEL_TIMEOUT", "90")))
    return EngineService(TaskStore(db_path), model_client=model_client)


def create_handler(service: EngineService, expected_token: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AliliCortexEngine/0.6"

        def setup(self):
            super().setup()
            self.connection.settimeout(REQUEST_TIMEOUT_SECONDS)

        def log_message(self, _format, *_args):
            LOGGER.info("%s - %s", self.client_address[0], _format % _args)

        def handle_one_request(self):
            try:
                return super().handle_one_request()
            except (TimeoutError, OSError):
                self.close_connection = True
            except Exception:
                LOGGER.exception("Unhandled AC API request failure")
                try:
                    self._send(500, {"ok": False, "error": "internal_server_error"})
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                self.close_connection = True

        def _send(self, status: int, payload: dict):
            encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(encoded)

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            prefix = "Bearer "
            return supplied.startswith(prefix) and hmac.compare_digest(supplied[len(prefix):], expected_token)

        def _read_json(self):
            if self.headers.get("Transfer-Encoding"):
                return None, (400, "transfer_encoding_not_supported")
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                return None, (411, "content_length_required")
            try:
                length = int(raw_length)
            except ValueError:
                return None, (400, "invalid_content_length")
            if length < 0 or length > MAX_BODY_BYTES:
                return None, (413, "request_too_large")
            try:
                raw_body = self.rfile.read(length)
                if len(raw_body) != length:
                    return None, (400, "incomplete_request_body")
                value = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None, (400, "invalid_json")
            if not isinstance(value, dict):
                return None, (400, "invalid_request")
            return value, None

        def do_GET(self):
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/health":
                return self._send(200, {"ok": True, "service": "alili-cortex-engine", "version": "0.6.0"})
            if not self._authorized():
                return self._send(401, {"ok": False, "error": "unauthorized"})
            if path == "/v1/execution/status":
                return self._send(200, {"ok": True, "execution": service.execution_status()})
            if path == "/v1/cloud/status":
                return self._send(200, {"ok": True, "cloud": service.cloud_status()})
            if path == "/v1/cloud/plan":
                query = parse_qs(parsed.query)
                try:
                    plan = service.cloud_plan(query.get("task", [""])[0],
                                             units=int(query.get("units", ["1"])[0]))
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc) or "invalid_cloud_plan"})
                return self._send(200, {"ok": True, "plan": plan})
            if path == "/v1/providers":
                query = parse_qs(parsed.query)
                try:
                    items = service.provider_catalog(
                        category=query.get("category", [None])[0],
                        query=query.get("q", [None])[0],
                        status=query.get("status", [None])[0],
                        limit=int(query.get("limit", ["100"])[0]))
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc) or "invalid_provider_query"})
                return self._send(200, {"ok": True, "summary": service.provider_summary(),
                                        "policy": "free_only_no_bank_card_no_paid_fallback",
                                        "providers": items})
            if path.startswith("/v1/providers/"):
                provider_id = path.removeprefix("/v1/providers/")
                if not provider_id or "/" in provider_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                provider = service.provider_detail(provider_id)
                return self._send(200, {"ok": True, "provider": provider}) if provider else self._send(404, {"ok": False, "error": "provider_not_found"})
            if path == "/v1/capabilities":
                return self._send(200, {"ok": True, **service.capabilities()})
            if path == "/v1/brains":
                return self._send(200, {"ok": True, **service.brains()})
            if path == "/v1/models":
                return self._send(200, {"ok": True, "family": service.model_family(),
                                        "models": service.list_models()})
            if path.startswith("/v1/models/"):
                model_id = path.removeprefix("/v1/models/")
                if not model_id or "/" in model_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                model = service.get_model(model_id)
                return self._send(200, {"ok": True, "model": model}) if model else self._send(404, {"ok": False, "error": "model_not_found"})
            if path == "/v1/model/status":
                return self._send(200, {"ok": True, "model": service.model_status()})
            if path == "/v1/learning/blueprints":
                query = parse_qs(parsed.query)
                try:
                    items = service.learning_blueprints(
                        brain_id=query.get("brain_id", [None])[0],
                        domain=query.get("domain", [None])[0])
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "status": "study_plans_only_not_ingested",
                                        "blueprints": items})
            if path == "/v1/ecosystem":
                query = parse_qs(parsed.query)
                try:
                    domain = query.get("domain", [None])[0]
                    search = query.get("q", [None])[0]
                    limit = int(query.get("limit", ["100"])[0])
                    items = service.ecosystem_catalog(domain=domain, query=search, limit=limit)
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc) or "invalid_ecosystem_query"})
                return self._send(200, {"ok": True, "summary": service.ecosystem_summary(), "sources": items})
            if path == "/v1/ecosystem/policy":
                return self._send(200, {"ok": True, "policy": service.ecosystem_policy()})
            if path.startswith("/v1/ecosystem/"):
                source_id = path.removeprefix("/v1/ecosystem/")
                if not source_id or "/" in source_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                source = service.ecosystem_source(source_id)
                return self._send(200, {"ok": True, "source": source}) if source else self._send(404, {"ok": False, "error": "ecosystem_source_not_found"})
            if path == "/v1/training/policy":
                return self._send(200, {"ok": True, "policy": service.training_policy()})
            if path == "/v1/training/curricula":
                return self._send(200, {"ok": True, "curricula": service.training_curricula()})
            if path == "/v1/training/runs":
                try:
                    limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
                    return self._send(200, {"ok": True, "runs": service.list_training_runs(limit)})
                except (ValueError, TypeError):
                    return self._send(400, {"ok": False, "error": "invalid_training_query"})
            if path.startswith("/v1/training/runs/"):
                run_id = path.removeprefix("/v1/training/runs/")
                if not run_id or "/" in run_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                run = service.get_training_run(run_id)
                return self._send(200, {"ok": True, "run": run}) if run else self._send(404, {"ok": False, "error": "training_run_not_found"})
            if path == "/v1/ai-observatory/capabilities":
                query = parse_qs(parsed.query)
                try:
                    items = service.ai_capabilities(
                        category=query.get("category", [None])[0],
                        query=query.get("q", [None])[0],
                        limit=int(query.get("limit", ["100"])[0]))
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "capabilities": items,
                                        "notice": "reference_catalog_not_runtime_integrations"})
            if path == "/v1/ai-observatory/response-style":
                return self._send(200, {"ok": True, "policy": service.ai_response_style()})
            if path == "/v1/cloud/reservations":
                task = body.get("task")
                units = body.get("units", 1)
                if not isinstance(task, str) or not task.strip():
                    return self._send(400, {"ok": False, "error": "invalid_cloud_task"})
                if isinstance(units, bool) or not isinstance(units, int) or units < 1:
                    return self._send(400, {"ok": False, "error": "invalid_quota_units"})
                try:
                    reservation = service.reserve_cloud_capacity(task.strip(), units=units)
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                status = 201 if reservation.get("reservation_created") else 409
                return self._send(status, {"ok": reservation.get("reservation_created", False),
                                           "reservation": reservation})

            if path == "/v1/ai-observatory/studies":
                query = parse_qs(parsed.query)
                try:
                    studies = service.ai_capability_studies(
                        capability_id=query.get("capability_id", [None])[0],
                        limit=int(query.get("limit", ["50"])[0]))
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "studies": studies})
            if path == "/v1/links":
                query = parse_qs(parsed.query)
                try:
                    node_type = query.get("node_type", [None])[0]
                    node_id = query.get("node_id", [None])[0]
                    links = service.list_links(node_type=node_type, node_id=node_id,
                                               limit=int(query.get("limit", ["100"])[0]))
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "links": links})
            if path == "/v1/study/evidence":
                query = parse_qs(parsed.query)
                try:
                    items = service.list_study_evidence(
                        source_id=query.get("source_id", [None])[0],
                        limit=int(query.get("limit", ["50"])[0]))
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "status": "local_evidence_quarantined", "evidence": items})
            if path.startswith("/v1/study/evidence/"):
                evidence_id = path.removeprefix("/v1/study/evidence/")
                if not evidence_id or "/" in evidence_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                item = service.get_study_evidence(evidence_id)
                return self._send(200, {"ok": True, "evidence": item}) if item else self._send(404, {"ok": False, "error": "study_evidence_not_found"})
            if path == "/v1/study/sessions":
                try:
                    limit = int(parse_qs(parsed.query).get("limit", ["50"])[0])
                    sessions = service.list_study_sessions(limit)
                except (ValueError, TypeError) as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "sessions": sessions})
            if path.startswith("/v1/study/sessions/"):
                session_id = path.removeprefix("/v1/study/sessions/")
                if not session_id or "/" in session_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                session = service.get_study_session(session_id)
                return self._send(200, {"ok": True, "session": session}) if session else self._send(404, {"ok": False, "error": "study_session_not_found"})
            if path == "/v1/knowledge":
                query = parse_qs(parsed.query)
                try:
                    artifacts = service.list_knowledge(status=query.get("status", [None])[0],
                                                       limit=int(query.get("limit", ["50"])[0]))
                except (ValueError, TypeError):
                    return self._send(400, {"ok": False, "error": "invalid_knowledge_query"})
                return self._send(200, {"ok": True, "artifacts": artifacts})
            if path.startswith("/v1/knowledge/"):
                artifact_id = path.removeprefix("/v1/knowledge/")
                if not artifact_id or "/" in artifact_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                artifact = service.get_knowledge(artifact_id)
                return self._send(200, {"ok": True, "artifact": artifact}) if artifact else self._send(404, {"ok": False, "error": "knowledge_artifact_not_found"})
            if path.startswith("/v1/tasks/"):
                task_id = path.removeprefix("/v1/tasks/")
                if not task_id or "/" in task_id:
                    return self._send(404, {"ok": False, "error": "not_found"})
                task = service.get_task(task_id)
                return self._send(200, {"ok": True, "task": task}) if task else self._send(404, {"ok": False, "error": "task_not_found"})
            return self._send(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            path = urlsplit(self.path).path
            if not self._authorized():
                return self._send(401, {"ok": False, "error": "unauthorized"})
            allowed = {"/v1/tasks", "/v1/generate", "/v1/route", "/v1/knowledge", "/v1/execution/run",
                       "/v1/training/runs", "/v1/training/preflight",
                       "/v1/study/evidence", "/v1/study/sessions",
                       "/v1/connectors/fetch", "/v1/links",
                       "/v1/ai-observatory/studies", "/v1/ai-observatory/evaluate-response"}
            is_knowledge_transition = path.startswith("/v1/knowledge/") and path.endswith("/transition")
            is_training_evaluation = path.startswith("/v1/training/runs/") and path.endswith("/evaluate")
            is_study_evaluation = path.startswith("/v1/study/sessions/") and path.endswith("/evaluate")
            is_study_knowledge_proposal = path.startswith("/v1/study/sessions/") and path.endswith("/propose-knowledge")
            if path not in allowed and not is_knowledge_transition and not is_training_evaluation and not is_study_evaluation and not is_study_knowledge_proposal:
                return self._send(404, {"ok": False, "error": "not_found"})
            body, error = self._read_json()
            if error:
                return self._send(error[0], {"ok": False, "error": error[1]})

            if path == "/v1/ai-observatory/studies":
                try:
                    study = service.record_ai_capability_study(
                        capability_id=body.get("capability_id"), title=body.get("title"),
                        notes=body.get("notes"), source_url=body.get("source_url"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(202, {"ok": True, "study": study,
                                        "notice": "quarantined_review_required_not_published"})
            if path == "/v1/ai-observatory/evaluate-response":
                text_value = body.get("text")
                try:
                    result = service.evaluate_response_style(text_value)
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "evaluation": result})
            if path == "/v1/execution/run":
                code = body.get("code")
                input_text = body.get("input_text", "")
                try:
                    result = service.execute_python(code, input_text=input_text)
                except ExecutionRejected as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                status = 200 if result.get("ok") else 422 if result.get("status") == "rejected" else 503 if result.get("status") == "unavailable" else 408 if result.get("status") == "timeout" else 500
                return self._send(status, {"ok": result.get("ok", False), "execution": result})

            if path == "/v1/generate":
                messages, temperature, max_tokens = body.get("messages"), body.get("temperature", 0.2), body.get("max_tokens", 512)
                if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
                    return self._send(400, {"ok": False, "error": "invalid_temperature"})
                if isinstance(max_tokens, bool) or not isinstance(max_tokens, int):
                    return self._send(400, {"ok": False, "error": "invalid_max_tokens"})
                try:
                    result = service.generate(messages, temperature=float(temperature), max_tokens=max_tokens)
                except ModelNotConfigured:
                    return self._send(503, {"ok": False, "error": "local_model_not_configured", "fallback": "disabled"})
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                except LocalModelError as exc:
                    return self._send(503, {"ok": False, "error": str(exc), "fallback": "disabled"})
                return self._send(200, {"ok": True, "result": result})

            if path == "/v1/tasks":
                user_input = body.get("input")
                if not isinstance(user_input, str) or not user_input.strip() or len(user_input) > MAX_INPUT_CHARS:
                    return self._send(400, {"ok": False, "error": "invalid_task_input"})
                return self._send(202, {"ok": True, "task": service.create_task(user_input.strip())})

            if path == "/v1/route":
                task_type = body.get("task_type")
                if not isinstance(task_type, str) or not task_type.strip() or len(task_type) > 100:
                    return self._send(400, {"ok": False, "error": "invalid_task_type"})
                return self._send(200, {"ok": True, "route": service.route(task_type)})

            if path == "/v1/connectors/fetch":
                source_id = body.get("source_id")
                artifact_url = body.get("artifact_url")
                if not isinstance(source_id, str) or not source_id:
                    return self._send(400, {"ok": False, "error": "invalid_source_id"})
                if artifact_url is not None and not isinstance(artifact_url, str):
                    return self._send(400, {"ok": False, "error": "invalid_artifact_url"})
                try:
                    result = service.fetch_source_document(
                        source_id, artifact_url,
                        if_none_match=body.get("if_none_match"),
                        if_modified_since=body.get("if_modified_since"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                if result.get("not_modified"):
                    return self._send(200, {"ok": True, **result,
                                            "notice": "source_not_modified_no_new_evidence"})
                return self._send(202, {"ok": True, **result,
                                        "notice": "fetched_text_stored_as_quarantined_evidence"})

            if path == "/v1/links":
                try:
                    link = service.create_link(
                        source_type=body.get("source_type"), source_id=body.get("source_id"),
                        relation=body.get("relation"), target_type=body.get("target_type"),
                        target_id=body.get("target_id"), metadata=body.get("metadata"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(201, {"ok": True, "link": link})

            if path == "/v1/study/evidence":
                try:
                    item = service.add_study_evidence(
                        source_id=body.get("source_id"), title=body.get("title"),
                        content=body.get("content"), artifact_url=body.get("artifact_url", ""),
                        version=body.get("version", "unspecified"),
                        license_status=body.get("license_status", "unknown"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(202, {"ok": True, "evidence": item,
                                        "notice": "stored_locally_quarantined_not_executed"})

            if path == "/v1/study/sessions":
                try:
                    session = service.create_study_session(
                        question=body.get("question"), evidence_ids=body.get("evidence_ids"),
                        domain=body.get("domain", "general"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(201, {"ok": True, "session": session})

            if is_study_evaluation:
                session_id = path.removeprefix("/v1/study/sessions/").removesuffix("/evaluate")
                if not session_id or "/" in session_id:
                    return self._send(400, {"ok": False, "error": "invalid_study_session_id"})
                try:
                    session = service.evaluate_study_session(session_id)
                except KeyError:
                    return self._send(404, {"ok": False, "error": "study_session_not_found"})
                return self._send(200, {"ok": True, "session": session})

            if is_study_knowledge_proposal:
                session_id = path.removeprefix("/v1/study/sessions/").removesuffix("/propose-knowledge")
                if not session_id or "/" in session_id:
                    return self._send(400, {"ok": False, "error": "invalid_study_session_id"})
                try:
                    artifact = service.propose_study_knowledge(
                        session_id, origin_brain=body.get("origin_brain", "ac_research"))
                except KeyError:
                    return self._send(404, {"ok": False, "error": "study_session_not_found"})
                except ValueError as exc:
                    return self._send(409, {"ok": False, "error": str(exc)})
                return self._send(201, {"ok": True, "artifact": artifact,
                                        "notice": "proposed_only_requires_independent_validation_and_approval"})

            if path == "/v1/knowledge":
                try:
                    artifact = service.propose_knowledge(
                        artifact_type=body.get("artifact_type"), title=body.get("title"),
                        content=body.get("content"), origin_brain=body.get("origin_brain"),
                        origin_version=body.get("origin_version"), sources=body.get("sources", []),
                        license_id=body.get("license_id"), confidence=body.get("confidence", 0.5),
                        metadata=body.get("metadata"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(201, {"ok": True, "artifact": artifact})

            if path == "/v1/training/runs":
                try:
                    run = service.create_training_run(curriculum_id=body.get("curriculum_id"),
                        trigger_mode=body.get("trigger_mode", "manual"),
                        dataset_manifest=body.get("dataset_manifest", []), notes=body.get("notes", ""))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(202, {"ok": True, "run": run})

            if path == "/v1/training/preflight":
                try:
                    result = service.training_preflight(
                        model_id=body.get("model_id"),
                        checkpoint_path=body.get("checkpoint_path"),
                        checkpoint_license_id=body.get("checkpoint_license_id"),
                        dataset_path=body.get("dataset_path"),
                        dataset_license_id=body.get("dataset_license_id"),
                        method=body.get("method", "lora"),
                        model_root=os.environ.get("AC_MODEL_ROOT", "./models"),
                        dataset_root=os.environ.get("AC_DATASET_ROOT", "./data/datasets"))
                except ValueError as exc:
                    return self._send(400, {"ok": False, "error": str(exc)})
                return self._send(409 if not result["structural_checks_passed"] else 200,
                                  {"ok": result["structural_checks_passed"], "preflight": result})

            if is_training_evaluation:
                run_id = path.removeprefix("/v1/training/runs/").removesuffix("/evaluate")
                try:
                    run = service.evaluate_training_run(run_id, metrics=body.get("metrics"),
                                                        held_out=body.get("held_out"))
                except KeyError:
                    return self._send(404, {"ok": False, "error": "training_run_not_found"})
                except ValueError as exc:
                    return self._send(409, {"ok": False, "error": str(exc)})
                return self._send(200, {"ok": True, "run": run})

            artifact_id = path.removeprefix("/v1/knowledge/").removesuffix("/transition")
            status = body.get("status")
            if not artifact_id or "/" in artifact_id or not isinstance(status, str):
                return self._send(400, {"ok": False, "error": "invalid_knowledge_transition"})
            try:
                artifact = service.transition_knowledge(
                    artifact_id, status,
                    reviewer_id=body.get("reviewer_id"),
                    review_note=body.get("review_note"),
                    license_decision=body.get("license_decision"))
            except KeyError:
                return self._send(404, {"ok": False, "error": "knowledge_artifact_not_found"})
            except ValueError as exc:
                return self._send(409, {"ok": False, "error": str(exc)})
            return self._send(200, {"ok": True, "artifact": artifact})

    return Handler


def main():
    token = os.environ.get("ALILI_ENGINE_API_TOKEN", "")
    if len(token) < 32:
        raise SystemExit("ALILI_ENGINE_API_TOKEN is required and must contain at least 32 characters.")
    host = os.environ.get("ALILI_ENGINE_HOST", "127.0.0.1")
    port = int(os.environ.get("ALILI_ENGINE_PORT", "8765"))
    if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("ALILI_ENGINE_TRUST_PROXY") != "1":
        raise SystemExit("Non-loopback binding requires a TLS-terminating trusted reverse proxy (set ALILI_ENGINE_TRUST_PROXY=1 only behind that proxy).")
    server = BoundedThreadingHTTPServer((host, port), create_handler(build_service(), token))
    print(f"Alili Cortex Engine listening on {host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
