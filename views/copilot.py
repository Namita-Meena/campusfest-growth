"""Page 5 - AI Growth Copilot: grounded analysis, recommendations and task drafts."""
import json

import streamlit as st

from core import ai_copilot as ai
from core import analytics as an
from core import config as C
from core import ui

W = ui.week()
ui.header("AI Growth Copilot", "Ask about performance, bottlenecks, budgets, history or next actions",
          f"Week {W} · Answers are computed from the live database and the original 2025 dataset through deterministic Python tools. "
          "The copilot cannot change data: tasks it drafts are saved only when you approve them.")
ui.show_flashes()

st.session_state.setdefault("chat", [])
chat = st.session_state["chat"]

if not ai.is_configured():
    st.warning("The AI model is not connected yet: GEMINI_API_KEY is missing from the app secrets. "
               "Every other page works without it. The data tools the copilot uses can be inspected below.")
    with st.expander("Preview the copilot's data tools (no AI model involved)"):
        box = ai.Toolbox(W)
        name = st.selectbox("Tool", [n for n in ai.TOOL_NAMES if n not in ("draft_task", "compare_campaigns", "two_proportion_test", "query_historical_data")])
        st.json(ai.run_tool(box, name, {}), expanded=1)

SUGGESTIONS = ["Are we on track for the base target? What is the biggest risk?",
               "Why is Club Contingent League performing the way it is, and what should we do?",
               "How much money can we actually reallocate right now?",
               "In 2025, which channel had the worst cost per verified attendee?",
               "What is the average age of festival attendees?"]

for i, m in enumerate(chat):
    with st.chat_message(m["role"], avatar=":material/person:" if m["role"] == "user" else ":material/smart_toy:"):
        st.markdown(m["content"])
        if m.get("calls"):
            with st.expander(f"Data retrieved for this answer ({len(m['calls'])} tool call{'s' if len(m['calls']) != 1 else ''})"):
                for c in m["calls"]:
                    st.markdown(f"- `{c['tool']}` {json.dumps(c['args']) if c['args'] else ''} {'✓' if c['ok'] else '— returned an error'}")
                if m.get("model"):
                    st.caption(f"Model: {m['model']} · simulated week {m.get('week')}")

pending = st.session_state.get("pending_task")
if pending:
    with st.container(border=True):
        st.markdown("#### Task draft awaiting your approval")
        st.caption("Proposed by the AI copilot. Nothing has been saved. Edit if needed, then approve or reject.")
        with st.form("approve_task"):
            a, b = st.columns(2)
            title = a.text_input("Title", pending["title"])
            names = {c["id"]: c["name"] for c in an.build_context(W)["campaigns"]}
            options = ["General"] + list(names.values())
            cur = names.get(pending.get("campaign_id"), "General")
            camp = b.selectbox("Campaign", options, index=options.index(cur))
            desc = st.text_area("Description", pending.get("description") or "", height=90)
            a, b, c = st.columns(3)
            owners = sorted(set(C.OWNERS + [pending["owner"]]))
            owner = a.selectbox("Owner", owners, index=owners.index(pending["owner"]))
            deadline = b.text_input("Deadline (YYYY-MM-DD)", pending["deadline"])
            prio = c.selectbox("Priority", C.TASK_PRIORITIES, index=C.TASK_PRIORITIES.index(pending["priority"]))
            evidence = st.text_area("Supporting evidence", pending.get("evidence") or "", height=70)
            c1, c2 = st.columns(2)
            ok = c1.form_submit_button("Approve and save task", type="primary", width="stretch")
            no = c2.form_submit_button("Reject draft", width="stretch")
        if ok:
            try:
                cid = next((k for k, v in names.items() if v == camp), None)
                an.save_task(dict(title=title, description=desc, campaign_id=cid, owner=owner, deadline=deadline, priority=prio, status="To Do",
                                  evidence=evidence, source="AI-generated"), is_new=True)
                st.session_state.pop("pending_task", None)
                chat.append({"role": "assistant", "content": f"Task **{title}** was approved and saved. It is now in the Task Manager (owner {owner}, deadline {deadline})."})
                st.rerun()
            except an.ValidationError as e:
                st.error(str(e))
        if no:
            st.session_state.pop("pending_task", None)
            chat.append({"role": "assistant", "content": "The task draft was rejected. Nothing was saved."})
            st.rerun()

if not chat:
    st.caption("Try one of these, or type your own question:")
    for n_, q in enumerate(SUGGESTIONS):
        if st.button(q, key=f"sg_{n_}", disabled=not ai.is_configured()):
            st.session_state["queued_question"] = q
            st.rerun()

question = st.chat_input("Ask the copilot, e.g. 'Why is Club Contingent League underperforming?'", disabled=not ai.is_configured())
question = question or st.session_state.pop("queued_question", None)

if question:
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(question)
    with st.chat_message("assistant", avatar=":material/smart_toy:"):
        with st.spinner("Retrieving current data and analysing…"):
            res = ai.ask(question, [{"role": m["role"], "content": m["content"]} for m in chat], W)
        chat.append({"role": "user", "content": question})
        if res["error"]:
            st.error(res["error"])
            chat.append({"role": "assistant", "content": f"_{res['error']}_", "calls": res["calls"]})
        else:
            chat.append({"role": "assistant", "content": res["text"], "calls": res["calls"], "model": res["model"], "week": W})
            if res["pending_task"]:
                st.session_state["pending_task"] = res["pending_task"]
    st.rerun()

if chat:
    if st.button("Clear conversation"):
        st.session_state["chat"] = []
        st.session_state.pop("pending_task", None)
        st.rerun()
