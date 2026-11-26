"""Scale / Change / Stop / Monitor decision rules from slide 3 of the strategy deck.

Every rule is a pure function of current numbers. Bands are mutually exclusive,
boundary values are explicit, and anything below its minimum sample returns
"Continue Monitoring". Nothing here writes to the database: recommendations are
only applied when a person approves them (see analytics.apply_decision).
"""
from __future__ import annotations

from . import config as C
from .forecasting import two_proportion_test

SCALE, CHANGE, STOP, MONITOR = "Scale", "Change / Fix", "Stop", "Continue Monitoring"


def _d(key, state, metric_label, metric_value, threshold, sample, sample_ok, action, **extra):
    return {"key": key, "name": C.EXPERIMENT_NAMES.get(key, key), "campaign_id": extra.pop("campaign_id", key),
            "state": state, "metric_label": metric_label, "metric_value": metric_value, "threshold": threshold,
            "sample": sample, "sample_ok": bool(sample_ok), "action": action, "transfer": extra.pop("transfer", None),
            "details": extra}


def _inr(x):
    return f"Rs {int(round(x)):,}"


def decide_club(week: int, pitches: int, regs_by_w4: int, reserve_uncommitted: float, club_uncommitted: float) -> dict:
    t = C.THRESHOLDS["club"]
    label = f"Club members registered by week {t['decision_week']}"
    thr = f"Scale >= {t['scale_at']} | Change {t['change_at']}-{t['scale_at'] - 1} | Stop < {t['change_at']}"
    sample = f"{pitches} club pitches completed (minimum {t['min_pitches']})"
    common = dict(registrations=regs_by_w4, pitches=pitches, week=week)
    if week < t["decision_week"]:
        return _d("club", MONITOR, label, f"{regs_by_w4} so far", thr, sample, pitches >= t["min_pitches"],
                  f"Week {t['decision_week']} has not arrived. Keep pitching clubs and review at week {t['decision_week']}.", **common)
    if pitches < t["min_pitches"]:
        return _d("club", MONITOR, label, str(regs_by_w4), thr, sample, False,
                  f"Only {pitches} pitches completed: below the minimum sample of {t['min_pitches']}. Complete more pitches before deciding.", **common)
    if regs_by_w4 >= t["scale_at"]:
        amt = max(0, int(reserve_uncommitted))
        act = (f"Scale: allocate the available uncommitted reserve ({_inr(amt)}) to the Club Contingent League."
               if amt > 0 else "Scale: threshold met, but no uncommitted reserve is left to allocate. Hold the current budget.")
        return _d("club", SCALE, label, str(regs_by_w4), thr, sample, True, act,
                  transfer={"from": "reserve", "to": "club", "amount": amt} if amt > 0 else None, **common)
    if regs_by_w4 >= t["change_at"]:
        return _d("club", CHANGE, label, str(regs_by_w4), thr, sample, True,
                  "Change: run ambassador-led college visits to convert pitched clubs into registered contingents.", **common)
    amt = max(0, int(min(t["stop_transfer_cap"], club_uncommitted)))
    act = (f"Stop scaling: reallocate {_inr(amt)} of uncommitted Club League funds to Squad Pass "
           f"(cap {_inr(t['stop_transfer_cap'])}; only {_inr(max(club_uncommitted, 0))} is uncommitted)."
           if amt > 0 else "Stop scaling: no uncommitted Club League funds remain to reallocate.")
    return _d("club", STOP, label, str(regs_by_w4), thr, sample, True, act,
              transfer={"from": "club", "to": "squad", "amount": amt} if amt > 0 else None, **common)


