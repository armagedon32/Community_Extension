"""Predictive Analytics and Performance Monitoring.

Produces lightweight, data-driven forecasts and trend analytics for the
extension portfolio. It uses historical activity and beneficiary data to:

  * compute month-over-month momentum of extension work,
  * estimate the expected number of activities and beneficiaries served in the
    next period using simple linear trend extrapolation, and
  * surface performance signals (trending up, flat, or down).

Everything is computed from existing records, so the analytics stay current
without any external services or heavy dependencies.
"""
from datetime import datetime, timedelta

from app.models import Activity, AccomplishmentReport, Beneficiary, Project

import calendar


def _month_key(d):
    return (d.year, d.month)


def _latest_months(keys, n=6):
    """Return the last ``n`` month keys present (or implied), oldest first."""
    if not keys:
        return []
    latest = max(keys)
    out = []
    y, m = latest
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _linest(xs, ys):
    """Least-squares slope/intercept for the given (x, y) pairs."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    intercept = my - slope * mx
    return slope, intercept


def _trend_series(keys, counts):
    """Fit a line over the last period and predict the next value."""
    if not keys:
        return [], 0, ""
    xs = list(range(len(keys)))
    ys = [counts.get(k, 0) for k in keys]
    slope, intercept = _linest(xs, ys)
    next_x = len(keys)
    prediction = max(0, int(round(intercept + slope * next_x)))
    if slope > 0.3:
        signal = "Trending up"
    elif slope < -0.3:
        signal = "Trending down"
    else:
        signal = "Stable"
    return [{"month": k[1], "year": k[0], "value": counts.get(k, 0)} for k in keys], prediction, signal


def build_analytics():
    """Compute predictive analytics from existing records."""
    now = datetime.utcnow()

    # Activities per month (by schedule date)
    activity_month = {}
    for a in Activity.query.all():
        if a.schedule_date:
            k = _month_key(a.schedule_date)
            activity_month[k] = activity_month.get(k, 0) + 1

    # Beneficiaries per project created month
    ben_month = {}
    for b in Beneficiary.query.all():
        if b.created_at:
            k = _month_key(b.created_at)
            ben_month[k] = ben_month.get(k, 0) + 1

    # Accomplishment reports per month
    acc_month = {}
    for r in AccomplishmentReport.query.all():
        if r.created_at:
            k = _month_key(r.created_at)
            acc_month[k] = acc_month.get(k, 0) + 1

    keys = _latest_months(
        set(activity_month) | set(ben_month) | set(acc_month)
    )

    activity_series, next_activities, activity_signal = _trend_series(keys, activity_month)
    ben_series, next_ben, ben_signal = _trend_series(keys, ben_month)
    acc_series, next_acc, acc_signal = _trend_series(keys, acc_month)

    total_projects = Project.query.count()
    ongoing = Project.query.filter_by(status="Ongoing").count()
    completed = Project.query.filter_by(status="Completed").count()

    # Average beneficiaries per project
    avg_ben = (Beneficiary.query.count() / total_projects) if total_projects else 0

    # Forecast horizon month label
    next_month = datetime(now.year, now.month, 1) + timedelta(days=32)
    horizon = f"{calendar.month_name[next_month.month]} {next_month.year}"

    return {
        "horizon": horizon,
        "activity_series": activity_series,
        "activity_prediction": next_activities,
        "activity_signal": activity_signal,
        "ben_series": ben_series,
        "ben_prediction": next_ben,
        "ben_signal": ben_signal,
        "acc_series": acc_series,
        "acc_prediction": next_acc,
        "acc_signal": acc_signal,
        "total_projects": total_projects,
        "ongoing": ongoing,
        "completed": completed,
        "avg_ben": round(avg_ben, 1),
    }