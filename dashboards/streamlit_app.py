"""Interactive healthcare operations dashboard.

Run from the repository root with:
    streamlit run dashboards/streamlit_app.py

The app reads generated Parquet/CSV batches from data/raw when available and
uses a deterministic demo dataset otherwise, so the UI can be explored before
the full data-generation pipeline has been run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"
MAX_ROWS_PER_TABLE = 30_000
PALETTE = {"ink": "#12211f", "teal": "#087f73", "mint": "#d9f2e8", "coral": "#e56855", "gold": "#c98b2e", "blue": "#24729a", "lime": "#98b83f", "paper": "#f4f7f1", "muted": "#667672", "line": "#d7e3dc"}

st.set_page_config(page_title="Northstar Health | Command Center", page_icon="+", layout="wide", initial_sidebar_state="expanded")


def inject_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink:#12211f; --teal:#087f73; --mint:#d9f2e8; --paper:#f4f7f1; --line:#d7e3dc; --coral:#e56855; --blue:#24729a; }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    .stApp { background: radial-gradient(circle at 96% 0%, #dff4eb 0, var(--paper) 32rem); }
    [data-testid="stSidebar"] { background: linear-gradient(165deg, #112d2a 0%, #174740 65%, #1b5148 100%); }
    [data-testid="stSidebar"] * { color: #eef8f2 !important; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: 0; }
    h1 { font-size: 2.6rem !important; margin-bottom: .2rem; color: #12211f; }
    h2 { font-size: 1.35rem !important; margin-top: 1.25rem; }
    .eyebrow { color: var(--teal); font-size: .75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .subhead { color: #64736e; margin: 0 0 1.5rem; }
    .kpi { background:rgba(255,255,255,.86); border:1px solid var(--line); border-radius:8px; padding:1rem 1.1rem; min-height:122px; box-shadow:0 8px 24px rgba(18,33,31,.06); }
    .kpi-label { color:#64736e; font-size:.76rem; text-transform:uppercase; letter-spacing:.06em; font-weight:700; }
    .kpi-value { font-family:'Space Grotesk'; font-size:1.75rem; font-weight:700; margin:.45rem 0 .15rem; }
    .kpi-note { color:#64736e; font-size:.78rem; }
    .good { color:#087f73; } .watch { color:#b27018; } .risk { color:#c34e3d; } .neutral { color:#24729a; }
    .section-rule { border-top:1px solid var(--line); margin:1.2rem 0; }
    .report-meta { color:#64736e; font-size:.76rem; padding:.45rem 0 .8rem; border-bottom:1px solid var(--line); }
    .insight { border-left:4px solid var(--teal); background:#eaf5f0; padding:.75rem .9rem; color:#23483d; font-size:.86rem; }
    .small-note { color:#64736e; font-size:.74rem; }
    .signal-card { background:#12211f; color:#effaf5; border-radius:8px; padding:1rem 1.1rem; min-height:104px; }
    .signal-card .label { color:#a8d9ca; font-size:.72rem; text-transform:uppercase; letter-spacing:.08em; font-weight:700; }
    .signal-card .value { font-family:'Space Grotesk'; font-size:1.8rem; font-weight:700; margin:.35rem 0; }
    .signal-card .note { color:#c5dfd5; font-size:.78rem; }
    .stButton > button, .stDownloadButton > button { border-radius:6px; border:1px solid #b9d7ce; }
    [data-testid="stMetricValue"] { font-family:'Space Grotesk', sans-serif; }
    </style>
    """, unsafe_allow_html=True)


