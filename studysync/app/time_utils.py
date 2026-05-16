from datetime import datetime, timedelta, timezone


APP_TIMEZONE = timezone(timedelta(hours=8))


def now_app_time():
    """Return the current application time in UTC+8."""
    return datetime.now(APP_TIMEZONE)


def today_app_date():
    """Return today's date in UTC+8."""
    return now_app_time().date()


def parse_date_as_app_time(date_str):
    """Parse a YYYY-MM-DD date string as midnight in UTC+8."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=APP_TIMEZONE)


def to_app_time(value):
    """Convert a datetime value to UTC+8 for display or comparison."""
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=APP_TIMEZONE)

    return value.astimezone(APP_TIMEZONE)
