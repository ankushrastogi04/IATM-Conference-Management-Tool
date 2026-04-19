from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from conference.models import Conference
from membership.models import Membership
from .models import Session, Speaker, Attendance


@login_required
def conference_schedule(request, slug):
    """Dynamic agenda with filters for tracks and session types."""
    conference = get_object_or_404(Conference, slug=slug)
    sessions = Session.objects.filter(conference=conference, is_published=True).select_related('track').prefetch_related('speakers')

    # Filters
    track_filter = request.GET.get('track')
    type_filter = request.GET.get('type')
    date_filter = request.GET.get('date')

    if track_filter:
        sessions = sessions.filter(track__id=track_filter)
    if type_filter:
        sessions = sessions.filter(session_type=type_filter)
    if date_filter:
        sessions = sessions.filter(start_time__date=date_filter)

    # Group sessions by date
    sessions_by_date = {}
    for session in sessions:
        date_key = session.start_time.date()
        if date_key not in sessions_by_date:
            sessions_by_date[date_key] = []
        sessions_by_date[date_key].append(session)

    # Get unique dates and tracks for filter dropdowns
    all_sessions = Session.objects.filter(conference=conference, is_published=True)
    available_dates = sorted(all_sessions.values_list('start_time__date', flat=True).distinct())
    tracks = conference.tracks.all()
    session_types = Session.SESSION_TYPES

    # Check if user is registered
    is_registered = Membership.objects.filter(user=request.user, conference=conference, is_paid=True).exists()

    context = {
        'conference': conference,
        'sessions_by_date': sessions_by_date,
        'available_dates': available_dates,
        'tracks': tracks,
        'session_types': session_types,
        'track_filter': track_filter,
        'type_filter': type_filter,
        'date_filter': date_filter,
        'is_registered': is_registered,
        'user_timezone': request.GET.get('tz', ''),
    }
    return render(request, 'schedule/conference_schedule.html', context)


@login_required
def speaker_directory(request, slug):
    """Public-facing speaker directory with bios and linked sessions."""
    conference = get_object_or_404(Conference, slug=slug)
    speakers = Speaker.objects.filter(sessions__conference=conference).distinct().prefetch_related('sessions')

    context = {
        'conference': conference,
        'speakers': speakers,
    }
    return render(request, 'schedule/speaker_directory.html', context)


@login_required
def join_session(request, session_id):
    """Gate-kept session join - only for paid registrants. Logs attendance."""
    session = get_object_or_404(Session, id=session_id)
    conference = session.conference

    # Check paid registration
    is_registered = Membership.objects.filter(user=request.user, conference=conference, is_paid=True).exists()
    if not is_registered:
        messages.error(request, "You must be a paid registrant to join this session.")
        return redirect('conference_schedule', slug=conference.slug)

    if not session.zoom_meeting_url:
        messages.info(request, "No virtual link is available for this session.")
        return redirect('conference_schedule', slug=conference.slug)

    # Log attendance
    Attendance.objects.get_or_create(user=request.user, session=session)

    return redirect(session.zoom_meeting_url)


@login_required
def export_schedule_ical(request, slug):
    conference = get_object_or_404(Conference, slug=slug)
    sessions = Session.objects.filter(conference=conference, is_published=True).order_by('start_time')

    from .ical import generate_schedule_ical
    ical_data = generate_schedule_ical(sessions, conference)

    response = HttpResponse(ical_data, content_type='text/calendar')
    response['Content-Disposition'] = f'attachment; filename="{conference.slug}_schedule.ics"'
    return response
