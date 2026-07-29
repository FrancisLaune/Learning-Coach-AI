"""Local-first registries, lifecycle, event dispatch and extension contracts."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from domain.platform_runtime.models import (
    AuditRecord,
    Compatibility,
    ConfigurationDefinition,
    ConfigurationValue,
    EventHandlerResult,
    FeatureFlagDefinition,
    HealthLevel,
    NotificationDeliveryResult,
    NotificationProvider,
    NotificationRequest,
    PlatformEvent,
    PlatformEventHandler,
    PlatformPlugin,
    PluginContext,
    PluginLifecycle,
    PluginManifest,
    PluginRequirement,
    SemanticVersion,
)

PLATFORM_VERSION = SemanticVersion(2, 0, 0)
PLUGIN_CONTRACT_VERSION = SemanticVersion(1, 0, 0)
EVENT_CONTRACT_VERSION = SemanticVersion(1, 0, 0)


def _parse(raw: str, value_type: type[bool] | type[int] | type[float] | type[str]) -> bool | int | float | str:
    if value_type is bool:
        normalized = raw.strip().lower()
        if normalized not in {"1", "0", "true", "false", "yes", "no"}:
            raise ValueError("CONFIGURATION_INVALID: expected boolean")
        return normalized in {"1", "true", "yes"}
    if value_type is int:
        return int(raw)
    if value_type is float:
        return float(raw)
    return raw


class ConfigurationService:
    """Typed configuration with test > environment > default precedence."""

    def __init__(self, definitions: Iterable[ConfigurationDefinition], overrides: dict[str, Any] | None = None) -> None:
        self._definitions = {definition.key: definition for definition in definitions}
        self._overrides = overrides or {}
        self._values: dict[str, ConfigurationValue] = {}
        self.resolve()

    def resolve(self) -> None:
        values: dict[str, ConfigurationValue] = {}
        for key, definition in self._definitions.items():
            source = "default"
            value = definition.default
            if key in self._overrides:
                source, value = "test_override", self._overrides[key]
            elif definition.environment_name and definition.environment_name in os.environ:
                source = "environment"
                value = _parse(os.environ[definition.environment_name], definition.value_type)
            if value is None and definition.required:
                raise ValueError(f"CONFIGURATION_MISSING: {key}")
            if value is not None and type(value) is not definition.value_type:
                raise ValueError(f"CONFIGURATION_INVALID: {key}")
            if isinstance(value, int | float) and not isinstance(value, bool):
                if definition.minimum is not None and value < definition.minimum:
                    raise ValueError(f"CONFIGURATION_OUT_OF_RANGE: {key}")
                if definition.maximum is not None and value > definition.maximum:
                    raise ValueError(f"CONFIGURATION_OUT_OF_RANGE: {key}")
            if definition.allowed_values and value not in definition.allowed_values:
                raise ValueError(f"CONFIGURATION_INVALID: {key}")
            values[key] = ConfigurationValue(key, value, source, definition.secret)
        self._values = values

    def get(self, key: str) -> bool | int | float | str | None:
        try:
            return self._values[key].value
        except KeyError as exc:
            raise KeyError(f"Unknown configuration: {key}") from exc

    def namespace(self, prefix: str) -> dict[str, Any]:
        marker = f"{prefix}."
        return {key: value.value for key, value in self._values.items() if key.startswith(marker)}

    def diagnostics(self) -> dict[str, dict[str, Any]]:
        return {
            key: {"value": value.diagnostic_value(), "source": value.source}
            for key, value in sorted(self._values.items())
        }

    def snapshot(self) -> tuple[str, dict[str, Any]]:
        data = {key: value.value for key, value in sorted(self._values.items()) if not value.secret}
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest(), data


class FeatureFlagService:
    def __init__(
        self,
        definitions: Iterable[FeatureFlagDefinition],
        overrides: dict[str, bool] | None = None,
    ) -> None:
        self._definitions = {definition.name: definition for definition in definitions}
        self._overrides = overrides or {}
        self._effective: dict[str, tuple[bool, str]] = {}
        self.resolve()

    def resolve(self) -> None:
        effective: dict[str, tuple[bool, str]] = {}
        for name, definition in self._definitions.items():
            value, source = definition.default, "default"
            if name in self._overrides:
                value, source = self._overrides[name], "test_override"
            elif definition.environment_name and definition.environment_name in os.environ:
                parsed = _parse(os.environ[definition.environment_name], bool)
                assert isinstance(parsed, bool)
                value = parsed
                source = "environment"
            effective[name] = (bool(value), source)
        for name, definition in self._definitions.items():
            if effective[name][0]:
                missing = [
                    dependency
                    for dependency in definition.dependencies
                    if not effective.get(dependency, (False, ""))[0]
                ]
                if missing:
                    effective[name] = (False, f"dependency_unsatisfied:{','.join(missing)}")
        self._effective = effective

    def enabled(self, name: str) -> bool:
        return self._effective.get(name, (False, "unknown"))[0]

    def diagnostics(self) -> dict[str, dict[str, Any]]:
        return {name: {"enabled": value, "source": source} for name, (value, source) in sorted(self._effective.items())}


class VersionRegistry:
    def __init__(self) -> None:
        self._versions: dict[str, SemanticVersion] = {}
        self._deprecations: dict[str, dict[str, str]] = {}

    def register(self, category: str, version: SemanticVersion) -> None:
        self._versions[category] = version

    def get(self, category: str) -> SemanticVersion:
        return self._versions[category]

    def all(self) -> dict[str, str]:
        return {category: str(version) for category, version in sorted(self._versions.items())}

    def deprecate(self, category: str, replacement: str, since: str, removal: str) -> None:
        self._deprecations[category] = {"replacement": replacement, "since": since, "removal": removal}


def compatible(current: SemanticVersion, minimum: SemanticVersion, maximum: SemanticVersion) -> Compatibility:
    if current < minimum or current > maximum or current.major != minimum.major:
        return Compatibility.INCOMPATIBLE
    if current.major == maximum.major and current.minor <= maximum.minor:
        return Compatibility.COMPATIBLE
    return Compatibility.COMPATIBLE_WITH_WARNING


@dataclass(slots=True)
class RegisteredPlugin:
    plugin: PlatformPlugin
    state: PluginLifecycle = PluginLifecycle.DISCOVERED
    error_code: str | None = None


class PluginRegistry:
    """Explicit reviewed-plugin registry with deterministic lifecycle."""

    def __init__(self, platform_version: SemanticVersion = PLATFORM_VERSION) -> None:
        self.platform_version = platform_version
        self._plugins: dict[str, RegisteredPlugin] = {}
        self._start_order: list[str] = []

    def register(self, plugin: PlatformPlugin) -> None:
        plugin.manifest.validate()
        if plugin.manifest.plugin_id in self._plugins:
            raise ValueError(f"PLUGIN_DUPLICATE_ID: {plugin.manifest.plugin_id}")
        self._plugins[plugin.manifest.plugin_id] = RegisteredPlugin(plugin)

    def _ordered(self) -> list[str]:
        missing = {
            dependency
            for registered in self._plugins.values()
            for dependency in registered.plugin.manifest.dependencies
            if dependency not in self._plugins
        }
        if missing:
            raise ValueError(f"PLUGIN_DEPENDENCY_MISSING: {','.join(sorted(missing))}")
        ordered: list[str] = []
        visiting: set[str] = set()

        def visit(plugin_id: str) -> None:
            if plugin_id in visiting:
                raise ValueError("PLUGIN_DEPENDENCY_CYCLE")
            if plugin_id in ordered:
                return
            visiting.add(plugin_id)
            for dependency in sorted(self._plugins[plugin_id].plugin.manifest.dependencies):
                visit(dependency)
            visiting.remove(plugin_id)
            ordered.append(plugin_id)

        for plugin_id in sorted(self._plugins):
            visit(plugin_id)
        return ordered

    def start_all(self, configuration: ConfigurationService, flags: FeatureFlagService) -> None:
        for plugin_id in self._ordered():
            registered = self._plugins[plugin_id]
            manifest = registered.plugin.manifest
            if (
                compatible(self.platform_version, manifest.platform_min, manifest.platform_max)
                is Compatibility.INCOMPATIBLE
            ):
                registered.state, registered.error_code = PluginLifecycle.INCOMPATIBLE, "PLUGIN_INCOMPATIBLE"
                if manifest.requirement is PluginRequirement.PLATFORM_REQUIRED:
                    raise RuntimeError("PLUGIN_INCOMPATIBLE")
                continue
            if any(not flags.enabled(flag) for flag in manifest.feature_flags):
                registered.state = PluginLifecycle.DISABLED
                continue
            registered.state = PluginLifecycle.VALIDATED
            try:
                registered.state = PluginLifecycle.INITIALIZING
                context = PluginContext(
                    plugin_id,
                    configuration.namespace(f"plugins.{plugin_id}"),
                    manifest.permissions,
                    f"startup-{plugin_id}",
                )
                registered.plugin.initialize(context)
                registered.state = PluginLifecycle.INITIALIZED
                registered.plugin.start()
                registered.state = PluginLifecycle.STARTED
                self._start_order.append(plugin_id)
            except Exception:
                registered.state, registered.error_code = PluginLifecycle.FAILED, "PLUGIN_INITIALIZATION_FAILED"
                if manifest.requirement is PluginRequirement.PLATFORM_REQUIRED:
                    raise

    def stop_all(self) -> None:
        for plugin_id in reversed(self._start_order):
            self._plugins[plugin_id].plugin.stop()
            self._plugins[plugin_id].state = PluginLifecycle.STOPPED
        self._start_order.clear()

    def states(self) -> dict[str, str]:
        return {plugin_id: registered.state.value for plugin_id, registered in sorted(self._plugins.items())}

    def manifests(self) -> tuple[PluginManifest, ...]:
        return tuple(self._plugins[key].plugin.manifest for key in sorted(self._plugins))


class DeliveryStore(Protocol):
    def create_or_get(self, event: PlatformEvent, handler_id: str) -> str | None: ...

    def mark_success(self, event_id: str, handler_id: str, result: EventHandlerResult) -> None: ...

    def mark_failure(self, event_id: str, handler_id: str, result: EventHandlerResult) -> None: ...


class InternalEventBus:
    def __init__(self, delivery_store: DeliveryStore | None = None) -> None:
        self._handlers: list[PlatformEventHandler] = []
        self.delivery_store = delivery_store

    def register(self, handler: PlatformEventHandler) -> None:
        if any(existing.handler_id == handler.handler_id for existing in self._handlers):
            raise ValueError(f"Duplicate event handler: {handler.handler_id}")
        self._handlers.append(handler)

    def dispatch(self, event: PlatformEvent) -> tuple[EventHandlerResult, ...]:
        handlers = sorted(
            (handler for handler in self._handlers if handler.supported_event_type == event.event_type),
            key=lambda handler: (handler.priority, handler.handler_id),
        )
        results: list[EventHandlerResult] = []
        for handler in handlers:
            if event.payload_version not in handler.supported_payload_versions:
                result = EventHandlerResult("FAILED_PERMANENT", False, error_code="EVENT_PAYLOAD_VERSION_UNSUPPORTED")
                results.append(result)
                if handler.required:
                    break
                continue
            previous = self.delivery_store.create_or_get(event, handler.handler_id) if self.delivery_store else None
            if previous == "COMPLETED":
                results.append(EventHandlerResult("ALREADY_COMPLETED"))
                continue
            started = time.perf_counter()
            context = PluginContext(handler.handler_id, {}, frozenset(), event.correlation_id)
            try:
                handled = handler.handle(event, context)
                result = EventHandlerResult(
                    handled.status,
                    handled.retryable,
                    handled.output_references,
                    handled.error_code,
                    (time.perf_counter() - started) * 1000,
                )
            except Exception:
                result = EventHandlerResult("FAILED_PERMANENT", False, error_code="EVENT_HANDLER_FAILED")
            results.append(result)
            if self.delivery_store:
                if result.status in {"COMPLETED", "SKIPPED"}:
                    self.delivery_store.mark_success(event.event_id, handler.handler_id, result)
                else:
                    self.delivery_store.mark_failure(event.event_id, handler.handler_id, result)
            if handler.required and result.status not in {"COMPLETED", "SKIPPED", "ALREADY_COMPLETED"}:
                break
        return tuple(results)

    def diagnostics(self) -> tuple[dict[str, Any], ...]:
        return tuple(
            {
                "handler_id": handler.handler_id,
                "event_type": handler.supported_event_type,
                "versions": sorted(handler.supported_payload_versions),
                "priority": handler.priority,
                "required": handler.required,
            }
            for handler in sorted(self._handlers, key=lambda item: (item.priority, item.handler_id))
        )


class AuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...

    def list_by_correlation(self, correlation_id: str) -> tuple[AuditRecord, ...]: ...


class AuditTrailService:
    _forbidden = {"password", "token", "secret", "answer_key", "credential"}

    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    def append(self, record: AuditRecord) -> None:
        if any(key.lower() in self._forbidden for key in record.metadata):
            raise ValueError("AUDIT_SENSITIVE_VALUE_FORBIDDEN")
        self.repository.append(record)

    def trace(self, correlation_id: str, authorized: bool) -> tuple[AuditRecord, ...]:
        if not authorized:
            raise PermissionError("AUDIT_ACCESS_DENIED")
        return self.repository.list_by_correlation(correlation_id)


@dataclass(frozen=True, slots=True)
class ImportPreview:
    source_hash: str
    format_name: str
    status: str
    record_count: int
    writes: int = 0


class ImportExportRegistry:
    """Formalizes existing importers and safe, authorized JSON/CSV exports."""

    DANGEROUS_PREFIXES = ("=", "+", "@")

    def __init__(self) -> None:
        self._importers: dict[str, Callable[[Path], Any]] = {}

    def register_importer(self, suffix: str, loader: Callable[[Path], Any]) -> None:
        self._importers[suffix.lower().lstrip(".")] = loader

    def preview(self, source: Path, maximum_bytes: int = 5_000_000) -> ImportPreview:
        if not source.is_file() or source.stat().st_size > maximum_bytes:
            raise ValueError("IMPORT_VALIDATION_FAILED")
        suffix = source.suffix.lower().lstrip(".")
        if suffix not in self._importers:
            raise ValueError("IMPORT_FORMAT_UNSUPPORTED")
        document = self._importers[suffix](source)
        count = sum(
            len(getattr(document, name, ())) for name in ("programs", "subjects", "domains", "skills", "exercises")
        )
        return ImportPreview(hashlib.sha256(source.read_bytes()).hexdigest(), suffix, "PREVIEW_READY", count)

    @classmethod
    def safe_cell(cls, value: Any) -> Any:
        if isinstance(value, str) and value.startswith(cls.DANGEROUS_PREFIXES):
            return f"'{value}"
        if isinstance(value, str) and value.startswith("-") and not value[1:].replace(".", "", 1).isdigit():
            return f"'{value}"
        return value

    @staticmethod
    def safe_output(base: Path, filename: str) -> Path:
        safe_name = Path(filename).name
        if safe_name != filename or safe_name in {"", ".", ".."}:
            raise ValueError("EXPORT_GENERATION_FAILED")
        target = (base / safe_name).resolve()
        if base.resolve() not in target.parents:
            raise ValueError("EXPORT_GENERATION_FAILED")
        return target


class DisabledAITutor:
    def get_capabilities(self) -> tuple[str, ...]:
        return ()

    def validate_configuration(self) -> bool:
        return True

    def generate_guidance(self, request: Any) -> None:
        raise RuntimeError("AI_TUTOR_DISABLED")

    def health_check(self) -> HealthLevel:
        return HealthLevel.DISABLED


class NotificationGateway:
    """Delivery isolation: policy prepares a minimal request, providers only deliver it."""

    def __init__(self, providers: Iterable[NotificationProvider] = ()) -> None:
        self._providers = {provider.provider_id: provider for provider in providers}
        self._results: dict[str, NotificationDeliveryResult] = {}

    def deliver(self, request: NotificationRequest, provider_id: str, enabled: bool) -> NotificationDeliveryResult:
        if request.notification_request_id in self._results:
            return self._results[request.notification_request_id]
        if not enabled:
            result = NotificationDeliveryResult(provider_id, "SKIPPED_FEATURE_DISABLED", False)
        elif provider_id not in self._providers:
            result = NotificationDeliveryResult(
                provider_id, "FAILED_PERMANENT", False, "NOTIFICATION_PROVIDER_UNAVAILABLE"
            )
        else:
            try:
                result = self._providers[provider_id].send(request)
            except Exception:
                result = NotificationDeliveryResult(
                    provider_id, "FAILED_RETRYABLE", True, "NOTIFICATION_DELIVERY_FAILED"
                )
        self._results[request.notification_request_id] = result
        return result


class ApiCapabilityRegistry:
    """Network-framework-independent metadata for application use cases."""

    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Any]] = {}

    def register(self, capability_id: str, *, write: bool, idempotency_required: bool) -> None:
        if capability_id in self._capabilities:
            raise ValueError(f"Duplicate API capability: {capability_id}")
        self._capabilities[capability_id] = {
            "write": write,
            "idempotency_required": idempotency_required,
            "version": "1.0.0",
        }

    def describe(self) -> dict[str, dict[str, Any]]:
        return {key: dict(value) for key, value in sorted(self._capabilities.items())}


def default_configuration() -> ConfigurationService:
    definitions = (
        ConfigurationDefinition(
            "session.autosave_interval_seconds",
            int,
            15,
            minimum=5,
            maximum=300,
            environment_name="LCAI_SESSION_AUTOSAVE_INTERVAL_SECONDS",
        ),
        ConfigurationDefinition(
            "platform.log_level",
            str,
            "INFO",
            allowed_values=frozenset({"DEBUG", "INFO", "WARNING", "ERROR"}),
            environment_name="LCAI_LOG_LEVEL",
        ),
        ConfigurationDefinition("plugins.core.in-app-notification.enabled", bool, False),
        ConfigurationDefinition(
            "notifications.email.secret", str, None, secret=True, required=False, environment_name="LCAI_EMAIL_SECRET"
        ),
    )
    return ConfigurationService(definitions)


def default_flags() -> FeatureFlagService:
    return FeatureFlagService(
        (
            FeatureFlagDefinition("v2.enabled", False, environment_name="LCAI_ENABLE_V2_UI"),
            FeatureFlagDefinition(
                "session.execution.enabled",
                False,
                ("v2.enabled",),
                environment_name="LCAI_V2_SESSION_EXECUTION_ENABLED",
            ),
            FeatureFlagDefinition(
                "analytics.enabled", False, ("v2.enabled",), environment_name="LCAI_ANALYTICS_ENABLED"
            ),
            FeatureFlagDefinition(
                "notifications.enabled", False, ("v2.enabled",), environment_name="LCAI_NOTIFICATIONS_ENABLED"
            ),
            FeatureFlagDefinition(
                "notifications.email.enabled",
                False,
                ("notifications.enabled",),
                environment_name="LCAI_EMAIL_NOTIFICATIONS_ENABLED",
            ),
            FeatureFlagDefinition("api.enabled", False, ("v2.enabled",), environment_name="LCAI_API_ENABLED"),
            FeatureFlagDefinition("ai_tutor.enabled", False, ("v2.enabled",), environment_name="LCAI_AI_TUTOR_ENABLED"),
            FeatureFlagDefinition(
                "homework_ai_fallback_4e",
                False,
                ("v2.enabled",),
                environment_name="HOMEWORK_AI_FALLBACK_4E_ENABLED",
            ),
        )
    )


def default_versions(database_migration: int = 14) -> VersionRegistry:
    registry = VersionRegistry()
    for category, version in {
        "PLATFORM": PLATFORM_VERSION,
        "DATABASE_SCHEMA": SemanticVersion(database_migration, 0, 0),
        "SESSION_ENGINE": SemanticVersion(1, 0, 0),
        "ASSESSMENT_ENGINE": SemanticVersion(1, 0, 0),
        "MASTERY_ENGINE": SemanticVersion(1, 0, 0),
        "ANALYTICS_ENGINE": SemanticVersion(1, 0, 0),
        "EVENT_CONTRACT": EVENT_CONTRACT_VERSION,
        "PLUGIN_CONTRACT": PLUGIN_CONTRACT_VERSION,
        "API_CONTRACT": SemanticVersion(1, 0, 0),
        "IMPORT_CONTRACT": SemanticVersion(1, 0, 0),
        "EXPORT_CONTRACT": SemanticVersion(1, 0, 0),
    }.items():
        registry.register(category, version)
    return registry


def utcnow() -> datetime:
    return datetime.now(UTC)
