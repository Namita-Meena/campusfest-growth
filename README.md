# CampusFest Growth Intelligence

Growth command centre for **CampusFest Bengaluru 2027** (Challenge A: Attendee Growth), built for the RISA Labs Growth APM assignment by **Namita Meena, IIT Kharagpur**.

**Public app:** `ADD-YOUR-STREAMLIT-URL-HERE` (replace after deployment)

It is one product with five working parts and a reference section:

| Page | What the team does there |
|---|---|
| Growth Overview | Targets vs forecast, funnel, weekly pace, budget, growth bridge, alerts |
| Campaign Intelligence | Compare campaigns, see the bottleneck, edit results and budgets, create or archive campaigns |
| Experiments and Budget | Decision engine (Scale / Change / Stop / Monitor), approve or reject, scenario simulator, decision log |
| Task Manager | Create, assign, filter, complete and delete tasks |
| AI Growth Copilot | Ask questions answered from live data and the 2025 dataset; draft tasks that need approval |
| Historical Data and Methodology | Explore the original dataset, data dictionary, quality checks, formulas |

Every saved edit is written to the database and every page and the AI copilot read the same data, so a change in one place updates all analytics.

---

## 1. The problem

RISA Labs asked for a three-slide growth strategy and a working "growth center" (analytics dashboard, campaign management tool and embedded AI chatbot) for a college festival in a Tier 1 Indian city. I chose **Challenge A: maximise the number of people who actually attend**.

North Star metric: **unique, verified external attendees**.

## 2. Strategy in one paragraph

CampusFest 2025 had 2,050 verified attendees on ₹2.74L. Paid social and creators took 55% of spend but produced 27% of registered attendees, and only about half of their registrants showed up. Clubs, referrals, organic and community showed up 78–86% of the time at a third of the cost. The 2027 plan keeps the approved ₹3,00,000 and moves money to high-show channels, adds a Show-Up Engine (reminders and waitlist release), a referral loop (Squad Pass) and a Day-2 guest pass. Targets: **2,600 base, 3,400 stretch**.

## 3. Why Bengaluru

