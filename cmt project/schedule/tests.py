from datetime import date, timedelta, datetime
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from conference.models import Conference, Track
from membership.models import Membership
from schedule.models import Speaker, Session, Attendance


class SpeakerModelTest(TestCase):
    """Tests for the Speaker model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='speaker@example.com', password='testpass123',
            first_name='Speaker', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )

    def test_create_speaker(self):
        speaker = Speaker.objects.create(
            first_name='Jane', last_name='Doe',
            email='jane@example.com', bio='A researcher.',
            organization='MIT', title='Professor',
        )
        self.assertEqual(speaker.first_name, 'Jane')
        self.assertEqual(speaker.last_name, 'Doe')
        self.assertEqual(speaker.email, 'jane@example.com')
        self.assertEqual(speaker.organization, 'MIT')

    def test_get_full_name(self):
        speaker = Speaker.objects.create(
            first_name='Jane', last_name='Doe',
        )
        self.assertEqual(speaker.get_full_name(), 'Jane Doe')

    def test_str_representation(self):
        speaker = Speaker.objects.create(
            first_name='Jane', last_name='Doe',
        )
        self.assertEqual(str(speaker), 'Jane Doe')

    def test_user_one_to_one(self):
        speaker = Speaker.objects.create(
            user=self.user, first_name='Speaker', last_name='User',
        )
        self.assertEqual(speaker.user, self.user)
        self.assertEqual(self.user.speaker_profile, speaker)

    def test_user_nullable(self):
        speaker = Speaker.objects.create(
            first_name='External', last_name='Speaker',
        )
        self.assertIsNone(speaker.user)

    def test_optional_fields_blank(self):
        speaker = Speaker.objects.create(
            first_name='Min', last_name='Fields',
        )
        self.assertEqual(speaker.bio, '')
        self.assertFalse(speaker.photo)
        self.assertEqual(speaker.organization, '')
        self.assertEqual(speaker.title, '')
        self.assertEqual(speaker.website, '')
        self.assertEqual(speaker.email, '')

    def test_ordering(self):
        s1 = Speaker.objects.create(first_name='Zara', last_name='Zebra')
        s2 = Speaker.objects.create(first_name='Alice', last_name='Alpha')
        s3 = Speaker.objects.create(first_name='Bob', last_name='Alpha')
        speakers = list(Speaker.objects.all())
        self.assertEqual(speakers[0], s2)  # Alpha, Alice
        self.assertEqual(speakers[1], s3)  # Alpha, Bob
        self.assertEqual(speakers[2], s1)  # Zebra, Zara

    def test_cascade_delete_user(self):
        speaker = Speaker.objects.create(
            user=self.user, first_name='Speaker', last_name='User',
        )
        self.user.delete()
        self.assertEqual(Speaker.objects.count(), 0)


class SessionModelTest(TestCase):
    """Tests for the Session model."""

    def setUp(self):
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.now = timezone.now()

    def _create_session(self, **kwargs):
        defaults = dict(
            conference=self.conference, title='Test Session',
            description='A test session',
            session_type='paper',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
            room='Room 101',
            is_published=True,
        )
        defaults.update(kwargs)
        return Session.objects.create(**defaults)

    def test_create_session(self):
        session = self._create_session()
        self.assertEqual(session.conference, self.conference)
        self.assertEqual(session.title, 'Test Session')
        self.assertEqual(session.session_type, 'paper')
        self.assertTrue(session.is_published)

    def test_str_representation(self):
        session = self._create_session()
        expected = f"Test Session ({session.start_time.strftime('%b %d %H:%M')})"
        self.assertEqual(str(session), expected)

    def test_duration_minutes(self):
        session = self._create_session(
            start_time=self.now,
            end_time=self.now + timedelta(hours=1, minutes=30),
        )
        self.assertEqual(session.duration_minutes, 90)

    def test_duration_minutes_short(self):
        session = self._create_session(
            start_time=self.now,
            end_time=self.now + timedelta(minutes=15),
        )
        self.assertEqual(session.duration_minutes, 15)

    def test_session_types(self):
        for type_val, type_label in Session.SESSION_TYPES:
            session = self._create_session(
                title=f'{type_label} Session',
                session_type=type_val,
            )
            self.assertEqual(session.session_type, type_val)
            session.delete()

    def test_track_nullable(self):
        session = self._create_session(track=None)
        self.assertIsNone(session.track)

    def test_track_set_null_on_delete(self):
        session = self._create_session(track=self.track)
        self.track.delete()
        session.refresh_from_db()
        self.assertIsNone(session.track)

    def test_speakers_many_to_many(self):
        speaker1 = Speaker.objects.create(first_name='Jane', last_name='Doe')
        speaker2 = Speaker.objects.create(first_name='John', last_name='Smith')
        session = self._create_session()
        session.speakers.add(speaker1, speaker2)
        self.assertEqual(session.speakers.count(), 2)
        self.assertIn(speaker1, session.speakers.all())
        self.assertIn(speaker2, session.speakers.all())

    def test_speakers_blank(self):
        session = self._create_session()
        self.assertEqual(session.speakers.count(), 0)

    def test_zoom_fields_blank(self):
        session = self._create_session()
        self.assertEqual(session.zoom_meeting_id, '')
        self.assertEqual(session.zoom_meeting_url, '')
        self.assertEqual(session.zoom_passcode, '')

    def test_zoom_fields_set(self):
        session = self._create_session(
            zoom_meeting_id='123456789',
            zoom_meeting_url='https://zoom.us/j/123456789',
            zoom_passcode='secret123',
        )
        self.assertEqual(session.zoom_meeting_id, '123456789')
        self.assertEqual(session.zoom_meeting_url, 'https://zoom.us/j/123456789')
        self.assertEqual(session.zoom_passcode, 'secret123')

    def test_is_published_default_false(self):
        session = Session.objects.create(
            conference=self.conference, title='Unpublished',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
        )
        self.assertFalse(session.is_published)

    def test_ordering_by_start_time(self):
        s1 = self._create_session(
            title='Later',
            start_time=self.now + timedelta(hours=2),
            end_time=self.now + timedelta(hours=3),
        )
        s2 = self._create_session(
            title='Earlier',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
        )
        sessions = list(Session.objects.filter(conference=self.conference))
        self.assertEqual(sessions[0], s2)
        self.assertEqual(sessions[1], s1)

    def test_created_at_auto(self):
        session = self._create_session()
        self.assertIsNotNone(session.created_at)

    def test_cascade_delete_conference(self):
        self._create_session()
        self.conference.delete()
        self.assertEqual(Session.objects.count(), 0)

    def test_speaker_sessions_reverse_relation(self):
        speaker = Speaker.objects.create(first_name='Jane', last_name='Doe')
        session = self._create_session()
        session.speakers.add(speaker)
        self.assertIn(session, speaker.sessions.all())


class AttendanceModelTest(TestCase):
    """Tests for the Attendance model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='attendee@example.com', password='testpass123',
            first_name='Attendee', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.now = timezone.now()
        self.session = Session.objects.create(
            conference=self.conference, title='Test Session',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
            is_published=True,
        )

    def test_create_attendance(self):
        att = Attendance.objects.create(user=self.user, session=self.session)
        self.assertEqual(att.user, self.user)
        self.assertEqual(att.session, self.session)
        self.assertIsNotNone(att.joined_at)

    def test_str_representation(self):
        att = Attendance.objects.create(user=self.user, session=self.session)
        expected = f"{self.user.email} - {self.session.title}"
        self.assertEqual(str(att), expected)

    def test_unique_together_user_session(self):
        Attendance.objects.create(user=self.user, session=self.session)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Attendance.objects.create(user=self.user, session=self.session)

    def test_multiple_users_same_session(self):
        user2 = CustomUser.objects.create_user(
            email='user2@example.com', password='testpass123',
            first_name='User', last_name='Two', country='US',
            organization='Org', phone='2222222222', occupation='faculty',
        )
        Attendance.objects.create(user=self.user, session=self.session)
        Attendance.objects.create(user=user2, session=self.session)
        self.assertEqual(Attendance.objects.filter(session=self.session).count(), 2)

    def test_same_user_multiple_sessions(self):
        session2 = Session.objects.create(
            conference=self.conference, title='Session 2',
            start_time=self.now + timedelta(hours=2),
            end_time=self.now + timedelta(hours=3),
            is_published=True,
        )
        Attendance.objects.create(user=self.user, session=self.session)
        Attendance.objects.create(user=self.user, session=session2)
        self.assertEqual(Attendance.objects.filter(user=self.user).count(), 2)

    def test_cascade_delete_user(self):
        Attendance.objects.create(user=self.user, session=self.session)
        self.user.delete()
        self.assertEqual(Attendance.objects.count(), 0)

    def test_cascade_delete_session(self):
        Attendance.objects.create(user=self.user, session=self.session)
        self.session.delete()
        self.assertEqual(Attendance.objects.count(), 0)

    def test_reverse_relation_user(self):
        att = Attendance.objects.create(user=self.user, session=self.session)
        self.assertIn(att, self.user.attendances.all())

    def test_reverse_relation_session(self):
        att = Attendance.objects.create(user=self.user, session=self.session)
        self.assertIn(att, self.session.attendances.all())


