from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from domain.platform_runtime.models import (
    AuditRecord,
    ConfigurationDefinition,
    EventHandlerResult,
    FeatureFlagDefinition,
    HealthLevel,
    NotificationDeliveryResult,
    NotificationRequest,
    PlatformEvent,
    PluginContext,
    PluginLifecycle,
    PluginManifest,
    PluginPermission,
    PluginRequirement,
    PluginType,
    SemanticVersion,
)
from infrastructure.repositories.platform_runtime import DuckDBPlatformRepository
from migrations.runner import apply_migrations
from services.content.importers import ImporterRegistry
from services.platform_runtime import (
    AuditTrailService,
    ConfigurationService,
    DisabledAITutor,
    FeatureFlagService,
    ImportExportRegistry,
    InternalEventBus,
    NotificationGateway,
    PluginRegistry,
    compatible,
    default_flags,
)

NOW = datetime(2026, 7, 23, tzinfo=UTC)


@dataclass
class FakePlugin:
    manifest: PluginManifest
    actions: list[str]
    fail: bool = False

    def initialize(self, context: PluginContext) -> None:
        assert context.plugin_id == self.manifest.plugin_id
        assert not hasattr(context, "database")
        self.actions.append(f"init:{self.manifest.plugin_id}")
        if self.fail:
            raise RuntimeError("isolated")

    def start(self) -> None:
        self.actions.append(f"start:{self.manifest.plugin_id}")

    def health_check(self) -> HealthLevel:
        return HealthLevel.HEALTHY

    def stop(self) -> None:
        self.actions.append(f"stop:{self.manifest.plugin_id}")


def manifest(plugin_id: str, dependencies: tuple[str, ...] = ()) -> PluginManifest:
    return PluginManifest(
        plugin_id,
        plugin_id,
        SemanticVersion(1, 0, 0),
        PluginType.EVENT_HANDLER,
        SemanticVersion(1, 0, 0),
        SemanticVersion(2, 0, 0),
        SemanticVersion(2, 9, 9),
        PluginRequirement.OPTIONAL,
        dependencies,
        frozenset({PluginPermission.READ_SESSION_SUMMARY}),
    )


def test_semantic_versions_manifest_and_compatibility() -> None:
    assert str(SemanticVersion.parse("2.1.3")) == "2.1.3"
    with pytest.raises(ValueError, match="semantic"):
        SemanticVersion.parse("2.1")
    manifest("core.sample").validate()
    with pytest.raises(ValueError, match="MANIFEST"):
        manifest("invalid").validate()
    assert (
        compatible(SemanticVersion(2, 1, 0), SemanticVersion(2, 0, 0), SemanticVersion(2, 9, 0)).value == "COMPATIBLE"
    )
    assert (
        compatible(SemanticVersion(3, 0, 0), SemanticVersion(2, 0, 0), SemanticVersion(2, 9, 0)).value == "INCOMPATIBLE"
    )


def test_plugin_lifecycle_order_duplicate_cycles_and_optional_failure() -> None:
    actions: list[str] = []
    registry = PluginRegistry()
    registry.register(FakePlugin(manifest("core.first"), actions))
    registry.register(FakePlugin(manifest("core.second", ("core.first",)), actions))
    registry.register(FakePlugin(manifest("optional.failure", ("core.first",)), actions, fail=True))
    with pytest.raises(ValueError, match="DUPLICATE"):
        registry.register(FakePlugin(manifest("core.first"), actions))
    registry.start_all(ConfigurationService(()), FeatureFlagService(()))
    assert registry.states()["optional.failure"] == PluginLifecycle.FAILED
    assert actions[:4] == ["init:core.first", "start:core.first", "init:core.second", "start:core.second"]
    registry.stop_all()
    assert actions[-2:] == ["stop:core.second", "stop:core.first"]

    cyclic = PluginRegistry()
    cyclic.register(FakePlugin(manifest("cycle.one", ("cycle.two",)), []))
    cyclic.register(FakePlugin(manifest("cycle.two", ("cycle.one",)), []))
    with pytest.raises(ValueError, match="CYCLE"):
        cyclic.start_all(ConfigurationService(()), FeatureFlagService(()))


