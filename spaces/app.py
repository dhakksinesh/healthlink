
import os
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

import streamlit as st
import requests
import pandas as pd

load_dotenv()
try:
    API_BASE_URL = os.environ["API_BASE_URL"]
except KeyError:
    st.error("API_BASE_URL not set — add it to .env (e.g. http://localhost:8000/api/v1) and restart.")
    st.stop()

API_TIMEOUT = int(os.getenv("API_TIMEOUT", "300"))
HEALTH_TIMEOUT = int(os.getenv("HEALTH_TIMEOUT", "10"))
APPOINTMENT_TIMEOUT = int(os.getenv("APPOINTMENT_TIMEOUT", "30"))

st.set_page_config(page_title="HealthLink — Smart Health", page_icon="🏥", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
h1,h2,h3 { font-family: 'Plus Jakarta Sans', sans-serif; letter-spacing: -0.02em; }

/* kill sidebar only — keep header/toolbar (Stop/Rerun) visible */
section[data-testid="stSidebar"]{display:none !important;}
div[data-testid="collapsedControl"]{display:none !important;}
header[data-testid="stHeader"] { background: transparent !important; }
.block-container { padding-top: 2.6rem !important; max-width: 1160px; overflow: visible !important; }

/* top nav — not sticky, clear breathing room so logo not clipped */
.topnav {
  background: #fff; border:1px solid #e2e8f0; border-radius:14px;
  margin: 0.6rem 0 1.4rem; padding: 0.9rem 1.15rem;
  display:flex; align-items:center; justify-content:space-between; gap:1rem;
  box-shadow: 0 4px 14px rgba(15,23,42,0.06); position: relative; z-index: 2;
}
.topnav .brand { display:flex; align-items:center; gap:0.7rem; font-weight:800; color:#0f172a; font-size:1.08rem; }
.topnav .brand i { width:36px; height:36px; border-radius:999px; display:inline-flex; align-items:center; justify-content:center;
  background: linear-gradient(135deg,#0e7490,#4f46e5); color:#fff; box-shadow:0 4px 12px rgba(79,70,229,0.28); }
.topnav .links { display:flex; gap:0.45rem; flex-wrap:wrap; }
.topnav .links a { font-size:0.84rem; font-weight:600; color:#334155; text-decoration:none; padding:0.4rem 0.75rem; border-radius:999px; border:1px solid #e2e8f0; background:#fff; }
.topnav .links a:hover { background:#f8fafc; border-color:#cbd5e1; }

/* hero — generous padding, not cramped */
.hero {
  background: linear-gradient(135deg,#0e7490 0%,#0891b2 38%,#4f46e5 100%);
  color:#fff; padding: 2.8rem 2.4rem 2.2rem; border-radius: 24px;
  box-shadow: 0 16px 40px rgba(14,116,144,0.28); margin-bottom: 2rem;
}
.hero h1 { font-size: 2.85rem; margin:0; color:#fff; font-weight:800; line-height:1.08; }
.hero p { opacity:0.93; font-size:1.08rem; margin-top:0.6rem; max-width:62ch; line-height:1.6; }
.hero .pill { display:inline-block; background:rgba(255,255,255,0.16); backdrop-filter:blur(6px);
  border:1px solid rgba(255,255,255,0.28); color:#fff; padding:0.36rem 0.75rem; border-radius:999px;
  font-size:0.78rem; font-weight:600; margin:0.7rem 0.4rem 0 0; }

/* step strip — airy cards with icon */
.step-card {
  background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:1.3rem 1.2rem;
  box-shadow:0 4px 18px rgba(15,23,42,0.06); text-align:center; height:100%;
}
.step-card .icon { width:48px; height:48px; border-radius:14px; display:inline-flex; align-items:center; justify-content:center;
  font-size:1.45rem; margin-bottom:0.6rem; }
.step-card b { display:block; color:#0f172a; font-size:0.98rem; margin-bottom:0.15rem; }
.step-card span { color:#64748b; font-size:0.86rem; line-height:1.5; }

/* generic cards — breathing room */
.card { background:#fff; border:1px solid #e2e8f0; border-radius:18px; padding:1.4rem 1.4rem; box-shadow:0 4px 18px rgba(15,23,42,0.06); margin-bottom:1rem; }
.doctor-card { background: linear-gradient(180deg,#fff 0%,#f8fafc 100%); border:1px solid #e2e8f0; border-radius:18px; padding:1.3rem 1.4rem; box-shadow:0 4px 18px rgba(15,23,42,0.06); margin:0.8rem 0; position:relative; overflow:hidden; }
.doctor-card:hover { transform:translateY(-1px); box-shadow:0 10px 28px rgba(15,23,42,0.10); }
.doctor-card:before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background: linear-gradient(180deg,#0e7490,#4f46e5); }
.avatar { width:46px; height:46px; border-radius:999px; display:inline-flex; align-items:center; justify-content:center; background: linear-gradient(135deg,#0e7490,#4f46e5); color:#fff; font-weight:700; font-size:0.95rem; box-shadow:0 4px 10px rgba(79,70,229,0.28); }
.badge { display:inline-block; padding:0.24rem 0.58rem; border-radius:999px; font-size:0.72rem; font-weight:600; border:1px solid transparent; }
.badge-specialty{background:#eef2ff;color:#4338ca;border-color:#c7d2fe;}
.badge-rating{background:#fef9c3;color:#854d0e;border-color:#fde68a;}
.badge-consult{background:#ecfeff;color:#155e75;border-color:#a5f3fc;}
.chip { display:inline-flex; align-items:center; gap:0.35rem; background:#f1f5f9; color:#0f172a; border:1px solid #e2e8f0; border-radius:999px; padding:0.36rem 0.7rem; font-size:0.82rem; font-weight:500; margin:0.2rem 0.3rem 0.2rem 0; }
.pill-urgency { display:inline-flex; align-items:center; gap:0.35rem; padding:0.34rem 0.75rem; border-radius:999px; font-size:0.78rem; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; border:1px solid transparent; }
.urgency-low{background:#dcfce7;color:#166534;border-color:#bbf7d0;}
.urgency-medium{background:#fef9c3;color:#854d0e;border-color:#fde68a;}
.urgency-high{background:#fee2e2;color:#991b1b;border-color:#fecaca;}
.stButton>button{border-radius:999px !important; font-weight:600 !important; box-shadow:0 4px 14px rgba(14,116,144,0.18) !important;}
/* secondary buttons (Wake API, Load doctors) — match top-bar pills */
div[data-testid="stButton"] button[kind="secondary"]{
  background:#fff !important; border:1px solid #e2e8f0 !important; border-radius:999px !important;
  color:#334155 !important; font-weight:600 !important; font-size:0.84rem !important;
  padding:0.4rem 0.75rem !important; box-shadow:none !important;
}
div[data-testid="stButton"] button[kind="secondary"]:hover{
  background:#f8fafc !important; border-color:#cbd5e1 !important; transform:none !important;
}
div[data-baseweb="tab-list"]{gap:0.3rem; margin-top:0.6rem;}
button[data-baseweb="tab"]{border-radius:999px; font-weight:600;}
button[data-baseweb="tab"][aria-selected="true"]{background:#0e7490; color:#fff;}
hr { margin: 1.8rem 0 !important; border-color:#e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

def check_api_health() -> bool:
    try:
        return requests.get(f"{API_BASE_URL}/health", timeout=HEALTH_TIMEOUT).status_code == 200
    except requests.RequestException:
        return False

def get_urgency_pill(lvl: str) -> str:
    lvl = (lvl or "medium").lower()
    klass = {"emergency":"urgency-high","high":"urgency-high","medium":"urgency-medium","low":"urgency-low"}.get(lvl,"urgency-medium")
    icon = {"emergency":"🚨","high":"⚠️","medium":"●","low":"✓"}.get(lvl,"●")
    return f"<span class='pill-urgency {klass}'>{icon} {lvl}</span>"

def display_symptom_analysis(data: dict):
    st.markdown(f"<div class='card' style='display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:1rem'><div><div style='font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;font-weight:600'>Primary complaint</div><div style='font-size:1.18rem;font-weight:700;color:#0f172a;margin-top:0.15rem'>{data['primary_complaint']}</div></div>{get_urgency_pill(data['urgency_level'])}</div>", unsafe_allow_html=True)
    chips = "".join([f"<span class='chip'><b>{s['name']}</b> {s['severity']}{(' · '+s['duration']) if s.get('duration') else ''}</span>" for s in data.get("symptoms",[])])
    if chips: st.markdown(f"<div style='margin:1rem 0 0.4rem'>{chips}</div>", unsafe_allow_html=True)
    if data.get("additional_context"): st.info(f"ℹ️ {data['additional_context']}")

def display_doctors(data: dict):
    c1,c2 = st.columns([1.35,0.65])
    with c1: st.markdown(f"<div style='font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;color:#64748b;font-weight:600'>Specialty rationale</div><div style='color:#334155;line-height:1.7;margin-top:0.3rem'>{data.get('specialty_rationale','')}</div>", unsafe_allow_html=True)
    with c2: st.metric("Match confidence", f"{data.get('match_score',0):.0%}")
    if not data.get("recommended_doctors"):
        st.warning("No doctors available.")
        return
    cols = st.columns(min(3, len(data["recommended_doctors"])))
    for i,d in enumerate(data["recommended_doctors"]):
        initials = "".join([p[0] for p in d['name'].split()[:2]]).upper()
        with cols[i % len(cols)]:
            st.markdown(f"""<div class='doctor-card'><div style='display:flex;gap:0.85rem;align-items:center;margin-bottom:0.6rem'><span class='avatar'>{initials}</span><div><div style='font-weight:700;color:#0f172a;line-height:1.15'>Dr. {d['name']}</div><div style='font-size:0.82rem;color:#64748b'>{d['specialty']}</div></div></div><div style='display:flex;gap:0.35rem;flex-wrap:wrap;margin-bottom:0.6rem'><span class='badge badge-rating'>⭐ {d['rating']}/5.0</span><span class='badge badge-specialty'>{d['specialty']}</span><span class='badge badge-consult'>{d.get('consultation_type') or 'In-person · Telemedicine'}</span></div><div style='font-size:0.86rem;color:#334155;line-height:1.6'><div>🕒 {d['experience_years']} yrs · {d['availability']}</div><div>📍 {d.get('location','N/A')}</div></div></div>""", unsafe_allow_html=True)

def display_scheduling(data: dict):
    if data.get("scheduling_notes"): st.info(data["scheduling_notes"])
    s = data.get("recommended_slot")
    if s:
        st.markdown(f"""<div class='card' style='background:linear-gradient(135deg,#ecfeff 0%,#eef2ff 100%);border-color:#a5f3fc'><div style='font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;color:#0e7490;font-weight:700'>Recommended appointment</div><div style='font-size:1.22rem;font-weight:800;color:#0f172a;margin-top:0.2rem'>{s['doctor_name']} · {s['date']} at {s['time']}</div><div style='color:#475569;font-size:0.88rem;margin-top:0.2rem'>{s.get('duration_minutes',30)} min · {s['slot_id']}</div></div>""", unsafe_allow_html=True)
    if data.get("available_slots"):
        st.markdown("<div style='font-weight:600;color:#0f172a;margin:1rem 0 0.4rem'>Other available slots</div>", unsafe_allow_html=True)
        by_doc = {}
        for x in data["available_slots"][:12]: by_doc.setdefault(x["doctor_name"], []).append(x)
        for doc, slots in by_doc.items():
            with st.expander(f"📅 {doc} — {len(slots)} slots"):
                st.markdown("".join([f"<span class='chip'>{x['date']} · {x['time']}</span>" for x in slots[:6]]), unsafe_allow_html=True)

def display_patient_summary(data: dict):
    st.markdown(f"<div class='card'><div style='font-size:0.76rem;letter-spacing:0.08em;text-transform:uppercase;color:#0e7490;font-weight:700'>Assessment</div><div style='color:#0f172a;line-height:1.75;margin-top:0.3rem'>{data['summary']}</div></div>", unsafe_allow_html=True)
    c1,c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("<div style='font-weight:700;color:#0f172a;margin:0.9rem 0 0.4rem'>Key findings</div>", unsafe_allow_html=True)
        for f in data.get("key_findings",[]): st.markdown(f"<div class='chip' style='background:#fff'>🔍 {f}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='font-weight:700;color:#0f172a;margin:0.9rem 0 0.4rem'>Next steps</div>", unsafe_allow_html=True)
        for a in data.get("recommended_actions",[]): st.markdown(f"<div class='chip' style='background:#ecfdf5;border-color:#a7f3d0'>✓ {a}</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='margin-top:1rem'>Overall urgency: {get_urgency_pill(data.get('urgency_assessment',''))}</div>", unsafe_allow_html=True)
    st.warning(f"⚠️ {data.get('disclaimer','')}")

def display_doctor_summary(data: dict):
    st.markdown(f"<div class='card'><b style='color:#0e7490'>Patient overview</b><div style='color:#334155;line-height:1.7;margin-top:0.3rem'>{data.get('patient_overview','')}</div></div>", unsafe_allow_html=True)
    a,b,c = st.columns(3, gap="large")
    with a:
        st.markdown("**Presenting symptoms**")
        for s in data.get("presenting_symptoms",[]): st.markdown(f"• {s}")
    with b:
        st.markdown("**Key points**")
        for p in data.get("key_points",[]): st.markdown(f"• {p}")
    with c:
        st.markdown("**Follow-ups**")
        for f in data.get("suggested_follow_ups",[]): st.markdown(f"• {f}")

def book_appointment(slot: dict, user_id: str) -> requests.Response:
    if not slot.get("slot_id"): raise ValueError("Invalid slot")
    return requests.post(f"{API_BASE_URL}/appointments", json={"user_id": user_id or "guest", "slot_id": slot["slot_id"]}, timeout=APPOINTMENT_TIMEOUT)

def display_booking(result: dict, user_id: str):
    slot = result["scheduling_options"].get("recommended_slot")
    if not slot: return
    st.divider()
    st.subheader("✅ Book your appointment")
    st.write(f"**{slot['doctor_name']}** on **{slot['date']}** at **{slot['time']}**")
    if st.button("🕐 Book this appointment", key=f"book_{slot['slot_id']}", type="primary", use_container_width=True):
        with st.spinner("Booking..."):
            resp = book_appointment(slot, user_id)
            if resp.status_code == 201:
                j = resp.json()
                st.success(f"Booked — {j['status']}")
                if j.get("reminder"): st.info(f"📩 {j['reminder']}")
            else: st.error(f"Booking failed: {resp.json().get('detail', resp.text)}")

def run_assessment(user_input: str, user_id: str, profile: dict, preferred_date: str, answers: list | None = None) -> requests.Response:
    return requests.post(f"{API_BASE_URL}/assess", json={"user_input": user_input, "user_id": user_id or None, "patient_profile": profile or None, "preferred_date": preferred_date or None, "clarifying_answers": answers or None}, timeout=API_TIMEOUT)

def main():
    _base = API_BASE_URL.rsplit("/api", 1)[0]
    st.markdown(f"""<div class='topnav'><div class='brand'><i>🏥</i> HealthLink</div><div class='links'><a href="{_base}/docs" target="_blank">Swagger</a><a href="{_base}/redoc" target="_blank">ReDoc</a><a href="{_base}/health" target="_blank">Health</a><a href="https://smith.langchain.com" target="_blank">LangSmith</a><a href="https://app.pinecone.io" target="_blank">Pinecone</a><a href="#" onclick="fetch('{_base}/health').then(r=>r.json()).then(j=>alert('API awake — '+j.status)).catch(e=>alert('Wake failed: '+e)); return false;">Wake API</a></div></div>""", unsafe_allow_html=True)
    st.markdown("<div class='hero'><h1>Smart Health Management</h1><p>Plain-language symptoms → right specialist → appointment → patient & doctor summaries. Multi-agent, RAG-powered, LangGraph-orchestrated.</p><div style='margin-top:0.9rem'><span class='pill'>● Symptom → Doctor → Scheduling → Summary</span><span class='pill'>↗ LangGraph · Pinecone · OpenRouter</span></div></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    a,b,c,d = st.columns(4, gap="large")
    with a: st.markdown("<div class='step-card'><div class='icon' style='background:#ecfeff;color:#0e7490'>💬</div><b>Describe</b><span>Free-text symptoms</span></div>", unsafe_allow_html=True)
    with b: st.markdown("<div class='step-card'><div class='icon' style='background:#fef9c3;color:#854d0e'>❓</div><b>Clarify</b><span>Follow-ups if needed</span></div>", unsafe_allow_html=True)
    with c: st.markdown("<div class='step-card'><div class='icon' style='background:#eef2ff;color:#4338ca'>👨‍⚕️</div><b>Match</b><span>Specialist + ranked doctors</span></div>", unsafe_allow_html=True)
    with d: st.markdown("<div class='step-card'><div class='icon' style='background:#dcfce7;color:#166534'>📅</div><b>Book</b><span>Slots + reminders</span></div>", unsafe_allow_html=True)

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    if not check_api_health():
        st.error(f"⚠️ Cannot reach API at `{API_BASE_URL}` — is `uvicorn app.main:app` running?")
        return

    with st.expander("🔗 Dashboards & SQLite Viewer", expanded=False):
        c1,c2 = st.columns([1,1], gap="large")
        with c1:
            st.markdown(f"**API** — [Swagger]({_base}/docs) · [ReDoc]({_base}/redoc) · [Health]({_base}/health)")
            st.markdown("**Observability** — [LangSmith](https://smith.langchain.com) `healthlink` · [Pinecone](https://app.pinecone.io)")
        with c2:
            if st.button("Load doctors (100)", key="view_doctors2", use_container_width=True):
                try:
                    r = requests.get(f"{API_BASE_URL}/doctors", timeout=HEALTH_TIMEOUT)
                    if r.status_code == 200:
                        df = pd.DataFrame(r.json())
                        st.dataframe(df, use_container_width=True, height=300)
                    else: st.error(r.text)
                except Exception as e: st.error(str(e))
            uid2 = st.text_input("user_id for appointments", key="view_uid2", placeholder="u1")
            if st.button("Load appointments", key="view_appts2", use_container_width=True):
                if not (uid2 or st.session_state.get("user_id","")): st.warning("Enter user_id or run an assessment")
                else:
                    try:
                        r = requests.get(f"{API_BASE_URL}/appointments", params={"user_id": uid2 or st.session_state.get("user_id","")}, timeout=APPOINTMENT_TIMEOUT)
                        if r.status_code == 200:
                            df = pd.DataFrame(r.json())
                            st.dataframe(df, use_container_width=True) if not df.empty else st.info("No rows")
                        else: st.error(r.text)
                    except Exception as e: st.error(str(e))

    st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
    st.markdown("### Tell us about your health concern")
    st.caption("All fields except symptoms are optional — assessment works with just a description.")
    with st.form("assessment_form"):
        user_input = st.text_area("Describe your symptoms", placeholder="Example: I have had a severe headache for 3 days, with fever and sensitivity to light...", height=150)
        st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="large")
        with c1:
            user_id = st.text_input("Your ID", placeholder="user123")
            age = st.number_input("Age", min_value=0, max_value=130, value=0, step=1)
            known_conditions = st.text_input("Known conditions", placeholder="e.g. diabetes, hypertension")
        with c2:
            use_date = st.checkbox("Set preferred date", value=False)
            preferred_date = st.date_input("Preferred date", value=datetime.now() + timedelta(days=1)) if use_date else None
            gender = st.selectbox("Gender", ["", "Female", "Male", "Other"])
            time_pref = st.selectbox("Preferred time", ["", "Morning", "Afternoon", "Evening"])
            consult_type = st.selectbox("Consultation type", ["", "In-person", "Telemedicine", "Either"])
        st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
        submitted = st.form_submit_button("✨ Get Assessment", type="primary", use_container_width=True)

    if submitted:
        if len(user_input.strip()) < 10:
            st.error("Please provide more details (at least 10 characters)")
            return
        profile = {"age": age if age>0 else None, "gender": gender or None, "known_conditions": known_conditions.strip() or None, "preferred_time_of_day": time_pref or None, "consultation_type": consult_type or None}
        preferred_date_str = preferred_date.strftime("%Y-%m-%d") if use_date and preferred_date else None
        with st.spinner("Analyzing — this may take a moment..."):
            try:
                response = run_assessment(user_input, user_id, profile, preferred_date_str)
                if response.status_code == 200:
                    st.session_state["result"] = response.json()
                    st.session_state["user_id"] = user_id
                    st.session_state["profile"] = profile
                    st.session_state["preferred_date"] = preferred_date_str
                    st.session_state["user_input"] = user_input
                    st.session_state["clarifying_done"] = False
                else: st.error(f"Error: {response.json().get('detail','Unknown error')}")
            except requests.exceptions.Timeout: st.error("Request timed out — try a faster model (e.g. `z-ai/glm-5.2:free`).")
            except requests.exceptions.ConnectionError: st.error("Cannot connect to API. Is it running on port 8000?")
            except Exception as e: st.error(str(e))

    result = st.session_state.get("result")
    if not result:
        st.divider()
        st.caption("⚠️ Not a substitute for professional medical advice.")
        return
    clarifying_questions = result.get("symptom_analysis", {}).get("clarifying_questions") or []
    if clarifying_questions and not st.session_state.get("clarifying_done"):
        st.divider()
        st.markdown("### ❓ A few quick questions")
        st.info("To be more accurate, please answer:")
        answers = []
        with st.form("clarifying_form"):
            for i, q in enumerate(clarifying_questions): answers.append(st.text_input(q, key=f"clarify_{i}"))
            submit_answers = st.form_submit_button("Submit answers", type="primary", use_container_width=True)
        if submit_answers:
            answers = [a for a in answers if a.strip()]
            with st.spinner("Re-evaluating with your answers..."):
                response = run_assessment(st.session_state.get("user_input",""), st.session_state.get("user_id",""), st.session_state.get("profile"), st.session_state.get("preferred_date"), answers)
                if response.status_code == 200:
                    st.session_state["result"] = response.json()
                    st.session_state["clarifying_done"] = True
                    st.rerun()
                else: st.error(f"Error: {response.json().get('detail','Unknown error')}")
        return

    st.divider()
    st.success("✅ Assessment completed")
    st.caption(f"Request `{result['request_id']}` · trace in LangSmith" if result.get("metadata",{}).get("trace") else "")
    st.markdown("<div style='height:0.4rem'></div>", unsafe_allow_html=True)
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Symptoms","👨‍⚕️ Doctors","📅 Scheduling","📝 Patient Summary","🧑‍⚕️ Doctor Summary"])
    with tab1: display_symptom_analysis(result["symptom_analysis"])
    with tab2: display_doctors(result["doctor_recommendations"])
    with tab3:
        display_scheduling(result["scheduling_options"])
        display_booking(result, st.session_state.get("user_id",""))
    with tab4: display_patient_summary(result["health_summary"])
    with tab5: display_doctor_summary(result["doctor_summary"])
    st.divider()
    c1,c2 = st.columns(2, gap="large")
    with c1: st.download_button("📥 Download assessment JSON", data=json.dumps(result, indent=2), file_name=f"health_assessment_{result['request_id']}.json", mime="application/json", use_container_width=True)
    with c2:
        if st.button("📅 My appointments", use_container_width=True):
            uid = st.session_state.get("user_id","")
            resp = requests.get(f"{API_BASE_URL}/appointments", params={"user_id": uid}, timeout=APPOINTMENT_TIMEOUT)
            if resp.status_code == 200:
                appts = resp.json()
                if not appts: st.info("No appointments yet.")
                for a in appts:
                    st.write(f"• **{a['doctor_name']}** — {a['appointment_date']} at {a['appointment_time']} ({a['status']})")
                    if a["status"] == "scheduled":
                        if st.button("Cancel", key=f"cancel_{a['id']}"):
                            r2 = requests.patch(f"{API_BASE_URL}/appointments/{a['id']}", params={"status":"cancelled"}, timeout=APPOINTMENT_TIMEOUT)
                            st.write("Cancelled." if r2.status_code==200 else f"Failed: {r2.text}")
            else: st.error(resp.text)
    st.caption("⚠️ Not a substitute for professional medical advice.")

if __name__ == "__main__":
    main()