class ConferenceScheduleViewTest(TestCase):
    """Tests for conference_schedule view."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='user@example.com', password='testpass123',
            first_name='Test', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.track2 = Track.objects.create(conference=self.conference, name='ML')
        self.membership = Membership.objects.create(
            user=self.user, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.now = timezone.now()
        self.session1 = Session.objects.create(
            conference=self.conference, track=self.track,
            title='AI Keynote', session_type='keynote',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
            room='Main Hall', is_published=True,
        )
        self.session2 = Session.objects.create(
            conference=self.conference, track=self.track2,
            title='ML Workshop', session_type='workshop',
            start_time=self.now + timedelta(hours=2),
            end_time=self.now + timedelta(hours=4),
            room='Room 201', is_published=True,
        )
        self.unpublished_session = Session.objects.create(
            conference=self.conference, track=self.track,
            title='Draft Session', session_type='paper',
            start_time=self.now + timedelta(hours=5),
            end_time=self.now + timedelta(hours=6),
            is_published=False,
        )

    def _login(self):
        self.client.login(email=self.user.email, password='testpass123')

    def test_requires_login(self):
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_schedule_accessible(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['conference'], self.conference)

    def test_schedule_only_published_sessions(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        all_sessions = []
        for sessions in resp.context['sessions_by_date'].values():
            all_sessions.extend(sessions)
        self.assertIn(self.session1, all_sessions)
        self.assertIn(self.session2, all_sessions)
        self.assertNotIn(self.unpublished_session, all_sessions)

    def test_schedule_grouped_by_date(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        sessions_by_date = resp.context['sessions_by_date']
        for date_key, sessions in sessions_by_date.items():
            for session in sessions:
                self.assertEqual(session.start_time.date(), date_key)

    def test_filter_by_track(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url, {'track': self.track.pk})
        all_sessions = []
        for sessions in resp.context['sessions_by_date'].values():
            all_sessions.extend(sessions)
        self.assertIn(self.session1, all_sessions)
        self.assertNotIn(self.session2, all_sessions)

    def test_filter_by_type(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url, {'type': 'workshop'})
        all_sessions = []
        for sessions in resp.context['sessions_by_date'].values():
            all_sessions.extend(sessions)
        self.assertIn(self.session2, all_sessions)
        self.assertNotIn(self.session1, all_sessions)

    def test_filter_by_date(self):
        self._login()
        target_date = self.session1.start_time.date().isoformat()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url, {'date': target_date})
        all_sessions = []
        for sessions in resp.context['sessions_by_date'].values():
            all_sessions.extend(sessions)
        for session in all_sessions:
            self.assertEqual(session.start_time.date().isoformat(), target_date)

    def test_is_registered_context(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertTrue(resp.context['is_registered'])

    def test_not_registered_context(self):
        unpaid_user = CustomUser.objects.create_user(
            email='unpaid@example.com', password='testpass123',
            first_name='Unpaid', last_name='User', country='US',
            organization='Org', phone='5555555555', occupation='faculty',
        )
        Membership.objects.create(
            user=unpaid_user, conference=self.conference,
            role1='Author', is_paid=False,
        )
        self.client.login(email=unpaid_user.email, password='testpass123')
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertFalse(resp.context['is_registered'])

    def test_context_contains_tracks(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertIn(self.track, resp.context['tracks'])
        self.assertIn(self.track2, resp.context['tracks'])

    def test_context_contains_session_types(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.context['session_types'], Session.SESSION_TYPES)

    def test_schedule_404_invalid_slug(self):
        self._login()
        url = reverse('conference_schedule', args=['nonexistent-slug'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_combined_filters(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        target_date = self.session1.start_time.date().isoformat()
        resp = self.client.get(url, {
            'track': self.track.pk,
            'type': 'keynote',
            'date': target_date,
        })
        all_sessions = []
        for sessions in resp.context['sessions_by_date'].values():
            all_sessions.extend(sessions)
        self.assertIn(self.session1, all_sessions)
        self.assertNotIn(self.session2, all_sessions)

    def test_no_sessions_match_filter(self):
        self._login()
        url = reverse('conference_schedule', args=[self.conference.slug])
        resp = self.client.get(url, {'type': 'break'})
        all_sessions = []
        for sessions in resp.context['sessions_by_date'].values():
            all_sessions.extend(sessions)
        self.assertEqual(len(all_sessions), 0)


class SpeakerDirectoryViewTest(TestCase):
    """Tests for speaker_directory view."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='user@example.com', password='testpass123',
            first_name='Test', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.now = timezone.now()
        self.speaker1 = Speaker.objects.create(
            first_name='Jane', last_name='Doe',
            bio='Expert in AI', organization='MIT',
        )
        self.speaker2 = Speaker.objects.create(
            first_name='John', last_name='Smith',
            bio='Expert in ML', organization='Stanford',
        )
        self.session = Session.objects.create(
            conference=self.conference, title='Keynote',
            session_type='keynote',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
            is_published=True,
        )
        self.session.speakers.add(self.speaker1)

    def _login(self):
        self.client.login(email=self.user.email, password='testpass123')

    def test_requires_login(self):
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_speaker_directory_accessible(self):
        self._login()
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_shows_speakers_with_sessions_at_conference(self):
        self._login()
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertIn(self.speaker1, resp.context['speakers'])

    def test_excludes_speakers_without_sessions_at_conference(self):
        self._login()
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertNotIn(self.speaker2, resp.context['speakers'])

    def test_speaker_from_other_conference_not_shown(self):
        other_conf = Conference.objects.create(
            conference_name='Other Conf', conference_description='Other',
            start_date=date.today() + timedelta(days=60),
            end_date=date.today() + timedelta(days=62),
            location='Other City',
        )
        other_session = Session.objects.create(
            conference=other_conf, title='Other Talk',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
            is_published=True,
        )
        other_session.speakers.add(self.speaker2)
        self._login()
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertNotIn(self.speaker2, resp.context['speakers'])

    def test_speaker_directory_404_invalid_slug(self):
        self._login()
        url = reverse('speaker_directory', args=['nonexistent-slug'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_context_has_conference(self):
        self._login()
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.context['conference'], self.conference)

    def test_speaker_distinct_with_multiple_sessions(self):
        session2 = Session.objects.create(
            conference=self.conference, title='Workshop',
            session_type='workshop',
            start_time=self.now + timedelta(hours=2),
            end_time=self.now + timedelta(hours=3),
            is_published=True,
        )
        session2.speakers.add(self.speaker1)
        self._login()
        url = reverse('speaker_directory', args=[self.conference.slug])
        resp = self.client.get(url)
        speaker_list = list(resp.context['speakers'])
        self.assertEqual(speaker_list.count(self.speaker1), 1)


class JoinSessionViewTest(TestCase):
    """Tests for join_session view."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='user@example.com', password='testpass123',
            first_name='Test', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.unpaid_user = CustomUser.objects.create_user(
            email='unpaid@example.com', password='testpass123',
            first_name='Unpaid', last_name='User', country='US',
            organization='TestOrg', phone='2222222222', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.membership = Membership.objects.create(
            user=self.user, conference=self.conference,
            role1='Author', is_paid=True,
        )
        Membership.objects.create(
            user=self.unpaid_user, conference=self.conference,
            role1='Author', is_paid=False,
        )
        self.now = timezone.now()
        self.session_with_zoom = Session.objects.create(
            conference=self.conference, title='Virtual Session',
            session_type='paper',
            start_time=self.now,
            end_time=self.now + timedelta(hours=1),
            zoom_meeting_url='https://zoom.us/j/123456789',
            zoom_passcode='abc123',
            is_published=True,
        )
        self.session_no_zoom = Session.objects.create(
            conference=self.conference, title='In-Person Session',
            session_type='paper',
            start_time=self.now + timedelta(hours=2),
            end_time=self.now + timedelta(hours=3),
            room='Room 101',
            is_published=True,
        )

    def _login(self, user=None):
        u = user or self.user
        self.client.login(email=u.email, password='testpass123')

    def test_requires_login(self):
        url = reverse('join_session', args=[self.session_with_zoom.pk])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_join_session_paid_user_redirects_to_zoom(self):
        self._login()
        url = reverse('join_session', args=[self.session_with_zoom.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, 'https://zoom.us/j/123456789')

    def test_join_session_creates_attendance(self):
        self._login()
        url = reverse('join_session', args=[self.session_with_zoom.pk])
        self.client.get(url)
        self.assertEqual(Attendance.objects.count(), 1)
        att = Attendance.objects.first()
        self.assertEqual(att.user, self.user)
        self.assertEqual(att.session, self.session_with_zoom)

    def test_join_session_idempotent_attendance(self):
        self._login()
        url = reverse('join_session', args=[self.session_with_zoom.pk])
        self.client.get(url)
        self.client.get(url)
        self.assertEqual(Attendance.objects.filter(
            user=self.user, session=self.session_with_zoom,
        ).count(), 1)

    def test_join_session_unpaid_user_rejected(self):
        self._login(self.unpaid_user)
        url = reverse('join_session', args=[self.session_with_zoom.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.conference.slug, resp.url)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_join_session_no_zoom_url(self):
        self._login()
        url = reverse('join_session', args=[self.session_no_zoom.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(self.conference.slug, resp.url)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_join_session_no_membership(self):
        unregistered = CustomUser.objects.create_user(
            email='noreg@example.com', password='testpass123',
            first_name='No', last_name='Reg', country='US',
            organization='Org', phone='3333333333', occupation='faculty',
        )
        self._login(unregistered)
        url = reverse('join_session', args=[self.session_with_zoom.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Attendance.objects.count(), 0)

    def test_join_session_404_nonexistent(self):
        self._login()
        url = reverse('join_session', args=[99999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_join_session_different_sessions_different_attendance(self):
        session2 = Session.objects.create(
            conference=self.conference, title='Another Virtual',
            session_type='workshop',
            start_time=self.now + timedelta(hours=4),
            end_time=self.now + timedelta(hours=5),
            zoom_meeting_url='https://zoom.us/j/987654321',
            is_published=True,
        )
        self._login()
        self.client.get(reverse('join_session', args=[self.session_with_zoom.pk]))
        self.client.get(reverse('join_session', args=[session2.pk]))
        self.assertEqual(Attendance.objects.filter(user=self.user).count(), 2)