def demo_data() -> dict[str, pd.DataFrame]:
    """Create compact, deterministic data for a useful no-setup demo."""
    rng = np.random.default_rng(42)
    n = 7_500
    dates = pd.date_range("2023-01-01", "2024-12-31", periods=n)
    hospitals = np.array([f"H-{i:02d}" for i in range(1, 9)])
    wards = np.array(["Medical", "Surgical", "ICU", "CCU", "Maternity", "Observation"])
    admissions = pd.DataFrame({
        "admission_id": [f"ADM{i:07d}" for i in range(n)], "patient_id": [f"P{i % 2200:07d}" for i in range(n)], "hospital_id": rng.choice(hospitals, n), "admit_date": dates,
        "discharge_date": dates + pd.to_timedelta(rng.integers(1, 11, n), unit="D"), "ward": rng.choice(wards, n, p=[.32, .2, .13, .08, .1, .17]),
        "admission_type": rng.choice(["Emergency", "Elective", "Urgent", "Maternity"], n, p=[.4, .32, .18, .1]), "discharge_status": rng.choice(["Discharged Home", "Transferred to SNF", "Expired", "Still Admitted"], n, p=[.75, .14, .03, .08]),
        "drg_code": rng.choice(["871", "470", "291", "194", "392", "683"], n), "actual_cost": rng.lognormal(9.5, .75, n).round(2), "readmission_within_30d": rng.random(n) < .145, "icu_hours": rng.integers(0, 200, n),
    })
    admissions["length_of_stay"] = (admissions["discharge_date"] - admissions["admit_date"]).dt.days.clip(0, 90)
    billing = pd.DataFrame({
        "invoice_id": [f"INV{i:07d}" for i in range(n)], "hospital_id": rng.choice(hospitals, n), "service_date": dates, "service_type": rng.choice(["Room & Board", "Surgery", "Lab", "ER", "ICU", "Imaging"], n),
        "gross_amount": rng.lognormal(7.3, 1.05, n).round(2), "insurance_adjustment": rng.uniform(0.1, .35, n), "insurance_paid": rng.lognormal(6.8, 1.0, n).round(2), "patient_paid": rng.lognormal(5.4, 1.0, n).round(2), "amount_due": rng.lognormal(5.3, 1.0, n).round(2),
        "payment_status": rng.choice(["Paid", "Pending", "Partial", "Written Off"], n, p=[.64, .18, .12, .06]), "payment_method": rng.choice(["Insurance", "Medicare", "Medicaid", "Self-Pay", "Charity Care"], n, p=[.48, .18, .12, .16, .06]), "bad_debt_flag": rng.random(n) < .06,
    })
    claims = pd.DataFrame({
        "claim_id": [f"CLM{i:07d}" for i in range(n)], "hospital_id": rng.choice(hospitals, n), "submission_date": dates, "insurance_provider": rng.choice(["UnitedHealth", "Aetna", "BCBS", "Medicare", "Medicaid"], n),
        "claim_amount": rng.lognormal(7.6, 1.1, n).round(2), "approved_amount": rng.lognormal(7.2, 1.0, n).round(2), "claim_status": rng.choice(["Approved", "Denied", "Partially Approved", "Pending", "Paid"], n, p=[.5, .14, .12, .1, .14]), "denial_reason": rng.choice(["Coding error", "Prior authorization required", "Eligibility issue", "Not medically necessary"], n), "fraud_flag": rng.random(n) < .015,
    })
    emergency = pd.DataFrame({
        "visit_id": [f"ERV{i:07d}" for i in range(n)], "hospital_id": rng.choice(hospitals, n), "arrival_datetime": dates, "triage_level": rng.choice([1, 2, 3, 4, 5], n, p=[.05, .15, .45, .25, .1]), "chief_complaint": rng.choice(["Chest pain", "Shortness of breath", "Fall/Injury", "Fever", "Headache", "Abdominal pain"], n), "door_to_doc_minutes": np.clip(rng.normal(26, 13, n), 2, 120).round(), "total_ed_minutes": np.clip(rng.normal(180, 70, n), 30, 600).round(), "disposition": rng.choice(["Discharged", "Admitted", "Transferred", "LWBS", "AMA"], n, p=[.62, .24, .06, .04, .04]), "return_within_72h": rng.random(n) < .03,
    })
    beds = pd.DataFrame({"hospital_id": rng.choice(hospitals, n), "ward": rng.choice(wards, n), "occupancy_status": rng.choice(["Occupied", "Available", "Housekeeping", "Maintenance"], n, p=[.72, .16, .08, .04])})
    feedback = pd.DataFrame({"hospital_id": rng.choice(hospitals, n), "survey_date": dates, "overall_rating": np.clip(rng.normal(8.25, 1.8, n), 0, 10).round(), "likelihood_recommend": np.clip(rng.normal(8.0, 2, n), 0, 10).round(), "sentiment_score": rng.normal(.35, .5, n).clip(-1, 1)})
    notes = pd.DataFrame({
        "note_id": ["NOTE-DEMO-001", "NOTE-DEMO-002", "NOTE-DEMO-003"],
        "patient_id": ["P0000001", "P0000002", "P0000003"],
        "hospital_id": ["H-01", "H-02", "H-03"],
        "note_datetime": pd.to_datetime(["2024-06-14", "2024-07-08", "2024-08-21"]),
        "note_type": ["Admission H&P", "Progress Note", "Discharge Summary"],
        "clinical_text": [
            "CHIEF COMPLAINT: Chest pain and shortness of breath. HISTORY OF PRESENT ILLNESS: Patient with type 2 diabetes, hypertension, and hyperlipidemia reports progressive chest discomfort. Troponin elevated. Assessment: rule out acute coronary syndrome. Plan: serial troponins and cardiology consult.",
            "PROGRESS NOTE: Patient with COPD and chronic kidney disease reports worsening cough and fatigue. Creatinine elevated. Denies chest pain. Plan: continue antibiotics, monitor oxygenation, and repeat labs.",
            "DISCHARGE SUMMARY: Patient treated for pneumonia and heart failure with improvement. Medication non-compliance was discussed. Follow-up with primary care and cardiology in two weeks.",
        ],
    })
    return {"admissions": admissions, "billing": billing, "insurance_claims": claims, "emergency_visits": emergency, "bed_utilization": beds, "patient_feedback": feedback, "clinical_notes": notes}


@st.cache_data(show_spinner=False)
def load_table(table: str, max_rows: int = 30_000) -> tuple[pd.DataFrame, str]:
    table_dir = DATA_DIR / table
    candidates = sorted(table_dir.glob("*.parquet")) if table_dir.exists() else []
    if not candidates:
        candidates = sorted(table_dir.glob("*.csv")) if table_dir.exists() else []
    if not candidates:
        candidates = [path for path in [DATA_DIR / f"{table}.parquet", DATA_DIR / f"{table}.csv"] if path.exists()]
    frames: list[pd.DataFrame] = []
    for path in candidates:
        remaining = max_rows - sum(len(frame) for frame in frames)
        if remaining <= 0:
            break
        frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, nrows=remaining)
        frames.append(frame.head(remaining))
    return (pd.concat(frames, ignore_index=True), "generated") if frames else (pd.DataFrame(), "demo")


