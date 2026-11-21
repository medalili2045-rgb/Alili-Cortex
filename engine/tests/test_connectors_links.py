import unittest
from unittest.mock import patch

from alili_engine.connectors import ConnectorError, UniversalSourceConnector, _TextExtractor
from alili_engine.ecosystem import EcosystemRegistry
from alili_engine.links import KnowledgeLinkGraph


class ConnectorSafetyTests(unittest.TestCase):
    def setUp(self):
        self.connector = UniversalSourceConnector(EcosystemRegistry())

    def test_only_exact_catalogued_https_host_is_allowed(self):
        source = self.connector.ecosystem.get("hf_transformers")
        good = source["url"] + "/blob/main/README.md"
        with patch.object(self.connector, "_resolver",
                   return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            target, address = self.connector._target("hf_transformers", good)
        self.assertEqual(target.hostname, "github.com")
        self.assertEqual(address, "93.184.216.34")
        with self.assertRaisesRegex(ConnectorError, "url_must_match"):
            self.connector._target("hf_transformers", "https://evil.example/readme")

    def test_private_and_loopback_dns_results_are_rejected(self):
        for address in ("127.0.0.1", "10.0.0.8", "169.254.169.254", "::1"):
            with self.subTest(address=address):
                with patch.object(self.connector, "_resolver",
                           return_value=[(None, None, None, None, (address, 443))]):
                    with self.assertRaisesRegex(ConnectorError, "non_public"):
                        self.connector._target("hf_transformers", "https://github.com/huggingface/transformers")

    def test_html_extraction_removes_script_and_style_content(self):
        parser = _TextExtractor()
        parser.feed("<h1>Docs</h1><script>secret()</script><p>Safe text</p><style>hidden</style>")
        self.assertIn("Docs", parser.text())
        self.assertIn("Safe text", parser.text())
        self.assertNotIn("secret", parser.text())
        self.assertNotIn("hidden", parser.text())

    def test_not_modified_response_is_reported_without_new_content(self):
        from urllib.parse import urlsplit
        with patch.object(self.connector, "_target",
                          return_value=(urlsplit("https://github.com/huggingface/transformers"), "93.184.216.34")), \
             patch.object(self.connector, "_request",
                          return_value=(304, {"etag": '"same"'}, b"")):
            result = self.connector.fetch("hf_transformers", if_none_match='"same"')
        self.assertTrue(result["not_modified"])
        self.assertEqual(result["etag"], '"same"')

    def test_redirects_are_revalidated_against_the_catalog_host(self):
        with patch("alili_engine.connectors.socket.getaddrinfo",
                   return_value=[(None, None, None, None, ("93.184.216.34", 443))]), \
             patch.object(self.connector, "_request",
                          return_value=(302, {"location": "https://evil.example/steal"}, b"")):
            with self.assertRaisesRegex(ConnectorError, "url_must_match"):
                self.connector.fetch("hf_transformers")

    def test_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ConnectorError, "unknown_ecosystem_source"):
            self.connector.fetch("not-a-source")


class KnowledgeLinkGraphTests(unittest.TestCase):
    def test_typed_links_are_persistent_idempotent_and_queryable(self):
        graph = KnowledgeLinkGraph(":memory:")
        first = graph.add(source_type="source", source_id="hf_transformers",
                          relation="documents", target_type="evidence", target_id="e-1",
                          metadata={"sha256": "abc"})
        second = graph.add(source_type="source", source_id="hf_transformers",
                           relation="documents", target_type="evidence", target_id="e-1",
                           metadata={"sha256": "abc"})
        self.assertEqual(first["link_id"], second["link_id"])
        self.assertEqual(len(graph.list(node_type="evidence", node_id="e-1")), 1)

    def test_invalid_relationship_is_rejected(self):
        graph = KnowledgeLinkGraph(":memory:")
        with self.assertRaisesRegex(ValueError, "invalid_link_relation"):
            graph.add(source_type="source", source_id="x", relation="owns",
                      target_type="brain", target_id="ac_research")


if __name__ == "__main__":
    unittest.main()
