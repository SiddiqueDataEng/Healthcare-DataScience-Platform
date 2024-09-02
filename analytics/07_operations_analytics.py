"""
Chapter 8: Healthcare Operations Optimization
Data-driven analytics for hospital operations.

Analyses:
  1. Patient admission forecasting (time-series)
  2. Staffing optimization (demand vs capacity)
  3. Bed management and occupancy optimization
  4. Revenue cycle performance
  5. Appointment scheduling efficiency
  6. Emergency department throughput

Usage:
    python analytics/07_operations_analytics.py
    python analytics/07_operations_analytics.py ./data/raw
"""

import sys
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder

warnings.filterwarnings("ignore")

OUTPUT_DIR = Path("analytics/outputs/ch08_operations")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR   = Path("./data/raw")


# ─── 1. Admission Volume Forecasting ────────────────────────────────

def forecast_admissions(admissions: pd.DataFrame):
    """
    Forecast daily admission volumes using trend + seasonality.
    Demonstrates operational planning for staffing and bed management.
    """
    logger.info("=== Admission Volume Forecasting ===")

    adm = admissions.copy()
    adm["admit_date"] = pd.to_datetime(adm["admit_date"], errors="coerce").dt.date
    daily = adm.groupby("admit_date").size().reset_index(name="admissions")
    daily["admit_date"] = pd.to_datetime(daily["admit_date"])
    daily = daily.sort_values("admit_date")

    if len(daily) < 14:
        logger.warning("Not enough data for forecasting. Need at least 14 days.")
        return daily

    # Add time features
    daily["day_of_week"]  = daily["admit_date"].dt.dayofweek
    daily["day_of_month"] = daily["admit_date"].dt.day
    daily["month"]        = daily["admit_date"].dt.month
    daily["t"]            = range(len(daily))

    # Day-of-week average (operational pattern)
    dow_avg = daily.groupby("day_of_week")["admissions"].mean()
    logger.info(f"\nAvg Daily Admissions by Day of Week:")
    dow_names = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    for i, avg in dow_avg.items():
        logger.info(f"  {dow_names[i]:4s}: {avg:.1f}")

    # Simple linear trend + DOW seasonality
    X = daily[["t","day_of_week","month"]].values
    y = daily["admissions"].values
    model = LinearRegression().fit(X, y)
    daily["fitted"]    = model.predict(X)

    # 7-day rolling average
    daily["rolling_7d"] = daily["admissions"].rolling(7, min_periods=1).mean()

    # 14-day forecast
    last_t = daily["t"].max()
    last_date = daily["admit_date"].max()
    future_dates = pd.date_range(last_date + timedelta(days=1), periods=14)
    future_df = pd.DataFrame({
        "admit_date":   future_dates,
        "day_of_week":  future_dates.dayofweek,
        "month":        future_dates.month,
        "t":            range(last_t+1, last_t+15),
    })
    future_df["forecast"] = model.predict(future_df[["t","day_of_week","month"]]).clip(0)

    logger.info(f"\n14-Day Admission Forecast:")
    for _, row in future_df.iterrows():
        logger.info(f"  {row['admit_date'].strftime('%Y-%m-%d')} ({dow_names[row['day_of_week']]}): "
                    f"{row['forecast']:.0f} predicted admissions")

    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(14, 8))
    fig.suptitle("Chapter 8: Admission Volume Analysis & Forecast", fontsize=13, fontweight="bold")

    axes[0].plot(daily["admit_date"], daily["admissions"], alpha=0.5, color="steelblue", label="Actual")
    axes[0].plot(daily["admit_date"], daily["rolling_7d"], color="navy", linewidth=2, label="7-day Rolling Avg")
    axes[0].plot(daily["admit_date"], daily["fitted"], color="orange", linewidth=1.5, linestyle="--", label="Trend")
    axes[0].set_title("Historical Admission Volumes")
    axes[0].set_ylabel("Daily Admissions")
    axes[0].legend()

    axes[1].bar(future_df["admit_date"], future_df["forecast"], color="steelblue", alpha=0.8)
    axes[1].set_title("14-Day Admission Forecast")
    axes[1].set_ylabel("Predicted Admissions")
    axes[1].set_xlabel("Date")
    for _, row in future_df.iterrows():
        axes[1].text(row["admit_date"], row["forecast"]+0.1, f"{row['forecast']:.0f}",
                     ha="center", va="bottom", fontsize=8)

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "admission_forecast.png", dpi=120)
    plt.close()

    future_df.to_csv(OUTPUT_DIR / "admission_forecast.csv", index=False)
    return daily, future_df


