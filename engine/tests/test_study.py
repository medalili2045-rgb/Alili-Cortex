import hashlib
import tempfile
import unittest
from pathlib import Path

from alili_engine.ecosystem import EcosystemRegistry
from alili_engine.knowledge import KnowledgeStore
from alili_engine.study import UniversalStudyEngine


class ACUniversalStudyEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "study.sqlite3")
        self.ecosystem = EcosystemRegistry()
        self.knowledge = KnowledgeStore(self.db_path)
        self.study = UniversalStudyEngine(self.db_path, self.ecosystem, self.knowledge)

    def tearDown(self):
        self.temp.cleanup()

    def add(self, source_id="hf_transformers", license_status="approved", content=None):
        return self.study.add_evidence(
            source_id=source_id, title="Reference notes",
            content=content or "Transformers provide model architectures.\nTokenizers process text input.",
            artifact_url="https://example.org/reference", version="v1",
            license_status=license_status)

    def test_evidence_is_hashed_and_always_quarantined(self):
        content = "Transformers provide model architectures."
        item = self.add(content=content)
        self.assertEqual(item["sha256"], hashlib.sha256(content.encode()).hexdigest())
        self.assertEqual(item["status"], "quarantined")
        self.assertEqual(item["license_status"], "approved")
        self.assertEqual(self.study.list_evidence()[0]["evidence_id"], item["evidence_id"])
        self.assertNotIn("content", self.study.list_evidence()[0])

    def test_unknown_sources_and_non_https_artifact_urls_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_ecosystem_source"):
            self.study.add_evidence(source_id="not_registered", title="x", content="y")
        with self.assertRaisesRegex(ValueError, "artifact_url_must_use_https"):
            self.study.add_evidence(source_id="hf_transformers", title="x", content="y",
                                    artifact_url="http://example.org")

    def test_evidence_size_and_license_status_are_validated(self):
        with self.assertRaisesRegex(ValueError, "content_must_be_1_to_64000_characters"):
            self.study.add_evidence(source_id="hf_transformers", title="x", content="z" * 64001)
        with self.assertRaisesRegex(ValueError, "invalid_license_status"):
            self.add(license_status="cleared_by_magic")

    def test_study_report_keeps_provenance_and_states_lexical_limitations(self):
        first = self.add(content="Transformers provide model architectures and tokenizers.")
        second = self.add(source_id="hf_tokenizers",
                          content="Tokenizers provide text normalization and vocabulary processing.")
        session = self.study.create_session(
            question="Compare transformers tokenizers and model architectures",
            evidence_ids=[first["evidence_id"], second["evidence_id"]],
            domain="language")
        self.assertEqual(session["report"]["evidence_count"], 2)
        self.assertEqual(len(session["report"]["findings"]), 2)
        self.assertIn("tokenizers", session["report"]["cross_source_comparison"]["shared_terms"])
        self.assertEqual(session["report"]["status"], "draft_requires_human_review")

    def test_evaluation_is_structural_and_proposal_never_auto_publishes(self):
        item = self.add()
        session = self.study.create_session(
            question="Study model architectures", evidence_ids=[item["evidence_id"]], domain="models")
        evaluated = self.study.evaluate_session(session["session_id"])
        self.assertEqual(evaluated["evaluation"]["status"],
                         "structural_checks_passed_human_review_required")
        self.assertTrue(evaluated["evaluation"]["checks"]["evidence_hashes_match"])
        self.assertEqual(evaluated["evaluation"]["semantic_accuracy"], "not_evaluated")
        artifact = self.study.propose_knowledge(session["session_id"])
        self.assertEqual(artifact["status"], "proposed")
        self.assertEqual(artifact["license_id"], "review_required")

    def test_unknown_license_blocks_structural_evaluation(self):
        item = self.add(license_status="unknown")
        session = self.study.create_session(
            question="Study source", evidence_ids=[item["evidence_id"]])
        evaluated = self.study.evaluate_session(session["session_id"])
        self.assertEqual(evaluated["evaluation"]["status"], "blocked_pending_license_provenance_or_relevance")
        with self.assertRaisesRegex(ValueError, "study_session_must_pass_structural_checks_first"):
            self.study.propose_knowledge(session["session_id"])

    def test_review_required_and_restricted_licenses_block_study_approval(self):
        for license_status in ("review_required", "restricted", "unknown"):
            item = self.add(license_status=license_status)
            session = self.study.create_session(
                question="Study model architectures", evidence_ids=[item["evidence_id"]])
            evaluated = self.study.evaluate_session(session["session_id"])
            self.assertEqual(evaluated["evaluation"]["status"],
                             "blocked_pending_license_provenance_or_relevance")
            self.assertFalse(evaluated["evaluation"]["checks"]["all_licenses_approved"])

    def test_arabic_and_french_queries_find_relevant_passages(self):
        arabic = self.add(content="بنية النماذج تحدد طبقات الشبكة العصبية وطريقة عملها.")
        arabic_session = self.study.create_session(
            question="ما هي بنية النماذج؟", evidence_ids=[arabic["evidence_id"]])
        arabic_report = arabic_session["report"]["findings"][0]
        self.assertTrue(arabic_report["candidate_passages"])

        french = self.add(source_id="hf_tokenizers",
                          content="Les architectures des modèles définissent les couches du réseau.")
        french_session = self.study.create_session(
            question="architectures des modèles", evidence_ids=[french["evidence_id"]])
        self.assertTrue(french_session["report"]["findings"][0]["candidate_passages"])

    def test_unrelated_question_cannot_pass_empty_evidence_evaluation(self):
        item = self.add(content="Transformers provide model architectures.")
        session = self.study.create_session(
            question="astronomy telescope galaxies", evidence_ids=[item["evidence_id"]])
        evaluated = self.study.evaluate_session(session["session_id"])
        self.assertFalse(evaluated["evaluation"]["checks"]["has_relevant_passages"])
        self.assertEqual(evaluated["evaluation"]["status"],
                         "blocked_pending_license_provenance_or_relevance")
        with self.assertRaisesRegex(ValueError, "study_session_must_pass_structural_checks_first"):
            self.study.propose_knowledge(session["session_id"])

    def test_bad_or_missing_evidence_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "evidence_ids_must_contain"):
            self.study.create_session(question="Study", evidence_ids=[])
        with self.assertRaisesRegex(ValueError, "evidence_ids_must_be_unique_strings"):
            self.study.create_session(question="Study", evidence_ids=[{}])
        with self.assertRaisesRegex(ValueError, "study_evidence_not_found"):
            self.study.create_session(question="Study", evidence_ids=["missing"])


if __name__ == "__main__":
    unittest.main()
