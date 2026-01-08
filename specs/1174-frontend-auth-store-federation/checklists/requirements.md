# Requirements Checklist: Feature 1174

## Functional Requirements

- [ ] FR-1: Anonymous users have role='anonymous' in state
- [ ] FR-2: Anonymous users have linkedProviders=[] in state
- [ ] FR-3: Anonymous users have verification='none' in state
- [ ] FR-4: OAuth users have federation fields from API
- [ ] FR-5: Profile refresh updates federation fields

## Non-Functional Requirements

- [ ] NFR-1: TypeScript compiles without errors
- [ ] NFR-2: Lint passes
- [ ] NFR-3: Existing tests still pass

## Testing Evidence

- [ ] TE-1: npm run typecheck passes
- [ ] TE-2: npm run lint passes
- [ ] TE-3: npm run test passes
