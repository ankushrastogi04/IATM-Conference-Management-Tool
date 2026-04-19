from django.db import models
from django.conf import settings
from conference.models import Conference, Track


class Room(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    location_description = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = ('conference', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.conference.conference_name})"


class Speaker(models.Model):
    """Speaker profile with bio, photo, and linked sessions."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='speaker_profile')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='speakers/', blank=True, null=True)
    organization = models.CharField(max_length=200, blank=True)
    title = models.CharField(max_length=200, blank=True, help_text="e.g., Professor, Researcher")
    website = models.URLField(blank=True)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.get_full_name()

    class Meta:
        ordering = ['last_name', 'first_name']


class Session(models.Model):
    """A scheduled session within a conference (talk, workshop, panel, etc.)."""
    SESSION_TYPES = [
        ('keynote', 'Keynote'),
        ('paper', 'Paper Presentation'),
        ('workshop', 'Workshop'),
        ('panel', 'Panel Discussion'),
        ('break', 'Break'),
        ('social', 'Social Event'),
        ('other', 'Other'),
    ]

    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='sessions')
    track = models.ForeignKey(Track, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='paper')
    speakers = models.ManyToManyField(Speaker, blank=True, related_name='sessions')

    # Scheduling
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    room = models.CharField(max_length=100, blank=True)
    venue = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')

    # Virtual meeting
    zoom_meeting_id = models.CharField(max_length=100, blank=True)
    zoom_meeting_url = models.URLField(blank=True)
    zoom_passcode = models.CharField(max_length=50, blank=True)

    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['start_time']

    def __str__(self):
        return f"{self.title} ({self.start_time.strftime('%b %d %H:%M')})"

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.venue:
            overlapping = Session.objects.filter(
                venue=self.venue,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError(f"Room '{self.venue.name}' has a conflicting session: {overlapping.first().title}")
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("End time must be after start time.")

    @property
    def duration_minutes(self):
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)


class Attendance(models.Model):
    """Track user attendance at sessions (for certificate eligibility)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='attendances')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='attendances')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'session')

    def __str__(self):
        return f"{self.user.email} - {self.session.title}"