# ─── 2. Staffing Optimization ────────────────────────────────────────

def analyze_staffing(staff_schedule: pd.DataFrame, admissions: pd.DataFrame):
    """Analyze staff utilization vs patient demand."""
    logger.info("\n=== Staffing Optimization Analysis ===")

    sched = staff_schedule.copy()
    sched["shift_date"] = pd.to_datetime(sched["shift_date"], errors="coerce").dt.date

    # Staff utilization — group by available columns
    group_cols = [c for c in ["department_id","shift_type"] if c in sched.columns]
    if not group_cols:
        group_cols = ["shift_type"] if "shift_type" in sched.columns else ["employee_type"]

    agg_dict = {}
    if "schedule_id"       in sched.columns: agg_dict["scheduled_shifts"] = ("schedule_id","count")
    if "status"            in sched.columns:
        agg_dict["completed"]   = ("status", lambda x: (x=="Completed").sum())
        agg_dict["called_off"]  = ("status", lambda x: (x=="Called Off").sum())
    if "overtime_hours"    in sched.columns: agg_dict["overtime_hours"] = ("overtime_hours","sum")
    if "patients_assigned" in sched.columns: agg_dict["avg_patients"]   = ("patients_assigned","mean")

    if agg_dict:
        utilization = sched.groupby(group_cols).agg(**agg_dict).reset_index()
        if "scheduled_shifts" in utilization.columns:
            utilization["completion_rate"] = utilization.get("completed", 0) / utilization["scheduled_shifts"].clip(1)
        logger.info(f"\nStaff utilization sample:\n{utilization.head(8).to_string(index=False)}")
    else:
        utilization = pd.DataFrame()
        logger.warning("No usable staff schedule columns for utilization analysis.")

    # Overtime analysis
    overtime_by_type = sched.groupby("employee_type")["overtime_hours"].sum().sort_values(ascending=False)
    logger.info(f"\nOvertime Hours by Employee Type:")
    logger.info(overtime_by_type.to_string())

    # Staff demand vs supply by day of week
    sched["dow"] = pd.to_datetime(sched["shift_date"], errors="coerce").dt.dayofweek
    daily_staff = sched.groupby("dow").size().rename("staff_count")

    adm = admissions.copy()
    adm["dow"] = pd.to_datetime(adm["admit_date"], errors="coerce").dt.dayofweek
    daily_adm = adm.groupby("dow").size().rename("admissions")

    demand_supply = pd.DataFrame({"staff": daily_staff, "admissions": daily_adm}).fillna(0)
    demand_supply["ratio"] = demand_supply["admissions"] / demand_supply["staff"].clip(1)

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Chapter 8: Staffing Analysis", fontsize=13, fontweight="bold")

    dow_labels = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    axes[0].bar(range(7), demand_supply["staff"],      alpha=0.7, color="steelblue", label="Staff Shifts")
    axes[0].bar(range(7), demand_supply["admissions"], alpha=0.7, color="tomato",    label="Admissions")
    axes[0].set_xticks(range(7))
    axes[0].set_xticklabels(dow_labels)
    axes[0].set_title("Staffing vs Admissions by Day of Week")
    axes[0].set_ylabel("Count")
    axes[0].legend()

    ot_data = overtime_by_type.values[:8]
    ot_labels = overtime_by_type.index[:8]
    axes[1].barh(ot_labels, ot_data, color="darkorange")
    axes[1].set_title("Overtime Hours by Employee Type")
    axes[1].set_xlabel("Total Overtime Hours")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "staffing_analysis.png", dpi=120)
    plt.close()

    utilization.to_csv(OUTPUT_DIR / "staffing_utilization.csv", index=False)
    return utilization


