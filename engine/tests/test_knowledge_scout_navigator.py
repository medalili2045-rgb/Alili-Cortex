import unittest

from alili_engine.knowledge_scout_navigator import KnowledgeScoutNavigator


class FakeScout:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.proposals = []

    def get_source(self, source_id):
        if source_id != "python-docs":
            return None
        return {"source_id": source_id, "enabled": self.enabled}

    def propose(self, **kwargs):
        self.proposals.append(kwargs)
        return {"proposal_id": "proposal-test", "status": "quarantined", **kwargs}


class FakeConnector:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def fetch(self, source_id, artifact_url=None):
        self.calls.append((source_id, artifact_url))
        return {"title": "Async Guide", "artifact_url": "https://docs.python.org/3/async",
                "retrieved_at": "2026-11-21T00:00:00+00:00",
                "content_type": "text/html", "sha256": "a" * 64,
                "content": self.content, "redirect_count": 0}


class NavigatorTests(unittest.TestCase):
    def test_extracts_headings_and_bullets_without_code_blocks(self):
        content = """# Async programming concepts
- Use async context managers for resource lifetimes
- Prefer structured concurrency for related tasks
```python
secret = "not a lesson"
```
## Cancellation and timeouts
"""
        note = KnowledgeScoutNavigator._extract_structured_note(content)
        self.assertIn("Use async context managers", note)
        self.assertIn("Cancellation and timeouts", note)
        self.assertNotIn("secret =", note)

    def test_fallback_extracts_short_sentences(self):
        content = ("Structured concurrency groups related tasks under one lifetime. "
                   "Cancellation should propagate to child tasks.")
        note = KnowledgeScoutNavigator._extract_structured_note(content)
        self.assertIn("Structured concurrency", note)

    def test_discovery_quarantines_proposal_with_source_provenance(self):
        scout = FakeScout()
        connector = FakeConnector("# Async programming concepts\n- Use async context managers for resource lifetimes")
        result = KnowledgeScoutNavigator(scout, connector).discover(
            source_id="python-docs", domain="software", brain_id="code")
        self.assertEqual(result["status"], "quarantined")
        self.assertEqual(result["proposal"]["status"], "quarantined")
        self.assertEqual(scout.proposals[0]["source_url"], "https://docs.python.org/3/async")
        self.assertEqual(result["extraction_method"], "structural_rules_v1")

    def test_disabled_sources_never_trigger_network_fetch(self):
        connector = FakeConnector("# A sufficiently long heading for discovery")
        navigator = KnowledgeScoutNavigator(FakeScout(enabled=False), connector)
        with self.assertRaisesRegex(ValueError, "scout_source_not_enabled"):
            navigator.discover(source_id="python-docs", domain="software", brain_id="code")
        self.assertEqual(connector.calls, [])

    def test_unknown_source_is_rejected(self):
        navigator = KnowledgeScoutNavigator(FakeScout(), FakeConnector("content"))
        with self.assertRaises(KeyError):
            navigator.discover(source_id="missing", domain="software", brain_id="code")

    def test_empty_or_unstructured_content_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "no_structured_learning_candidates_found"):
            KnowledgeScoutNavigator._extract_structured_note("short")
