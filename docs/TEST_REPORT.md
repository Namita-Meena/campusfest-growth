# Test report

Automated tests executed on 26 and 28 November 2026 in the development environment (Python 3.13, local SQLite store, no network access to Supabase or Gemini). Deployment checks executed on the live app at https://campusfest-growth-namita.streamlit.app on 26 and 28 November 2026.

## Part 1 — Automated (`python -m pytest -q`: 113 passed)

| Test | Expected | Actual | Result |
|---|---|---|---|
| 2025 funnel from raw data | 666,297 reach; 3,500 leads; 2,800 registrations; 1,925 + 125 = 2,050 attendees; ₹2,74,000 spend | Same | Passed |
| Rate denominators | 77.0% among confirmed; 0% among unconfirmed; 81.3 and 62.6 per 100 starts | Same | Passed |
| Duplicate handling and historical integrity | 2 / 4 / 20 duplicate IDs removed; raw files unchanged; names not exposed | Same | Passed |
| As-of-date snapshot | No attendance before 12 April 2025; launch-plan targets before 15 March | Same | Passed |
| Budget reconciliation | Allocations = ₹3,00,000; reserve ₹20,000 | Same | Passed |
| Double-counting prevention | Forecast = registered + walk-ins + guests; interventions hold no registrations; Show-Up Engine changes rates only | Same | Passed |
| Forecast reconciliation | Plan inputs give 2,600 (base) and 3,400 (stretch) within rounding | 2,599 and 3,400 | Passed |
| Decision boundaries | Club 250 / 249 / 150 / 149; deposit ±5 points; k 0.20 / 0.10; guest 6% / 3%; ambassadors 10 / 2 | As specified | Passed (one floating-point boundary bug found and fixed: +5.0 points was read as 4.99999) |
| Minimum samples | Below minimum → Continue Monitoring | Same | Passed |
| Statistical test | z = 3.2566, p = 0.00113 (SciPy reference) | Same | Passed |
| Significant vs not | +5.2 points with p = 0.10 → Continue Monitoring | Same | Passed |
| Fraud override | Any confirmed fraud → deactivate regardless of volume | Same | Passed |
| Reserve allocation | Second approval refused; reserve cannot go below zero | Same | Passed |
| Persistence | Edit and task survive re-opening the database file | Same | Passed |
| Validation | Negative values, over-budget allocation, invalid rates, invalid counts, empty title, bad date rejected | Same | Passed |
| Reset | Seed restored; historical figures unchanged | Same | Passed |
| Copilot tools after an edit | 140 registrations, Stop, ₹38,800 transferable | Same | Passed |
| Missing data | "age" query returns an error and is listed as not available | Same | Passed |
| Task approval | Draft tool saves nothing | Same | Passed |
| Model loop | Tool calls executed, results returned with matching IDs, final text returned | Same, with a scripted fake model | Passed |
| Every page renders | 6 pages × weeks 1, 4, 8, 12 without exceptions | Same | Passed |
| Recruiter demo through the forms | 260 → 140 → Stop → forecast lower → approve moves ₹38,800 → second approval refused | Same | Passed |
| Model fallback | A key that cannot use the configured models falls back to one it can; a busy model is retried, not blacklisted | Same | Passed |
| Theme switch | Exactly one Dark / Light control, in the sidebar; switching redraws the page in the other theme; the choice is still set after moving to another page | Same | Passed |
| Every page in both themes | 6 pages × Dark and Light render without exceptions | Same | Passed |
| Colour contrast | Every text colour in both palettes reaches 4.5:1 on page, panel and field backgrounds; white labels on light-theme badges reach 4.5:1; chart fills reach 3:1 | Same | Passed |

### Visual check of the two themes (executed locally in a real browser, 28 November 2026)

The app was run locally and driven with headless Chrome (Playwright). These were looked at as screenshots, not only asserted in code.

| Check | Outcome | Result |
|---|---|---|
| Every page and every tab in Dark (6 pages, 14 tabs, plus a copilot exchange) | No unstyled or unreadable element; no exception | Passed |
| Every page and every tab in Light (same set) | Same. First pass found dark input boxes and a dark message box on the light page; the selectors were corrected and the set re-captured | Passed after fix |
| Switch used on each of the 6 pages | Page background changes, the reader stays on the same page, the selected option is highlighted | Passed |
| Theme carried across navigation and a browser refresh | Light chosen on one page is Light on the next and after reload (URL carries `?theme=light`) | Passed |
| Clicking the already-selected option | Selection is kept (the control cannot be left empty) | Passed |
| Old `.streamlit/config.toml` still in place | Both themes still render correctly; grids are flipped by filter | Passed |
| Phone width (430 px) | Header, focal number and alerts stack in one column in both themes | Passed |

Not covered locally: the Google-hosted fonts (the development environment cannot reach Google Fonts, so screenshots used locally installed Inter and Anonymous Pro), and the deployed app itself (see Part 3).

## Part 2 — Executed on the deployed app

| Test | Expected outcome | Actual outcome | Result |
|---|---|---|---|
| Public deployment | App opens at the public URL with no install and no key from the visitor | Opens; all six pages render | Passed |
| Supabase connection | Sidebar reports persistent storage; empty database seeds itself | "Storage: Supabase PostgreSQL (persistent)"; six tables created by `sql/schema.sql` and filled on first start | Passed |
| Cross-session persistence | A change saved in one session is still there days later | An approved Club League transfer made on 26 Nov (reserve ₹20,000 → ₹0) was still in effect on 28 Nov in a new browser session | Passed |
| AI copilot grounded answer | Numbers come from the live database, labelled as simulated, with the tool calls shown | Answered "on track": 2,686 forecast vs 2,600 base (103.3%), 646 registrations vs 620 plan, 580 confirmed (89.8%), named the ₹0 uncommitted reserve as the biggest risk and the ambassadors' Change / Fix state, listed its assumptions, and showed the tool call it used | Passed |
| AI copilot respects budget rules | Does not propose money that is not uncommitted | With the reserve already spent it recommended holding the Club League budget instead of expanding it | Passed |
| Behaviour when the AI service is busy | A clear message, no crash, other pages unaffected | On 26 Nov every Gemini model returned 503 "high demand" or 504; the app reported which models it tried and what the key can use, and the rest of the app kept working. Retry logic was then improved (rotate models, pause, retry busy ones, "Ask the same question again") and a later question answered normally | Passed, after a fix |

## Part 3 — Still to confirm before submission

| Test | How to verify |
|---|---|
| Full recruiter demo on the deployed app | `docs/DEMO_GUIDE.md` steps 1–10, after pressing "Reset demo workspace" |
| Task approval round trip | Ask the copilot to create a task, approve it, refresh the browser, check the Task Manager |
| Missing-data question | Ask "What is the average age of festival attendees?" and confirm the copilot says the data cannot answer it |
| Theme switch on the deployed app | After uploading update 4: click Light, open each of the six pages, click Dark, refresh once |
| Incognito access | Open the URL in a private window and confirm no sign-in is required |