@st.cache_data(show_spinner=False)
def load_all_tables() -> tuple[dict[str, pd.DataFrame], str]:
    demo = demo_data(); tables: dict[str, pd.DataFrame] = {}; source = "demo"
    for table in demo:
        frame, table_source = load_table(table)
        tables[table] = frame if not frame.empty else demo[table]
        source = "generated" if table_source == "generated" else source
    return tables, source


@st.cache_data(show_spinner=False)
def load_model_scorecard() -> pd.DataFrame:
    scorecard = ROOT / "ml_models" / "disease_risk" / "artifacts" / "patient_risk_scorecard.csv"
    if scorecard.exists():
        return pd.read_csv(scorecard)
    return pd.DataFrame()


def run_nlp_analysis(note_text: str) -> dict[str, Any]:
    """Run the repository's dependency-light NLP fallbacks on one note."""
    from nlp.entity_recognition.clinical_ner import extract_entities_regex
    from nlp.icd_prediction.icd_predictor import predict_icd_codes_keyword
    from nlp.note_summarization.summarizer import extractive_summarize
    from nlp.risk_extraction.risk_extractor import compute_composite_risk_score, extract_risk_factors

    entities = extract_entities_regex(note_text)
    risks = extract_risk_factors(note_text)
    composite = compute_composite_risk_score({
        name: {"weight": 0.7, "present": value}
        for name, value in risks.items()
        if isinstance(value, bool) and value
    })
    return {"entities": entities, "icd": predict_icd_codes_keyword(note_text), "risks": risks, "composite": composite, "summary": extractive_summarize(note_text, n_sentences=3)}


def sql_reference() -> str:
    sql_path = ROOT / "analytics" / "01_patient_readmission_analysis.sql"
    if sql_path.exists():
        text = sql_path.read_text(encoding="utf-8")
        return text[text.find("-- 6. Monthly readmission trend"):]
    return "-- SQL reference unavailable"


def executive_findings(t: dict[str, pd.DataFrame]) -> list[dict[str, str]]:
    """Translate scoped metrics into concise operational actions."""
    admissions, claims, emergency, beds, feedback = (t[name] for name in ["admissions", "insurance_claims", "emergency_visits", "bed_utilization", "patient_feedback"])
    findings = []
    readmission = admissions["readmission_within_30d"].mean() * 100
    if readmission > 15.6:
        findings.append({"priority": "High", "area": "Clinical quality", "issue": f"Readmission is {readmission:.1f}%, above the 15.6% benchmark.", "solution": "Launch a 48-hour post-discharge call list for high-risk DRGs and review discharge barriers by ward."})
    approval = claims["claim_status"].isin(["Approved", "Paid"]).mean() * 100
    if approval < 88:
        findings.append({"priority": "High", "area": "Revenue cycle", "issue": f"Claim approval is {approval:.1f}%, below the 88% target.", "solution": "Prioritize denial reasons by payer, then route coding and authorization exceptions to a daily work queue."})
    door_to_doc = emergency["door_to_doc_minutes"].mean()
    if door_to_doc > 30:
        findings.append({"priority": "High", "area": "Emergency flow", "issue": f"Average door-to-doctor time is {door_to_doc:.0f} minutes.", "solution": "Match triage staffing to the arrival-by-hour pattern and create a fast-track lane for low-acuity visits."})
    occupancy = beds["occupancy_status"].eq("Occupied").mean() * 100
    if occupancy < 80 or occupancy > 90:
        findings.append({"priority": "Watch", "area": "Capacity", "issue": f"Bed occupancy is {occupancy:.1f}%, outside the 80-90% operating band.", "solution": "Review housekeeping and discharge-ready beds every two hours; escalate units with constrained capacity."})
    rating = feedback["overall_rating"].mean()
    if rating < 8:
        findings.append({"priority": "Watch", "area": "Patient experience", "issue": f"Patient rating is {rating:.1f}/10.", "solution": "Use the feedback themes to target wait-time communication and discharge education on the lowest-rated sites."})
    if not findings:
        findings.append({"priority": "Stable", "area": "Network health", "issue": "Core scoped metrics are within the configured operating thresholds.", "solution": "Maintain current controls and use the AI & Insights workspace to investigate emerging signals."})
    return findings


def report_download(t: dict[str, pd.DataFrame], source: str, date_range: tuple[Any, Any]) -> None:
    findings = pd.DataFrame(executive_findings(t))
    report = "\n".join([
        "NORTHSTAR HEALTH | EXECUTIVE OPERATING BRIEF",
        f"Reporting period: {date_range[0]} to {date_range[1]}",
        f"Source: {source.title()} data",
        "",
        "PRIORITIES",
        *[f"[{row.priority}] {row.area}: {row.issue}\nAction: {row.solution}" for row in findings.itertuples()],
    ])
    st.download_button("Download executive brief", data=report.encode("utf-8"), file_name="northstar_executive_brief.txt", mime="text/plain", use_container_width=True)


