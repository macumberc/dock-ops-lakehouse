# Roleplay Demo Script — Meridian Freight Dock Operations Intelligence

A ~20–25 minute customer presentation to **two AI personas at once**: a **business
stakeholder** (VP of Terminal Operations — funds the decision) and a **technical
stakeholder** (Data/Platform Architect — has to live with the build). Deliver the walkthrough
once, make the value case, then take questions and objections from each.

**Golden rules for the whole session**
- Lead with the **business outcome**, always. Every screen returns to detention $, overtime $, or utilization.
- **Tell → Show → Tell** on every segment: say what you'll show, show it, land what it means.
- **Switch altitude on demand.** Business questions → dollars, risk, time-to-value. Technical questions → architecture, governance, data quality — then one sentence back up to the business impact so you never lose the exec.
- Keep the demo tight: 5–6 screens, not a feature tour.
- Have the **deck** (`deck/index.html`) and the **app**
  (`https://dock-ops-app-7474658947307895.aws.databricksapps.com`) open before you start.

---

## 0 · Demo setup (frame it before you show anything) — ~2 min

> "Meridian Freight is a national LTL carrier running three cross-dock terminals — Atlanta,
> Dallas, Memphis, 36 doors total. The loading dock is their bottleneck: trailers arrive in
> waves, doors sit idle in the morning and get slammed by midday, and supervisors staff from
> a fixed shift plan that never changes. The result, measured over just 31 days: **$235,799 in
> trailer detention fees and $108,780 in avoidable overtime — about $4.1M a year** — and no
> real-time visibility into what's actually happening on the dock.
>
> In the next 20 minutes I'll show you the platform we built to fix that: it sees every dock
> in real time, forecasts labor demand, and tells supervisors where to move people *before*
> trailers start racking up detention. I'll show you the operational console, the forecast,
> the AI briefing, and how it's governed — and I'll tie each one back to the dollars."

