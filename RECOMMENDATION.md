# Sentiment Analysis Model Selection - Executive Recommendation

## Decision: Use HuggingFace Transformers (DistilBERT)

### Model
`distilbert-base-uncased-finetuned-sst-2-english` from HuggingFace

---

## Key Metrics Comparison

| Metric | HuggingFace | AWS Comprehend | OpenAI GPT-3.5 |
|--------|---|---|---|
| **Cost per 1,000 items** | <$0.001 | $0.10 | $0.125 |
| **Monthly cost (500 items/hr)** | $2.50 | $36 | $45 |
| **Cold start latency** | 1.7-4.9s | None (API) | None (API) |
| **Warm latency per item** | 60-115ms | 200-600ms | 300-800ms |
| **Sentiment accuracy** | 91% | 90-94% | 95-97% |
| **Setup complexity** | Medium | Low | Low |
| **External dependency** | No | Yes | Yes |
| **Scalability (10K items/hr)** | Excellent | Fair | Fair |

---

## Rationale

### Why HuggingFace Wins

1. **Cost Efficiency** (Primary)
   - 95%+ cost savings vs alternatives at scale
   - Demo: $2.50/month vs $36-45/month
   - Production (5,000 items/hr): $25/month vs $360-450/month

2. **Demo Responsiveness** (Secondary - "demo impact")
   - Warm latency: 100-150ms (sub-100ms for batch processing)
   - 3-5x faster than Comprehend, 5-8x faster than GPT-3.5
   - Demonstrates production-grade performance to audience

3. **No External Dependencies**
   - Local processing guarantees availability
   - No API rate limits or throttling
   - Privacy-compliant (no external data transfer)
   - Aligns with Lambda serverless best practices

4. **Accuracy Adequate for Use Case**
   - 91% accuracy sufficient for demo
   - Trade-off: 4% accuracy loss for 40% speed + 95% cost savings
   - Social media optimized (trained on sentiment classification)

5. **Scalability Advantage**
   - Linear cost model (no tier changes needed)
   - Supports 5,000+ items/hour without architecture changes
   - Cost scales with Lambda compute, not per-API-call

---

## Implementation Summary

### Quick Start (Week 1-2)
1. Package DistilBERT in Lambda container image
2. Implement inference handler with batching (10 items per invocation)
3. Target P95 latency: <100ms on warm containers

### Deployment (Week 3)
1. Add Lambda layers for model pre-caching
2. Optional: Configure provisioned concurrency if consistent <50ms needed
3. Deploy to production

### Costs
- Infrastructure: Lambda free tier (1M invocations/month)
- Operational: ~$0.50/month (100 items/hr) to $2.50/month (500 items/hr)
- Setup: 2-4 hours engineering

### Performance Targets
- Cold start: 1.7-4.9s (first invocation, model loading)
- Warm start: 100-150ms per item (cached model)
- Batch processing: 150-300ms per 10 items (15-30ms per item)

---

## Alternatives Considered

### AWS Comprehend (Runner-up)
**When to use instead:**
- Team prefers zero infrastructure complexity
- 4-label sentiment critical (neutral + mixed support)
- Budget allows 15-20% premium for simplicity

**Trade-offs:**
- 15x higher cost ($36 vs $2.50/month at demo scale)
- 3-5x slower latency (200-600ms vs 100-150ms)
- External API dependency
- Setup: 30 minutes (vs 2-4 hours)

### OpenAI GPT-3.5-turbo (Rejected)
**Why not:**
- 5-10x higher cost ($45 vs $2.50/month)
- 5-8x slower latency (300-800ms vs 100-150ms)
- Unnecessary accuracy (95% vs 91% not required for demo)
- External API dependency
- Overkill for binary sentiment classification

**When GPT-3.5 IS recommended:**
- Nuanced sentiment analysis (sarcasm, mixed emotion detection)
- Multi-domain text (movies, products, news, user feedback combined)
- Accuracy >95% critical to business logic

---

## Risk Assessment

| Risk | Mitigation | Priority |
|------|-----------|----------|
| Cold start latency (1.7-4.9s) | Use Lambda layers + SQS batching | Medium |
| Neutral sentiment not explicit | Binary classification acceptable for demo | Low |
| 91% accuracy vs 95%+ | Acceptable trade-off for 95% cost savings | Low |
| Model size (250MB) | Container image avoids 250MB zip limit | Low |
| GPU unavailable on Lambda | CPU inference adequate for demo latency targets | Low |

---

## Next Steps

1. **Weeks 1-2:** Implement DistilBERT inference Lambda
   - Create Dockerfile with model + dependencies
   - Build inference handler (~50 lines Python)
   - Target: cold start <5s, warm start <150ms

2. **Week 3:** Performance optimization
   - Add Lambda layers for model pre-caching
   - Implement SQS-based batching (10 items/invocation)
   - Target: P95 warm latency <100ms

3. **Week 4:** Deploy to production
   - Configure CloudWatch metrics (inference latency, cost)
   - Smoke test with 100-500 items/hour load
   - Ready for demo

---

## Decision Confidence

**Very High (95%)**

Recommendation is clear:
- HuggingFace offers 95% cost advantage (primary decision factor)
- Sufficient accuracy for demo (91% vs 95%+ not a show-stopper)
- Superior responsiveness (100-150ms vs 300-800ms) improves demo impact
- No external dependencies align with serverless best practices
- Scales linearly to 5,000+ items/hour

**Only reconsider if:**
- Nuanced sentiment analysis becomes critical requirement
- 4-label sentiment (neutral) becomes must-have feature
- Setup complexity becomes blocker (then choose Comprehend)

