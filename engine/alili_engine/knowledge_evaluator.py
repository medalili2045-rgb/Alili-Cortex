"""AC Knowledge Evidence Evaluator v1: transparent human-review triage."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlsplit
from .knowledge_scout import validate_public_https_url

_SOURCE_WEIGHT = {"official_docs": 0.90, "standards_body": 1.0, "government_open_data": 0.95, "academic_repository": 0.90, "open_access_research": 0.90, "security_advisory": 0.95, "public_repository": 0.72, "open_source_project": 0.78, "educational_resource": 0.72, "open_courseware": 0.78, "public_dataset": 0.82}

class KnowledgeEvidenceEvaluator:
    VERSION = "1.0.0"
    MAX_EVIDENCE = 100

    @staticmethod
    def _timestamp(value):
        if not isinstance(value, str) or len(value) > 64: raise ValueError("invalid_retrieved_at")
        try: parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc: raise ValueError("invalid_retrieved_at") from exc
        if parsed.tzinfo is None: raise ValueError("retrieved_at_timezone_required")
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _host(url):
        if not isinstance(url, str) or len(url) > 2048: raise ValueError("invalid_evidence_url")
        safe_url = validate_public_https_url(url)
        return urlsplit(safe_url).hostname.lower().rstrip(".")

    def evaluate(self, evidence, *, now=None):
        if not isinstance(evidence, list) or not evidence or len(evidence) > self.MAX_EVIDENCE: raise ValueError("evidence_count_out_of_range")
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None: raise ValueError("evaluation_time_timezone_required")
        current = current.astimezone(timezone.utc)
        normalized, groups = [], defaultdict(set)
        for item in evidence:
            if not isinstance(item, dict): raise ValueError("invalid_evidence_record")
            claim, value, kind = item.get("claim_key"), item.get("value"), item.get("source_type")
            if not isinstance(claim, str) or not claim.strip() or len(claim) > 200: raise ValueError("invalid_claim_key")
            if not isinstance(value, str) or not value.strip() or len(value) > 500: raise ValueError("invalid_evidence_value")
            if kind not in _SOURCE_WEIGHT: raise ValueError("unsupported_evidence_source_type")
            host = self._host(item.get("url")); retrieved = self._timestamp(item.get("retrieved_at"))
            age = max(0.0, (current - retrieved).total_seconds() / 86400)
            fresh = max(0.0, 1.0 - age / 365.0)
            groups[claim.strip().casefold()].add(value.strip().casefold())
            normalized.append({"claim_key": claim.strip(), "value": value.strip(), "source_type": kind, "host": host, "retrieved_at": retrieved.isoformat(), "source_weight": _SOURCE_WEIGHT[kind], "freshness": round(fresh, 4)})
        hosts = {item["host"] for item in normalized}
        authority = sum(x["source_weight"] for x in normalized) / len(normalized)
        freshness = sum(x["freshness"] for x in normalized) / len(normalized)
        diversity = min(1.0, len(hosts) / 3.0)
        conflicts = [{"claim_key": key, "distinct_values": sorted(values)} for key, values in sorted(groups.items()) if len(values) > 1]
        corroboration = min(1.0, len(normalized) / 3.0)
        score = round(100 * (0.45 * authority + 0.30 * diversity + 0.15 * freshness + 0.10 * corroboration))
        if conflicts: triage = "expert_review_required_conflicting_evidence"
        elif score >= 75 and len(hosts) >= 2: triage = "higher_priority_for_human_review"
        else: triage = "insufficient_independent_evidence"
        return {"evaluator_version": self.VERSION, "evidence_count": len(normalized), "independent_hosts": len(hosts), "score": score, "triage": triage, "conflicts": conflicts, "evidence": normalized, "decision": "human_review_required", "truth_verified": False, "automatic_publication": False, "automatic_training": False, "notice": "heuristic_evidence_triage_not_a_truth_or_safety_verdict"}
