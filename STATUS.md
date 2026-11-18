# Project status

_Last reviewed: 2026-11-19_

This file is a short handover note for continuing work on the project. Update it when the implementation state or next priority changes.

## Project

A Django prototype for working with Saby (СБИС) documents through the Saby API.

The current focus is the document workflow: connect a user to Saby, retrieve incoming document events, show documents that require approval, and provide an approval action. The prototype is being built incrementally; this is not yet a declaration that the whole workflow is production-ready.

## Technology and structure

- Python and Django.
- Django project package: `config/`.
- Application code is grouped under `apps/` (currently `accounts`, `core`, `documents`).
- Saby API requests use an asynchronous HTTP client; synchronous Django views bridge to async service functions with `async_to_sync`.
- HTMX is used for partial page updates and pagination; HTMX 4 request type is checked through `HX-Request-Type`.
- Templates and static assets are maintained separately from Python application code.
- Current database setting in the inspected `dev` branch is SQLite. Do not assume PostgreSQL has been configured.

## Implemented in the inspected `dev` branch

- Django authentication and Saby OAuth connection flow:
  - start authorization;
  - validate OAuth `state` on callback;
  - exchange authorization code for an access token;
  - keep the Saby token in the Django session;
  - disconnect the Saby session.
- Saby API client methods for:
  - listing the user's organizations;
  - retrieving document events;
  - preparing an action;
  - executing an action.
- Parsing and normalization of documents, counterparties, events, attachments, and signatures.
- Counterparty parsing supports legal entities (`СвЮЛ`) and individuals / sole proprietors (`СвФЛ`).
- Retrieval of documents requiring approval, with completed approvals filtered out.
- Date range parameters for event retrieval.
- Local minimum / maximum amount filtering with inclusive boundaries.
- Pagination cursor data is taken from the original parsed API page before local filtering.
- A document approval view that calls Saby prepare-action and execute-action methods.
- Error handling and logging for expected Saby/API/HTTP errors.
- Full-page vs partial-template selection based on `HX-Request-Type`.

## Current work area

Continue developing the document workflow in small, testable steps. The next concrete task should be agreed in the active chat after checking the current branch and local test results.

Potential follow-up areas already discussed:

- Test the date and amount filters together, including empty bounds and boundary values.
- Test HTMX partial responses and pagination, especially that the cursor advances when local filters remove records.
- Verify the approval flow against real Saby responses and confirm the certificate/action parameters are appropriate for the intended account.
- Review how errors are displayed for both full-page and HTMX requests.
- After the main prototype scenarios work, do a focused refactor of views, services, filters, client error handling, and templates. Avoid broad refactoring before the core workflow is verified.
- Keep filter criteria reusable because they may later become the basis for document automation rules.

## Verification status and cautions

- The repository's `dev` branch was inspected to prepare this status on 2026-11-19.
- The code was inspected remotely; this review did **not** run the project, automated tests, browser checks, or live Saby API calls.
- Therefore, items listed as implemented mean that corresponding code exists in the inspected branch, not that every scenario has been verified end to end.
- Local working-tree state and local branch synchronization were not inspected. Before pulling or merging, check the local Git status in PyCharm or with `git status` and `git branch -vv`.
- The `master` branch is the stable branch; `dev` is the working branch. Continue making and testing feature changes in `dev`. Merge into `master` only after local verification and an explicit decision to release the changes.

## How to use this file

At the start of a new development chat, share this file or ask the assistant to read the current version from the repository. Update it when a meaningful feature is completed, a known issue is found, or the next priority changes. Keep it concise; detailed reasoning behind architectural choices belongs in `DECISIONS.md`.