def metric_card(label: str, value: str, note: str, tone: str = "good") -> None:
    st.markdown(f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value {tone}">{value}</div><div class="kpi-note">{note}</div></div>', unsafe_allow_html=True)


def require_data(tables: dict[str, pd.DataFrame], page: str) -> bool:
    """Keep filtered views usable when a scope contains no records."""
    empty = [name.replace("_", " ").title() for name, frame in tables.items() if frame.empty]
    if empty:
        st.warning(f"No records match the current scope for {page}.")
        st.caption("Try widening the date range or selecting All hospitals.")
        return False
    return True


def report_meta(source: str, date_range: tuple[Any, Any]) -> None:
    st.markdown(
        f'<div class="report-meta">Reporting period: {date_range[0]} to {date_range[1]} &nbsp; | &nbsp; Source: {source.title()} data &nbsp; | &nbsp; Refreshed: {pd.Timestamp.now().strftime("%d %b %Y, %H:%M")}</div>',
        unsafe_allow_html=True,
    )


def prepare_dates(tables: dict[str, pd.DataFrame]) -> tuple[pd.Timestamp, pd.Timestamp]:
    values = []
    for frame in tables.values():
        for column in ("admit_date", "service_date", "submission_date", "arrival_datetime", "survey_date"):
            if column in frame:
                values.extend(pd.to_datetime(frame[column], errors="coerce").dropna().tolist())
    return (min(values), max(values)) if values else (pd.Timestamp("2023-01-01"), pd.Timestamp("2024-12-31"))


def filter_tables(tables: dict[str, pd.DataFrame], date_range: tuple[Any, Any], hospital: str) -> dict[str, pd.DataFrame]:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    date_columns = {"admissions": "admit_date", "billing": "service_date", "insurance_claims": "submission_date", "emergency_visits": "arrival_datetime", "patient_feedback": "survey_date"}
    result = {}
    for name, frame in tables.items():
        current = frame.copy()
        if hospital != "All hospitals" and "hospital_id" in current:
            current = current[current["hospital_id"].astype(str) == hospital]
        date_column = date_columns.get(name)
        if date_column and date_column in current:
            dates = pd.to_datetime(current[date_column], errors="coerce")
            current = current[(dates >= start) & (dates < end)]
        result[name] = current
    return result


def chart_layout(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=42, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(family="DM Sans", color=PALETTE["ink"]), legend=dict(orientation="h", y=1.12), hovermode="x unified")
    fig.update_xaxes(showgrid=False, linecolor="#dce5df"); fig.update_yaxes(gridcolor="#e7eeea", zeroline=False)
    return fig


def overview(t: dict[str, pd.DataFrame], source: str = "demo", date_range: tuple[Any, Any] = ("selected", "period")) -> None:
    if not require_data(t, "the command center"):
        return
    admissions, billing, claims, emergency, beds, feedback = (t[name] for name in ["admissions", "billing", "insurance_claims", "emergency_visits", "bed_utilization", "patient_feedback"])
    readmit = admissions["readmission_within_30d"].mean() * 100; occupancy = beds["occupancy_status"].eq("Occupied").mean() * 100; net_revenue = billing["gross_amount"].sum() - billing["insurance_adjustment"].sum(); approval = claims["claim_status"].isin(["Approved", "Paid"]).mean() * 100; los = admissions["length_of_stay"].mean(); satisfaction = feedback["overall_rating"].mean(); door_to_doc = emergency["door_to_doc_minutes"].mean(); bad_debt = billing.loc[billing["bad_debt_flag"], "amount_due"].sum(); ed_return = emergency["return_within_72h"].mean() * 100
    st.markdown('<div class="eyebrow">Northstar Health / Command Center</div><h1>Hospital performance, in one view.</h1><p class="subhead">A live operating picture across clinical quality, revenue cycle, patient flow, and experience.</p>', unsafe_allow_html=True)
    report_meta(source, date_range)
    cards = st.columns(8); values = [("Bed occupancy", f"{occupancy:.1f}%", "Target 85%", "watch" if occupancy < 80 else "good"), ("30-day readmission", f"{readmit:.1f}%", "Target below 15.6%", "risk" if readmit > 15.6 else "good"), ("Net revenue", f"${net_revenue / 1e6:.2f}M", "Selected period", "good"), ("Claim approval", f"{approval:.1f}%", "Target above 88%", "risk" if approval < 88 else "good"), ("Average LOS", f"{los:.1f} days", "DRG-adjusted view", "good"), ("Patient rating", f"{satisfaction:.1f}/10", "Target above 8.0", "good" if satisfaction >= 8 else "watch"), ("Door to doctor", f"{door_to_doc:.0f} min", "ED target < 30", "risk" if door_to_doc > 30 else "good"), ("72-hour return", f"{ed_return:.1f}%", "Target below 3%", "risk" if ed_return > 3 else "good")]
    for column, item in zip(cards, values):
        with column: metric_card(*item)
    st.markdown("<div class='section-rule'></div>", unsafe_allow_html=True); left, right = st.columns([1.5, 1])
    with left:
        trend = admissions.assign(month=pd.to_datetime(admissions["admit_date"]).dt.to_period("M").astype(str)).groupby("month").agg(admissions=("admission_id", "count"), readmission_rate=("readmission_within_30d", "mean")).reset_index(); trend["readmission_rate"] *= 100
        st.plotly_chart(chart_layout(px.line(trend, x="month", y=["admissions", "readmission_rate"], markers=True, color_discrete_sequence=[PALETTE["teal"], PALETTE["coral"]], title="Volume and quality trend")), use_container_width=True)
    with right:
        dist = emergency["disposition"].value_counts().rename_axis("disposition").reset_index(name="visits")
        st.plotly_chart(chart_layout(px.pie(dist, values="visits", names="disposition", hole=.62, title="Emergency disposition", color_discrete_sequence=[PALETTE["teal"], PALETTE["blue"], PALETTE["gold"], PALETTE["coral"], "#9ab5a9"])), use_container_width=True)
    st.markdown("### The operating story")
    findings = pd.DataFrame(executive_findings(t))
    st.dataframe(findings.rename(columns={"priority": "Priority", "area": "Area", "issue": "What is happening", "solution": "Recommended response"}), use_container_width=True, hide_index=True)
    report_download(t, source, date_range)
    st.markdown("### Network signals")
    hospital_view = admissions.groupby("hospital_id").agg(admissions=("admission_id", "count"), readmission_rate=("readmission_within_30d", "mean"), avg_los=("length_of_stay", "mean")).reset_index()
    hospital_view["readmission_rate"] *= 100
    st.plotly_chart(chart_layout(px.scatter(hospital_view, x="avg_los", y="readmission_rate", size="admissions", color="readmission_rate", text="hospital_id", color_continuous_scale=[PALETTE["mint"], PALETTE["gold"], PALETTE["coral"]], title="Hospital performance matrix", labels={"avg_los": "Average LOS (days)", "readmission_rate": "Readmission rate (%)"})), use_container_width=True)
    metric_card("Bad debt exposure", f"${bad_debt / 1e6:.2f}M", "Open amount on flagged invoices", "risk" if bad_debt > 100_000 else "watch")


def clinical(t: dict[str, pd.DataFrame], source: str = "demo", date_range: tuple[Any, Any] = ("selected", "period")) -> None:
    if not require_data({name: t[name] for name in ("admissions", "patient_feedback")}, "clinical quality"):
        return
    admissions, feedback = t["admissions"], t["patient_feedback"]; st.markdown('<div class="eyebrow">Clinical quality</div><h1>Care outcomes worth acting on.</h1><p class="subhead">Track avoidable returns, mortality signals, length of stay, and experience by ward.</p>', unsafe_allow_html=True)
    report_meta(source, date_range)
    cols = st.columns(4); metrics = [("30-day readmission", f"{admissions['readmission_within_30d'].mean() * 100:.1f}%", "Target < 15.6%"), ("In-hospital mortality", f"{admissions['discharge_status'].eq('Expired').mean() * 100:.1f}%", "All discharges"), ("Average LOS", f"{admissions['length_of_stay'].mean():.1f} days", "Selected admissions"), ("Patient rating", f"{feedback['overall_rating'].mean():.1f}/10", "HCAHPS proxy")]
    for col, item in zip(cols, metrics): col.metric(*item)
    by_ward = admissions.groupby("ward").agg(admissions=("admission_id", "count"), readmission_rate=("readmission_within_30d", "mean"), avg_los=("length_of_stay", "mean")).reset_index(); by_ward["readmission_rate"] *= 100
    left, right = st.columns(2)
    with left: st.plotly_chart(chart_layout(px.bar(by_ward.sort_values("readmission_rate"), x="readmission_rate", y="ward", orientation="h", color="readmission_rate", color_continuous_scale=[PALETTE["mint"], PALETTE["coral"]], title="Readmission rate by ward", labels={"readmission_rate": "% readmitted"})), use_container_width=True)
    with right:
        fig = px.scatter(by_ward, x="avg_los", y="readmission_rate", size="admissions", text="ward", color="ward", title="Quality matrix: LOS vs readmission", labels={"avg_los": "Average LOS (days)", "readmission_rate": "Readmission rate (%)"}); fig.update_traces(textposition="top center")
        st.plotly_chart(chart_layout(fig), use_container_width=True)
    st.dataframe(by_ward.rename(columns={"ward": "Ward", "admissions": "Admissions", "readmission_rate": "Readmission %", "avg_los": "Avg LOS (days)"}).round(2), use_container_width=True, hide_index=True)


def financial(t: dict[str, pd.DataFrame]) -> None:
    if not require_data({name: t[name] for name in ("billing", "insurance_claims")}, "revenue cycle"):
        return
    billing, claims = t["billing"], t["insurance_claims"]; gross = billing["gross_amount"].sum(); net = gross - billing["insurance_adjustment"].sum(); paid = billing["insurance_paid"].sum() + billing["patient_paid"].sum(); approval = claims["claim_status"].isin(["Approved", "Paid"]).mean() * 100; denial = claims["claim_status"].isin(["Denied", "Partially Approved"]).mean() * 100
    st.markdown('<div class="eyebrow">Revenue cycle</div><h1>Follow the money, without losing the patient.</h1><p class="subhead">A compact view of revenue realization, payer mix, claims friction, and bad debt.</p>', unsafe_allow_html=True)
    cols = st.columns(5); metrics = [("Gross revenue", f"${gross / 1e6:.2f}M", "Before adjustments"), ("Net revenue", f"${net / 1e6:.2f}M", "After adjustments"), ("Collection rate", f"{paid / max(net, 1) * 100:.1f}%", "Paid / net revenue"), ("Claim approval", f"{approval:.1f}%", "Approved + paid"), ("Denial rate", f"{denial:.1f}%", "Target below 5%")]
    for col, item in zip(cols, metrics): col.metric(*item)
    left, right = st.columns(2)
    with left:
        payer = billing.groupby("payment_method")["gross_amount"].sum().sort_values(ascending=False).reset_index(); st.plotly_chart(chart_layout(px.bar(payer, x="gross_amount", y="payment_method", orientation="h", title="Gross charges by payer", color="gross_amount", color_continuous_scale=[PALETTE["mint"], PALETTE["teal"]])), use_container_width=True)
    with right:
        denial_reasons = claims[claims["claim_status"].isin(["Denied", "Partially Approved"])]["denial_reason"].value_counts().head(8).reset_index(); denial_reasons.columns = ["reason", "claims"]; st.plotly_chart(chart_layout(px.bar(denial_reasons, x="claims", y="reason", orientation="h", title="Top denial reasons", color_discrete_sequence=[PALETTE["coral"]])), use_container_width=True)


def operations(t: dict[str, pd.DataFrame]) -> None:
    if not require_data({name: t[name] for name in ("emergency_visits", "bed_utilization", "admissions")}, "operations"):
        return
    emergency, beds, admissions = t["emergency_visits"], t["bed_utilization"], t["admissions"]; st.markdown('<div class="eyebrow">Operations</div><h1>Make the next hour run better.</h1><p class="subhead">Capacity, emergency throughput, and demand signals for the operating team.</p>', unsafe_allow_html=True)
    cols = st.columns(5); metrics = [("Bed occupancy", f"{beds['occupancy_status'].eq('Occupied').mean() * 100:.1f}%", "Target 85%"), ("Door to doctor", f"{emergency['door_to_doc_minutes'].mean():.0f} min", "Target < 30 min"), ("ED length of stay", f"{emergency['total_ed_minutes'].mean() / 60:.1f} hrs", "Arrival to disposition"), ("LWBS rate", f"{emergency['disposition'].eq('LWBS').mean() * 100:.1f}%", "Target < 2%"), ("72-hour return", f"{emergency['return_within_72h'].mean() * 100:.1f}%", "Target < 3%")]
    for col, item in zip(cols, metrics): col.metric(*item)
    left, right = st.columns(2)
    with left:
        by_level = emergency.groupby("triage_level")["door_to_doc_minutes"].agg(["mean", "count"]).reset_index(); st.plotly_chart(chart_layout(px.bar(by_level, x="triage_level", y="mean", title="Door-to-doctor by triage level", labels={"mean": "Minutes", "triage_level": "ESI level"}, color="mean", color_continuous_scale=[PALETTE["mint"], PALETTE["coral"]])), use_container_width=True)
    with right:
        ward = beds.groupby(["ward", "occupancy_status"]).size().reset_index(name="beds"); st.plotly_chart(chart_layout(px.bar(ward, x="ward", y="beds", color="occupancy_status", barmode="stack", title="Capacity mix by ward", color_discrete_sequence=[PALETTE["teal"], PALETTE["blue"], PALETTE["gold"], PALETTE["coral"]])), use_container_width=True)
    demand = admissions.assign(day=pd.to_datetime(admissions["admit_date"]).dt.day_name()).groupby("day").size().reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).reset_index(name="admissions"); st.plotly_chart(chart_layout(px.line(demand, x="day", y="admissions", markers=True, title="Admission demand by day of week", color_discrete_sequence=[PALETTE["blue"]]), 260), use_container_width=True)