def decide_showup(i: dict) -> dict:
    t = C.THRESHOLDS["showup"]
    n1, x1 = int(i.get("control_starts") or 0), int(i.get("control_confirmed") or 0)
    n2, x2 = int(i.get("treatment_starts") or 0), int(i.get("treatment_confirmed") or 0)
    label = "Confirmed per 100 registration starts: deposit minus no-deposit"
    thr = (f"Scale >= +{t['scale_pts']:g} pts AND significant at {int(t['alpha'] * 100)}% | "
           f"Change {t['stop_pts']:g} to < +{t['scale_pts']:g} pts | Stop < {t['stop_pts']:g} pts")
    sample = f"{n1} control / {n2} deposit registration starts (minimum {t['min_starts_per_arm']} per arm)"
    ok = min(n1, n2) >= t["min_starts_per_arm"]
    test = two_proportion_test(x1, n1, x2, n2, t["alpha"])
    extra = dict(test=test, early_metric="confirmed per 100 starts",
                 final_metric="verified attendees per 100 starts (available only after check-in data)")
    a1, a2 = i.get("control_attended"), i.get("treatment_attended")
    if a1 is not None and a2 is not None and test.get("valid"):
        extra["final_test"] = two_proportion_test(int(a1), n1, int(a2), n2, t["alpha"])
    if not test.get("valid"):
        return _d("showup", MONITOR, label, "n/a", thr, sample, False,
                  "Invalid or missing experiment counts. Keep reminders running; record valid counts.", **extra)
    val = f"{test['diff_pts']:+.1f} pts ({100 * test['control_rate']:.1f} -> {100 * test['treatment_rate']:.1f}), p = {test['p_value']:.3f}"
    if not ok:
        return _d("showup", MONITOR, label, val, thr, sample, False,
                  "Insufficient sample. Continue the A/B test; reminders and waitlist release keep running for everyone.", **extra)
    diff = round(test["diff_pts"], 6)  # avoid floating-point noise exactly on a boundary
    if diff >= t["scale_pts"]:
        if test["significant"]:
            return _d("showup", SCALE, label, val, thr, sample, True,
                      "Scale: roll the Rs 99 refundable deposit out to all registrants, then confirm with verified attendance per 100 starts.", **extra)
        return _d("showup", MONITOR, label, val, thr, sample, True,
                  "Lift is at least 5 points but not statistically significant. Continue testing until week 8.", **extra)
    if diff >= t["stop_pts"]:
        return _d("showup", CHANGE, label, val, thr, sample, True,
                  "Change: continue without the deposit (or keep testing until week 8). Reminders and waitlist release stay on.", **extra)
    return _d("showup", STOP, label, val, thr, sample, True,
              "Stop: drop the deposit. Keep WhatsApp reminders and waitlist release.", **extra)


def decide_squad(i: dict) -> dict:
    t = C.THRESHOLDS["squad"]
    n_c, n_t = int(i.get("control_registrants") or 0), int(i.get("treatment_registrants") or 0)
    new_c, new_t = int(i.get("control_new_people") or 0), int(i.get("treatment_new_people") or 0)
    squads = int(i.get("squads_formed") or 0)
    k_t = new_t / n_t if n_t else None
    k_c = new_c / n_c if n_c else None
    label = "New people acquired per registrant (k), squad-link arm"
    thr = f"Scale k >= {t['scale_k']:.2f} | Change {t['change_k']:.2f} <= k < {t['scale_k']:.2f} | Stop k < {t['change_k']:.2f}"
    sample = f"{n_c} plain-link / {n_t} squad-link registrants (minimum {t['min_registrants_per_arm']} per arm)"
    extra = dict(k_treatment=k_t, k_control=k_c, squads_formed=squads, fast_lane_cap=t["fast_lane_cap"],
                 fast_lane_remaining=max(t["fast_lane_cap"] - squads, 0),
                 note="k counts only people who were not already registered.")
    val = "n/a" if k_t is None else f"k = {k_t:.3f} (plain link {k_c:.3f})" if k_c is not None else f"k = {k_t:.3f}"
    if new_t > n_t * 10 or new_c < 0 or new_t < 0:
        return _d("squad", MONITOR, label, val, thr, sample, False, "Invalid experiment counts. Re-check the inputs.", **extra)
    if min(n_c, n_t) < t["min_registrants_per_arm"] or k_t is None:
        return _d("squad", MONITOR, label, val, thr, sample, False, "Insufficient sample. Keep both links running.", **extra)
    cap_note = " Fast-lane cap of 300 squads reached: new squads get the perk only." if squads >= t["fast_lane_cap"] else ""
    if k_t >= t["scale_k"] - 1e-9:
        return _d("squad", SCALE, label, val, thr, sample, True, "Scale: make the squad link the default and add a perk tier." + cap_note, **extra)
    if k_t >= t["change_k"] - 1e-9:
        return _d("squad", CHANGE, label, val, thr, sample, True, "Change: swap the squad perk (fast lane <-> food credit) and re-test." + cap_note, **extra)
    return _d("squad", STOP, label, val, thr, sample, True, "Stop: move uncommitted Squad Pass money to the Club Contingent League.", **extra)


