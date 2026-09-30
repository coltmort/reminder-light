"""Calendar view for Reminder Light schedules."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CALENDAR_EVENT_DURATION_MINUTES, WEEKDAYS
from .coordinator import ReminderLightCoordinator
from .models import ReminderDefinition

_WEEKDAY_LABELS = {
    "mon": "Mon",
    "tue": "Tue",
    "wed": "Wed",
    "thu": "Thu",
    "fri": "Fri",
    "sat": "Sat",
    "sun": "Sun",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the combined reminder calendar."""

    async_add_entities([ReminderScheduleCalendar(entry.runtime_data)])


class ReminderScheduleCalendar(
    CoordinatorEntity[ReminderLightCoordinator], CalendarEntity
):
    """Show every configured reminder in Home Assistant's calendar UI."""

    _attr_has_entity_name = False
    _attr_name = "Reminder Light schedule"
    _attr_initial_color = "#00AEEF"

    def __init__(self, coordinator: ReminderLightCoordinator) -> None:
        """Initialize the calendar."""

        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_schedule"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next scheduled reminder."""

        now = dt_util.now()
        events = self._events_between(
            now - timedelta(minutes=CALENDAR_EVENT_DURATION_MINUTES),
            now + timedelta(days=8),
        )
        return next((event for event in events if event.end > now), None)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return expanded reminder occurrences for a calendar range."""

        return self._events_between(start_date, end_date)

    def _events_between(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Expand weekly schedules into individual calendar events."""

        events: list[CalendarEvent] = []
        day = start_date.date() - timedelta(days=1)
        final_day = end_date.date()

        while day <= final_day:
            weekday = WEEKDAYS[day.weekday()]
            for reminder in self.coordinator.data.reminders.values():
                if not reminder.enabled or weekday not in reminder.weekdays:
                    continue
                events.extend(
                    self._events_for_reminder_on_date(
                        reminder, day, start_date, end_date
                    )
                )
            day += timedelta(days=1)

        return sorted(events, key=lambda event: event.start)

    def _events_for_reminder_on_date(
        self,
        reminder: ReminderDefinition,
        day: date,
        range_start: datetime,
        range_end: datetime,
    ) -> list[CalendarEvent]:
        """Create one event for each reminder time on a date."""

        events: list[CalendarEvent] = []
        state = self.coordinator.state(reminder.reminder_id)
        schedule = ", ".join(
            _WEEKDAY_LABELS[weekday]
            for weekday in WEEKDAYS
            if weekday in reminder.weekdays
        )
        status = "Due" if state.due else "Scheduled"

        for configured_time in reminder.times:
            event_start = datetime.combine(
                day,
                time.fromisoformat(configured_time),
                tzinfo=range_start.tzinfo,
            )
            event_end = event_start + timedelta(
                minutes=CALENDAR_EVENT_DURATION_MINUTES
            )
            if event_end <= range_start or event_start >= range_end:
                continue
            events.append(
                CalendarEvent(
                    start=event_start,
                    end=event_end,
                    summary=reminder.name,
                    description=(
                        f"{status}. Repeats {schedule} at "
                        f"{', '.join(value[:5] for value in reminder.times)}."
                    ),
                    uid=f"{reminder.reminder_id}:{event_start.isoformat()}",
                )
            )
        return events