def test_incompatible_optional_plugin_is_disabled_without_core_failure() -> None:
    bad = manifest("optional.future")
    bad = PluginManifest(
        bad.plugin_id,
        bad.name,
        bad.version,
        bad.plugin_type,
        bad.contract_version,
        SemanticVersion(3, 0, 0),
        SemanticVersion(3, 9, 0),
    )
    registry = PluginRegistry()
    registry.register(FakePlugin(bad, []))
    registry.start_all(ConfigurationService(()), FeatureFlagService(()))
    assert registry.states() == {"optional.future": "INCOMPATIBLE"}


def test_configuration_types_precedence_ranges_namespace_and_secret_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_PORT", "42")
    definitions = (
        ConfigurationDefinition("plugins.demo.port", int, 10, minimum=1, maximum=100, environment_name="TEST_PORT"),
        ConfigurationDefinition("plugins.demo.secret", str, None, secret=True, environment_name="TEST_SECRET"),
    )
    service = ConfigurationService(definitions)
    assert service.get("plugins.demo.port") == 42
    assert service.namespace("plugins.demo")["plugins.demo.port"] == 42
    assert service.diagnostics()["plugins.demo.secret"]["value"] is None
    monkeypatch.setenv("TEST_SECRET", "do-not-print")
    service.resolve()
    assert service.diagnostics()["plugins.demo.secret"]["value"] == "<redacted>"
    assert "do-not-print" not in json.dumps(service.diagnostics())
    assert ConfigurationService(definitions, {"plugins.demo.port": 7}).get("plugins.demo.port") == 7
    with pytest.raises(ValueError, match="OUT_OF_RANGE"):
        ConfigurationService(definitions, {"plugins.demo.port": 999})


def test_feature_dependencies_and_ai_are_disabled_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LCAI_ENABLE_V2_UI", raising=False)
    flags = default_flags()
    assert not flags.enabled("v2.enabled")
    assert not flags.enabled("ai_tutor.enabled")
    inconsistent = FeatureFlagService(
        (
            FeatureFlagDefinition("parent", False),
            FeatureFlagDefinition("child", False, ("parent",)),
        ),
        {"child": True},
    )
    assert not inconsistent.enabled("child")
    assert "dependency_unsatisfied" in inconsistent.diagnostics()["child"]["source"]
    ai = DisabledAITutor()
    assert ai.health_check() is HealthLevel.DISABLED
    with pytest.raises(RuntimeError, match="AI_TUTOR_DISABLED"):
        ai.generate_guidance({})


@dataclass
class Handler:
    handler_id: str
    priority: int
    results: list[str]
    status: str = "COMPLETED"
    required: bool = False
    supported_event_type: str = "SessionCompleted"
    supported_payload_versions: frozenset[int] = frozenset({1})
    idempotent: bool = True

    def handle(self, event: PlatformEvent, context: PluginContext) -> EventHandlerResult:
        assert context.correlation_id == event.correlation_id
        self.results.append(self.handler_id)
        return EventHandlerResult(self.status, self.status == "FAILED_RETRYABLE")


def event(event_id: str = "event-1") -> PlatformEvent:
    return PlatformEvent(event_id, "SessionCompleted", 1, {"session_id": 12}, NOW, "corr-1", "cause-1")


def test_event_bus_order_failure_isolation_and_versions() -> None:
    calls: list[str] = []
    bus = InternalEventBus()
    bus.register(Handler("optional.failed", 20, calls, "FAILED_RETRYABLE"))
    bus.register(Handler("analytics.core", 10, calls))
    results = bus.dispatch(event())
    assert calls == ["analytics.core", "optional.failed"]
    assert [result.status for result in results] == ["COMPLETED", "FAILED_RETRYABLE"]
    wrong = event("event-v2")
    wrong = PlatformEvent(
        wrong.event_id, wrong.event_type, 2, wrong.payload, NOW, wrong.correlation_id, wrong.causation_id
    )
    assert bus.dispatch(wrong)[0].error_code == "EVENT_PAYLOAD_VERSION_UNSUPPORTED"


