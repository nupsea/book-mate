# Search Evaluation

Scripts for generating ground truth and evaluating search performance.

## Quick Start

### 1. Generate Ground Truth

Generate evaluation queries for a book:

```bash
source .env
uv run python -m src.flows.generate_ground_truth <book_slug> <num_chunks>
```

**Examples:**
```bash
# Generate 30 queries for The Odyssey (5 queries per chunk = 150 total)
uv run python -m src.flows.generate_ground_truth ody 30

# Generate 50 queries for Sherlock Holmes
uv run python -m src.flows.generate_ground_truth sha 50
```

**Output:** `DATA/GT/<book_slug>_golden_data.json`

### 2. Evaluate Search Performance

Compare baseline vs adaptive retriever:

```bash
source .env
uv run python -m src.flows.evaluate_search <book_slug>
```

**Examples:**
```bash
# Evaluate on The Odyssey
uv run python -m src.flows.evaluate_search ody

# Evaluate on Alice in Wonderland
uv run python -m src.flows.evaluate_search aiw
```

## Current Results

### The Odyssey (150 queries, 445 chunks)

| Configuration | Hit@5 | MRR@5 | Hit@7 | MRR@7 | Improvement |
|--------------|-------|-------|-------|-------|-------------|
| Baseline | 67.3% | 50.0% | 70.0% | 50.4% | - |
| Adaptive | **68.7%** | **53.6%** | **74.0%** | **54.4%** | **+2.0%** |

### Alice in Wonderland (495 queries, 99 chunks)

| Configuration | Hit@5 | MRR@5 | Hit@7 | MRR@7 | Improvement |
|--------------|-------|-------|-------|-------|-------------|
| Baseline | 81.0% | 59.4% | 84.0% | 60.5% | - |
| Adaptive | **81.4%** | **60.7%** | **84.2%** | **61.5%** | **+0.5%** |

## Supported Books

| Slug | Title | Pattern |
|------|-------|---------|
| `ody` | The Odyssey | `^(?:BOOK [IVXLCDM]+)\s*\n` |
| `aiw` | Alice in Wonderland | `^(?:CHAPTER [IVXLCDM]+\.)\s*\n` |
| `mma` | Meditations | `^(?:THE .* BOOK)\s*\n` |
| `sha` | Sherlock Holmes | `^[IVXLCDM]+\.\s+.*\n` |

## Ground Truth Generation

**Method:** LLM-as-judge using GPT-4o-mini

For each sampled chunk, generates 5 diverse queries:
1. Short keywords (2-4 words)
2. Natural language question
3. Phrase fragment
4. Detail-oriented query
5. Reflective/interpretive query

**Time:** ~2 seconds per chunk (30 chunks ≈ 1 minute)

## Metrics

- **Hit@5**: % of queries where correct chunk appears in top-5 results
- **MRR@5**: Mean Reciprocal Rank (average of 1/rank for correct results)
- **Hit@7**: % of queries where correct chunk appears in top-7 results
- **MRR@7**: MRR calculated over top-7 results

## Files

- `src/flows/generate_ground_truth.py` - Generate queries
- `src/flows/evaluate_search.py` - Evaluate retrievers
- `src/search/adaptive.py` - Improved retriever
- `DATA/GT/` - Ground truth data
