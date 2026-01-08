# Tasks: Feature 1174

## Implementation Tasks

- [ ] 1. Update anonymous session initialization
  - Add role: 'anonymous'
  - Add linkedProviders: []
  - Add verification: 'none'
  - Add lastProviderUsed: undefined

- [ ] 2. Add response mapper for /me endpoint (if needed)
  - Handle snake_case → camelCase
  - Map all federation fields

- [ ] 3. Add refreshUserProfile action
  - Call /api/v2/auth/me
  - Map response to User
  - Update state via setUser

- [ ] 4. Validate
  - Run typecheck
  - Run lint
  - Run tests

## Completion Criteria

- TypeScript compiles
- Lint passes
- Tests pass
- PR created with auto-merge
