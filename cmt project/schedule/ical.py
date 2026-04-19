from icalendar import Calendar, Event
from django.utils import timezone


def generate_schedule_ical(sessions, conference):
    cal = Calendar()
    cal.add('prodid', '-//IATM Conference//EN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', conference.conference_name)

    for session in sessions:
        event = Event()
        event.add('summary', session.title)
        event.add('dtstart', session.start_time)
        event.add('dtend', session.end_time)
        event.add('description', session.description or '')
        if session.room:
            event.add('location', session.room)
        event.add('uid', f'session-{session.pk}@iatm.us')
        cal.add_component(event)

    return cal.to_ical()
