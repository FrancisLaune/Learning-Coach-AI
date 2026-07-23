# Platform extensibility foundation

LCAI-0010 Part 07 adds a local, explicit extension boundary around the existing
application services. Educational services remain the source of truth and are
not plugins. No remote discovery, executable upload, broker, external database,
network API, notification provider, or AI provider is introduced.

## Configuration and features

`ConfigurationService` resolves typed values in this order: test override,
environment variable, registered default. Invalid types and ranges fail
explicitly. Diagnostics show the source and redact every secret value.
Configuration snapshots hash only non-secret values.

Registered settings:

| Key | Type | Default | Environment | Constraint |
| --- | --- | --- | --- | --- |
| `session.autosave_interval_seconds` | integer | 15 | `LCAI_SESSION_AUTOSAVE_INTERVAL_SECONDS` | 5–300 |
| `platform.log_level` | string | INFO | `LCAI_LOG_LEVEL` | DEBUG/INFO/WARNING/ERROR |
| `plugins.core.in-app-notification.enabled` | boolean | false | — | restart |
| `notifications.email.secret` | secret string | absent | `LCAI_EMAIL_SECRET` | optional while disabled |

Feature flags are centralized. `v2.enabled` remains false by default and maps
to `LCAI_ENABLE_V2_UI`. Session execution, analytics, notifications, API, and
AI depend on V2. Email depends on notifications. An unsatisfied dependency
disables the child and appears in diagnostics; a flag never grants access.

## Plugins

Plugin IDs are namespaced (`core.import.json`, for example). A manifest declares
type, semantic version, contract version, compatible platform range,
dependencies, requirement level, feature flags, and internal permissions.
Registration is explicit and reviewed; arbitrary filesystem discovery is
forbidden.

Lifecycle:

`DISCOVERED → VALIDATED → INITIALIZING → INITIALIZED → STARTED → STOPPED`

Disabled, incompatible, degraded, and failed states are explicit. Dependencies
are topologically sorted with stable IDs; cycles and missing dependencies fail
before initialization. Shutdown reverses startup order. Optional failures do
not stop the educational core. `PluginContext` exposes only namespaced
configuration, declared permissions, and correlation metadata—never a raw
database connection or unrestricted repository.

## Events and audit

`InternalEventBus` accepts typed, versioned `PlatformEvent` values and orders
handlers by numeric priority then stable handler ID. Handlers declare payload
versions, requirement, and idempotence. The local DuckDB outbox stores
post-commit events and one unique delivery per `(event_id, handler_id,
handler_version)`. Completed deliveries are not replayed. Retryable and
permanent failures remain inspectable; external calls stay outside educational
transactions. Correlation and causation IDs pass unchanged.

The platform audit table is append-oriented and distinct from logs. Records
contain structured references, not answers, corrections, credentials, tokens,
or secrets. Queries require an explicit authorized context.

## Import, export, notifications, API and future AI

The import registry wraps the existing JSON, CSV, Markdown, YAML, and Excel
content importers. Preview computes a source hash and performs zero writes.
The existing editorial validation and Draft → Review → Approved workflow
remains authoritative.

Export foundations require authorization at the adapter boundary, generated
safe paths, explicit fields, and spreadsheet formula escaping. Text beginning
with `=`, `+`, `@`, or a non-numeric `-` is prefixed with an apostrophe;
negative numeric values remain numeric text.

Notification policy and delivery are separate. Requests are idempotent by
request ID, providers receive a minimal prepared message, and provider failure
cannot invalidate a session. No external provider is configured.

The API capability registry is metadata only; it defines versioned application
use cases and idempotency requirements without exposing DuckDB rows or claiming
that a network API exists.

`DisabledAITutor` is a provider-independent boundary. It is disabled by
default, requires no credentials, and cannot grade answers, update mastery,
approve content, or mutate any business state.

## Operations

- `python -m scripts.platform_diagnostics --json`
- `python -m scripts.validate_plugins --all --report`
- `python -m scripts.process_platform_events --dry-run`
- `python -m scripts.validate_platform_import --source FILE --dry-run`
- `python -m scripts.validate_platform_export --output-directory DIR --authorized --dry-run`

Diagnostics redact secrets and separate core health from optional extension
health. All operations remain local and offline-capable.
