# Architecture and workflow decisions

This is a lightweight decision log. It records decisions that affect how the project is built and why. It is not a list of universal rules: revisit an item when requirements or evidence change.

## 1. Keep the application Django-first

**Decision**

Use Django as the main application framework and keep the implementation straightforward.

**Why**

The project is being developed by one person, and the goal is to deliver a working product without unnecessary infrastructure or framework complexity.

**Current convention**

- Organize application code under `apps/`.
- Keep templates under `templates/<app_name>/` (including app partials).
- Keep static assets under `static/`.
- Prefer ordinary Django views, services, forms/filters, and templates where they are sufficient.
- Do not introduce extra layers or dependencies without a concrete need.

## 2. Use HTMX for server-rendered interactions

**Decision**

Use Django-rendered HTML and HTMX for interactions that need a server round-trip. Use JavaScript only for behavior that genuinely belongs in the browser.

**Why**

This keeps most application behavior on the server and avoids building a separate frontend application.

**Current convention**

- Return a full page for a normal browser request.
- Return the relevant partial for an HTMX partial request.
- In the current HTMX 4 integration, distinguish these with the `HX-Request-Type` header (for example, `partial`).
- Keep client-side state and JavaScript small; do not duplicate server-side business rules in the browser.

## 3. Keep Saby API communication in a client/service boundary

**Decision**

Keep low-level Saby HTTP/JSON-RPC calls in the API client, and compose application operations in service functions.

**Why**

Views should not need to know Saby endpoint details, raw response structure, or how multiple API calls are orchestrated.

**Current convention**

- `DocumentsClient` exposes domain-oriented methods such as `get_events`, `get_organizations`, `prepare_action`, and `execute_action`.
- Service functions open and close the async client and normalize API response shapes.
- Views call async services through `async_to_sync` while the current Django views remain synchronous.
- Do not move raw Saby request construction into templates or views.

## 4. Normalize Saby responses before applying application logic

**Decision**

Parse Saby's external response into a predictable internal Python structure before filtering or rendering it.

**Why**

Saby's response is an external format and may contain optional fields or values represented as either a single object or a list. Application code should not have to repeatedly handle those variations.

**Current convention**

- Parsing functions live in `apps/documents/parsers.py`.
- Filters and services work with normalized document/event dictionaries rather than reaching into raw Saby JSON.
- Counterparty parsing accounts for both legal entities (`СвЮЛ`) and individuals / sole proprietors (`СвФЛ`).
- When adding a field, inspect real API examples and treat optional fields defensively.

## 5. Keep document filtering server-side and reusable

**Decision**

Apply document criteria on the server after parsing, rather than filtering raw API payloads in views or in browser JavaScript.

**Why**

The same criteria may later be reused by automation rules. Keeping the rules independent from HTTP request handling makes that evolution easier.

**Current convention**

- Filtering functions live in `apps/documents/filters.py`.
- Amount range bounds are optional and inclusive.
- Use `Decimal` for monetary comparisons rather than binary floating-point arithmetic.
- Keep request parsing/validation in the view layer; keep the actual document-selection logic in reusable functions.
- Avoid coupling future automation criteria to Django's `request` or template context.

## 6. Compute pagination cursor before local filtering

**Decision**

Derive the next-page cursor from the original parsed API page before applying local document filters.

**Why**

If the cursor is taken from the filtered result, a page in which every document is filtered out may fail to advance pagination. That can cause repeated requests or skipped progress.

**Current convention**

The service finds the last event from the parsed page first, then applies document status and amount filters, and returns the cursor separately from the filtered documents.

## 7. Keep OAuth flow on the Django server

**Decision**

Use a server-managed OAuth authorization-code flow for Saby. Django starts authorization, validates the returned `state`, exchanges the code for an access token, and stores the token in the user's session.

**Why**

The client secret and token exchange belong on the server. Validating `state` protects the callback from unsolicited or mismatched authorization responses.

**Current convention**

- Generate a cryptographically random `state` value and keep it in the session.
- Compare the callback's `state` with the stored value.
- Exchange the authorization code server-side.
- Keep the Saby access token in the Django session; do not expose it to browser JavaScript or templates.
- Use the configured redirect URI and OAuth endpoints from Django settings/environment configuration.

## 8. Handle expected API failures at the view boundary

**Decision**

Catch expected Saby and HTTP exceptions at the view boundary, log technical details, and return a user-facing error response.

**Why**

A remote API failure should not result in an unhandled server error, and users should receive a useful message without exposing unnecessary implementation details.

**Current convention**

- Saby/API exception formatting is centralized in view helpers.
- Log technical context for diagnosis.
- Return an appropriate HTTP status and pass a readable message/details to the template.
- Avoid swallowing unexpected programming errors with a broad `except Exception`.

## 9. Use `dev` for work and `master` for stable code

**Decision**

Develop and test changes in `dev`; keep `master` as the stable branch.

**Why**

This gives the project a safe place to integrate and test changes before treating them as stable.

**Current convention**

- Make feature changes in `dev`.
- Pull and test `dev` locally before release.
- Merge `dev` into `master` only after the change has been checked.
- Do not use rebase or force-push as part of the ordinary workflow.
- Do not merge branches mechanically; first inspect whether either branch contains commits missing from the other.

## 10. Refactor after the core prototype scenarios work

**Decision**

Prefer incremental delivery now; schedule a focused refactoring pass after the main prototype workflows are implemented and tested.

**Why**

Premature cleanup can distract from validating the actual workflow. At the same time, recurring issues should be recorded so they can be addressed systematically later.

**Planned review areas**

- View complexity, repeated context construction, and error handling.
- Service return structures and boundaries between services and views.
- Reusable filter/criteria design for future automation.
- Client typing and error handling.
- Template partials and HTMX request/response behavior.

The goal is to simplify code that has demonstrated friction, not to introduce abstractions merely for stylistic consistency.
