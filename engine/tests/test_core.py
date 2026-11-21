import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from alili_engine.api import create_handler
from alili_engine.planner import TaskPlanner
from alili_engine.policy import FreePolicyGate
from alili_engine.registry import CapabilityRegistry
from alili_engine.provider_catalog import ProviderCatalog
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.gate = FreePolicyGate()

    def test_local_builtin_is_allowed(self):
        self.assertTrue(self.gate.evaluate("local_builtin").allowed)

    def test_open_source_requires_license_review(self):
        self.assertFalse(self.gate.evaluate("local_open_source").allowed)
        self.assertTrue(self.gate.evaluate("local_open_source", license_approved=True).allowed)

    def test_paid_and_unknown_routes_are_denied(self):
        for route in ("paid", "subscription", "metered_paid", "unknown-provider"):
            with self.subTest(route=route):
                self.assertFalse(self.gate.evaluate(route).allowed)

    def test_hosted_free_requires_all_operator_checks(self):
        self.assertFalse(self.gate.evaluate("hosted_free", free_terms_confirmed=True, billing_disabled=True).allowed)
        decision = self.gate.evaluate(
            "hosted_free",
            free_terms_confirmed=True,
            billing_disabled=True,
            quota_verified=True,
        )
        self.assertTrue(decision.allowed)


class PlannerTests(unittest.TestCase):
    def test_arabic_document_request_is_classified(self):
        plan = TaskPlanner().plan("حلل ملف PDF واستخرج الجداول")
        self.assertEqual(plan.capability_id, "document_processing")

    def test_general_request_uses_builtin_planner(self):
        plan = TaskPlanner().plan("اشرح لي مفهوم الاستدلال")
        self.assertEqual(plan.capability_id, "task_planning")
        self.assertEqual(plan.execution_status, "not_started")


class StoreAndServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TaskStore(os.path.join(self.temp.name, "tasks.sqlite3"))
        self.service = EngineService(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_task_lifecycle_creates_reviewable_plan_not_fake_completion(self):
        task = self.service.create_task("أنشئ تطبيقاً")
        self.assertEqual(task["status"], "planned")
        self.assertEqual(task["capability_id"], "software_execution")
        self.assertEqual(task["plan"]["execution_status"], "capability_not_implemented")
        self.assertNotEqual(task["status"], "completed")

    def test_invalid_state_transition_is_rejected(self):
        task = self.store.create("طلب")
        self.store.transition(task["task_id"], "planning")
        self.store.transition(task["task_id"], "planned")
        with self.assertRaises(ValueError):
            self.store.transition(task["task_id"], "planning")

    def test_registry_has_unique_ids_and_marks_only_planner_available(self):
        registry = CapabilityRegistry()
        values = registry.all()
        self.assertEqual(len(values), len({item["capability_id"] for item in values}))
        self.assertEqual([item["capability_id"] for item in values if item["status"] == "available"], ["task_planning"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        service = EngineService(TaskStore(os.path.join(self.temp.name, "api.sqlite3")))
        self.token = "test-token-that-is-long-enough-123456"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(service, self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def test_health_is_public(self):
        with urlopen(self.base + "/health") as response:
            data = json.loads(response.read())
        self.assertTrue(data["ok"])

    def test_private_routes_require_token(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/v1/capabilities")
        self.assertEqual(caught.exception.code, 401)

    def test_authenticated_task_creation_and_fetch(self):
        request = Request(
            self.base + "/v1/tasks",
            data=json.dumps({"input": "حلل ملف PDF"}).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            self.assertEqual(response.status, 202)
            task = json.loads(response.read())["task"]
        self.assertEqual(task["status"], "planned")
        get_request = Request(self.base + "/v1/tasks/" + task["task_id"], headers={"Authorization": "Bearer " + self.token})
        with urlopen(get_request) as response:
            saved = json.loads(response.read())["task"]
        self.assertEqual(saved["task_id"], task["task_id"])
        self.assertEqual(saved["plan"]["execution_status"], "capability_not_implemented")


    def test_ac_master_plans_independent_specialists_without_fake_dispatch(self):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        payload = {"objective": "ابحث عن مصادر ثم برمج تطبيقاً واختبره", "max_brains": 6}
        request = Request(self.base + "/v1/brains/plan", data=json.dumps(payload).encode(),
                          headers=headers, method="POST")
        with urlopen(request) as response:
            result = json.loads(response.read())
        self.assertTrue(result["ok"])
        plan = result["plan"]
        ids = {item["brain_id"] for item in plan["assignments"]}
        self.assertTrue({"ac_research", "ac_code", "ac_execution", "ac_reasoning"} <= ids)
        self.assertFalse(plan["execution"]["dispatched"])
        self.assertTrue(plan["isolation"]["separate_assignment_contexts"])
        self.assertFalse(plan["isolation"]["shared_mutable_context"])

    def test_evolution_api_proposals_require_review_before_activation(self):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        with urlopen(Request(self.base + "/v1/evolution/status", headers=headers)) as response:
            status = json.loads(response.read())
        self.assertTrue(status["evolution"]["requires_human_review"])
        payload = {"proposal_type": "knowledge_library", "item_id": "ac_api_test_library",
                   "name": "API Test Library", "domain": "biology",
                   "rationale": "Test an evidence-backed growth proposal.",
                   "evidence_refs": ["https://example.org/evidence"]}
        request = Request(self.base + "/v1/evolution/proposals", data=json.dumps(payload).encode(),
                          headers=headers, method="POST")
        with urlopen(request) as response:
            created = json.loads(response.read())["proposal"]
        self.assertEqual(created["status"], "pending_review")
        review_payload = {"decision": "approve", "reviewer": "test-reviewer", "notes": "Reviewed"}
        review_request = Request(self.base + "/v1/evolution/proposals/" + created["proposal_id"] + "/review",
                                 data=json.dumps(review_payload).encode(), headers=headers, method="POST")
        with urlopen(review_request) as response:
            reviewed = json.loads(response.read())["proposal"]
        self.assertEqual(reviewed["status"], "approved")
        self.assertFalse(status["evolution"]["automatic_creation"])
        self.assertFalse(status["evolution"]["automatic_brain_activation"])

    def test_brain_runtime_api_is_authenticated_and_fails_closed_without_local_model(self):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        with urlopen(Request(self.base + "/v1/brains/runtime", headers=headers)) as response:
            runtime = json.loads(response.read())["runtime"]
        self.assertEqual(runtime["status"], "unconfigured")
        request = Request(self.base + "/v1/brains/dispatch",
                          data=json.dumps({"objective": "Research and code a safe application"}).encode(),
                          headers=headers, method="POST")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 503)
        payload = json.loads(caught.exception.read())
        self.assertFalse(payload["dispatch"]["dispatched"])
        self.assertEqual(payload["dispatch"]["hosted_fallback"], "disabled")

    def test_knowledge_scout_api_is_authenticated_and_quarantine_first(self):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        with urlopen(Request(self.base + "/v1/knowledge-scout/status", headers=headers)) as response:
            status = json.loads(response.read())
        self.assertEqual(status["scout"]["network_fetch"], "catalog_bound_dns_pinned_connector")
        payload = {"source_id": "python-docs", "name": "Python Docs",
                   "base_url": "https://docs.python.org", "source_type": "official_docs",
                   "domains": ["software"], "brains": ["code"], "terms_reviewed": True}
        request = Request(self.base + "/v1/knowledge-scout/sources",
                          data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(request) as response:
            source = json.loads(response.read())["source"]
        self.assertFalse(source["enabled"])
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base + "/v1/knowledge-scout/jobs",
                            data=json.dumps({"source_id": "python-docs", "query": "async"}).encode(),
                            headers=headers, method="POST"))
        self.assertEqual(caught.exception.code, 400)
        enable = Request(self.base + "/v1/knowledge-scout/sources/python-docs/enable",
                         data=json.dumps({"terms_evidence_url": "https://docs.python.org/3/license.html"}).encode(),
                         headers=headers, method="POST")
        with urlopen(enable) as response:
            self.assertTrue(json.loads(response.read())["source"]["enabled"])
        job_request = Request(self.base + "/v1/knowledge-scout/jobs",
                              data=json.dumps({"source_id": "python-docs", "query": "async"}).encode(),
                              headers=headers, method="POST")
        with urlopen(job_request) as response:
            job = json.loads(response.read())["job"]
        self.assertEqual(job["status"], "queued")


    def test_knowledge_scout_discovery_requires_registered_enabled_source(self):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        request = Request(
            self.base + "/v1/knowledge-scout/discover",
            data=json.dumps({"source_id": "missing-source", "domain": "software",
                             "brain_id": "code"}).encode(),
            headers=headers, method="POST")
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 404)

    def test_license_intelligence_api_is_authenticated_and_never_approves_or_installs(self):
        headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}
        with urlopen(Request(self.base + "/v1/license-intelligence/status", headers=headers)) as response:
            status = json.loads(response.read())
        self.assertFalse(status["license_intelligence"]["automatic_approval"])
        payload = {"dependency_report": {"nodes": [
            {"name": "safe-candidate", "version": "1.0", "root": True,
             "resolution_status": "resolved", "license": {"expression": "MIT"}}]}}
        request = Request(self.base + "/v1/license-intelligence/analyze", data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urlopen(request) as response:
            result = json.loads(response.read())
        self.assertTrue(result["ok"])
        self.assertTrue(result["report"]["summary"]["all_packages_quarantined"])
        self.assertEqual(result["report"]["summary"]["approval_count"], 0)
        self.assertEqual(result["report"]["summary"]["install_enabled_count"], 0)

    def test_provider_catalog_api_is_authenticated_and_reports_no_connections(self):
        headers = {"Authorization": "Bearer " + self.token}
        with urlopen(Request(self.base + "/v1/providers", headers=headers)) as response:
            payload = json.loads(response.read())
        self.assertTrue(payload["ok"])
        self.assertGreater(payload["summary"]["total"], 0)
        self.assertEqual(payload["summary"]["connected"], 0)
        self.assertTrue(all(not item["enabled_by_default"] for item in payload["providers"]))

    def test_cloud_adapter_status_and_default_plan_are_authenticated_and_fail_closed(self):
        headers = {"Authorization": "Bearer " + self.token}
        with urlopen(Request(self.base + "/v1/cloud/status", headers=headers)) as response:
            status = json.loads(response.read())
        self.assertTrue(status["ok"])
        self.assertEqual(status["cloud"]["connected_providers"], 0)
        with urlopen(Request(self.base + "/v1/cloud/plan?task=gpu_experiment", headers=headers)) as response:
            plan = json.loads(response.read())
        self.assertEqual(plan["plan"]["status"], "unavailable")
        self.assertEqual(plan["plan"]["paid_fallback"], "prohibited")

    def test_ecosystem_catalog_and_domain_filter(self):
        headers = {"Authorization": "Bearer " + self.token}
        with urlopen(Request(self.base + "/v1/ecosystem?domain=robotics", headers=headers)) as response:
            payload = json.loads(response.read())
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["sources"])
        self.assertTrue(all("robotics" in item["domains"] for item in payload["sources"]))

    def test_ecosystem_policy_is_reachable_and_free_first(self):
        headers = {"Authorization": "Bearer " + self.token}
        with urlopen(Request(self.base + "/v1/ecosystem/policy", headers=headers)) as response:
            payload = json.loads(response.read())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["policy"]["paid_services"], "prohibited")
        self.assertFalse(payload["policy"]["automatic_code_execution"])

    def test_ecosystem_query_validation(self):
        headers = {"Authorization": "Bearer " + self.token}
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.base + "/v1/ecosystem?domain=not-a-domain", headers=headers))
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