# ─── 3. Bed Management Optimization ─────────────────────────────────

def analyze_bed_management(bed_util: pd.DataFrame):
    """Analyze bed occupancy, turnover, and bottlenecks."""
    logger.info("\n=== Bed Management Optimization ===")

    beds = bed_util.copy()

    # Current occupancy by ward
    occupancy = beds.groupby(["ward","occupancy_status"]).size().unstack(fill_value=0).reset_index()

    status_cols = [c for c in ["Occupied","Available","Housekeeping","Maintenance","Blocked"]
                   if c in occupancy.columns]
    if status_cols:
        occupancy["total"] = occupancy[status_cols].sum(axis=1)
        if "Occupied" in occupancy.columns:
            occupancy["occ_rate"] = (occupancy["Occupied"] / occupancy["total"] * 100).round(1)
        else:
            occupancy["occ_rate"] = 0

        logger.info(f"\nBed Occupancy by Ward:")
        logger.info(occupancy[["ward"] + status_cols + ["total","occ_rate"]].to_string(index=False))

    # Cleaning time analysis
    if "cleaning_minutes" in beds.columns:
        clean_stats = beds.groupby("ward")["cleaning_minutes"].agg(["mean","median","max"]).round(1)
        logger.info(f"\nBed Cleaning Time (minutes) by Ward:")
        logger.info(clean_stats.to_string())

    # Average occupancy hours
    if "hours_occupied" in beds.columns:
        occ_hours = beds.groupby("ward")["hours_occupied"].agg(["mean","median"]).round(1)
        logger.info(f"\nAvg Occupancy Hours by Ward:")
        logger.info(occ_hours.to_string())

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Chapter 8: Bed Management Dashboard", fontsize=13, fontweight="bold")

    if "occ_rate" in occupancy.columns:
        occ_sorted = occupancy.sort_values("occ_rate", ascending=True)
        colors = ["tomato" if r > 90 else "goldenrod" if r > 80 else "steelblue"
                  for r in occ_sorted["occ_rate"]]
        axes[0].barh(occ_sorted["ward"], occ_sorted["occ_rate"], color=colors)
        axes[0].axvline(85, color="red", linestyle="--", label="Target 85%")
        axes[0].set_title("Bed Occupancy Rate by Ward")
        axes[0].set_xlabel("Occupancy %")
        axes[0].legend()
        for _, row in occ_sorted.iterrows():
            axes[0].text(row["occ_rate"]+0.5, row.name, f"{row['occ_rate']:.1f}%",
                         va="center", fontsize=8)

    # Occupancy status distribution
    status_counts = beds["occupancy_status"].value_counts()
    axes[1].pie(status_counts.values, labels=status_counts.index,
                autopct="%1.1f%%", colors=sns.color_palette("Set2"))
    axes[1].set_title("Overall Bed Status Distribution")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "bed_management.png", dpi=120)
    plt.close()

    return occupancy


# ─── 4. Revenue Cycle Performance ───────────────────────────────────

