"""
Working time for SLA targets: adds "4 working hours" or "3 working days" to a moment, skipping evenings,
weekends and holidays.

The working week comes from settings (SLA_WORKING_WEEKDAYS, SLA_WORKDAY_START, SLA_WORKDAY_END), by default
Monday to Friday, 08:00 to 17:00, in the site's time zone. Holidays are the dates in the Holiday table
(managed in the admin). One working day is one full working day's length of working time, so 1 working day
from 10:00 on a Monday is 10:00 on Tuesday, and from 18:00 on a Friday it's 17:00 the next Monday.
"""
from datetime import datetime, time, timedelta

from django.conf import settings
from django.utils import timezone


def _hours_setting(name, default):
    return time.fromisoformat(getattr(settings, name, default))


def working_week():
    days = tuple(getattr(settings, 'SLA_WORKING_WEEKDAYS', (0, 1, 2, 3, 4)))  # Monday is 0
    return days, _hours_setting('SLA_WORKDAY_START', '08:00'), _hours_setting('SLA_WORKDAY_END', '17:00')


def workday_hours():
    _, start, end = working_week()
    return (datetime.combine(datetime.min, end) - datetime.combine(datetime.min, start)).total_seconds() / 3600


def _holidays():
    from .models import Holiday
    return set(Holiday.objects.values_list('date', flat=True))


def add_working_hours(moment, hours, holidays=None):
    """The moment `hours` of working time after `moment`."""
    days, day_start, day_end = working_week()
    holidays = _holidays() if holidays is None else holidays
    tz = timezone.get_current_timezone()
    cursor = timezone.localtime(moment, tz)
    remaining = timedelta(hours=hours)

    def next_morning(dt):
        return datetime.combine(dt.date() + timedelta(days=1), day_start, tzinfo=tz)

    for _ in range(3660):  # ten years of days, so a misconfiguration can't loop for ever
        if cursor.weekday() not in days or cursor.date() in holidays or cursor.time() >= day_end:
            cursor = next_morning(cursor)
            continue
        if cursor.time() < day_start:
            cursor = datetime.combine(cursor.date(), day_start, tzinfo=tz)
        available = datetime.combine(cursor.date(), day_end, tzinfo=tz) - cursor
        if remaining <= available:
            return cursor + remaining
        remaining -= available
        cursor = next_morning(cursor)
    raise ValueError('No working days found: check SLA_WORKING_WEEKDAYS and the holidays.')


def add_target(moment, amount, unit, holidays=None):
    """`moment` plus an SLA target: round-the-clock hours, working hours or working days."""
    if unit == 'hours':
        return moment + timedelta(hours=amount)
    if unit == 'working_hours':
        return add_working_hours(moment, amount, holidays)
    if unit == 'working_days':
        return add_working_hours(moment, amount * workday_hours(), holidays)
    raise ValueError(f'Unknown SLA unit: {unit}')