| Factor | Evidence | Source |
|---|---|---|
| Reachable student base | Bengaluru Urban has the most colleges of any district in India (1,106; Jaipur 703, Hyderabad 491, Pune 475) | AISHE 2021-22, reported by [Careers360 / PTI](https://news.careers360.com/up-has-highest-number-of-colleges-in-country-followed-maharashtra-karnataka-aishe-report) |
| Transit | Namma Metro reached 103.6 km and 91 stations in November 2026, the second-largest metro network in India | [Siasat](https://www.siasat.com/pink-lines-7-5-km-stretch-to-open-for-commuters-on-november-14-3576124/), [Wikipedia: Namma Metro](https://en.wikipedia.org/wiki/Namma_Metro) |
| Existing inter-college club networks | Mount Carmel College's Cul-Ah admits college contingents with 15 free cheer-squad members plus up to 50 more (65 per college) | [Cul-Ah '26 brochure](https://mccblr.edu.in/wp-content/uploads/2026/02/cul-ah-brochure-26.pdf) |

Assumptions (not sourced): about 300 colleges within reach of a metro station, venue within 1 km of a station, venue capacity 3,000 simultaneous occupants, festival on 20–21 February 2027.

Benchmark used for the Show-Up Engine: free events have a median no-show of about 28% and paid events about 17% ([PheedLoop Event Data Lab #05](https://pheedloop.com/blog/event-data-lab-report-5)); CampusFest 2025 was at 31%.

## 4. Data sources and what is fact vs simulated

| Kind | Where it comes from | In the app |
|---|---|---|
| **Historical 2025 (fact)** | `data/historical/`: the original RISA dataset (fictional, synthetic). The original workbook is kept unchanged next to CSV exports of each sheet | Recomputed from raw records on load. Read-only. Never stored in the editable database |
| **Simulated 2027** | `core/seed.py`: deterministic demo data for campaign weeks 1–8 | Editable. Labelled "Simulated 2027" |
| **Targets** | The three-slide deck | Labelled "Target" |
| **Forecast** | Formula in section 8 applied to simulated data | Labelled "Forecast" |
| **Assumptions** | Listed in section 6; adjustable in the simulator | Labelled "Assumption" |

### Cleaning rules (from the dataset's own "Read me" sheet)

1. Exact repeated IDs are import retries and count once (2 daily-marketing rows, 4 status-history rows, 20 check-in rows removed).
2. Only `person_type = external` counts toward attendee metrics (internal 40, staff 10, test 10 excluded).
3. Attendance means an **admitted + verified** check-in (50 denied and 30 pending/unverified excluded). A person who came on both days counts once.
4. For any date, the latest registration-status version effective by the end of that day is used. No later outcome appears in an earlier snapshot.
5. Summed platform reach is not unique people and is always labelled that way.

### 2025 figures verified against the raw data (`tests/test_historical.py`)

| Metric | Deck | Recomputed | Note |
|---|---:|---:|---|
| Reported platform reach | 666,000 | 666,297 | Sum of daily reach, not unique |
| Identified leads | 3,500 | 3,500 | Campaign-attributed external people. 3,625 external people were identified in total (adds 125 walk-ins) |
| Registrations | 2,800 | 2,800 | Distinct external people; 40 internal registrations excluded |
| Registered attendees | 1,925 | 1,925 | |
| Unique walk-ins | 125 | 125 | Verified external visitors without a registration |
| New Day-2 guests | 0 | 0 | By definition: no guest-pass programme existed in 2025. The dataset has no "guest" field |
| Total verified attendees | 2,050 | 2,050 | Against a revised goal of 2,200 |
| Marketing spend | ≈₹2,74,000 | ₹2,74,000 | Net of 4 vendor-credit rows |
| Attendance among confirmed | 77% | 77.0% (1,925 / 2,500) | |
| Attendance among unconfirmed | 0% | 0% (0 / 300) | Cancelled 183, waitlisted 88, interested 29 |
| Confirmed per 100 registration starts | ≈81 | 81.3 (2,500 / 3,075) | Identified starters |
| Attended per 100 registration starts | ≈63 | 62.6 | |

**Discrepancies found and how they were resolved**

- The deck rounds reach to 666k; the app uses the exact 666,297.
- "Identified leads" can mean 3,500 (campaign-attributed) or 3,625 (all identified external people). The app shows both and uses 3,500 for the funnel, as the deck does.
- No personal data such as phone numbers or emails exists in the dataset. Person names are synthetic display labels; the app drops them on load, so they are never shown or sent to the AI model.

### Data dictionary

The full field guide ships with the dataset and is shown in the app (Historical Data and Methodology → Data dictionary and quality). Tables: `event`, `targets`, `campaigns`, `daily_marketing`, `people`, `interactions`, `registrations`, `registration_history`, `checkins`, plus a derived `people_summary` (one row per identified person with funnel outcome flags). **Not in the dataset:** age, gender, college, course, home city, contact details, ticket revenue, satisfaction scores, per-ambassador or per-club performance, unique cross-day reach.

## 5. Base and stretch model

One counterfactual is used throughout: **the 2025 channel mix scaled to ₹3L** (2,167 attendees). Each lever's contribution is its attendees in the plan minus that channel's attendees in the counterfactual, so the extra budget is never counted twice.

Assumption on diminishing returns: when a channel's spend doubles, its cost per registration rises about 27% in the base case (exponent 0.35) and about 15% in the stretch case (exponent 0.20; one club deal brings many sign-ups). Scaling is therefore **not** linear in budget.

| Lever | Counterfactual | Plan (base) | Base | Stretch | What changes in stretch |
|---|---|---|---:|---:|---|
| 2025 verified attendance | | | 2,050 | 2,050 | |
| Same mix at ₹3L | 2,167 attendees | | +117 | +117 | |
| Cut cold paid + macro-creators | ₹1,66,400 → 547 attendees | ₹35,000 → 200 attendees | −346 | −346 | |
| Club Contingent League | ₹33,900 → 477 regs × 85.6% = 408 | ₹95,000 at ₹102/reg → 932 regs × 85.6% = 797 | +389 | +535 | Cost per registration ₹86 → 1,102 regs |
| Show-Up Engine | 0 | +5 points on registered → attended across 2,888 regs | +144 | +298 | +10 points (deposit also wins its test) |
| Squad Pass | 371 referral regs → 292 | k = 0.20 × 2,407 other regs = 481 regs × 78.6% = 378 | +86 | +322 | k = 0.30 × 2,603 = 781 regs |
| Day-2 guests + walk-ins | 125 walk-ins | 150 walk-ins + 6% × 1,646 Day-1 registered attendees = 99 guests | +124 | +369 | 250 walk-ins + 12% × 2,034 = 244 guests |
| Pay-per-check-in ambassadors | 552 regs → 414 | 582 regs → 437 | +23 | +34 | |
| Organic + community | 382 | 395 | +13 | +21 | |
| **Target** | | | **2,600** | **3,400** | |

Funnel reconciliation: registered attendees + walk-ins + new guests = 2,351 + 150 + 99 = **2,600** (base) and 2,906 + 250 + 244 = **3,400** (stretch). 2025 referral coefficient k = 350 / 2,450 = 0.14. The 12% stretch guest rate is twice the pilot's scale line and is the least certain number in the model.

## 6. Assumptions (all adjustable in the simulator)

Venue capacity 3,000 at once · festival dates · 60 clubs signed by week 6 · ambassadors open about 25% of club deals · walk-ins 150 (base) / 250 (stretch) · guest redemption 6% / 12% · Day 1 holds 70% of unique attendees (2025: 1,430 of 2,050) · referral k 0.20 / 0.30 · the 2025 weekly registration curve applies to 2027 · Show-Up Engine lifts (section 8).

## 7. Prioritisation framework and budget

`rank score = extra attendees × confidence`. Confidence weights are **judgment-based**, not estimated probabilities: 0.8 proven in 2025 data, 0.7, 0.6, 0.5, 0.4 untested.

Cost screen: new money per weighted attendee should beat ₹274 (paid social's 2025 cost per verified attendee). This is a conservative benchmark, not a like-for-like acquisition cost. New money = plan spend − counterfactual spend.

| Rank | Bet | Budget | New money | Base / stretch | Confidence | Weighted | ₹ per weighted | Call |
|---|---|---:|---:|---|---:|---:|---:|---|
| 1 | Club Contingent League | ₹95,000 | ₹61,000 | +389 / +535 | 0.8 | 311 | ₹196 | Double down |
| 2 | Show-Up Engine | ₹25,000 | ₹25,000 | +144 / +298 | 0.7 | 101 | ₹248 | Double down |
| 3 | Squad Pass | ₹30,000 | ₹9,200 | +86 / +322 | 0.6 | 52 | ₹177 | Scale |
| 4 | Day-2 Guest Pass + walk-ins | ₹10,000 | ₹10,000 | +124 / +369 | 0.4 | 50 | ₹200 | Test small |
| 5 | Pay-per-check-in ambassadors | ₹50,000 | ₹4,000 | +23 / +34 | 0.5 | 12 | ₹333 | Keep as enabler |

Other lines: organic ₹15,000 · community ₹20,000 · paid retargeting ₹25,000 · micro-creators ₹10,000 · reserve ₹20,000 (6.7%). **Total ₹3,00,000.** Ambassadors fail the screen on new money alone; they stay because the whole channel costs about ₹114 per attendee and it opens club doors. Reduce it if its cost per verified attendee rises above ₹274.

## 8. Forecast formula

```
expected attendance = confirmed registrants   × P(attend | confirmed)
                    + unconfirmed registrants × P(attend | unconfirmed)
                    + expected unique walk-ins
                    + expected unique new Day-2 guests
```

- Projected final registrations per campaign = registrations to date + remaining plan × current pace, with pace = registrations to date ÷ time-aligned plan (limited to 0.25–2.0×). The time-aligned plan spreads planned registrations by the 2025 weekly curve (22% by week 4).
- Confirm rate = observed to date once a campaign has 30 registrations, otherwise the matching 2025 channel rate.
- `P(attend | confirmed)` uses **confirmed** registrants as the denominator (club 91.7%, referrals 85.9%, organic 86.7%, community 89.2%, ambassadors 81.2%, paid 58.6%, creators 60.3%; 77% overall), so the confirmation drop is not applied twice. `P(attend | unconfirmed)` = 0.
- **Show-Up Engine is an intervention, not an acquisition campaign.** While active it adds +3.0 points to the confirm rate (waitlist release: 88 of 2,800 registrants were stuck on the waitlist in 2025) and +2.65 points to attendance among confirmed (calibrated so the base plan reproduces 2,351 registered attendees). It never adds people.
- New guests = Day-1 registered attendees (70%) × redemption rate. Walk-ins and guests hold no registration.
- Attribution: each registration belongs to exactly one acquisition campaign (its recorded source), the same rule as the 2025 dataset. The deck's incremental estimates are never added to campaign attendance.

`tests/test_forecasting.py` checks that the formula reproduces 2,600 and 3,400 from the plan inputs.

## 9. Decision rules

Bands are mutually exclusive; below the minimum sample every rule returns **Continue Monitoring**; nothing is applied without approval.

| Experiment | Metric | Minimum sample | Scale | Change / Fix | Stop |
|---|---|---|---|---|---|
| Club Contingent League | Club members registered by week 4 | 20 pitches, week ≥ 4 | ≥ 250 → allocate uncommitted reserve | 150–249 → ambassador-led visits | < 150 → move up to ₹40,000 of uncommitted club money to Squad Pass |
| Show-Up Engine (₹99 refundable deposit) | Confirmed per 100 registration starts, deposit − no deposit | 500 starts per arm | ≥ +5 pts **and** significant at 5% | −5 to < +5 pts | < −5 pts |
| Squad Pass | New people per registrant, k | 300 registrants per arm | k ≥ 0.20 | 0.10 ≤ k < 0.20 | k < 0.10 |
| Day-2 Guest Pass | Redemption by new people | 200 passes (week-8 pilot) | ≥ 6% | 3% to < 6% | < 3% |
| Ambassadors | Legitimate registrations per ambassador per 2 weeks | 20 per cohort | ≥ 10 | 2 to < 10 | < 2; any confirmed fraud → deactivate |

- Deposit test: two-sided two-proportion z-test (pooled standard error) with a 95% Wald interval, implemented in `core/forecasting.py` and checked against SciPy reference values. A lift of 5 points or more that is not significant stays in Continue Monitoring. With 500 per arm, a true 7-point lift is detected about 80% of the time; detecting 3 points would need about 2,500 per arm. Confirmation is an early indicator; the final metric is verified attendees per 100 starts.
- The guest pilot is directional (200 passes ≈ 12 redemptions at 6%).
- Week-6 guardrail: if the forecast is below 90% of the base plan, the engine names the campaign furthest below its plan, the stage that is failing, the uncommitted reserve available, and whether paid retargeting is itself within limits. It never cuts a campaign automatically.
- Budget control: uncommitted = allocation − spend − open commitments. An approved transfer reduces the source, so the reserve cannot be allocated twice, and the same recommendation cannot be approved twice in one week.

## 10. AI copilot architecture

- **Model:** Google Gemini through the `google-genai` SDK (`gemini-3.8-flash` by default, with fallbacks; set `GEMINI_MODEL` to override). The key stays in server-side secrets.
- **Grounding:** the model has 14 deterministic Python tools (`core/ai_copilot.py`): dashboard summary, campaign metrics, campaign comparison, experiment decisions, budget availability, attendance forecast, scenario simulation, tasks, decision log, historical metrics (optionally as of a date), a restricted historical query (filter / group / aggregate on whitelisted tables), data dictionary, a two-proportion test, and task drafting. Each tool reads the current database at call time, so answers reflect edits made seconds earlier.
- **No arithmetic by the model:** numbers come from the tools. No model-generated code or SQL is executed.
- **No writes by the model:** `draft_task` only prepares a draft. The page shows it with Approve and Reject buttons; only Approve saves it (source "AI-generated").
- **Uncertainty:** the data dictionary tool lists what is not available (age, gender, college …), and the system instruction tells the model to say so instead of estimating.
- **Transparency:** every answer shows which tools were called.

## 11. Technology

Streamlit 1.67 · Python · pandas · Plotly · Supabase PostgreSQL (`supabase` client) · Google Gemini (`google-genai`) · pytest. No LangChain, Docker or separate front end.

### Database (Supabase)

`sql/schema.sql` creates six tables: `settings`, `campaigns`, `campaign_metrics` (weekly rows), `experiment_results` (inputs per experiment and week), `tasks`, `decision_logs`. Row Level Security is enabled on all of them with no policies, so the publishable key can access nothing; the app uses the secret key from server-side secrets. The app seeds an empty database itself and "Reset demo workspace" restores the seed.

**The demo workspace is shared:** all visitors see and edit the same data, and edits persist. Anyone can press Reset. The 2025 dataset is not in the database and cannot be changed.

Without Supabase credentials the app falls back to a local SQLite file so it can run on a laptop; that file is not persistent on Streamlit Community Cloud and the sidebar shows which storage is active.

## 12. Run locally (optional)

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501. Without secrets the app uses local SQLite and the copilot page explains that the AI key is missing. To connect services locally, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the three values (never upload that file).

## 13. Deploy

1. Supabase: create a project, run `sql/schema.sql` in the SQL Editor, copy the Project URL and a secret key.
2. Google AI Studio: create a Gemini API key.
3. GitHub: upload this folder to a repository.
4. Streamlit Community Cloud (share.streamlit.io): Create app → pick the repository, branch `main`, file `app.py` → Advanced settings → paste the three secrets → Deploy.

## 14. Testing

```bash
python -m pip install pytest
python -m pytest -q
```

85 automated tests: historical figures re-derived from raw data; every decision boundary, minimum sample and the fraud override; forecast reconciliation to 2,600 and 3,400; z-test against SciPy reference values; persistence across a restart; reserve double-allocation; input validation; copilot tools reflecting edits; the model loop with a scripted fake model; headless rendering of every page at weeks 1, 4, 8 and 12; and the recruiter demo through the real forms. See `docs/TEST_REPORT.md` for what was and was not executed, and `docs/DEMO_GUIDE.md` for the walkthrough.

## 15. Known limitations

- 2027 campaign data is simulated. Forecast quality depends on the assumption that 2025 pacing and show rates carry over.
- Simulated weekly data exists for weeks 1–8. Later weeks show the latest recorded position until numbers are added.
- Experiment inputs are entered as counts; there is no live integration with ticketing, WhatsApp or UPI (out of scope by design).
- No login: the public demo is a single shared workspace. A production version would add authentication and per-user audit trails.
- Budget-to-registration elasticity in the simulator is an explicit assumption, off by default.
- The copilot depends on the Gemini API quota of the configured key. If the quota is exhausted it says so; the rest of the app keeps working.
- Attribution is by recorded source, which is not proof of incrementality.

## 16. AI assistance disclosure

The application code, tests and this README were produced with Claude (Anthropic) under my direction, from my three-slide strategy and the RISA dataset. Calculations were verified by recomputing every 2025 figure from the raw records and by the automated tests above. The embedded copilot uses Google Gemini. Strategy choices (city, five bets, thresholds, budget) are documented in the deck; numbers marked as assumptions are mine to defend.
