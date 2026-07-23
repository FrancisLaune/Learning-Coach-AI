"""Dependency-free platform contracts; educational domain services stay authoritative."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

PLUGIN_ID = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")


class PluginType(StrEnum):
    IMPORTER = "IMPORTER"
    EXPORTER = "EXPORTER"
    NOTIFICATION = "NOTIFICATION"
    EVENT_HANDLER = "EVENT_HANDLER"
    PRESENTATION = "PRESENTATION"
    ANALYTICS = "ANALYTICS"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class PluginLifecycle(StrEnum):
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    DISABLED = "DISABLED"
    INCOMPATIBLE = "INCOMPATIBLE"
    INITIALIZING = "INITIALIZING"
    INITIALIZED = "INITIALIZED"
    STARTED = "STARTED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class PluginRequirement(StrEnum):
    OPTIONAL = "OPTIONAL"
    REQUIRED_FOR_FEATURE = "REQUIRED_FOR_FEATURE"
    PLATFORM_REQUIRED = "PLATFORM_REQUIRED"


class PluginPermission(StrEnum):
    READ_LEARNER_SUMMARY = "READ_LEARNER_SUMMARY"
    READ_SESSION_SUMMARY = "READ_SESSION_SUMMARY"
    READ_ANALYTICS = "READ_ANALYTICS"
    WRITE_NOTIFICATION_DELIVERY = "WRITE_NOTIFICATION_DELIVERY"
    IMPORT_CONTENT_DRAFT = "IMPORT_CONTENT_DRAFT"
    EXPORT_CURRICULUM = "EXPORT_CURRICULUM"
    READ_AUDIT_EVENTS = "READ_AUDIT_EVENTS"
    CALL_AI_CONTEXT_PORT = "CALL_AI_CONTEXT_PORT"


class Compatibility(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    COMPATIBLE_WITH_WARNING = "COMPATIBLE_WITH_WARNING"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class HealthLevel(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    INCOMPATIBLE = "INCOMPATIBLE"


@dataclass(frozen=True, slots=True, order=True)
class SemanticVersion:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> SemanticVersion:
        parts = value.split(".")
        if len(parts) != 3 or any(not part.isdigit() for part in parts):
            raise ValueError(f"Invalid semantic version: {value}")
        return cls(*(int(part) for part in parts))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True, slots=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: SemanticVersion
    plugin_type: PluginType
    contract_version: SemanticVersion
    platform_min: SemanticVersion
    platform_max: SemanticVersion
    requirement: PluginRequirement = PluginRequirement.OPTIONAL
    dependencies: tuple[str, ...] = ()
    permissions: frozenset[PluginPermission] = frozenset()
    feature_flags: tuple[str, ...] = ()

    def validate(self) -> None:
        if not PLUGIN_ID.fullmatch(self.plugin_id):
            raise ValueError("PLUGIN_MANIFEST_INVALID: plugin_id must be stable and namespaced")
        if self.platform_max < self.platform_min:
            raise ValueError("PLUGIN_MANIFEST_INVALID: invalid platform range")
        if self.plugin_id in self.dependencies:
            raise ValueError("PLUGIN_DEPENDENCY_CYCLE: plugin depends on itself")


@dataclass(frozen=True, slots=True)
class PluginContext:
    plugin_id: str
    configuration: dict[str, Any]
    permissions: frozenset[PluginPermission]
    correlation_id: str


class PlatformPlugin(Protocol):
    manifest: PluginManifest

    def initialize(self, context: PluginContext) -> None: ...

    def start(self) -> None: ...

    def health_check(self) -> HealthLevel: ...

    def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PlatformEvent:
    event_id: str
    event_type: str
    payload_version: int
    payload: dict[str, Any]
    occurred_at: datetime
    correlation_id: str
    causation_id: str | None = None
    aggregate_type: str | None = None
    aggregate_id: str | None = None


@dataclass(frozen=True, slots=True)
class EventHandlerResult:
    status: str
    retryable: bool = False
    output_references: tuple[str, ...] = ()
    error_code: str | None = None
    duration_ms: float = 0.0


class PlatformEventHandler(Protocol):
    handler_id: str
    supported_event_type: str
    supported_payload_versions: frozenset[int]
    priority: int
    required: bool
    idempotent: bool

    def handle(self, event: PlatformEvent, context: PluginContext) -> EventHandlerResult: ...


@dataclass(frozen=True, slots=True)
class ConfigurationDefinition:
    key: str
    value_type: type[bool] | type[int] | type[float] | type[str]
    default: bool | int | float | str | None
    required: bool = False
    minimum: float | None = None
    maximum: float | None = None
    allowed_values: frozenset[bool | int | float | str] = frozenset()
    secret: bool = False
    restart_required: bool = True
    description: str = ""
    version: str = "1.0.0"
    environment_name: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigurationValue:
    key: str
    value: bool | int | float | str | None
    source: str
    secret: bool = False

    def diagnostic_value(self) -> bool | int | float | str | None:
        return "<redacted>" if self.secret and self.value is not None else self.value


@dataclass(frozen=True, slots=True)
class FeatureFlagDefinition:
    name: str
    default: bool = False
    dependencies: tuple[str, ...] = ()
    description: str = ""
    environment_name: str | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    audit_id: str
    category: str
    action: str
    occurred_at: datetime
    actor_type: str
    actor_id: str | None
    outcome: str
    correlation_id: str
    resource_type: str | None = None
    resource_id: str | None = None
    learner_id: int | None = None
    causation_id: str | None = None
    summary_code: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    sensitivity_level: str = "INTERNAL"

    @classmethod
    def now(cls, **values: Any) -> AuditRecord:
        return cls(occurred_at=datetime.now(UTC), **values)


@dataclass(frozen=True, slots=True)
class SafePlatformError:
    error_code: str
    user_message: str
    technical_message: str
    recoverable: bool
    retry_allowed: bool
    affected_feature: str | None
    correlation_id: str
    plugin_id: str | None = None
    recommended_action: str | None = None


@dataclass(frozen=True, slots=True)
class NotificationRequest:
    notification_request_id: str
    notification_type: str
    recipient_type: str
    recipient_id: str
    channel: str
    template_code: str
    template_parameters: dict[str, str]
    source_event_id: str
    correlation_id: str
    status: str = "CREATED"
    policy_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class NotificationDeliveryResult:
    provider_id: str
    status: str
    retryable: bool
    error_code: str | None = None
    provider_message_id: str | None = None


class NotificationProvider(Protocol):
    provider_id: str
    supported_channels: frozenset[str]
    contract_version: SemanticVersion

    def validate_configuration(self) -> bool: ...

    def send(self, request: NotificationRequest) -> NotificationDeliveryResult: ...

    def health_check(self) -> HealthLevel: ...


@dataclass(frozen=True, slots=True)
class ApiCapability:
    capability_id: str
    version: SemanticVersion
    write: bool
    idempotency_required: bool
    required_permissions: frozenset[str]