def experience(t: dict[str, pd.DataFrame]) -> None:
    if not require_data({"patient_feedback": t["patient_feedback"]}, "patient experience"):
        return
    feedback = t["patient_feedback"].copy(); st.markdown('<div class="eyebrow">Patient experience</div><h1>Listen at the speed of care.</h1><p class="subhead">See what patients feel, where the signal is moving, and which sites need attention.</p>', unsafe_allow_html=True)
    cols = st.columns(4); metrics = [("Overall rating", f"{feedback['overall_rating'].mean():.1f}/10", "Target > 8.0"), ("Promoters", f"{(feedback['likelihood_recommend'] >= 9).mean() * 100:.1f}%", "Recommend 9 or 10"), ("NPS proxy", f"{((feedback['likelihood_recommend'] >= 9).mean() - (feedback['likelihood_recommend'] <= 6).mean()) * 100:+.0f}", "Promoters less detractors"), ("Sentiment", f"{feedback['sentiment_score'].mean():+.2f}", "-1 to +1")]
    for col, item in zip(cols, metrics): col.metric(*item)
    feedback["month"] = pd.to_datetime(feedback["survey_date"]).dt.to_period("M").astype(str); trend = feedback.groupby("month").agg(rating=("overall_rating", "mean"), sentiment=("sentiment_score", "mean")).reset_index(); st.plotly_chart(chart_layout(px.line(trend, x="month", y=["rating", "sentiment"], markers=True, title="Experience trend", color_discrete_sequence=[PALETTE["teal"], PALETTE["coral"]])), use_container_width=True)
    hospital = feedback.groupby("hospital_id").agg(rating=("overall_rating", "mean"), responses=("overall_rating", "size"), sentiment=("sentiment_score", "mean")).reset_index().sort_values("rating"); fig = px.bar(hospital, x="rating", y="hospital_id", orientation="h", title="Rating by hospital", text="rating", color="sentiment", color_continuous_scale=[PALETTE["coral"], PALETTE["mint"], PALETTE["teal"]]); fig.update_traces(texttemplate="%{text:.1f}", textposition="outside"); st.plotly_chart(chart_layout(fig), use_container_width=True)