*(This single paragraph frames the customer, the problem, the quantified stakes, and the
agenda. That's the "demo setup" and "tell" the rubric wants — do not skip it.)*

---

## 1 · The problem, in their numbers (deck) — ~3 min

**Tell:** "First, let me show you where the money is going."

**Show:** Deck slides 2–3 (the cost breakdown + the staffing-mismatch table).

**Tell (land it):**
> "The root cause isn't capacity — average utilization is only ~40%. It's *timing*. At 11am
> the docks need ~10 workers and the plan schedules 7; at 2am the plan has people standing
> around. Memphis is the worst — **$91,642 in detention** and a peak need of 17 workers
> against 8 scheduled. This is a scheduling problem hiding as a capacity problem, and today
> nobody can see it."

---

## 2 · The live operations console (app) — ~5 min

**Tell:** "Here's what the terminal supervisor sees now — one screen for all 36 doors."

**Show:** The app. Walk top to bottom:
- **KPI header** — detention, avoidable overtime, avg vs peak utilization (88–95% peak).
- **Live dock board** — every door, colored by real-time occupancy and confirmed by the
  computer-vision read of the camera frame. "This is served from Lakebase — our operational
  Postgres — so it's a low-latency, always-current board, not a report that's an hour stale."
- **Next-shift understaffing table** — "The forecast has already flagged the exact
  terminal-hours that will be short next week. Memphis, 10–11am, nine people short."
- **Utilization-by-hour chart** — orange bars are the mid-day crunch.

**Tell (land it):**
> "So in one glance the supervisor knows what's happening now *and* what's coming — and every
> number on this screen ties to a dollar figure the VP cares about."

---

## 3 · The AI shift briefing (app) — ~3 min

**Tell:** "Supervisors don't have time to read charts at 6am. So we ground a foundation model
in this exact data and let it write the shift plan."

**Show:** Click **Generate briefing**. Read the top action aloud.

**Tell (land it):**
> "That briefing is generated live from the current numbers — it's telling the supervisor to
> move nine people into Memphis 10–11am and what it's worth. This is the difference between a
> dashboard and a decision. It closes the loop from *data* to *action*."

---

## 4 · Natural-language analytics (Genie) — ~2 min

**Tell:** "When leadership has a one-off question, they shouldn't have to file a ticket."

**Show:** Genie: ask *"Which terminal has the highest detention fees?"* → Memphis, $91,642.

**Tell (land it):**
> "No SQL, no analyst in the loop — governed answers straight from the same certified tables."

---

## 5 · How it's built & governed (for the architect) — ~3 min

**Tell:** "Quickly, for the technical side of the room — this is one governed journey, not six
stitched-together tools."

**Show:** Deck architecture slide (or the repo). Name the stages:
- Lakeflow ingests gate telemetry **and** dock-camera images; bronze→silver with
  data-quality expectations.
- Unity Catalog governs all of it — lineage end to end, a **column mask on worker IDs**,
  role-based access so analysts get gold, not raw.
- A CV model and a staffing forecast, both registered in UC and served.
- Lakebase serves the live state; Genie and the app read the same certified gold.

**Tell (land it, back to business):**
> "The point for the business: it's one platform, one governance model, one source of truth —
> which is what makes it cheap to extend to the next terminal and safe to put in front of the
> floor."

---

## Objection handling — prepare for both, expect to switch altitude mid-answer

### Business stakeholder (cost · risk · time-to-value)

**"How much of that $4.1M do we actually get back?"**
> "Proactive dock staffing typically recovers 30–40% of detention — call it **$1.2–1.6M
> annual run-rate** across the three terminals. I'd hold us to a measured detention-reduction
> target on a single pilot terminal in the first 30 days before we claim the network number."

**"What's the time to value?"**
> "This is a working platform today. 30 days to wire one terminal's real yard-management and
> camera feeds and baseline the savings; 60–90 days to roll to all three and connect the
> staffing recommendations into your labor system. You see the detention line move inside a
> quarter."

**"What's the risk if the forecast is wrong?"**
> "The forecast is decision support, not autopilot — the supervisor still approves the move.
> And the downside is asymmetric: being one head over at 11am costs a few dollars of labor;
> being nine heads short costs hundreds in detention. The forecast beats the flat plan it
> replaces, and even a rough forecast beats a fixed shift that's wrong every single day."

**"Why Databricks and not a point solution / a dashboard we already have?"**
> "A dashboard shows you the problem after the fact. This closes the loop — vision, forecast,
> live serving, and the AI briefing — on one governed platform, so it extends to your next
> use case (yard, linehaul, labor) without re-buying the stack."

### Technical stakeholder (architecture · data quality · security · integration)

**"Is the data quality real or is this a happy-path demo?"**
> "Data quality is enforced in the pipeline — the silver layer has expectations
> (`valid_visit`, `non_negative_dwell`, `has_dock`) and the run logged **zero failed records
> across 9,149 visits**. If a feed sends malformed events, they're dropped and counted in the
> pipeline event log, not silently trusted." *(Then, one line up: "so the numbers the VP is
> looking at are trustworthy.")*

**"How is the CV model actually served, and how do you retrain it?"**
> "It's registered in Unity Catalog with a `@prod` alias and served as a pyfunc endpoint that
> takes the raw image — decode, featurize, predict — so integration is just an HTTP call.
> Retraining is a job against the same governed image table; you promote a new version by
> moving the alias, no endpoint change."

**"Security — this has worker data and cameras."**
> "Worker IDs are protected by an attribute-based **column mask** tied to group membership —
> a supervisor group sees them, everyone else sees a redacted token — and it's enforced in
> Unity Catalog, so it holds no matter how the data is queried: app, Genie, or SQL. Access is
> role-based: analysts get the gold layer, not the raw feeds. Nothing is hardcoded; the app
> runs as a service principal with least-privilege grants."

**"How does this integrate with our existing YMS / camera infrastructure?"**
> "Ingest is Auto Loader over a landing volume, so any system that can drop files or stream
> events plugs in — we're reading gate scans and image frames today. The operational store is
> standard Postgres (Lakebase), so your existing tools can read the live board over a normal
> SQL connection." *(Up a level: "which means we integrate without ripping out what you have.")*

**"What about latency / scale on the live board?"**
> "The live board reads from Lakebase Postgres, which is built for low-latency operational
> reads — that's exactly why the serving layer is Postgres and the analytics stay on the
> lakehouse. Scaling to more terminals is more rows, not a re-architecture."

**"Genie — can I trust the SQL it writes?"**
> "It's constrained to the certified gold tables with curated instructions and example SQL,
> and every answer shows the generated SQL and the rows — it's auditable, and it inherits the
> same Unity Catalog permissions, so it can't see anything the user couldn't."

---

## Closing (land the value one more time) — ~1 min
> "So: today Meridian is losing about $4.1M a year to a dock scheduling problem it can't see.
> This platform makes the dock visible, forecasts the crunch, and tells supervisors what to do
> about it — on one governed lakehouse we can stand up on a pilot terminal in 30 days. The ask
> is a pilot at your worst terminal, Memphis, with a detention-reduction target we measure
> against. Where would you want to start?"

---

### Delivery reminders
- Open with the outcome; never open with the architecture.
- When the architect drills in, give the real detail — then one sentence back to the dollars.
- If a question is above your certainty, commit to the follow-up rather than bluffing.
- Watch the clock: setup 2, problem 3, app 5, briefing 3, Genie 2, architecture 3, objections + close ~7.
