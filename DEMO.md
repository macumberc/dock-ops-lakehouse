# Meridian Freight Dock Operations Intelligence

Meridian Freight Systems is a fictional national LTL carrier operating 36 loading doors across Atlanta, Dallas, and Memphis. Trailer arrivals concentrate around midday, while fixed staffing schedules leave the busiest hours short of workers. The reconciled synthetic scenario produces $235,940.19 in detention fees and $108,780 in modeled overtime across 31 days, approximately $4.06 million at an annual run rate. The demonstration shows how a supervisor can inspect dock conditions, plan staffing, and review an AI briefing on Databricks.

## Presentation and delivery

Audience: a VP of Terminal Operations and a Data/Platform Architect. Target 19 minutes of prepared material and 6 minutes for discussion. Use Tell, Show, Tell for each transition. The Google Slides deck includes twelve main slides and two optional appendices, with presenter notes and source references. Use Databricks corporate typography and colors. The fictional company has no separate trademark or customer branding.

## Existing architecture

Synthetic telemetry and procedural camera images land in a user-scoped Unity Catalog Volume. Lakeflow ingests bronze data and builds silver visits. Gold tables support a staffing forecast, a dock image classifier, Genie, and a Databricks App. Lakebase holds an operational snapshot for app reads. The workspace walkthrough links these assets and provides repeatable validation queries.

Target CLI profile: `fedex-fevm`. Verify its host and current identity before writing. Reuse the existing `dock_ops_chad_macumber` schema only after confirming its contents. Discover the current catalog and available serverless warehouse. Do not create a new workspace or change unrelated resources.

## Accuracy and limitations

- All figures describe deterministic synthetic data, originally generated in August 2026. They are not Federal Express operational results.
- A historical snapshot is not a streaming production feed. Show its timestamp and label the replay clearly.
- The proposed pilot target is at least 10% lower detention per trailer with no overtime increase. The Memphis economics illustrate that same target at constant volume; platform, implementation, and incremental labor costs require separate sizing.
- The staffing forecast's recorded test MAE is 1.885 workers, 5.6% better than the hourly-mean baseline on synthetic data. Validate model quality on a pilot terminal before relying on recommendations.
- Synthetic camera classification accuracy does not establish performance on real cameras.
- Verify model endpoints, app identity, UC permissions, and Lakebase reads against the live workspace before describing them as currently working.

## Teardown

Track created resources and provide an explicit teardown path. Preserve existing data during deployment. Removing the complete demo is a separate, deliberate operation through `scripts/teardown.sh` or the package entry point.
