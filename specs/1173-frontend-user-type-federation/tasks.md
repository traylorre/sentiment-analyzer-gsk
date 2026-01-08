# Tasks: Feature 1173

## Implementation Tasks

- [ ] 1. Add type aliases in auth.ts
  - Add `UserRole` type alias
  - Add `VerificationStatus` type alias
  - Verify/add `ProviderType` if needed

- [ ] 2. Update User interface
  - Add `role?: UserRole`
  - Add `linkedProviders?: ProviderType[]`
  - Add `verification?: VerificationStatus`
  - Add `lastProviderUsed?: ProviderType`

- [ ] 3. Validate
  - Run `npm run typecheck`
  - Run `npm run lint`
  - Run `npm run test`

## Completion Criteria

- TypeScript compiles without errors
- Lint passes
- Tests pass
- Feature committed and PR created
