# Message Validation & Deterministic Scoring

## Quality Score Dimensions (0–100)

| Dimension | Max Points | Description |
| :--- | :--- | :--- |
| **Evidence Coverage** | 25 | Percentage of claims backed by verified context evidence |
| **Personalization** | 20 | Specificity of references to company, pain points, and decision-maker |
| **Relevance** | 20 | Alignment with intent signals and lead domain |
| **Service Alignment** | 15 | Accurate reflection of the recommended service catalog item |
| **Clarity** | 10 | Syntax cleanliness, readability, and punctuation control |
| **CTA Quality** | 5 | Natural, proportionate closing question |
| **Natural Tone** | 5 | Absence of stilted, archaic, or overly promotional phrasing |

## Thresholds
- **Score >= 75 and 0 Errors**: Status set to `READY_FOR_APPROVAL`.
- **Score < 75 or Errors present**: Status set to `NEEDS_REVIEW`.
- **Channel Length Limits**:
  - Instagram DM: 50 – 700 chars
  - Reddit Reply: 80 – 1200 chars
  - LinkedIn Message: 100 – 1000 chars
  - Email: 100 – 2000 chars
