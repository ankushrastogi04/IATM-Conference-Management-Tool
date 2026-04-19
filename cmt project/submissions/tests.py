from datetime import date, timedelta
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from conference.models import Conference, Track
from membership.models import Membership
from review.models import Review
from submissions.forms import SubmissionForm
from submissions.models import Submissions


class SubmissionsModelTest(TestCase):
    """Tests for the Submissions model."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.membership = Membership.objects.create(
            user=self.user, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.test_file = SimpleUploadedFile(
            'test.pdf', b'%PDF-1.4 test content', content_type='application/pdf',
        )

    def _create_submission(self, **kwargs):
        defaults = dict(
            membership=self.membership, track=self.track,
            paper_title='Test Paper', file=self.test_file,
        )
        defaults.update(kwargs)
        return Submissions.objects.create(**defaults)

    def test_create_submission(self):
        sub = self._create_submission()
        self.assertEqual(sub.paper_title, 'Test Paper')
        self.assertEqual(sub.status, 'PENDING')
        self.assertEqual(sub.membership, self.membership)
        self.assertEqual(sub.track, self.track)
        self.assertIsNotNone(sub.submission_date)

    def test_str_representation(self):
        sub = self._create_submission()
        expected = f"Test Paper - {self.user.email} ({sub.submission_date.date()})"
        self.assertEqual(str(sub), expected)

    def test_default_status_is_pending(self):
        sub = self._create_submission()
        self.assertEqual(sub.status, Submissions.StatusChoices.PENDING)

    def test_unique_together_membership_paper_title(self):
        self._create_submission()
        with self.assertRaises(IntegrityError):
            Submissions.objects.create(
                membership=self.membership, track=self.track,
                paper_title='Test Paper',
                file=SimpleUploadedFile('dup.pdf', b'%PDF-1.4', content_type='application/pdf'),
            )

    def test_different_titles_same_membership(self):
        self._create_submission(paper_title='Paper A')
        sub2 = self._create_submission(
            paper_title='Paper B',
            file=SimpleUploadedFile('b.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        self.assertEqual(Submissions.objects.count(), 2)
        self.assertEqual(sub2.paper_title, 'Paper B')

    def test_co_authors_nullable(self):
        sub = self._create_submission()
        self.assertIsNone(sub.co_author1)
        self.assertIsNone(sub.co_author2)
        self.assertIsNone(sub.co_author3)

    def test_co_authors_assigned(self):
        co1 = CustomUser.objects.create_user(
            email='co1@example.com', password='pass123',
            first_name='Co', last_name='One', country='US',
            organization='Org', phone='1111111111', occupation='faculty',
        )
        co2 = CustomUser.objects.create_user(
            email='co2@example.com', password='pass123',
            first_name='Co', last_name='Two', country='US',
            organization='Org', phone='2222222222', occupation='faculty',
        )
        sub = self._create_submission(co_author1=co1, co_author2=co2)
        self.assertEqual(sub.co_author1, co1)
        self.assertEqual(sub.co_author2, co2)
        self.assertIsNone(sub.co_author3)

    def test_ordering_by_submission_date_desc(self):
        s1 = self._create_submission(paper_title='First')
        s2 = self._create_submission(
            paper_title='Second',
            file=SimpleUploadedFile('s2.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        subs = list(Submissions.objects.all())
        self.assertEqual(subs[0], s2)
        self.assertEqual(subs[1], s1)

    def test_file_upload_path(self):
        sub = self._create_submission()
        self.assertTrue(sub.file.name.startswith('submissions/'))

    def test_cascade_delete_membership(self):
        self._create_submission()
        self.assertEqual(Submissions.objects.count(), 1)
        self.membership.delete()
        self.assertEqual(Submissions.objects.count(), 0)

    def test_cascade_delete_track(self):
        self._create_submission()
        self.track.delete()
        self.assertEqual(Submissions.objects.count(), 0)

    def test_co_author_set_null_on_delete(self):
        co = CustomUser.objects.create_user(
            email='coauthor@example.com', password='pass123',
            first_name='Co', last_name='Author', country='US',
            organization='Org', phone='3333333333', occupation='faculty',
        )
        sub = self._create_submission(co_author1=co)
        co.delete()
        sub.refresh_from_db()
        self.assertIsNone(sub.co_author1)


class UpdateStatusFromReviewsTest(TestCase):
    """Tests for Submissions.update_status_from_reviews()."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.reviewer1 = CustomUser.objects.create_user(
            email='rev1@example.com', password='testpass123',
            first_name='Rev', last_name='One', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.reviewer2 = CustomUser.objects.create_user(
            email='rev2@example.com', password='testpass123',
            first_name='Rev', last_name='Two', country='US',
            organization='TestOrg', phone='2222222222', occupation='faculty',
        )
        self.reviewer3 = CustomUser.objects.create_user(
            email='rev3@example.com', password='testpass123',
            first_name='Rev', last_name='Three', country='US',
            organization='TestOrg', phone='3333333333', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.membership = Membership.objects.create(
            user=self.user, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.membership, track=self.track,
            paper_title='Status Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    def _create_review(self, reviewer, recommendation=None, is_submitted=False):
        return Review.objects.create(
            submission=self.submission, reviewer=reviewer,
            recommendation=recommendation, is_submitted=is_submitted,
            comment='Test comment',
        )

    @patch('submissions.emails.send_submission_decision')
    def test_no_reviews_sets_pending(self, mock_email):
        self.submission.status = 'ACCEPTED'
        self.submission.save()
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'PENDING')

    @patch('submissions.emails.send_submission_decision')
    def test_unsubmitted_reviews_ignored(self, mock_email):
        self._create_review(self.reviewer1, recommendation='ACCEPT', is_submitted=False)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'PENDING')

    @patch('submissions.emails.send_submission_decision')
    def test_all_accept_sets_accepted(self, mock_email):
        self._create_review(self.reviewer1, recommendation='ACCEPT', is_submitted=True)
        self._create_review(self.reviewer2, recommendation='ACCEPT', is_submitted=True)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'ACCEPTED')

    @patch('submissions.emails.send_submission_decision')
    def test_single_accept_sets_accepted(self, mock_email):
        self._create_review(self.reviewer1, recommendation='ACCEPT', is_submitted=True)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'ACCEPTED')

    @patch('submissions.emails.send_submission_decision')
    def test_any_reject_overrides_to_rejected(self, mock_email):
        self._create_review(self.reviewer1, recommendation='ACCEPT', is_submitted=True)
        self._create_review(self.reviewer2, recommendation='REJECT', is_submitted=True)
        self._create_review(self.reviewer3, recommendation='ACCEPT', is_submitted=True)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'REJECTED')

    @patch('submissions.emails.send_submission_decision')
    def test_revise_overrides_accept(self, mock_email):
        self._create_review(self.reviewer1, recommendation='ACCEPT', is_submitted=True)
        self._create_review(self.reviewer2, recommendation='REVISE', is_submitted=True)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'REVISION')

    @patch('submissions.emails.send_submission_decision')
    def test_reject_overrides_revise(self, mock_email):
        self._create_review(self.reviewer1, recommendation='REVISE', is_submitted=True)
        self._create_review(self.reviewer2, recommendation='REJECT', is_submitted=True)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'REJECTED')

    @patch('submissions.emails.send_submission_decision')
    def test_null_recommendation_excluded(self, mock_email):
        self._create_review(self.reviewer1, recommendation=None, is_submitted=True)
        self.submission.update_status_from_reviews()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'PENDING')

    @patch('submissions.emails.send_submission_decision')
    def test_email_sent_on_status_change_to_accepted(self, mock_email):
        self._create_review(self.reviewer1, recommendation='ACCEPT', is_submitted=True)
        self.submission.update_status_from_reviews()
        mock_email.assert_called_once_with(self.submission)

    @patch('submissions.emails.send_submission_decision')
    def test_email_not_sent_when_status_unchanged(self, mock_email):
        """If status stays PENDING (no submitted reviews), no email is sent."""
        self.submission.update_status_from_reviews()
        mock_email.assert_not_called()


