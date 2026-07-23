# Learning Experience presentation layer

## Scope

LCAI-0010 Part 04 introduces the optional Student and Parent experience for the
V2 Session Engine. The existing V1 interface remains the default. The new
experience is enabled explicitly with `LCAI_ENABLE_V2_UI=true`.

## Dependency direction

Streamlit views call presentation controllers. Controllers call application
services. Application services consume typed read-model and session-service
ports. Only the composition root constructs DuckDB adapters.

```text
Streamlit views
      ↓
Presentation controllers
      ↓
Learner Experience / Learning Session services
      ↓
Typed ports
      ↓
DuckDB V2 adapters
```

No business calculation is implemented in Streamlit Session State. Session
State contains navigation and selected identifiers only.

## Implemented views

The Student experience provides a dashboard, current session, session summary,
history and settings boundary. It displays the objective, study duration,
mastery, progress, activities, scores and revision information available in
V2.

The Parent experience provides learner selection, KPI cards, mastery and
completed-session history. Teacher, gamification and AI Tutor features remain
out of scope.

## Accessibility and errors

Controls retain visible labels, keyboard focus has a high-contrast outline,
progress is expressed through text as well as color, and responsive columns
wrap on narrower screens. Technical exceptions are converted by controllers
into short user-facing messages with a recovery action; stack traces and
database details are not displayed.

## Performance

Dashboard queries are bounded and ordered. Controllers return immutable DTOs
and views perform no business-data persistence. The architecture leaves room
for read-model caching without changing the UI contract.