def population_health(t: dict[str, pd.DataFrame], source: str) -> None:
    """DRG-derived population health view for the executive report suite."""
    if not require_data({"admissions": t["admissions"]}, "population health"):
        return
    admissions = t["admissions"].copy()
    admissions["condition"] = admissions["drg_code"].map({"871": "Sepsis", "291": "Heart failure", "194": "Pneumonia", "470": "Joint replacement", "392": "GI disorders", "683": "Renal failure"}).fillna("Other")
    admissions["critical"] = admissions["discharge_status"].eq("Expired")
    st.markdown('<div class="eyebrow">CMO / Population health</div><h1>Know what is moving through the community.</h1><p class="subhead">Disease burden, severity mix, and high-risk cohorts for clinical surveillance.</p>', unsafe_allow_html=True)
    summary = admissions.groupby("condition").agg(cases=("admission_id", "count"), critical_rate=("critical", "mean"), avg_los=("length_of_stay", "mean")).reset_index().sort_values("cases", ascending=False); summary["critical_rate"] *= 100
    cards = st.columns(4)
    for column, item in zip(cards, [("Active cohorts", str(len(summary)), "DRG-derived conditions", "neutral"), ("Admissions", f"{len(admissions):,}", "Selected period", "neutral"), ("Highest burden", summary.iloc[0]["condition"], f"{int(summary.iloc[0]['cases']):,} cases", "watch"), ("Critical outcome rate", f"{admissions['critical'].mean() * 100:.1f}%", "Mortality proxy", "risk")]):
        with column: metric_card(*item)
    left, right = st.columns(2)
    with left:
        fig = px.bar(summary.sort_values("cases"), x="cases", y="condition", orientation="h", color="critical_rate", color_continuous_scale=[PALETTE["mint"], PALETTE["coral"]], title="Condition burden and criticality", labels={"cases": "Admissions", "condition": "Condition", "critical_rate": "Critical %"}); st.plotly_chart(chart_layout(fig), use_container_width=True)
    with right:
        trend = admissions.assign(week=pd.to_datetime(admissions["admit_date"]).dt.to_period("W").astype(str)).groupby(["week", "condition"]).size().reset_index(name="cases"); fig = px.area(trend, x="week", y="cases", color="condition", title="Weekly surveillance trend"); st.plotly_chart(chart_layout(fig), use_container_width=True)
    st.dataframe(summary.rename(columns={"condition": "Condition", "cases": "Cases", "critical_rate": "Critical %", "avg_los": "Avg LOS (days)"}).round(2), use_container_width=True, hide_index=True)