def test_persisted_event_idempotence_retry_and_append_only_audit(tmp_path: Path) -> None:
    database = tmp_path / "platform.duckdb"
    apply_migrations(database)
    repository = DuckDBPlatformRepository(database)
    calls: list[str] = []
    bus = InternalEventBus(repository)
    bus.register(Handler("analytics.core", 10, calls))
    assert bus.dispatch(event())[0].status == "COMPLETED"
    assert bus.dispatch(event())[0].status == "ALREADY_COMPLETED"
    assert calls == ["analytics.core"]
    assert repository.backlog_counts() == {"COMPLETED": 1}

    audit = AuditTrailService(repository)
    audit.append(AuditRecord("audit-1", "SESSION", "COMPLETED", NOW, "LEARNER", "actor-1", "SUCCESS", "corr-1"))
    audit.append(
        AuditRecord(
            "audit-2", "ANALYTICS", "CALCULATED", NOW, "SYSTEM", None, "SUCCESS", "corr-1", causation_id="event-1"
        )
    )
    assert [record.audit_id for record in audit.trace("corr-1", True)] == ["audit-1", "audit-2"]
    with pytest.raises(PermissionError):
        audit.trace("corr-1", False)
    with pytest.raises(ValueError, match="SENSITIVE"):
        audit.append(
            AuditRecord("bad", "SECURITY", "BAD", NOW, "SYSTEM", None, "FAILED", "corr", metadata={"token": "x"})
        )


def test_existing_importer_preview_is_dry_run_and_export_safety(tmp_path: Path) -> None:
    source = tmp_path / "content.json"
    source.write_text('{"subjects":[{"code":"MATH","label":"Mathématiques"}]}', encoding="utf-8")
    existing = ImporterRegistry.defaults()
    registry = ImportExportRegistry()
    registry.register_importer("json", lambda path: existing.for_source(path).load(path))
    preview = registry.preview(source)
    assert preview.status == "PREVIEW_READY"
    assert preview.record_count == 1
    assert preview.writes == 0
    assert registry.safe_cell("=1+1") == "'=1+1"
    assert registry.safe_cell("-12.5") == "-12.5"
    assert registry.safe_cell("-cmd") == "'-cmd"
    assert registry.safe_output(tmp_path, "safe.csv") == tmp_path / "safe.csv"
    with pytest.raises(ValueError, match="EXPORT"):
        registry.safe_output(tmp_path, "../escape.csv")


@dataclass
class FailingProvider:
    provider_id: str = "local.failure"
    supported_channels: frozenset[str] = frozenset({"IN_APP"})
    contract_version: SemanticVersion = SemanticVersion(1, 0, 0)
    calls: int = field(default=0)

    def validate_configuration(self) -> bool:
        return True

    def send(self, request: NotificationRequest) -> NotificationDeliveryResult:
        self.calls += 1
        raise RuntimeError("provider unavailable")

    def health_check(self) -> HealthLevel:
        return HealthLevel.DEGRADED


def test_notification_failure_is_isolated_and_request_idempotent() -> None:
    provider = FailingProvider()
    gateway = NotificationGateway((provider,))
    request = NotificationRequest(
        "notification-1",
        "SESSION_COMPLETED",
        "LEARNER",
        "learner-1",
        "IN_APP",
        "session.completed",
        {"session_id": "12"},
        "event-1",
        "corr-1",
    )
    first = gateway.deliver(request, provider.provider_id, True)
    second = gateway.deliver(request, provider.provider_id, True)
    assert first.status == "FAILED_RETRYABLE"
    assert second == first
    assert provider.calls == 1
    assert "answer_key" not in request.template_parameters
