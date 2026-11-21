import json
import tempfile
import unittest
from pathlib import Path

from alili_engine.models import ModelRegistry
from alili_engine.training_runtime import training_preflight


def approved_review(license_id):
    return {
        "status": "approved",
        "license_id": license_id,
        "reviewer_id": "human-reviewer",
        "reviewed_at": "2026-11-21T00:00:00Z",
        "evidence_url": "https://example.org/license",
    }


class ACModelFoundryTests(unittest.TestCase):
    def test_ac_yzn_family_and_specialist_names_are_registered(self):
        registry = ModelRegistry()
        models = {item["model_id"]: item for item in registry.all()}
        for model_id in ("ac_yzn1", "ac_yzn1_r", "ac_yzn1_c", "ac_yzn1_sci",
                         "ac_yzn1_v", "ac_yzn1_mm", "ac_yzn2"):
            self.assertIn(model_id, models)
            self.assertEqual(models[model_id]["family"], "AC_YZN")
            self.assertEqual(models[model_id]["weights_status"], "not_created")
            self.assertEqual(models[model_id]["strength_tier"], "unrated")

    def test_capacity_suffixes_do_not_conflict_with_specializations(self):
        family = ModelRegistry().family()
        naming = family["naming"]
        self.assertIn("SCI", naming["specialization"])
        self.assertIn("S", naming["capacity_suffixes"])
        self.assertIn("published, reproducible held-out benchmark", family["strength_rule"])

    def test_unknown_or_non_string_model_is_rejected(self):
        for model_id in ("ac_yzn999", 123, None):
            with self.assertRaisesRegex(ValueError, "unknown_ac_model_id"):
                training_preflight(model_id=model_id, model_registry=ModelRegistry(),
                    checkpoint_path="none", checkpoint_license_id="none",
                    dataset_path="none", dataset_license_id="unknown")

    def _fixture(self, root):
        models, datasets = root / "models", root / "datasets"
        models.mkdir(); datasets.mkdir()
        checkpoint = models / "checkpoint"
        checkpoint.mkdir()
        (checkpoint / "config.json").write_text('{"model_type":"test"}', encoding="utf-8")
        (checkpoint / "model.safetensors").write_bytes(b"placeholder-weight-bytes")
        dataset = datasets / "train.jsonl"
        dataset.write_text(json.dumps({"prompt": "question", "text": "answer"}) + "\n", encoding="utf-8")
        return models, datasets, checkpoint, dataset

    def test_preflight_hashes_artifacts_and_requires_explicit_license_reviews(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            models, datasets, checkpoint, dataset = self._fixture(root)
            result = training_preflight(model_id="ac_yzn1", model_registry=ModelRegistry(),
                checkpoint_path=str(checkpoint), checkpoint_license_id="checkpoint-license",
                dataset_path=str(dataset), dataset_license_id="dataset-license",
                model_root=str(models), dataset_root=str(datasets), method="lora")
            self.assertEqual(result["execution"], "not_started")
            self.assertFalse(result["training_ready"])
            self.assertFalse(result["weights_updated"])
            self.assertEqual(result["checkpoint"]["weight_integrity"], "hash_computed_reference_not_verified")
            self.assertEqual(len(result["dataset"]["sha256"]), 64)
            self.assertFalse(result["checks"]["dataset_license_human_review_approved"])
            self.assertFalse(result["checks"]["checkpoint_license_human_review_approved"])
            self.assertFalse(result["structural_checks_passed"])

    def test_preflight_accepts_only_matching_artifact_specific_license_reviews(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            models, datasets, checkpoint, dataset = self._fixture(root)
            result = training_preflight(model_id="ac_yzn1", model_registry=ModelRegistry(),
                checkpoint_path=str(checkpoint), checkpoint_license_id="checkpoint-license",
                dataset_path=str(dataset), dataset_license_id="dataset-license",
                model_root=str(models), dataset_root=str(datasets),
                checkpoint_license_review=approved_review("checkpoint-license"),
                dataset_license_review=approved_review("dataset-license"))
            self.assertTrue(result["checks"]["dataset_license_human_review_approved"])
            self.assertTrue(result["checks"]["checkpoint_license_human_review_approved"])
            self.assertFalse(result["training_ready"])
            self.assertFalse(result["weights_updated"])

    def test_preflight_detects_reference_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            models, datasets, checkpoint, dataset = self._fixture(root)
            result = training_preflight(model_id="ac_yzn1", model_registry=ModelRegistry(),
                checkpoint_path=str(checkpoint), checkpoint_license_id="checkpoint-license",
                dataset_path=str(dataset), dataset_license_id="dataset-license",
                model_root=str(models), dataset_root=str(datasets),
                expected_dataset_sha256="0" * 64)
            self.assertFalse(result["checks"]["expected_dataset_hash_matches"])
            self.assertFalse(result["structural_checks_passed"])

    def test_preflight_rejects_paths_outside_roots_and_json_not_jsonl(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            models, datasets, outside = root / "models", root / "datasets", root / "outside"
            models.mkdir(); datasets.mkdir(); outside.mkdir()
            dataset = datasets / "train.json"
            dataset.write_text(json.dumps({"text": "sample"}), encoding="utf-8")
            result = training_preflight(model_id="ac_yzn1", model_registry=ModelRegistry(),
                checkpoint_path=str(outside), checkpoint_license_id="review-me",
                dataset_path=str(dataset), dataset_license_id="review-me",
                model_root=str(models), dataset_root=str(datasets))
            self.assertFalse(result["structural_checks_passed"])
            self.assertFalse(result["checks"]["checkpoint_inside_local_model_root"])
            self.assertFalse(result["checks"]["jsonl_dataset_rows_valid"])


if __name__ == "__main__":
    unittest.main()
