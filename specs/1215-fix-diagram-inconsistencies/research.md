# Research: Fix Architecture Diagram Inconsistencies

**Feature**: 1215-fix-diagram-inconsistencies
**Date**: 2026-01-20

## Research Questions

1. How does mermaid.live encode diagrams in URLs?
2. How to embed dark theme consistently?
3. What existing assets can be reused?

## Findings

### 1. Mermaid.live URL Encoding

**Decision**: Use pako (zlib) compression with base64url encoding

**Rationale**:
- mermaid.live uses pako.js for compression, which is zlib-compatible
- Python's `zlib.compress()` produces compatible output
- Base64url encoding (with `-` and `_` instead of `+` and `/`) required for URL safety
- Padding (`=`) can be stripped since pako decoder handles it

**Alternatives Considered**:
- Raw base64 without compression: URLs too long for complex diagrams
- gzip instead of zlib: Not compatible with pako.js

**Source**: TEMPLATE.md lines 99-117, mermaid.live source code inspection

### 2. Theme Embedding Strategy

**Decision**: Embed theme via `%%{init: ...}%%` directive in diagram code, use `{"theme": "dark"}` in payload as fallback

**Rationale**:
- The `%%{init: ...}%%` directive takes precedence and is preserved in the diagram
- Payload theme setting provides fallback if init directive is missing
- This approach means diagrams are self-contained with their styling

**Alternatives Considered**:
- Payload-only theme: Lost when diagram is edited in mermaid.live editor
- Separate theme file: Not supported by mermaid.live URL format

**Source**: Mermaid.js documentation, existing README.md diagrams

### 3. Reusable Assets from TEMPLATE.md

**Decision**: Leverage existing TEMPLATE.md for theme config and URL generation logic

**Assets Available**:
- Line 10-11: Full dark theme init configuration
- Lines 18-33: Standard classDef styles for all node types
- Lines 99-117: Python URL generation function

**Rationale**:
- TEMPLATE.md was created specifically for this purpose
- Using it ensures consistency across all diagrams
- Avoids reinventing the wheel

## Implementation Notes

### README.md CF Node Removal

Current problematic lines:
```mermaid
Browser ==>|HTTPS| CF           # Line 248 - CF undefined
CF ==>|/static/*| Amplify       # Line 250
CF ==>|/api/*| APIGW            # Line 251
CF ==>|/api/v2/stream*| SSELambda  # Line 252
class CF,Amplify,APIGW edgeStyle   # Line 314
```

Corrected flow (Browser direct):
```mermaid
Browser ==>|Static| Amplify
Browser ==>|/api/*| APIGW
Browser ==>|/api/v2/stream*| SSELambda
class Amplify,APIGW edgeStyle
```

### architecture.mmd NewsAPI Replacement

Current (incorrect):
```mermaid
subgraph External["External Services"]
    NewsAPI["NewsAPI<br/>News Articles"]
    OAuthProviders["OAuth Providers<br/>Google, GitHub"]
end
```

Corrected (matches README.md):
```mermaid
subgraph External["External Services"]
    Tiingo["Tiingo API<br/>Financial News"]
    Finnhub["Finnhub API<br/>Market Data"]
    OAuthProviders["OAuth Providers<br/>Google, GitHub"]
end
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Mermaid syntax errors after edit | Script validates before encoding |
| Theme not rendering | Dark theme in both init directive AND payload |
| URL too long | zlib compression keeps URL reasonable |
| Diagram drift in future | Script makes regeneration reproducible |
