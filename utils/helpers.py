from datetime import datetime
import pytz
from config import DEFAULT_TIMEZONE

def get_current_time():
    return datetime.now(pytz.timezone(DEFAULT_TIMEZONE))

def format_datetime(dt):
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def validate_date_format(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        return True
    except ValueError:
        return False
