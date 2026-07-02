"""Prometheus metrics definitions for SignalScout."""
from prometheus_client import Counter, Gauge, Histogram

BRIEF_REQUESTS = Counter(
    "signalscout_brief_requests_total",
    "Total investment brief requests",
    labelnames=["ticker"],
)

BRIEF_LATENCY = Histogram(
    "signalscout_brief_latency_seconds",
    "End-to-end brief generation latency",
    labelnames=["ticker"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60],
)

INGESTION_DOCS = Counter(
    "signalscout_ingestion_docs_total",
    "Total documents ingested",
    labelnames=["ticker", "modality"],
)

AGENT_LATENCY = Histogram(
    "signalscout_agent_latency_seconds",
    "Per-agent node latency",
    labelnames=["agent_name"],
    buckets=[0.1, 0.5, 1, 2, 5, 10],
)

RETRIEVAL_HIT_RATE = Gauge(
    "signalscout_retrieval_chunks_returned",
    "Number of chunks returned by retriever",
    labelnames=["ticker"],
)

TOKEN_COST = Counter(
    "signalscout_token_cost_usd_total",
    "Estimated token cost in USD",
    labelnames=["model"],
)

CRITIQUE_SCORE = Histogram(
    "signalscout_critique_score",
    "Critique agent quality score",
    labelnames=["ticker"],
    buckets=[0.1, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

CONTRADICTIONS_DETECTED = Counter(
    "signalscout_contradictions_detected_total",
    "Total cross-modal contradictions detected",
    labelnames=["ticker", "severity"],
)

EMBEDDING_DRIFT = Gauge(
    "signalscout_embedding_drift",
    "Cosine distance of embedding centroid vs last week",
    labelnames=["ticker"],
)
