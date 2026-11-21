import unittest
from datetime import datetime, timezone
from alili_engine.knowledge_evaluator import KnowledgeEvidenceEvaluator

class KnowledgeEvidenceEvaluatorTests(unittest.TestCase):
    def setUp(self): self.evaluator = KnowledgeEvidenceEvaluator(); self.now = datetime(2026, 11, 21, tzinfo=timezone.utc)
    def record(self, host, value="stable", source_type="official_docs"):
        return {"claim_key":"api.stability","value":value,"source_type":source_type,"url":f"https://{host}/guide","retrieved_at":"2026-11-20T12:00:00+00:00"}
    def test_independent_authoritative_sources_raise_review_priority(self):
        result=self.evaluator.evaluate([self.record("docs.example.org"),self.record("standards.example.net",source_type="standards_body"),self.record("data.example.com",source_type="government_open_data")],now=self.now)
        self.assertEqual(result["independent_hosts"],3); self.assertEqual(result["triage"],"higher_priority_for_human_review"); self.assertFalse(result["truth_verified"])
    def test_conflicting_values_force_expert_review(self):
        result=self.evaluator.evaluate([self.record("docs.example.org"),self.record("standards.example.net","deprecated","standards_body")],now=self.now)
        self.assertEqual(len(result["conflicts"]),1); self.assertEqual(result["triage"],"expert_review_required_conflicting_evidence")
    def test_same_host_is_not_independent(self):
        result=self.evaluator.evaluate([self.record("docs.example.org"),self.record("docs.example.org",source_type="educational_resource")],now=self.now)
        self.assertEqual(result["independent_hosts"],1); self.assertEqual(result["triage"],"insufficient_independent_evidence")
    def test_rejects_http_credentials_and_unknown_types(self):
        for url in ("http://example.org","https://127.0.0.1/x","https://user@host.org"):
            item=self.record("example.org"); item["url"]=url
            with self.assertRaises(ValueError): self.evaluator.evaluate([item],now=self.now)
        item=self.record("example.org"); item["source_type"]="unknown"
        with self.assertRaisesRegex(ValueError,"unsupported_evidence_source_type"): self.evaluator.evaluate([item],now=self.now)
    def test_rejects_naive_timestamps_and_oversized_batches(self):
        item=self.record("example.org"); item["retrieved_at"]="2026-11-20T12:00:00"
        with self.assertRaises(ValueError): self.evaluator.evaluate([item],now=self.now)
        with self.assertRaises(ValueError): self.evaluator.evaluate([self.record("example.org")]*101,now=self.now)

if __name__ == "__main__": unittest.main()