def analyze_revenue_cycle(billing: pd.DataFrame, claims: pd.DataFrame):
    """Revenue cycle KPIs and bottleneck identification."""
    logger.info("\n=== Revenue Cycle Performance ===")

    # Monthly revenue trend
    billing["billing_date"] = pd.to_datetime(billing["billing_date"], errors="coerce")
    monthly = billing.groupby(billing["billing_date"].dt.to_period("M")).agg(
        gross_revenue    = ("gross_amount", "sum"),
        insurance_paid   = ("insurance_paid", "sum"),
        patient_paid     = ("patient_paid", "sum"),
        bad_debt         = ("amount_due", lambda x: x[billing.loc[x.index,"bad_debt_flag"]==True].sum()
                            if "bad_debt_flag" in billing.columns else 0),
    ).reset_index()
    monthly["total_collected"]  = monthly["insurance_paid"] + monthly["patient_paid"]
    monthly["collection_rate"]  = (monthly["total_collected"] / monthly["gross_revenue"].clip(1) * 100).round(1)
    monthly["billing_date"]     = monthly["billing_date"].astype(str)

    logger.info(f"\nMonthly Revenue Summary:")
    logger.info(monthly.tail(6).to_string(index=False))

    # Payment method distribution
    pay_method = billing.groupby("payment_method")["gross_amount"].sum().sort_values(ascending=False)
    logger.info(f"\nRevenue by Payment Method:")
    total_rev = pay_method.sum()
    for method, amount in pay_method.items():
        logger.info(f"  {method:25s}: ${amount:>12,.0f}  ({amount/total_rev*100:.1f}%)")

    # Claim denial analysis
    if "claim_status" in claims.columns:
        denial_rate = (claims["claim_status"] == "Denied").mean() * 100
        logger.info(f"\nClaim Denial Rate: {denial_rate:.1f}%  (Target: <5%)")

        if "insurance_provider" in claims.columns:
            denial_by_provider = (
                claims.groupby("insurance_provider")["claim_status"]
                .apply(lambda x: (x == "Denied").mean() * 100)
                .sort_values(ascending=False)
                .round(1)
            )
            logger.info(f"\nDenial Rate by Insurer:\n{denial_by_provider.to_string()}")

    # A/R aging
    if "payment_status" in billing.columns and "days_outstanding" in billing.columns:
        ar_open = billing[billing["payment_status"].isin(["Pending","Partial"])]
        ar_aging = pd.cut(
            ar_open["days_outstanding"].fillna(0),
            bins=[0, 30, 60, 90, 120, float("inf")],
            labels=["0-30d","31-60d","61-90d","91-120d","120d+"]
        ).value_counts().sort_index()
        logger.info(f"\nA/R Aging Buckets:\n{ar_aging.to_string()}")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Chapter 8: Revenue Cycle Analytics", fontsize=13, fontweight="bold")

    axes[0].bar(range(len(monthly)), monthly["gross_revenue"]/1000, color="steelblue", alpha=0.8, label="Gross Revenue")
    axes[0].bar(range(len(monthly)), monthly["total_collected"]/1000, color="green", alpha=0.8, label="Collected")
    axes[0].set_xticks(range(len(monthly)))
    axes[0].set_xticklabels(monthly["billing_date"], rotation=45, fontsize=7)
    axes[0].set_title("Monthly Revenue vs Collected ($K)")
    axes[0].set_ylabel("Amount ($K)")
    axes[0].legend()

    axes[1].barh(pay_method.index[:8], pay_method.values[:8]/1000, color="teal")
    axes[1].set_title("Revenue by Payment Method ($K)")
    axes[1].set_xlabel("Revenue ($K)")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "revenue_cycle.png", dpi=120)
    plt.close()

    monthly.to_csv(OUTPUT_DIR / "monthly_revenue.csv", index=False)
    return monthly


# ─── 5. ED Throughput Analysis ───────────────────────────────────────

