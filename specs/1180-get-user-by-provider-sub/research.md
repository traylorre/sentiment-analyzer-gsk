# Research: GSI Design for Provider Sub Lookup

## Decision: Single-attribute composite key GSI

**Rationale**: DynamoDB GSIs work best with a single hash key. Using a composite string `{provider}:{sub}` allows efficient lookup by the unique combination of provider and subject claim.

**Alternatives considered**:

1. **Two-attribute GSI (provider as hash, sub as range)**
   - Rejected: Requires provider in all queries, less flexible
   - Would need partition per provider (google, github)

2. **Table scan with filter**
   - Rejected: O(n) performance, unacceptable for auth flows
   - Would not scale with user growth

3. **Sparse GSI on existing provider_metadata**
   - Rejected: DynamoDB doesn't support indexing nested map attributes
   - Would require data model change

## GSI Configuration

```hcl
global_secondary_index {
  name            = "by_provider_sub"
  hash_key        = "provider_sub"
  projection_type = "KEYS_ONLY"
}

attribute {
  name = "provider_sub"
  type = "S"
}
```

### Why KEYS_ONLY Projection

- **Cost**: KEYS_ONLY minimizes GSI storage (only PK/SK stored)
- **Latency**: Additional get_item adds ~10ms but acceptable for auth flows
- **Flexibility**: Can change projection later without code changes

### Composite Key Format

Format: `{provider}:{sub}`
Examples:
- `google:118368473829470293847`
- `github:12345678`

**Why colon delimiter**:
- Neither provider names nor OAuth subs contain colons
- Easy to split for debugging
- Standard key format in DynamoDB composite keys

## DynamoDB Considerations

### Attribute Population

The `provider_sub` attribute must be set when linking a provider:
- On first OAuth link: set `provider_sub = "{provider}:{sub}"`
- On subsequent links: overwrite with latest provider (or use list for multi-provider)

### Multi-Provider Users

A user can have multiple OAuth providers (Google + GitHub). Options:
1. **Single provider_sub attribute**: Only index one provider per user
   - Simpler but limits lookups to one provider
2. **Separate attributes**: `google_sub`, `github_sub` with separate GSIs
   - More flexible but requires GSI per provider
3. **Item per provider link**: Separate DynamoDB items for provider links
   - Most flexible but adds complexity

**Decision**: Use single `provider_sub` for now, set to most recent provider. Future features can add separate provider-link items if needed.

### Existing Users

Users linked before this feature won't have `provider_sub` attribute:
- `get_user_by_provider_sub()` returns None (not found)
- No backfill needed - users will get attribute on next provider interaction
- Graceful degradation for legacy users

## Conclusion

Add single GSI with KEYS_ONLY projection on composite `provider_sub` attribute. Update `_link_provider()` to populate attribute. No backfill needed.