class SubmissionFormTest(TestCase):
    """Tests for the SubmissionForm."""

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.co_author = CustomUser.objects.create_user(
            email='coauthor@example.com', password='testpass123',
            first_name='Co', last_name='Author', country='US',
            organization='TestOrg', phone='9999999999', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.membership = Membership.objects.create(
            user=self.user, conference=self.conference,
            role1='Author', is_paid=True,
        )

    def _valid_form_data(self, **overrides):
        data = {
            'paper_title': 'A Great Paper',
            'track': self.track.pk,
            'co_author_email_1': '',
            'co_author_email_2': '',
            'co_author_email_3': '',
        }
        data.update(overrides)
        return data

    def _pdf_file(self, name='test.pdf', size=None):
        content = b'%PDF-1.4 test content'
        if size:
            content = b'%PDF-1.4 ' + b'x' * size
        return SimpleUploadedFile(name, content, content_type='application/pdf')

    def test_valid_form(self):
        form = SubmissionForm(
            data=self._valid_form_data(),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_track_queryset_filtered_by_conference(self):
        other_conf = Conference.objects.create(
            conference_name='Other Conf', conference_description='Other',
            start_date=date.today() + timedelta(days=60),
            end_date=date.today() + timedelta(days=62),
            location='Other City',
        )
        other_track = Track.objects.create(conference=other_conf, name='ML')
        form = SubmissionForm(conference=self.conference)
        qs = form.fields['track'].queryset
        self.assertIn(self.track, qs)
        self.assertNotIn(other_track, qs)

    def test_file_required_on_create(self):
        form = SubmissionForm(
            data=self._valid_form_data(),
            files={},
            conference=self.conference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_non_pdf_rejected(self):
        form = SubmissionForm(
            data=self._valid_form_data(),
            files={'file': SimpleUploadedFile('test.docx', b'not a pdf', content_type='application/msword')},
            conference=self.conference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_file_over_10mb_rejected(self):
        big_file = self._pdf_file(size=11 * 1024 * 1024)
        form = SubmissionForm(
            data=self._valid_form_data(),
            files={'file': big_file},
            conference=self.conference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_valid_co_author_email(self):
        form = SubmissionForm(
            data=self._valid_form_data(co_author_email_1=self.co_author.email),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.membership = self.membership
        instance.save()
        self.assertEqual(instance.co_author1, self.co_author)

    def test_invalid_co_author_email_unregistered(self):
        form = SubmissionForm(
            data=self._valid_form_data(co_author_email_1='nobody@example.com'),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('co_author_email_1', form.errors)

    def test_paper_title_required(self):
        form = SubmissionForm(
            data=self._valid_form_data(paper_title=''),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('paper_title', form.errors)

    def test_track_required(self):
        form = SubmissionForm(
            data=self._valid_form_data(track=''),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('track', form.errors)

    def test_save_sets_pending_status_on_new(self):
        form = SubmissionForm(
            data=self._valid_form_data(),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertTrue(form.is_valid())
        instance = form.save(commit=False)
        instance.membership = self.membership
        instance.save()
        self.assertEqual(instance.status, 'PENDING')

    def test_file_not_required_on_edit(self):
        sub = Submissions.objects.create(
            membership=self.membership, track=self.track,
            paper_title='Original',
            file=SimpleUploadedFile('orig.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        form = SubmissionForm(
            data=self._valid_form_data(paper_title='Updated Title'),
            files={},
            instance=sub,
            conference=self.conference,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_multiple_co_authors(self):
        co2 = CustomUser.objects.create_user(
            email='co2@example.com', password='pass123',
            first_name='Co', last_name='Two', country='US',
            organization='Org', phone='5555555555', occupation='faculty',
        )
        form = SubmissionForm(
            data=self._valid_form_data(
                co_author_email_1=self.co_author.email,
                co_author_email_2=co2.email,
            ),
            files={'file': self._pdf_file()},
            conference=self.conference,
        )
        self.assertTrue(form.is_valid(), form.errors)
        instance = form.save(commit=False)
        instance.membership = self.membership
        instance.save()
        self.assertEqual(instance.co_author1, self.co_author)
        self.assertEqual(instance.co_author2, co2)
        self.assertIsNone(instance.co_author3)


class SubmissionViewTest(TestCase):
    """Tests for submission views."""

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.other_user = CustomUser.objects.create_user(
            email='other@example.com', password='testpass123',
            first_name='Other', last_name='User', country='US',
            organization='TestOrg', phone='0000000000', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
            submission_deadline=timezone.now() + timedelta(days=20),
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.membership = Membership.objects.create(
            user=self.user, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.test_file = SimpleUploadedFile(
            'test.pdf', b'%PDF-1.4 test content', content_type='application/pdf',
        )

    def _login(self, user=None):
        u = user or self.user
        self.client.login(email=u.email, password='testpass123')

    def _create_submission(self, **kwargs):
        defaults = dict(
            membership=self.membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('v.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        defaults.update(kwargs)
        return Submissions.objects.create(**defaults)

    # --- create_submission ---

    @patch('submissions.views.send_submission_confirmation')
    def test_create_submission_get(self, mock_email):
        self._login()
        url = reverse('create_submission', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)

    @patch('submissions.views.send_submission_confirmation')
    def test_create_submission_post_success(self, mock_email):
        self._login()
        url = reverse('create_submission', args=[self.conference.slug])
        resp = self.client.post(url, {
            'paper_title': 'New Paper',
            'track': self.track.pk,
            'file': SimpleUploadedFile('new.pdf', b'%PDF-1.4 content', content_type='application/pdf'),
            'co_author_email_1': '',
            'co_author_email_2': '',
            'co_author_email_3': '',
        })
        self.assertEqual(Submissions.objects.count(), 1)
        sub = Submissions.objects.first()
        self.assertRedirects(resp, reverse('submission_detail', args=[sub.pk]))
        mock_email.assert_called_once()

    def test_create_submission_requires_login(self):
        url = reverse('create_submission', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)
        self.assertIn('/accounts/', resp.url)

    def test_create_submission_requires_paid_membership(self):
        unpaid_user = CustomUser.objects.create_user(
            email='unpaid@example.com', password='testpass123',
            first_name='Unpaid', last_name='User', country='US',
            organization='Org', phone='7777777777', occupation='faculty',
        )
        Membership.objects.create(
            user=unpaid_user, conference=self.conference,
            role1='Author', is_paid=False,
        )
        self._login(unpaid_user)
        url = reverse('create_submission', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_create_submission_non_member_redirected(self):
        non_member = CustomUser.objects.create_user(
            email='nonmember@example.com', password='testpass123',
            first_name='Non', last_name='Member', country='US',
            organization='Org', phone='6666666666', occupation='faculty',
        )
        Membership.objects.create(
            user=non_member, conference=self.conference,
            role1='Author', is_paid=True,
        )
        other_conf = Conference.objects.create(
            conference_name='Other', conference_description='Desc',
            start_date=date.today() + timedelta(days=60),
            end_date=date.today() + timedelta(days=62),
            location='Other',
            submission_deadline=timezone.now() + timedelta(days=50),
        )
        self._login(non_member)
        url = reverse('create_submission', args=[other_conf.slug])
        resp = self.client.get(url)
        # No paid membership for other_conf, so redirected by decorator
        self.assertEqual(resp.status_code, 302)

    def test_create_submission_deadline_passed(self):
        self.conference.submission_deadline = timezone.now() - timedelta(days=1)
        self.conference.save()
        self._login()
        url = reverse('create_submission', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    @patch('submissions.views.send_submission_confirmation')
    def test_create_submission_invalid_form(self, mock_email):
        self._login()
        url = reverse('create_submission', args=[self.conference.slug])
        resp = self.client.post(url, {
            'paper_title': '',
            'track': self.track.pk,
            'co_author_email_1': '',
            'co_author_email_2': '',
            'co_author_email_3': '',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Submissions.objects.count(), 0)

    # --- submission_detail ---

    def test_submission_detail_owner_access(self):
        self._login()
        sub = self._create_submission()
        url = reverse('submission_detail', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['submission'], sub)

    def test_submission_detail_unauthorized_user(self):
        self._login(self.other_user)
        sub = self._create_submission()
        url = reverse('submission_detail', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_submission_detail_co_author_access(self):
        sub = self._create_submission(co_author1=self.other_user)
        self._login(self.other_user)
        url = reverse('submission_detail', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_submission_detail_chair_access(self):
        chair = CustomUser.objects.create_user(
            email='chair@example.com', password='testpass123',
            first_name='Chair', last_name='Person', country='US',
            organization='Org', phone='4444444444', occupation='faculty',
        )
        Membership.objects.create(
            user=chair, conference=self.conference,
            role1='Chair', is_paid=True,
        )
        self._login(chair)
        sub = self._create_submission()
        url = reverse('submission_detail', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_submission_detail_404(self):
        self._login()
        url = reverse('submission_detail', args=[99999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    # --- submission_list ---

    def test_submission_list_shows_own_submissions(self):
        self._login()
        sub = self._create_submission()
        url = reverse('submission_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(sub, resp.context['all_submissions'])

    def test_submission_list_shows_co_authored(self):
        sub = self._create_submission(co_author1=self.other_user)
        self._login(self.other_user)
        url = reverse('submission_list')
        resp = self.client.get(url)
        self.assertIn(sub, resp.context['all_submissions'])

    def test_submission_list_chair_sees_all_conference_submissions(self):
        chair = CustomUser.objects.create_user(
            email='chair@example.com', password='testpass123',
            first_name='Chair', last_name='Person', country='US',
            organization='Org', phone='4444444444', occupation='faculty',
        )
        Membership.objects.create(
            user=chair, conference=self.conference,
            role1='Chair', is_paid=True,
        )
        sub = self._create_submission()
        self._login(chair)
        url = reverse('submission_list')
        resp = self.client.get(url)
        self.assertIn(sub, resp.context['all_submissions'])

    def test_submission_list_requires_login(self):
        url = reverse('submission_list')
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    # --- edit_submission ---

    def test_edit_submission_get(self):
        self._login()
        sub = self._create_submission()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)

    def test_edit_submission_post_success(self):
        self._login()
        sub = self._create_submission()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.post(url, {
            'paper_title': 'Updated Title',
            'track': self.track.pk,
            'co_author_email_1': '',
            'co_author_email_2': '',
            'co_author_email_3': '',
        })
        sub.refresh_from_db()
        self.assertEqual(sub.paper_title, 'Updated Title')
        self.assertRedirects(resp, reverse('submission_detail', args=[sub.pk]))

    def test_edit_submission_unauthorized(self):
        self._login(self.other_user)
        sub = self._create_submission()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_edit_accepted_submission_blocked(self):
        self._login()
        sub = self._create_submission()
        sub.status = 'ACCEPTED'
        sub.save()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_edit_rejected_submission_blocked(self):
        self._login()
        sub = self._create_submission()
        sub.status = 'REJECTED'
        sub.save()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_edit_pending_submission_allowed(self):
        self._login()
        sub = self._create_submission()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_edit_revision_submission_allowed(self):
        self._login()
        sub = self._create_submission()
        sub.status = 'REVISION'
        sub.save()
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_edit_co_author_can_edit(self):
        sub = self._create_submission(co_author1=self.other_user)
        self._login(self.other_user)
        url = reverse('edit_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    # --- delete_submission ---

    def test_delete_submission_get_confirmation(self):
        self._login()
        sub = self._create_submission()
        url = reverse('delete_submission', args=[sub.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_delete_submission_post(self):
        self._login()
        sub = self._create_submission()
        url = reverse('delete_submission', args=[sub.pk])
        resp = self.client.post(url)
        self.assertEqual(Submissions.objects.count(), 0)
        self.assertEqual(resp.status_code, 302)

    def test_delete_submission_unauthorized(self):
        self._login(self.other_user)
        sub = self._create_submission()
        url = reverse('delete_submission', args=[sub.pk])
        resp = self.client.post(url)
        self.assertEqual(Submissions.objects.count(), 1)
        self.assertEqual(resp.status_code, 302)

    def test_delete_accepted_submission_blocked(self):
        self._login()
        sub = self._create_submission()
        sub.status = 'ACCEPTED'
        sub.save()
        url = reverse('delete_submission', args=[sub.pk])
        resp = self.client.post(url)
        self.assertEqual(Submissions.objects.count(), 1)

    def test_delete_rejected_submission_allowed(self):
        self._login()
        sub = self._create_submission()
        sub.status = 'REJECTED'
        sub.save()
        url = reverse('delete_submission', args=[sub.pk])
        resp = self.client.post(url)
        self.assertEqual(Submissions.objects.count(), 0)

    # --- proceedings_list ---

    def test_proceedings_list_public(self):
        url = reverse('proceedings_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_proceedings_list_shows_conferences_with_accepted_papers(self):
        sub = self._create_submission()
        sub.status = 'ACCEPTED'
        sub.save()
        url = reverse('proceedings_list')
        resp = self.client.get(url)
        self.assertIn(self.conference, resp.context['conferences'])

    def test_proceedings_list_excludes_conferences_without_accepted_papers(self):
        self._create_submission()  # PENDING status
        url = reverse('proceedings_list')
        resp = self.client.get(url)
        self.assertNotIn(self.conference, resp.context['conferences'])

    # --- proceedings_conference ---

    def test_proceedings_conference_public(self):
        url = reverse('proceedings_conference', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_proceedings_conference_shows_accepted_only(self):
        accepted = self._create_submission(paper_title='Accepted Paper')
        accepted.status = 'ACCEPTED'
        accepted.save()
        pending = self._create_submission(
            paper_title='Pending Paper',
            file=SimpleUploadedFile('p.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        url = reverse('proceedings_conference', args=[self.conference.slug])
        resp = self.client.get(url)
        self.assertIn(accepted, resp.context['papers'])
        self.assertNotIn(pending, resp.context['papers'])

    def test_proceedings_conference_search_by_title(self):
        sub = self._create_submission(paper_title='Machine Learning Paper')
        sub.status = 'ACCEPTED'
        sub.save()
        url = reverse('proceedings_conference', args=[self.conference.slug])
        resp = self.client.get(url, {'q': 'Machine'})
        self.assertIn(sub, resp.context['papers'])

    def test_proceedings_conference_search_no_results(self):
        sub = self._create_submission(paper_title='AI Paper')
        sub.status = 'ACCEPTED'
        sub.save()
        url = reverse('proceedings_conference', args=[self.conference.slug])
        resp = self.client.get(url, {'q': 'Blockchain'})
        self.assertNotIn(sub, resp.context['papers'])

    def test_proceedings_conference_filter_by_track(self):
        track2 = Track.objects.create(conference=self.conference, name='ML')
        sub1 = self._create_submission(paper_title='AI Paper', track=self.track)
        sub1.status = 'ACCEPTED'
        sub1.save()
        sub2 = self._create_submission(
            paper_title='ML Paper', track=track2,
            file=SimpleUploadedFile('ml.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        sub2.status = 'ACCEPTED'
        sub2.save()
        url = reverse('proceedings_conference', args=[self.conference.slug])
        resp = self.client.get(url, {'track': track2.pk})
        self.assertIn(sub2, resp.context['papers'])
        self.assertNotIn(sub1, resp.context['papers'])

    def test_proceedings_conference_404_invalid_slug(self):
        url = reverse('proceedings_conference', args=['nonexistent'])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)