def analyze_ed_throughput(emergency_visits: pd.DataFrame):
    """ED efficiency metrics: door-to-doc time, LWBS, boarding."""
    logger.info("\n=== Emergency Department Throughput ===")

    ev = emergency_visits.copy()
    ev["arrival_datetime"] = pd.to_datetime(ev["arrival_datetime"], errors="coerce")
    ev["hour"] = ev["arrival_datetime"].dt.hour
    ev["dow"]  = ev["arrival_datetime"].dt.dayofweek

    # Hourly volume pattern
    hourly = ev.groupby("hour").agg(
        visit_count      = ("visit_id", "count"),
        avg_wait_minutes = ("wait_time_minutes", "mean"),
        lwbs_count       = ("left_without_seen", "sum") if "left_without_seen" in ev.columns else ("visit_id", lambda x: 0),
    ).reset_index()

    # Key ED metrics
    avg_wait     = ev["wait_time_minutes"].mean()
    avg_d2d      = ev["door_to_doc_minutes"].mean() if "door_to_doc_minutes" in ev.columns else 0
    admit_rate   = ev["admitted_flag"].astype(float).mean() * 100 if "admitted_flag" in ev.columns else 0

    logger.info(f"\nED Performance Metrics:")
    logger.info(f"  Avg Wait Time:        {avg_wait:.1f} min  (Target: <30 min)")
    logger.info(f"  Avg Door-to-Doctor:   {avg_d2d:.1f} min  (Target: <30 min)")
    logger.info(f"  Admission Rate:       {admit_rate:.1f}%")
    logger.info(f"  Total Visits:         {len(ev):,}")

    # Triage level distribution
    if "triage_level" in ev.columns:
        triage_dist = ev["triage_level"].value_counts().sort_index()
        logger.info(f"\nTriage Level Distribution:")
        triage_labels = {1:"Immediate",2:"Emergent",3:"Urgent",4:"Less Urgent",5:"Non-Urgent"}
        for level, count in triage_dist.items():
            logger.info(f"  Level {level} ({triage_labels.get(level,'?')}): {count:,} ({count/len(ev)*100:.1f}%)")

    # Peak hours identification
    peak_hours = hourly.nlargest(3, "visit_count")["hour"].tolist()
    logger.info(f"\nPeak ED Hours: {peak_hours} (24h format)")

    # Plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("Chapter 8: ED Throughput Analysis", fontsize=13, fontweight="bold")

    axes[0].bar(hourly["hour"], hourly["visit_count"], color="steelblue", alpha=0.8)
    axes[0].set_title("ED Hourly Volume")
    axes[0].set_xlabel("Hour of Day")
    axes[0].set_ylabel("Visit Count")
    axes[0].set_xticks(range(0, 24, 2))

    if "triage_level" in ev.columns:
        triage_counts = ev["triage_level"].value_counts().sort_index()
        colors = ["red","orangered","goldenrod","steelblue","green"]
        axes[1].bar([f"L{l}" for l in triage_counts.index],
                    triage_counts.values,
                    color=colors[:len(triage_counts)])
        axes[1].set_title("ED Triage Level Distribution (ESI)")
        axes[1].set_ylabel("Visits")

    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / "ed_throughput.png", dpi=120)
    plt.close()

    return hourly


# ─── Main ────────────────────────────────────────────────────────────

def main():
    logger.info("Chapter 8: Healthcare Operations Optimization")
    logger.info(f"Output: {OUTPUT_DIR}\n")

    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA_DIR

    try:
        admissions      = pd.read_parquet(data_dir / "admissions")
        staff_schedule  = pd.read_parquet(data_dir / "staff_schedule")
        bed_util        = pd.read_parquet(data_dir / "bed_utilization")
        billing         = pd.read_parquet(data_dir / "billing")
        claims          = pd.read_parquet(data_dir / "insurance_claims")
        emergency       = pd.read_parquet(data_dir / "emergency_visits")
        logger.info("Data loaded from parquet files.")
    except FileNotFoundError as e:
        logger.error(f"Data not found: {e}. Run generate_all.py first.")
        return

    forecast_admissions(admissions)
    analyze_staffing(staff_schedule, admissions)
    analyze_bed_management(bed_util)
    analyze_revenue_cycle(billing, claims)
    analyze_ed_throughput(emergency)

    logger.success(f"\nChapter 8 Operations Analytics complete. All charts saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
