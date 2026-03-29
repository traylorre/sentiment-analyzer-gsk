# Research: Bidirectional Validation for Target Repos

**Feature**: 055-target-bidirectional
**Date**: 2025-12-06

## Executive Summary

The template repo already has mature semantic comparison infrastructure in `.specify/verification/`. This feature extends the existing `BidirectionalValidator` to use intrinsic detection for target repos, leveraging the existing spec parser, LLM client, and gap classification logic.

## Research Topics

### 1. Semantic Comparison Approach

**Decision**: Hybrid LLM-first with offline fallback

**Rationale**:

- Existing infrastructure in `.specify/verification/bidirectional.py` already implements this pattern
- Multi-model consensus (Claude Sonnet + Haiku) reduces hallucination
- LLM naturally handles semantic equivalence ("authenticate" vs "login")
- Battle-tested offline fallback uses token overlap + sequence matching

**Alternatives Considered**:

| Approach                                | Pros                     | Cons                       | Verdict                         |
| --------------------------------------- | ------------------------ | -------------------------- | ------------------------------- |
| Embedding-based (sentence-transformers) | Offline, fast, semantic  | ~500MB model, no reasoning | Rejected - adds dependency      |
| Pure token-based (Jaccard)              | Zero deps, deterministic | Fails on synonyms          | Already implemented as fallback |
| Rule-based mapping                      | Fast, deterministic      | Brittle, requires curation | Rejected - not scalable         |

### 2. Existing Infrastructure to Reuse

The template repo has comprehensive bidirectional verification already:

| Component          | Location                                         | Reuse Strategy                           |
| ------------------ | ------------------------------------------------ | ---------------------------------------- |
| Spec parser        | `.specify/verification/spec_parser.py`           | Import directly                          |
| LLM client         | `.specify/verification/llm_client.py`            | Import directly                          |
| Gap classification | `.specify/verification/bidirectional.py:274-355` | Import `classify_gaps()`                 |
| Offline similarity | `.specify/verification/bidirectional.py:358-412` | Import `calculate_semantic_similarity()` |

### 3. Intrinsic Detection Strategy

**Decision**: Glob-based spec discovery with convention-based code mapping

**Detection Algorithm**:

```python
def detect_specs(repo_path: Path) -> list[SpecFile]:
    """Find all spec files using convention: specs/*/spec.md"""
    return list(repo_path.glob("specs/*/spec.md"))

def map_spec_to_code(spec_path: Path, repo_path: Path) -> list[Path]:
    """Map spec to corresponding code using feature name"""
    feature_name = spec_path.parent.name  # e.g., "001-auth"
    # Convention: feature name appears in module/package names
    candidates = []
    for src_dir in ["src", "lib", "app"]:
        candidates.extend(repo_path.glob(f"{src_dir}/**/*{feature_name}*"))
    return candidates
```

**Rationale**: Follows existing convention in both template and target repos.

### 4. Graceful Degradation

**Decision**: Three-tier fallback strategy

| Tier | Condition                  | Capability                                                |
| ---- | -------------------------- | --------------------------------------------------------- |
| 1    | Claude API available       | Full semantic comparison with gap classification          |
| 2    | API unavailable, cache hit | Use cached responses for previously analyzed specs        |
| 3    | API unavailable, no cache  | Offline validation only (testability, references, naming) |

**Offline-only capabilities**:

- Spec file existence and structure validation
- FR-NNN reference integrity (dangling references)
- Testability detection (percentages, RFC 2119 keywords)
- Resource naming convention checks

**LLM-required capabilities**:

- Semantic equivalence ("encrypt data" ≈ "encrypted=true")
- Implicit requirement extraction
- Contradiction detection
- Hallucination classification

### 5. Finding Taxonomy

**Decision**: Extend existing BIDIR-XXX taxonomy

| ID        | Severity | Description                                   |
| --------- | -------- | --------------------------------------------- |
| BIDIR-001 | HIGH     | Spec requirement without code implementation  |
| BIDIR-002 | MEDIUM   | Code functionality without spec documentation |
| BIDIR-003 | LOW      | Semantic drift (partial mismatch)             |
| BIDIR-004 | INFO     | Spec lacks testable acceptance criteria       |
| BIDIR-005 | HIGH     | Contradiction between spec sections           |

### 6. Performance Considerations

**Decision**: Incremental validation with caching

**Strategies**:

1. **Cache all LLM responses** by `hash(spec_content + code_content)`
2. **Batch requirements** - Group multiple FR-NNN into single prompt
3. **Skip unchanged files** - Only validate specs/code with git changes
4. **Parallel processing** - Use `asyncio.gather()` for multi-spec repos

**Target**: < 30 seconds for repos with < 50 spec files

## Key Decisions Summary

| Topic               | Decision                               | Confidence                    |
| ------------------- | -------------------------------------- | ----------------------------- |
| Comparison approach | Hybrid LLM-first with offline fallback | High (proven in codebase)     |
| Spec discovery      | `specs/*/spec.md` glob pattern         | High (established convention) |
| Code mapping        | Feature name matching in src/ paths    | Medium (may need refinement)  |
| Degradation         | Three-tier (API → cache → offline)     | High (already implemented)    |
| Finding IDs         | BIDIR-001 through BIDIR-005            | High (extends existing)       |

## Dependencies

**Existing (no new deps)**:

- `anthropic` - Claude API client
- `pydantic` - Data models
- `pyyaml` - YAML output

**Internal imports**:

- `.specify/verification/spec_parser` - Requirement extraction
- `.specify/verification/llm_client` - Multi-model consensus
- `.specify/verification/bidirectional` - Gap classification

## References

- `.specify/verification/bidirectional.py` - Core semantic comparison
- `.specify/verification/spec_parser.py` - FR-NNN extraction
- `.specify/verification/llm_client.py` - Multi-model consensus
- `docs/ai-first-testing-methodology.md` - Testing hierarchy
