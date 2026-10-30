# Meridian Freight presenter guide

19 minutes of story and live demo, then 6 minutes of discussion.

## 1. Dock staffing before the rush

TIME: 30 seconds

LEAD WITH
Meridian Freight is a fictional LTL carrier. Today we will follow one decision: how a terminal manager prepares the dock shift before trailer queues and overtime build up.

SHOW
Introduce the VP of Terminal Operations as the economic sponsor and the Data/Platform Architect as the owner of trusted, usable data. The proposed outcome is a scoped Memphis pilot, with owners and measurable gates.

LAND THE POINT
The story starts with the operator's problem, then tests a specific staffing decision in the working demo.

TRANSITION
First, where does a loading-dock decision fit in this carrier's operation?

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
DEMO.md; src/dock_ops/config.py. Cover photograph: Pexels, https://www.pexels.com/photo/warehouse-with-delivery-truck-exiting-the-loading-dock-29786116/ (illustrative stock photograph, not Meridian or Federal Express).


## 2. The loading dock sets the pace

TIME: 1.5 minutes

LEAD WITH
This is a less-than-truckload operation: freight moves through the terminal and changes trailers. The dock connects the arrival schedule to the outbound departure.

SHOW
Orient the room to Atlanta, Dallas, and Memphis, totaling 36 doors. The terminal manager must align workers with door activity. The VP cares about trailer waiting and labor cost. The architect must provide reliable data to both.

LAND THE POINT
A useful solution must improve a shift decision, not merely collect another camera feed or report.

TRANSITION
The problem is that the arrival wave changes while the roster barely does.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
src/dock_ops/config.py; DEMO.md. Operational framing describes the fictional scenario, not a real carrier assessment.


## 3. The rush arrives. The roster stays flat

TIME: 1.5 minutes

LEAD WITH
The schedule is nearly flat during the day. The workload has a pronounced peak. That mismatch is visible before we discuss any AI.

SHOW
Read the chart at 06:00 and 11:00. At 11:00, actual-workload staffing averages 10.1 workers per terminal against 7.0 scheduled, a 3.1-worker gap. These are historical network averages, not Memphis forecast rows.

LAND THE POINT
This is a timing opportunity. It suggests reallocating labor across hours, subject to skills, breaks, and labor constraints.

TRANSITION
Now connect the missed hours to the cost line the VP owns.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
evidence/2026-10-15-data-reconciliation.md. Selected-hour chart after the arrival-hour correction. Model forecasts appear separately on slide 7.


## 4. The mismatch creates a measurable cost

TIME: 1 minute

LEAD WITH
The synthetic baseline is $235,940.19 in detention plus $108,780 in modeled overtime. Together that is $344,720.19 across 31 days.

SHOW
Compare the stacked terminal bars. Memphis combines $91,649.63 in detention and $43,974 in modeled overtime, or $135,623.63. It has the largest detention cost and becomes the pilot candidate.

LAND THE POINT
The network annualized cost is about $4.06 million. This is cost exposure in a synthetic scenario; it is not realized savings or a Federal Express financial result.

TRANSITION
So what should change in the manager's next shift?

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
evidence/2026-10-15-data-reconciliation.md; evidence/workspace-demo-current.json. Economics assume a two-hour free window and $75 per trailer-hour beyond it.


## 5. A different start to the next shift

TIME: 1 minute

LEAD WITH
The proposed workflow changes when and how the manager makes a staffing decision.

SHOW
Walk one row at a time. A dock snapshot gives an observation time and door state. A dated forecast identifies the gap. A concise briefing supports the supervisor, who still checks worker availability, skills, and shift rules.

LAND THE POINT
The prototype is decision support. It does not autonomously dispatch labor or integrate with an HR scheduler.

TRANSITION
Let's follow that routine in the working console.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
app/app.py; app/static/index.html; notebooks/00_demo_walkthrough.py. The current and proposed routines are scenario framing, not a measured customer before/after study.


## 6. One operating view for all 36 doors

TIME: 4 minutes including the live app

LEAD WITH
The terminal manager should be able to answer: what is the dock state, and which shift needs attention? I will show both in one operating view.

