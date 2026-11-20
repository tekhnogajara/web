import pytz
from django.utils import timezone

def utc_to_ist(utc_dt):
    """
    Convert a UTC datetime to Indian Standard Time (IST, Asia/Kolkata).
    Returns None if input is None.
    """
    if not utc_dt:
        return None
    if utc_dt.tzinfo is None:
        # Assume naive datetime is UTC
        utc_dt = pytz.UTC.localize(utc_dt)
    ist = pytz.timezone('Asia/Kolkata')
    return utc_dt.astimezone(ist)