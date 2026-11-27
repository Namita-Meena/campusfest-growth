"""Page 4 - Task Manager: turn decisions into owned, dated actions."""
from datetime import date

import pandas as pd
import streamlit as st

from core import analytics as an
from core import config as C
from core import ui

W = ui.week()
ctx = an.build_context(W)
ui.header("Task Manager", "Who is doing what, by when?",
          f"Week {W} ({ctx['week_dates']}) · Tasks are saved to the database and survive a browser refresh. AI-proposed tasks appear here only after approval.")
ui.show_flashes()

names = {c["id"]: c["name"] for c in ctx["campaigns"]}
camp_options = ["General"] + list(names.values())
by_name = {v: k for k, v in names.items()}
tasks = ctx["tasks"]
week_end = str(C.week_end(W))

open_t = [t for t in tasks if t["status"] != "Completed"]
ui.cards([("Open tasks", ui.num(len(open_t)), "", None),
          ("Overdue", ui.num(sum(1 for t in open_t if str(t["deadline"]) < week_end)), f"deadline before {C.week_end(W):%d %b %Y}", None),
          ("Blocked", ui.num(sum(1 for t in tasks if t["status"] == "Blocked")), "", None),
          ("Completed", ui.num(sum(1 for t in tasks if t["status"] == "Completed")), "", None),
          ("AI-generated", ui.num(sum(1 for t in tasks if t["source"] == "AI-generated")), "approved from the copilot", None)])

f1, f2, f3, f4 = st.columns(4)
fc_ = f1.multiselect("Campaign", camp_options, key="tf_c")
fo = f2.multiselect("Owner", sorted({t["owner"] for t in tasks} | set(C.OWNERS)), key="tf_o")
fp = f3.multiselect("Priority", C.TASK_PRIORITIES, key="tf_p")
fs = f4.multiselect("Status", C.TASK_STATUSES, key="tf_s")


def cname(t):
    return names.get(t.get("campaign_id"), "General")


view = [t for t in tasks if (not fc_ or cname(t) in fc_) and (not fo or t["owner"] in fo) and (not fp or t["priority"] in fp) and (not fs or t["status"] in fs)]
order = {p: i for i, p in enumerate(C.TASK_PRIORITIES)}
view.sort(key=lambda t: (t["status"] == "Completed", str(t["deadline"]), order.get(t["priority"], 9)))

if view:
    df = pd.DataFrame([{"Title": t["title"], "Campaign": cname(t), "Owner": t["owner"], "Deadline": str(t["deadline"])[:10], "Priority": t["priority"],
                        "Status": t["status"], "Source": t["source"], "Evidence": t.get("evidence") or "", "Description": t.get("description") or "",
                        "Created": str(t.get("created_at") or "")[:10]} for t in view])

    def colour(v):
        return {"Completed": f"color:{ui.grid_tone('green')};font-weight:600", "Blocked": f"color:{ui.grid_tone('red')};font-weight:600",
                "In Progress": f"color:{ui.grid_tone('blue')};font-weight:600"}.get(v, "")

    st.dataframe(df.style.map(colour, subset=["Status"]), hide_index=True, width="stretch")
else:
    st.info("No tasks match the filters.")

st.divider()
tab_new, tab_edit = st.tabs(["Create task", "Edit, complete or delete"])

with tab_new:
    with st.form("new_task", clear_on_submit=True):
        a, b = st.columns(2)
        title = a.text_input("Task title")
        camp = b.selectbox("Linked campaign", camp_options)
        desc = st.text_area("Description", height=80)
        a, b, c, d = st.columns(4)
        owner = a.selectbox("Owner", C.OWNERS)
        deadline = b.date_input("Deadline", C.week_end(min(W + 1, 12)))
        prio = c.selectbox("Priority", C.TASK_PRIORITIES, index=1)
        status = d.selectbox("Status", C.TASK_STATUSES)
        evidence = st.text_input("Supporting evidence (metric, threshold or decision)")
        if st.form_submit_button("Create task", type="primary"):
            try:
                an.save_task(dict(title=title, description=desc, campaign_id=by_name.get(camp), owner=owner, deadline=str(deadline), priority=prio,
                                  status=status, evidence=evidence, source="Manual"), is_new=True)
                ui.flash(f"Task '{title}' created.")
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))

with tab_edit:
    if not tasks:
        st.info("There are no tasks yet.")
    else:
        labels = {f"{t['title']}  ·  {t['owner']}  ·  {t['status']}": t for t in sorted(tasks, key=lambda t: str(t["deadline"]))}
        pick = st.selectbox("Select a task", list(labels), key="task_pick")
        t = labels[pick]
        with st.form(f"edit_task_{t['id']}"):
            a, b = st.columns(2)
            title = a.text_input("Task title", t["title"])
            cur_c = cname(t)
            camp = b.selectbox("Linked campaign", camp_options, index=camp_options.index(cur_c) if cur_c in camp_options else 0)
            desc = st.text_area("Description", t.get("description") or "", height=80)
            a, b, c, d = st.columns(4)
            owners = sorted(set(C.OWNERS + [t["owner"]]))
            owner = a.selectbox("Owner", owners, index=owners.index(t["owner"]))
            deadline = b.date_input("Deadline", date.fromisoformat(str(t["deadline"])[:10]))
            prio = c.selectbox("Priority", C.TASK_PRIORITIES, index=C.TASK_PRIORITIES.index(t["priority"]))
            status = d.selectbox("Status", C.TASK_STATUSES, index=C.TASK_STATUSES.index(t["status"]))
            evidence = st.text_input("Supporting evidence", t.get("evidence") or "")
            st.caption(f"Source: {t['source']} · Created: {str(t.get('created_at') or '')[:10]}")
            if st.form_submit_button("Save changes", type="primary"):
                try:
                    an.save_task({**t, "title": title, "description": desc, "campaign_id": by_name.get(camp), "owner": owner, "deadline": str(deadline),
                                  "priority": prio, "status": status, "evidence": evidence})
                    st.session_state.pop("task_pick", None)
                    ui.flash(f"Task '{title}' updated.")
                    st.rerun()
                except an.ValidationError as e:
                    st.error(str(e))
        a, b, c = st.columns([1, 1, 2])
        if a.button("Mark complete", disabled=t["status"] == "Completed", width="stretch"):
            an.save_task({**t, "status": "Completed"})
            st.session_state.pop("task_pick", None)
            ui.flash(f"Task '{t['title']}' marked complete.")
            st.rerun()
        sure = c.checkbox("Confirm delete", key=f"del_ok_{t['id']}")
        if b.button("Delete task", disabled=not sure, width="stretch"):
            an.delete_task(t["id"])
            st.session_state.pop("task_pick", None)
            ui.flash(f"Task '{t['title']}' deleted.", "info")
            st.rerun()