def decide_guest(i: dict) -> dict:
    t = C.THRESHOLDS["guest"]
    n, new = int(i.get("passes_issued") or 0), int(i.get("redeemed_new_people") or 0)
    existing = int(i.get("redeemed_existing_registrants") or 0)
    rate = new / n if n else None
    label = "Guest passes redeemed by genuinely new people"
    thr = f"Scale >= {t['scale_rate']:.0%} | Change {t['change_rate']:.0%} to < {t['scale_rate']:.0%} | Stop < {t['change_rate']:.0%}"
    sample = f"{n} passes issued in the week-{t['pilot_week']} pilot (minimum {t['min_passes']})"
    extra = dict(redemption_rate_new=rate, redeemed_new_people=new, redeemed_existing_registrants=existing,
                 note="Directional evidence only: at 200 passes a 6% rate is about 12 redemptions. Existing registrants and walk-ins are not counted as new guests.")
    val = "n/a" if rate is None else f"{rate:.1%} ({new} of {n}); {existing} more redeemed by existing registrants"
    if new + existing > n or new < 0 or existing < 0:
        return _d("guest", MONITOR, label, val, thr, sample, False, "Invalid counts: redemptions exceed passes issued.", **extra)
    if n < t["min_passes"]:
        return _d("guest", MONITOR, label, val, thr, sample, False, f"Insufficient sample. The pilot runs at the week-{t['pilot_week']} pre-fest event.", **extra)
    if rate >= t["scale_rate"] - 1e-9:
        return _d("guest", SCALE, label, val, thr, sample, True, "Scale: issue a Day-2 guest pass to every Day-1 attendee.", **extra)
    if rate >= t["change_rate"] - 1e-9:
        return _d("guest", CHANGE, label, val, thr, sample, True, "Change: make passes valid for new phone numbers only and re-brief the desk.", **extra)
    return _d("guest", STOP, label, val, thr, sample, True, "Stop: drop the guest pass and move volunteers to the entry gates.", **extra)


def decide_ambassadors(i: dict) -> dict:
    t = C.THRESHOLDS["amb"]
    a, b = int(i.get("cohort_checkin_pay") or 0), int(i.get("cohort_signup_pay") or 0)
    active = int(i.get("active_ambassadors") or 0)
    regs = int(i.get("legit_registrations_last_2_weeks") or 0)
    fraud = int(i.get("fraud_confirmed") or 0)
    per = regs / active if active else None
    label = "Legitimate verified registrations per ambassador per 2 weeks"
    thr = f"Scale >= {t['scale_per_amb']:g} | Change {t['change_per_amb']:g} to < {t['scale_per_amb']:g} | Stop < {t['change_per_amb']:g} | any confirmed fraud -> deactivate"
    sample = f"cohorts of {a} and {b} ambassadors (minimum {t['min_cohort']} per cohort); {active} active"
    extra = dict(per_ambassador=per, fraud_confirmed=fraud, payout=f"Rs {t['payout_per_attendee']} per verified attendee + Rs {t['top_bonus']:,} to each of the top {t['top_n']}",
                 max_allocation=t["max_allocation"], verified_attendees=i.get("verified_attendees"),
                 final_metric="verified attendees (available after the festival)")
    val = "n/a" if per is None else f"{per:.1f} per ambassador ({regs} registrations / {active} ambassadors)"
    if fraud > 0:
        return _d("amb", STOP, label, val, thr, sample, True,
                  f"Fraud override: deactivate the {fraud} ambassador(s) with confirmed fake registrations and void their payouts. This applies regardless of other thresholds.",
                  fraud_override=True, **extra)
    if min(a, b) < t["min_cohort"] or not active:
        return _d("amb", MONITOR, label, val, thr, sample, False, "Insufficient data: each payout cohort needs at least 20 ambassadors.", **extra)
    if per >= t["scale_per_amb"] - 1e-9:
        return _d("amb", SCALE, label, val, thr, sample, True, "Scale: raise quotas and bonuses for the top 20% of ambassadors (within the Rs 50,000 cap).", **extra)
    if per >= t["change_per_amb"] - 1e-9:
        return _d("amb", CHANGE, label, val, thr, sample, True, "Change: pair low performers with a club lead and coach on the referral pitch.", **extra)
    return _d("amb", STOP, label, val, thr, sample, True, "Stop: deactivate ambassadors below 2 registrations per fortnight and redeploy their budget.", **extra)


