# Test report

Executed on 26 November 2026 in the development environment (Python 3.13, local SQLite store, no network access to Supabase or Gemini).

## Executed and passed (automated, `python -m pytest -q`: 85 passed)

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

## Not executed yet (needs the live services)

| Test | Why not yet | How to verify |
|---|---|---|
| Supabase read / write / reset | No Supabase project existed in the development environment. Only the client call syntax was checked | Sidebar shows "Supabase PostgreSQL (persistent)"; edit a value, refresh, value remains; rows visible in Supabase Table Editor |
| Live Gemini answers (grounding, follow-ups, missing data, task draft) | No API key or network access in the development environment | Steps 5–9 of `DEMO_GUIDE.md` on the deployed app |
| Gemini free-tier availability of `gemini-3.8-flash` | Could not be confirmed from the documentation | First chatbot question after deployment; fallbacks are configured |
| Public accessibility | App not deployed yet | Open the URL in an incognito window |

Update this table after deployment.