SHOW
Open https://dock-ops-app-7474658947307895.aws.databricksapps.com. Confirm the visible synthetic snapshot timestamp. Inspect all 36 doors, then point to the top Memphis staffing rows. The board and staffing plan report Lakebase as their source. Show the historical KPI period and the hour-of-day profile without reading every tile. Use the slide screenshot only as a labeled fallback.

LAND THE POINT
The manager can move from a network view to a particular terminal-hour. The screenshot shows a verified October 15 app session, with July–September synthetic data; it is not a live customer feed.

TRANSITION
The next screen makes the proposed staffing action explicit.

OPTIONAL DISCUSSION
If the app reports a warehouse fallback, state that source. Lakebase provides fast reads of the copied snapshot; a production implementation still needs a freshness SLA and ongoing synchronization.

SOURCES
deck/assets/operations-focus.png, cropped from scratch/deployed-app-verified.png; evidence/2026-10-15-app-current.json; app/app.py.


## 7. A recommendation the supervisor can act on

TIME: 3 minutes including briefing and Genie

LEAD WITH
Here is the specific decision the forecast supports: Memphis at 10am on September 3 needs 17 workers against 8 scheduled, a gap of 9. This is a dated synthetic example.

SHOW
In the app (https://dock-ops-app-7474658947307895.aws.databricksapps.com), click Generate briefing. Check the first recommendation against that exact forecast row. Then open Genie (https://fevm-fedex-fevm.cloud.databricks.com/genie/rooms/01f1a3243b00149fa4876211f8b5c004) and ask: Which terminal has the highest total detention fees? Include the date range of this synthetic dataset. The verified answer is Memphis, $91,650 rounded. Inspect the SQL and result rows. If useful, ask which dated shifts have the largest staffing gaps.

LAND THE POINT
The staffing number is a planning signal. A supervisor must decide whether workers can move and record the actual action. The model's $378 for this hour is modeled overtime exposure, not a proven saving.

TRANSITION
For the architect, here is the data path that makes this answer traceable.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
evidence/06_forecast.md; evidence/2026-10-15-genie-current.json; evidence/2026-10-15-genie-staffing.json; evidence/2026-10-15-app-current.json.


## 8. The data journey behind that decision

TIME: 1.5 minutes

LEAD WITH
The architecture follows the operational decision we just made.

SHOW
Lakeflow ingests gate events and camera frames into bronze and silver. Gold provides curated metrics and the operational snapshot. Unity Catalog governs lakehouse access and registered models. Forecast and CV predictions feed the gold serving tables. Lakebase stores an operational copy for the app; Genie queries the gold analytics directly. The app also calls a Databricks-hosted foundation model to draft the briefing from the selected staffing rows.

LAND THE POINT
The same definitions support operational reads and leadership questions. Lakebase has separate Postgres roles and a snapshot-copy script; UC policies do not automatically follow copied data. The forecast is batch scored, and the image classifier has a model endpoint.

TRANSITION
Integration is demonstrated. The next question is what the pilot still needs to prove.

OPTIONAL DISCUSSION
Show the worker-ID mask and grants in the walkthrough if asked. It is a group-based table column mask, not a governed-tag ABAC policy. A real-feed design must address late events, identity, image retention, and serving freshness.

SOURCES
notebooks/01_generate_data.py through notebooks/07_genai_assistant.py; scripts/lakebase_sync.py; app/app.py; original icons from ~/Documents/logos.


## 9. Prototype evidence and pilot success measures

TIME: 1 minute

LEAD WITH
The demo proves that the components connect and that the displayed answer can be checked. It does not prove savings on real operations.

SHOW
Separate four verified prototype checks from four proposed pilot targets. Detention per trailer should fall at least 10%, overtime per trailer should not rise, forecast MAE should be no greater than two workers, and p95 observation age should be within five minutes. These are suggested acceptance criteria for sponsor review, not achieved prototype SLAs or industry benchmarks.

LAND THE POINT
Baseline and comparable-shift selection come before the intervention. Real-camera evaluation and supervisor acceptance remain part of readiness.

TRANSITION
A small pilot needs named owners and explicit stop/go gates to produce that evidence.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
evidence/2026-10-15-app-current.json; evidence/2026-10-15-cv-current.json; evidence/2026-10-15-genie-current.json; evidence/workspace-demo-current.json. Pilot thresholds are proposed assumptions.


## 10. A 30-day pilot with owners and decision gates

TIME: 1.5 minutes

LEAD WITH
Propose one terminal for 30 days, with a decision gate each week. The calendar begins when owners and access are ready, not on a promise made in this presentation.

SHOW
Week 1 establishes feeds, metric definitions, and comparable shifts. Week 2 runs the forecast in shadow mode and validates camera conditions and freshness. Week 3 trials supervisor-approved staffing changes and logs overrides. Week 4 compares detention and overtime per trailer and reviews the net cost.

LAND THE POINT
The VP and finance partner decide whether to expand, correct the approach, or stop. Each gate has an accountable role; names must be assigned at kickoff.

TRANSITION
That decision needs a transparent economic baseline and an agreed cost envelope.

OPTIONAL DISCUSSION
If feeds or labor-system constraints block Week 1, scope a data-readiness phase rather than claiming that a fixed 30-day value test has begun.

SOURCES
Proposed pilot plan. No customer dates, staffing commitments, budget, or implementation effort have been approved.


## 11. The Memphis business case

TIME: 1 minute

LEAD WITH
Size the first business case for Memphis, not the entire network.

SHOW
The exact Memphis synthetic baseline is $91,649.63 plus $43,974 = $135,623.63 over 31 days. At constant trailer volume, the proposed 10% detention-per-trailer improvement would reduce detention by $9,164.96, rounded to $9,165 gross benefit. This assumes no overtime increase and illustrates the same target shown on the pilot scorecard; it is not an achieved saving.

LAND THE POINT
Before approval, finance must replace simulated exposure with actual invoices and payroll. Subtract incremental regular labor, platform consumption, and implementation cost. Do not double-count overtime shifted to regular staffing as free savings.

TRANSITION
The immediate ask is a named sponsor and a scoped kickoff that can approve those assumptions.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
evidence/2026-10-15-data-reconciliation.md. Calculation: 91649.63 * 0.10 = 9164.963 at constant trailer volume and no overtime increase. No industry benchmark or guaranteed ROI claim.


## 12. Decision today: a Memphis pilot

TIME: 1.5 minutes, then 6 minutes for discussion

LEAD WITH
We have followed the problem from the roster mismatch to a specific Memphis staffing decision. The next step is a measured pilot with an accountable sponsor.

SHOW
Ask the VP to nominate the Memphis sponsor and terminal owner within two business days. Ask the terminal manager and architect to confirm access to gate events, camera frames, labor schedules, and cost data within five business days. Propose a 45-minute kickoff with the sponsor, finance, and delivery owners to approve the scorecard, cost cap, and start gate.

LAND THE POINT
The meeting should end with a named accountable owner and a scheduled kickoff. If readiness is incomplete, agree the missing input and its owner rather than accepting a vague follow-up.

TRANSITION
Invite questions from the VP on economics and adoption, and from the architect on data readiness and governance. Use the appendices only as needed.

OPTIONAL DISCUSSION
Ask: Who will own Memphis operations for this pilot, and can we schedule the kickoff with the platform and finance owners? Confirm the answer and the next deliverable before closing.

SOURCES
Proposed next steps. Timing is relative to sponsor agreement, not a calendar commitment. DEMO.md; the preceding pilot scope and illustrative economics.


## Objection-response drills

Use these as concise answer patterns, then return to the decision the stakeholder owns.
Lead with the direct answer, give one supporting fact, name the limitation, and close with
the pilot action that resolves the uncertainty.

### VP of Terminal Operations

**"How much money will this actually save?"**

The prototype does not establish realized savings. Memphis has $91,649.63 of synthetic
31-day detention exposure, so the proposed 10% detention-per-trailer target represents
about $9,165 of gross benefit at constant volume. Finance still needs to replace the
simulation with invoice and payroll data, then subtract labor, platform, and implementation
cost. The pilot decision is whether that measured net benefit clears the agreed cost cap.

**"How quickly do we see value?"**

The proposed pilot is four weeks after the owners, feeds, and baseline are ready. Week 1
establishes comparable shifts, Week 2 runs in shadow mode, Week 3 trials
supervisor-approved changes, and Week 4 compares detention and overtime per trailer. If
data readiness slips, call it a readiness phase rather than promising a fixed value date.

**"What happens when the forecast is wrong?"**

The forecast is decision support, not autonomous dispatch. Its recorded synthetic-data MAE
is 1.885 workers, but a supervisor still checks skills, breaks, and availability before
moving labor. The pilot runs shadow mode first, records overrides, and stops or recalibrates
if the error or overtime guardrail misses the agreed threshold.

**"Why Databricks instead of another dashboard?"**

The operating view is the last mile, not the whole solution. The same governed journey
ingests the events, creates trusted metrics, trains and registers the models, serves the
operational snapshot, supports natural-language questions, and produces the supervisor
briefing. The pilot tests whether that integrated path improves the staffing decision; it
does not assume platform consolidation is valuable by itself.

### Data and Platform Architect

**"How do you know the data is trustworthy?"**

Lakeflow applies expectations while building the silver visit records, Unity Catalog
captures lineage into the gold layer, and the walkthrough independently reconciles
$235,940.19 of detention and $108,780 of modeled overtime to their source formulas. The
pilot must add real-feed freshness, late-event handling, and comparable-shift definitions
before these figures can become operational KPIs.

**"How are worker and camera data secured?"**

The lakehouse uses a group-based worker-ID column mask, role-based access, and a dedicated
app service principal. Lakebase is a separate security boundary with Postgres roles; Unity
Catalog masks do not automatically follow copied data. A production design therefore needs
explicit Lakebase grants, image-retention policy, and identity testing as pilot gates.

**"How does this integrate with our current systems, and what is the latency?"**

The prototype lands gate events and camera frames for Lakeflow ingestion, then copies the
curated operational state into Lakebase for low-latency app reads. That proves the interfaces,
not a production SLA. During the pilot, define the source-system contract, automate the
incremental synchronization, measure p95 observation age, and fail visibly to the governed
gold snapshot if Lakebase is unavailable.

**"Can we trust the models and Genie answers?"**

The staffing model uses a time-based holdout and beats the hourly-mean baseline by 5.6%; the
camera classifier and its endpoint work on synthetic images only. Genie is constrained to
the curated gold tables, and its generated SQL and result rows are inspectable. Real-camera
accuracy, model monitoring, promotion criteria, and user-identity behavior remain explicit
pilot validation work rather than demonstrated production guarantees.


## 13. Appendix: technical evidence and limits

TIME: Optional technical appendix

LEAD WITH
The technical proof is inspectable, and its limits define the pilot work.

SHOW
The forecast uses GradientBoosting with a five-day time holdout. MAE is 1.885, versus 1.997 for the hourly-mean baseline, and R-squared is 0.606. The arrival-hour correction did not retrain that model. The classifier is a UC-registered pyfunc deployed as version 2; a UC alias change alone does not refresh the serving endpoint.

LAND THE POINT
Four successful image-state requests and synthetic holdout accuracy do not establish real-camera accuracy. UC masks apply to lakehouse reads, while Lakebase uses separate Postgres roles. Genie and the app can run under different configured identities.

TRANSITION
Return to the specific pilot gate or decision the question concerns.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
evidence/05_cv_model.md; evidence/06_forecast.md; evidence/2026-10-15-cv-current.json; evidence/2026-10-15-app-current.json; notebooks/04_governance.py.


## 14. Appendix: presenter navigation

TIME: Presenter reference

LEAD WITH
Pre-open the console, Genie, and the walkthrough. Keep the two stakeholder roles in mind throughout.

SHOW
Delivery timing: setup and context 2 minutes; roster mismatch 1.5; cost 1; operating change 1; console 4; briefing and Genie 3; architecture 1.5; scorecard 1; pilot 1.5; economics 1; decision 1.5. Total 19 minutes plus 6 for discussion. The actual prepared segment totals 19 minutes by the slide-level timing plan.

LAND THE POINT
History is July 30–August 29, 2026. Forecasts cover August 30–September 5. The software runs live, while its underlying example data is a dated synthetic replay. If a live step fails, label the displayed screenshot or saved evidence as a fallback.

TRANSITION
Resume the main narrative at the customer decision, not a feature tour.

OPTIONAL DISCUSSION
Take the question at the audience's level, then return to the operational decision.

SOURCES
deck/deck-spec.json; evidence/workspace-demo-current.json; evidence/2026-10-15-app-current.json; evidence/2026-10-15-genie-current.json.