def decide_generic(c: dict, cost_screen: float) -> dict:
    """Rule for acquisition campaigns without a dedicated experiment (organic, community, paid, creators)."""
    regs = c.get("registrations", 0)
    pace = (c.get("projection") or {}).get("pace_vs_plan")
    cost = c.get("cost_per_projected_attendee")
    label = "Pace vs time-aligned plan and cost per projected attendee"
    thr = f"Scale: pace >= 1.10 and cost <= Rs {cost_screen:g} | Change: pace < 0.80 or cost > Rs {cost_screen:g} | Stop: both"
    sample = f"{regs} registrations so far (minimum 50)"
    val = "n/a" if pace is None or cost is None else f"pace {pace:.2f}x plan, Rs {cost:,.0f} per projected attendee"
    kw = dict(campaign_id=c["id"], pace=pace, cost_per_projected_attendee=cost)
    if regs < 50 or pace is None or cost is None:
        return _d(f"generic:{c['id']}", MONITOR, label, val, thr, sample, False, "Insufficient data to judge this campaign yet.", **kw)
    slow, costly = pace < 0.80, cost > cost_screen
    if slow and costly:
        return _d(f"generic:{c['id']}", STOP, label, val, thr, sample, True, "Stop: behind plan and above the cost screen. Move uncommitted budget to a campaign that is scaling.", **kw)
    if slow or costly:
        why = "behind plan" if slow else "above the cost screen"
        return _d(f"generic:{c['id']}", CHANGE, label, val, thr, sample, True, f"Change: {why}. Fix targeting or creative before spending more.", **kw)
    if pace >= 1.10:
        return _d(f"generic:{c['id']}", SCALE, label, val, thr, sample, True, "Scale: ahead of plan and within the cost screen. Eligible for uncommitted budget.", **kw)
    return _d(f"generic:{c['id']}", MONITOR, label, val, thr, sample, True, "On plan. Continue and review next Monday.", **kw)


def decide_guardrail(week: int, forecast: dict, campaigns: list, decisions: dict, s: dict, reserve_uncommitted: float) -> dict:
    """Week-6 guardrail: diagnose the cause before recommending any reallocation."""
    gw, ratio = int(s.get("guardrail_week", 6)), float(s.get("guardrail_ratio", 0.9))
    base = float(s.get("base_target", 0))
    fc = forecast["expected_attendance"]
    line = ratio * base
    label = "Forecast attendance vs base plan"
    thr = f"Trigger if forecast < {ratio:.0%} of base plan ({line:,.0f}) from week {gw}"
    val = f"{fc:,} forecast = {100 * fc / base:.1f}% of {base:,.0f}" if base else "n/a"
    kw = dict(campaign_id=None, forecast=fc, line=line)
    if week < gw:
        return _d("guardrail", MONITOR, label, val, thr, f"week {week} of {C.TOTAL_WEEKS}", False,
                  f"The guardrail is evaluated from week {gw}. No action yet.", **kw)
    if fc >= line:
        return _d("guardrail", MONITOR, label, val, thr, f"week {week}", True, "Forecast is within 90% of plan. No guardrail action.", **kw)
    acq = [c for c in campaigns if c.get("projection")]
    worst = min(acq, key=lambda c: c["projection"]["attendee_gap_vs_plan"]) if acq else None
    if not worst:
        return _d("guardrail", CHANGE, label, val, thr, f"week {week}", True, "Forecast below plan but no acquisition campaign data is available to diagnose.", **kw)
    p = worst["projection"]
    causes = []
    if p["pace_vs_plan"] is not None and p["pace_vs_plan"] < 0.9:
        causes.append(f"registrations are at {p['pace_vs_plan']:.0%} of the time-aligned plan ({worst['registrations']} vs {p['plan_registrations_to_date']:.0f})")
    exp = worst.get("exp_confirm_rate")
    if exp and worst.get("confirm_rate") is not None and worst["confirm_rate"] < exp - 0.05:
        causes.append(f"confirm rate is {worst['confirm_rate']:.0%} vs {exp:.0%} expected")
    if not causes:
        causes.append("projected attendees are below plan although pace and confirmation are near plan")
    own = decisions.get(worst["id"])
    fix = own["action"] if own and own["state"] in (CHANGE, STOP) else "Assign a recovery task to the campaign owner and review weekly."
    paid = next((c for c in campaigns if c["id"] == "paid"), None)
    paid_note = ""
    if paid and paid.get("projection") and paid["projection"]["pace_vs_plan"] is not None:
        ok = paid["projection"]["pace_vs_plan"] >= 0.8 and (paid.get("cost_per_projected_attendee") or 0) <= float(s.get("cost_screen_inr", 274))
        paid_note = (" Paid Retargeting is performing within its limits, so it is not cut." if ok
                     else " Paid Retargeting is itself below its limits; review it on its own evidence before cutting.")
    res = max(0, int(reserve_uncommitted))
    res_note = f" Uncommitted reserve available: {_inr(res)}." if res else " No uncommitted reserve is left."
    action = (f"Bottleneck: {worst['name']} is {abs(p['attendee_gap_vs_plan']):,.0f} projected attendees below its plan because "
              + "; ".join(causes) + f". Recommended: {fix}{res_note}{paid_note}")
    return _d("guardrail", CHANGE, label, val, thr, f"week {week}", True, action,
              bottleneck=worst["id"], bottleneck_gap=p["attendee_gap_vs_plan"], causes=causes, reserve_uncommitted=res, **{k: v for k, v in kw.items() if k != "campaign_id"},
              campaign_id=worst["id"])
