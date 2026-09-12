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
PALETTE = {"ink": "#15231f", "teal": "#0f766e", "mint": "#dff3ec", "coral": "#e87561", "gold": "#d49b42", "blue": "#2f6f9f", "muted": "#64736e"}

st.set_page_config(page_title="Northstar Health | Command Center", page_icon="+", layout="wide", initial_sidebar_state="expanded")


def inject_styles() -> None:
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    :root { --ink:#15231f; --teal:#0f766e; --mint:#dff3ec; --paper:#f5f7f3; --line:#dce5df; }
    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; color: var(--ink); }
    .stApp { background: var(--paper); }
    [data-testid="stSidebar"] { background: #17322d; }
    [data-testid="stSidebar"] * { color: #eef8f2 !important; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif; letter-spacing: 0; }
    h1 { font-size: 2.5rem !important; margin-bottom: .2rem; }
    .eyebrow { color: var(--teal); font-size: .75rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
    .subhead { color: #64736e; margin: 0 0 1.5rem; }
    .kpi { background:#fff; border:1px solid var(--line); border-radius:8px; padding:1rem 1.1rem; min-height:122px; box-shadow:0 5px 18px rgba(21,35,31,.04); }
    .kpi-label { color:#64736e; font-size:.76rem; text-transform:uppercase; letter-spacing:.06em; font-weight:700; }
    .kpi-value { font-family:'Space Grotesk'; font-size:1.75rem; font-weight:700; margin:.45rem 0 .15rem; }
    .kpi-note { color:#64736e; font-size:.78rem; }
    .good { color:#16805d; } .watch { color:#bd7529; } .risk { color:#c65443; }
    .section-rule { border-top:1px solid var(--line); margin:1.2rem 0; }
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
    return {"admissions": admissions, "billing": billing, "insurance_claims": claims, "emergency_visits": emergency, "bed_utilization": beds, "patient_feedback": feedback}


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


def metric_card(label: str, value: str, note: str, tone: str = "good") -> None:
    st.markdown(f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value {tone}">{value}</div><div class="kpi-note">{note}</div></div>', unsafe_allow_html=True)


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


def overview(t: dict[str, pd.DataFrame]) -> None:
    admissions, billing, claims, emergency, beds, feedback = (t[name] for name in ["admissions", "billing", "insurance_claims", "emergency_visits", "bed_utilization", "patient_feedback"])
    readmit = admissions["readmission_within_30d"].mean() * 100; occupancy = beds["occupancy_status"].eq("Occupied").mean() * 100; net_revenue = billing["gross_amount"].sum() - billing["insurance_adjustment"].sum(); approval = claims["claim_status"].isin(["Approved", "Paid"]).mean() * 100; los = admissions["length_of_stay"].mean(); satisfaction = feedback["overall_rating"].mean()
    st.markdown('<div class="eyebrow">Northstar Health / Command Center</div><h1>Hospital performance, in one view.</h1><p class="subhead">A live operating picture across clinical quality, revenue cycle, patient flow, and experience.</p>', unsafe_allow_html=True)
    cards = st.columns(6); values = [("Bed occupancy", f"{occupancy:.1f}%", "Target 85%", "watch" if occupancy < 80 else "good"), ("30-day readmission", f"{readmit:.1f}%", "Target below 15.6%", "risk" if readmit > 15.6 else "good"), ("Net revenue", f"${net_revenue / 1e6:.2f}M", "Selected period", "good"), ("Claim approval", f"{approval:.1f}%", "Target above 88%", "risk" if approval < 88 else "good"), ("Average LOS", f"{los:.1f} days", "DRG-adjusted view", "good"), ("Patient rating", f"{satisfaction:.1f}/10", "Target above 8.0", "good" if satisfaction >= 8 else "watch")]
    for column, item in zip(cards, values):
        with column: metric_card(*item)
    st.markdown("<div class='section-rule'></div>", unsafe_allow_html=True); left, right = st.columns([1.5, 1])
    with left:
        trend = admissions.assign(month=pd.to_datetime(admissions["admit_date"]).dt.to_period("M").astype(str)).groupby("month").agg(admissions=("admission_id", "count"), readmission_rate=("readmission_within_30d", "mean")).reset_index(); trend["readmission_rate"] *= 100
        st.plotly_chart(chart_layout(px.line(trend, x="month", y=["admissions", "readmission_rate"], markers=True, color_discrete_sequence=[PALETTE["teal"], PALETTE["coral"]], title="Volume and quality trend")), use_container_width=True)
    with right:
        dist = emergency["disposition"].value_counts().rename_axis("disposition").reset_index(name="visits")
        st.plotly_chart(chart_layout(px.pie(dist, values="visits", names="disposition", hole=.62, title="Emergency disposition", color_discrete_sequence=[PALETTE["teal"], PALETTE["blue"], PALETTE["gold"], PALETTE["coral"], "#9ab5a9"])), use_container_width=True)


def clinical(t: dict[str, pd.DataFrame]) -> None:
    admissions, feedback = t["admissions"], t["patient_feedback"]; st.markdown('<div class="eyebrow">Clinical quality</div><h1>Care outcomes worth acting on.</h1><p class="subhead">Track avoidable returns, mortality signals, length of stay, and experience by ward.</p>', unsafe_allow_html=True)
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
    feedback = t["patient_feedback"].copy(); st.markdown('<div class="eyebrow">Patient experience</div><h1>Listen at the speed of care.</h1><p class="subhead">See what patients feel, where the signal is moving, and which sites need attention.</p>', unsafe_allow_html=True)
    cols = st.columns(4); metrics = [("Overall rating", f"{feedback['overall_rating'].mean():.1f}/10", "Target > 8.0"), ("Promoters", f"{(feedback['likelihood_recommend'] >= 9).mean() * 100:.1f}%", "Recommend 9 or 10"), ("NPS proxy", f"{((feedback['likelihood_recommend'] >= 9).mean() - (feedback['likelihood_recommend'] <= 6).mean()) * 100:+.0f}", "Promoters less detractors"), ("Sentiment", f"{feedback['sentiment_score'].mean():+.2f}", "-1 to +1")]
    for col, item in zip(cols, metrics): col.metric(*item)
    feedback["month"] = pd.to_datetime(feedback["survey_date"]).dt.to_period("M").astype(str); trend = feedback.groupby("month").agg(rating=("overall_rating", "mean"), sentiment=("sentiment_score", "mean")).reset_index(); st.plotly_chart(chart_layout(px.line(trend, x="month", y=["rating", "sentiment"], markers=True, title="Experience trend", color_discrete_sequence=[PALETTE["teal"], PALETTE["coral"]])), use_container_width=True)
    hospital = feedback.groupby("hospital_id").agg(rating=("overall_rating", "mean"), responses=("overall_rating", "size"), sentiment=("sentiment_score", "mean")).reset_index().sort_values("rating"); fig = px.bar(hospital, x="rating", y="hospital_id", orientation="h", title="Rating by hospital", text="rating", color="sentiment", color_continuous_scale=[PALETTE["coral"], PALETTE["mint"], PALETTE["teal"]]); fig.update_traces(texttemplate="%{text:.1f}", textposition="outside"); st.plotly_chart(chart_layout(fig), use_container_width=True)


def explorer(t: dict[str, pd.DataFrame], source: str) -> None:
    st.markdown('<div class="eyebrow">Data explorer</div><h1>Inspect the signal behind the score.</h1><p class="subhead">Tables are sampled for responsiveness. Identifiers are shown only to support local development and should be masked in production.</p>', unsafe_allow_html=True); st.info(f"Data source: {source}. Showing up to {MAX_ROWS_PER_TABLE:,} rows per table for this session.")
    table = st.selectbox("Dataset", list(t.keys())); frame = t[table]; search = st.text_input("Search visible values", placeholder="hospital, ward, status...")
    if search:
        mask = frame.astype(str).apply(lambda column: column.str.contains(search, case=False, na=False)).any(axis=1); frame = frame[mask]
    st.caption(f"{len(frame):,} rows x {len(frame.columns)} columns"); st.dataframe(frame.head(5_000), use_container_width=True, hide_index=True)


def main() -> None:
    inject_styles(); tables, source = load_all_tables(); start, end = prepare_dates(tables)
    with st.sidebar:
        st.markdown("## NORTHSTAR HEALTH"); st.caption("Clinical intelligence / v1.0"); page = st.radio("Workspace", ["Command center", "Clinical quality", "Revenue cycle", "Operations", "Patient experience", "Data explorer"], label_visibility="collapsed"); st.markdown("---"); st.markdown("### Scope")
        date_range = st.date_input("Date range", value=(start.date(), end.date()), min_value=start.date(), max_value=end.date()); hospitals = sorted({str(value) for frame in tables.values() if "hospital_id" in frame for value in frame["hospital_id"].dropna().unique()}); hospital = st.selectbox("Hospital", ["All hospitals"] + hospitals); st.markdown("---"); st.caption("Refresh after new files land in data/raw.")
        if st.button("Refresh data", use_container_width=True): st.cache_data.clear(); st.rerun()
    if not isinstance(date_range, (tuple, list)) or len(date_range) != 2: date_range = (start.date(), end.date())
    filtered = filter_tables(tables, date_range, hospital)
    if page == "Command center": overview(filtered)
    elif page == "Clinical quality": clinical(filtered)
    elif page == "Revenue cycle": financial(filtered)
    elif page == "Operations": operations(filtered)
    elif page == "Patient experience": experience(filtered)
    else: explorer(filtered, source)


if __name__ == "__main__": main()