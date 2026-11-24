from vayron_core import Capability, CapabilityRegistry, MemoryStore, VayronEngine


def test_registry_register_and_execute():
    registry = CapabilityRegistry()
    registry.register(Capability("echo", lambda data: data["value"]))
    engine = VayronEngine(registry=registry)
    assert engine.execute_capability("ECHO", {"value": "ok"}) == "ok"


def test_registry_rejects_duplicate():
    registry = CapabilityRegistry()
    registry.register(Capability("echo", lambda data: data))
    try:
        registry.register(Capability("echo", lambda data: data))
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate capability should fail")


def test_memory_roundtrip(tmp_path):
    memory = MemoryStore(tmp_path / "memory.sqlite3")
    memory.add("Vayron core foundation", "project")
    results = memory.search("foundation")
    assert len(results) == 1
    assert results[0]["category"] == "project"


def test_engine_reports_model_not_loaded():
    status = VayronEngine().status()
    assert status["ready"] is True
    assert status["model_loaded"] is False
    assert status["external_api_required"] is False
