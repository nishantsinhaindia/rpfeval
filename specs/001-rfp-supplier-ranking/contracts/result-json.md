# Contract: Run result JSON (persisted in `rfp_runs.result_json`, downloaded by the user)

`RunResult.model_dump(mode="json")`, numbers at full precision (FR-032, FR-027).

```json
{
  "rfp_run_id": "3f2a…",
  "created_at": "2026-10-25T10:15:00Z",
  "status": "COMPLETED",
  "failure_reason": null,
  "criteria_snapshot": [
    {"criterion_id": 1, "name": "Technical Capability", "description": "…", "weight": 30, "max_score": 10.0, "is_active": true}
  ],
  "suppliers": [
    {
      "rank": 1,
      "supplier_name": "NexaWorks",
      "submission_date": "2026-03-01",
      "experience_rating": 4,
      "file_name": "NexaWorks.pdf",
      "absolute_score": 82.0,
      "ppi": 93.33333333333333,
      "tie_break_rule": "ppi",
      "evaluation_failed": false,
      "criteria": [
        {"criterion_id": 1, "name": "Technical Capability", "weight": 30, "max_score": 10.0,
         "score": 8.0, "benchmark": 9.0, "gap": -1.0, "relative_pct": 88.88888888888889,
         "weighted_contribution": 24.0, "evidence": "…", "justification": "…", "flags": []}
      ],
      "risks": ["…"],
      "overall_summary": "…",
      "attempts": [
        {"attempt": 1, "raw_response": "{…exact string…}", "failure_reason": null, "used_for_normalization": true}
      ]
    }
  ],
  "warnings": [
    {"supplier_name": "Orbit Digital", "criterion_id": 3, "issue": "clipped",
     "original_value": "12", "applied_value": "10", "message": "Score 12 above max 10; clipped to 10"}
  ],
  "tie_break_explanation": [
    "NexaWorks ranks above Orbit Digital: higher PPI 93.33 vs 88.10"
  ]
}
```

`supplier_results.result_json` holds one `suppliers[i]` object. Reopened runs (FR-034) render
exclusively from this JSON and its own `criteria_snapshot`.