def ai_insights(t: dict[str, pd.DataFrame], source: str) -> None:
    st.markdown('<div class="eyebrow">AI / analytics studio</div><h1>Turn clinical text into next actions.</h1><p class="subhead">Interpretable NLP, model scorecards, and SQL-backed analytics in one review surface.</p>', unsafe_allow_html=True)
    notes = t.get("clinical_notes", pd.DataFrame())
    tab_nlp, tab_ml, tab_sql = st.tabs(["Clinical NLP", "ML scorecards", "SQL analytics"])
    with tab_nlp:
        if notes.empty or "clinical_text" not in notes:
            st.info("Clinical notes are not available in the current data source.")
        else:
            selected_note = st.selectbox("Clinical note", notes["note_id"].astype(str).tolist())
            note_row = notes.loc[notes["note_id"].astype(str).eq(selected_note)].iloc[0]
            note_text = st.text_area("Note text", value=str(note_row["clinical_text"]), height=180)
            if st.button("Analyze note", type="primary"):
                with st.spinner("Running local NLP analysis..."):
                    result = run_nlp_analysis(note_text)
                score = result["composite"]["score"]
                cols = st.columns(4)
                for col, item in zip(cols, [("NLP risk score", f"{score:.1f}/100", "Rule-based composite", "risk" if score >= 45 else "watch"), ("Conditions", str(len(result["entities"].get("conditions", []))), "NER entities", "neutral"), ("Medications", str(len(result["entities"].get("medications", []))), "NER entities", "neutral"), ("ICD suggestions", str(len(result["icd"])), "Keyword-ranked", "good")]):
                    with col: metric_card(*item)
                left, right = st.columns(2)
                with left:
                    st.markdown("#### Extractive summary")
                    st.write(result["summary"])
                    st.markdown("#### Risk drivers")
                    st.write(", ".join(result["composite"].get("drivers", [])) or "No risk drivers detected")
                with right:
                    st.markdown("#### Suggested ICD-10 codes")
                    icd_frame = pd.DataFrame(result["icd"], columns=["Code", "Condition", "Confidence"])
                    st.dataframe(icd_frame, use_container_width=True, hide_index=True)
                    st.markdown("#### Clinical entities")
                    entities = [(kind.replace("_", " ").title(), value) for kind, values in result["entities"].items() for value in values]
                    st.dataframe(pd.DataFrame(entities, columns=["Entity type", "Value"]), use_container_width=True, hide_index=True)
    with tab_ml:
        scorecard = load_model_scorecard()
        if scorecard.empty:
            st.info("No disease-risk scorecard artifact is available.")
        else:
            risk_columns = [column for column in scorecard.columns if column.startswith("risk_") and not column.endswith("_category")]
            cards = st.columns(min(4, max(1, len(risk_columns))))
            for col, column in zip(cards, risk_columns):
                value = pd.to_numeric(scorecard[column], errors="coerce").mean()
                with col: metric_card(column.replace("risk_", "").replace("_", " ").title(), f"{value:.1f}", "Average risk score", "watch" if value >= 50 else "good")
            st.plotly_chart(chart_layout(px.box(scorecard[risk_columns].rename(columns=lambda value: value.replace("risk_", "").replace("_", " ").title()), title="Population risk distribution", labels={"value": "Risk score", "variable": "Condition"})), use_container_width=True)
            st.dataframe(scorecard.head(500), use_container_width=True, hide_index=True)
    with tab_sql:
        st.markdown("#### Monthly readmission trend query")
        st.code(sql_reference(), language="sql")
        st.caption("Source: analytics/01_patient_readmission_analysis.sql. Query is shown as a transparent reference; the dashboard chart above is computed from the active dataframe scope.")


