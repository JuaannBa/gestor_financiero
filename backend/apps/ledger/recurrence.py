from datetime import date

from dateutil.relativedelta import relativedelta


def advance_date(current: date, frequency: str, interval: int) -> date:
    """Advance a date by one recurrence period (interval multiples)."""
    if interval < 1:
        interval = 1
    if frequency == "daily":
        return date.fromordinal(current.toordinal() + interval)
    if frequency == "weekly":
        return date.fromordinal(current.toordinal() + 7 * interval)
    if frequency == "monthly":
        return current + relativedelta(months=interval)
    if frequency == "yearly":
        return current + relativedelta(years=interval)
    raise ValueError(f"Unknown frequency: {frequency}")
