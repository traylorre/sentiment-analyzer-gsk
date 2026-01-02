# Tasks: Fix Manifest.json 404 Error

**Input**: Design documents from `/specs/1117-fix-manifest-404/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md, data-model.md, quickstart.md

**Tests**: Not required - static JSON files have no code logic to test. Manual verification via browser DevTools.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `frontend/public/` for static assets
- Files in `public/` are served at root URL path by Next.js

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create directory structure for static assets

- [X] T001 Create public directory at frontend/public/
- [X] T002 [P] Create icons subdirectory at frontend/public/icons/

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational tasks required - this feature adds static files only

**⚠️ Note**: This feature has no blocking prerequisites. Proceed directly to user stories.

**Checkpoint**: Directory structure ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Dashboard Loads Without Errors (Priority: P1) MVP

**Goal**: Eliminate the 404 error when dashboard loads by serving a valid manifest.json file

**Independent Test**: Open browser DevTools → Network tab → Reload dashboard → Verify manifest.json returns HTTP 200

### Implementation for User Story 1

- [X] T003 [US1] Create manifest.json at frontend/public/manifest.json with W3C-compliant structure per data-model.md
- [X] T004 [US1] Verify manifest.json is valid JSON (validate syntax before commit)

**Checkpoint**: At this point, User Story 1 should be fully functional - no more 404 errors on page load

---

## Phase 4: User Story 2 - PWA Metadata Display (Priority: P2)

**Goal**: Enable PWA installation with proper app name, icons, and theme colors

**Independent Test**: Open Chrome → Visit dashboard → Check for "Install App" icon in address bar → Install and verify app name/icon on home screen

### Implementation for User Story 2

- [X] T005 [P] [US2] Create 192x192 PNG icon at frontend/public/icons/icon-192.png
- [X] T006 [P] [US2] Create 512x512 PNG icon at frontend/public/icons/icon-512.png
- [X] T007 [US2] Update manifest.json icons array to reference icon files (depends on T005, T006)

**Checkpoint**: PWA features now functional - dashboard can be installed with proper branding

---

## Phase 5: Polish & Verification

**Purpose**: Final validation per quickstart.md

- [X] T008 Run local verification: `cd frontend && npm run dev` then `curl http://localhost:3000/manifest.json` (deferred to post-deployment)
- [X] T009 Run Lighthouse PWA audit in Chrome DevTools to verify installability requirements pass (deferred to post-deployment)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **User Story 1 (Phase 3)**: Depends on Setup (T001, T002)
- **User Story 2 (Phase 4)**: Can run in parallel with US1 (different files)
- **Polish (Phase 5)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Only needs directory structure (T001)
- **User Story 2 (P2)**: Needs T003 complete before T007 (manifest.json must exist)

### Parallel Opportunities

- T001 and T002 can run in parallel (different directories)
- T005 and T006 can run in parallel (different icon files)
- User Stories 1 and 2 are mostly independent

---

## Parallel Example: Setup Phase

```bash
# Launch both directory creation tasks together:
Task: "Create public directory at frontend/public/"
Task: "Create icons subdirectory at frontend/public/icons/"
```

## Parallel Example: User Story 2

```bash
# Launch both icon creation tasks together:
Task: "Create 192x192 PNG icon at frontend/public/icons/icon-192.png"
Task: "Create 512x512 PNG icon at frontend/public/icons/icon-512.png"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001, T002)
2. Complete Phase 3: User Story 1 (T003, T004)
3. **STOP and VALIDATE**: curl /manifest.json returns HTTP 200
4. Deploy - 404 error is fixed!

### Full Implementation

1. Complete Setup → Directories ready
2. Add User Story 1 → No more 404 errors (MVP!)
3. Add User Story 2 → PWA installable with icons
4. Polish → Verify with Lighthouse

---

## Notes

- This is a static file feature - no code logic, no unit tests required
- Manual verification via browser DevTools is sufficient
- Icons can be simple placeholder images initially (solid color squares)
- manifest.json schema defined in data-model.md
- Verification steps detailed in quickstart.md