def reports_actions(t: dict[str, pd.DataFrame], source: str, date_range: tuple[Any, Any]) -> None:
    st.markdown('<div class="eyebrow">Executive reporting</div><h1>From signal to accountable action.</h1><p class="subhead">A review-ready brief of problems, likely causes, interventions, and measures of success.</p>', unsafe_allow_html=True)
    findings = pd.DataFrame(executive_findings(t))
    high_count = int(findings["priority"].eq("High").sum())
    cards = st.columns(4)
    for col, item in zip(cards, [("Open priorities", str(len(findings)), "Scoped issues and controls", "risk" if high_count else "good"), ("High priority", str(high_count), "Requires owner assignment", "risk" if high_count else "good"), ("Reporting period", f"{date_range[0]}", f"Through {date_range[1]}", "neutral"), ("Data readiness", source.title(), "Dashboard source", "good")]):
        with col: metric_card(*item)
    st.markdown("### Priority register")
    st.dataframe(findings.rename(columns={"priority": "Priority", "area": "Area", "issue": "Problem / signal", "solution": "Suggested solution"}), use_container_width=True, hide_index=True)
    st.markdown("### Suggested review cadence")
    cadence = pd.DataFrame([
        ["Daily huddle", "Emergency flow, occupancy, high-risk returns", "COO / Nursing operations"],
        ["Weekly quality review", "Readmission, mortality proxy, NLP risk drivers", "CMO / Quality"],
        ["Weekly revenue review", "Denials, approval rate, bad debt exposure", "CFO / Revenue cycle"],
        ["Monthly board brief", "Network trend, financial realization, patient voice", "Executive team"],
    ], columns=["Cadence", "Review", "Accountable group"])
    st.dataframe(cadence, use_container_width=True, hide_index=True)
    report_download(t, source, date_range)


def explorer(t: dict[str, pd.DataFrame], source: str) -> None:
    st.markdown('<div class="eyebrow">Data explorer</div><h1>Inspect the signal behind the score.</h1><p class="subhead">Tables are sampled for responsiveness. Identifiers are shown only to support local development and should be masked in production.</p>', unsafe_allow_html=True); st.info(f"Data source: {source}. Showing up to {MAX_ROWS_PER_TABLE:,} rows per table for this session.")
    table = st.selectbox("Dataset", list(t.keys())); frame = t[table]; search = st.text_input("Search visible values", placeholder="hospital, ward, status...")
    if search:
        mask = frame.astype(str).apply(lambda column: column.str.contains(search, case=False, na=False)).any(axis=1); frame = frame[mask]
    st.caption(f"{len(frame):,} rows x {len(frame.columns)} columns")
    preview = frame.head(5_000)
    st.dataframe(preview, use_container_width=True, hide_index=True)
    st.download_button("Download filtered CSV", data=preview.to_csv(index=False).encode("utf-8"), file_name=f"{table}_filtered.csv", mime="text/csv", use_container_width=True)


def main() -> None:
    inject_styles(); tables, source = load_all_tables(); start, end = prepare_dates(tables)
    with st.sidebar:
        st.markdown("## NORTHSTAR HEALTH"); st.caption("Enterprise clinical intelligence / v2.0"); page = st.radio("Workspace", ["Command center", "Clinical quality", "Revenue cycle", "Operations", "Patient experience", "Population health", "AI & insights", "Reports & actions", "Data explorer"], label_visibility="collapsed"); st.markdown("---"); st.markdown("### Scope")
        date_range = st.date_input("Date range", value=(start.date(), end.date()), min_value=start.date(), max_value=end.date()); hospitals = sorted({str(value) for frame in tables.values() if "hospital_id" in frame for value in frame["hospital_id"].dropna().unique()}); hospital = st.selectbox("Hospital", ["All hospitals"] + hospitals); st.markdown("---"); st.caption("Refresh after new files land in data/raw.")
        st.caption(f"{source.title()} source · {sum(len(frame) for frame in tables.values()):,} loaded rows")
        if st.button("Refresh data", use_container_width=True): st.cache_data.clear(); st.rerun()
    if not isinstance(date_range, (tuple, list)) or len(date_range) != 2: date_range = (start.date(), end.date())
    filtered = filter_tables(tables, date_range, hospital)
    if page == "Command center": overview(filtered, source, date_range)
    elif page == "Clinical quality": clinical(filtered, source, date_range)
    elif page == "Revenue cycle": financial(filtered)
    elif page == "Operations": operations(filtered)
    elif page == "Patient experience": experience(filtered)
    elif page == "Population health": population_health(filtered, source)
    elif page == "AI & insights": ai_insights(filtered, source)
    elif page == "Reports & actions": reports_actions(filtered, source, date_range)
    else: explorer(filtered, source)


if __name__ == "__main__": main()