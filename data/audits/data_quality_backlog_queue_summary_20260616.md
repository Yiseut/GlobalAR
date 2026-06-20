# Data Quality Backlog Queue Summary

Generated at: 2026-06-16T16:30:07+08:00

| Queue | Rows | Latest CSV |
| --- | ---: | --- |
| entity_resolution_review_queue | 10 | `E:\shared\Documents\data\global_aesthetics_dashboard\data\audits\entity_resolution_review_queue_latest.csv` |
| registration_review_queue | 120 | `E:\shared\Documents\data\global_aesthetics_dashboard\data\audits\registration_review_queue_latest.csv` |
| aesthetics_revenue_pct_collection_queue | 21 | `E:\shared\Documents\data\global_aesthetics_dashboard\data\audits\aesthetics_revenue_pct_collection_queue_latest.csv` |

## Checks

- Financial blank company_id after Galderma remap: 4
- Listed batch blank company_id: 6
- Registration evidence review backlog: 120
- Public company aesthetics revenue pct backlog: 21

## Notes

- These queues are backlog controls, not release-blocking failures by themselves.
- Entity candidates are hints only; a candidate_company_id still requires source review before mapping.
- Aesthetics revenue pct should be filled only from segment evidence or explicit unavailable/not-disclosed review.
