from datetime import datetime, timedelta, timezone


APP_TIMEZONE = timezone(timedelta(hours=8))


def now_app_time():
    """
    Return the current application time in UTC+8 as a naive datetime.

    SQLite does not reliably preserve timezone-aware datetime values.
    Storing and comparing app timestamps as UTC+8 naive datetimes avoids
    mixing offset-aware and offset-naive datetime objects.
    """
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)


def today_app_date():
    """Return today's date in UTC+8."""
    return now_app_time().date()


def parse_date_as_app_time(date_str):
    """
    Parse a YYYY-MM-DD date string as midnight in application time.

    The returned value is a naive UTC+8 datetime for SQLite consistency.
    """
    return datetime.strptime(date_str, "%Y-%m-%d")


def to_app_time(value):
    """
    Normalize a datetime value to application time.

    - Naive values are treated as already being in app time.
    - Aware values are converted to UTC+8 and returned as naive values.

    This avoids TypeError caused by comparing aware and naive datetimes.
    """
    if value is None:
        return None

    if value.tzinfo is None:
        return value

    return value.astimezone(APP_TIMEZONE).replace(tzinfo=None)
