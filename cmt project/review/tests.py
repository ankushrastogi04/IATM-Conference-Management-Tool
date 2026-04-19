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
from review.forms import ReviewForm, AssignReviewersForm
from review.models import Review
from submissions.models import Submissions


class ReviewModelTest(TestCase):
    """Tests for the Review model."""

    def setUp(self):
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.reviewer = CustomUser.objects.create_user(
            email='reviewer@example.com', password='testpass123',
            first_name='Reviewer', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.reviewer2 = CustomUser.objects.create_user(
            email='reviewer2@example.com', password='testpass123',
            first_name='Reviewer2', last_name='User', country='US',
            organization='TestOrg', phone='2222222222', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    def test_create_review(self):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        self.assertEqual(review.submission, self.submission)
        self.assertEqual(review.reviewer, self.reviewer)
        self.assertFalse(review.is_submitted)
        self.assertIsNone(review.recommendation)
        self.assertIsNone(review.comment)
        self.assertIsNone(review.date_reviewed)
        self.assertIsNotNone(review.date_assigned)

    def test_str_representation(self):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        expected = f"Review by {self.reviewer} for {self.submission.paper_title}"
        self.assertEqual(str(review), expected)

    def test_unique_together_submission_reviewer(self):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        with self.assertRaises(IntegrityError):
            Review.objects.create(
                submission=self.submission, reviewer=self.reviewer,
            )

    def test_different_reviewers_same_submission(self):
        r1 = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        r2 = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer2,
        )
        self.assertEqual(Review.objects.filter(submission=self.submission).count(), 2)

    def test_same_reviewer_different_submissions(self):
        sub2 = Submissions.objects.create(
            membership=self.membership, track=self.track,
            paper_title='Second Paper',
            file=SimpleUploadedFile('s2.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        Review.objects.create(submission=self.submission, reviewer=self.reviewer)
        Review.objects.create(submission=sub2, reviewer=self.reviewer)
        self.assertEqual(Review.objects.filter(reviewer=self.reviewer).count(), 2)

    @patch('submissions.emails.send_submission_decision')
    def test_save_sets_date_reviewed_on_submit(self, mock_email):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        self.assertIsNone(review.date_reviewed)
        review.is_submitted = True
        review.recommendation = 'ACCEPT'
        review.save()
        self.assertIsNotNone(review.date_reviewed)

    @patch('submissions.emails.send_submission_decision')
    def test_save_does_not_overwrite_date_reviewed(self, mock_email):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        review.is_submitted = True
        review.recommendation = 'ACCEPT'
        review.save()
        original_date = review.date_reviewed
        review.comment = 'Updated comment'
        review.save()
        self.assertEqual(review.date_reviewed, original_date)

    @patch('submissions.emails.send_submission_decision')
    def test_save_triggers_update_status_on_submission(self, mock_email):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        review.is_submitted = True
        review.recommendation = 'ACCEPT'
        review.save()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'ACCEPTED')

    @patch('submissions.emails.send_submission_decision')
    def test_recommendation_choices(self, mock_email):
        for choice in ['ACCEPT', 'REJECT', 'REVISE']:
            review = Review.objects.create(
                submission=self.submission, reviewer=self.reviewer,
                recommendation=choice, is_submitted=True,
            )
            self.assertEqual(review.recommendation, choice)
            review.delete()

    def test_comment_nullable(self):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            comment=None,
        )
        self.assertIsNone(review.comment)

    def test_comment_blank(self):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            comment='',
        )
        self.assertEqual(review.comment, '')

    def test_ordering(self):
        """Reviews ordered by -date_reviewed, -date_assigned."""
        r1 = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        r2 = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer2,
        )
        reviews = list(Review.objects.filter(submission=self.submission))
        # Both unsubmitted (date_reviewed is None), ordered by -date_assigned
        self.assertEqual(reviews[0], r2)
        self.assertEqual(reviews[1], r1)

    def test_cascade_delete_submission(self):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        self.assertEqual(Review.objects.count(), 1)
        self.submission.delete()
        self.assertEqual(Review.objects.count(), 0)

    def test_cascade_delete_reviewer(self):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        self.assertEqual(Review.objects.count(), 1)
        self.reviewer.delete()
        self.assertEqual(Review.objects.count(), 0)

    @patch('submissions.emails.send_submission_decision')
    def test_update_all_submission_statuses(self, mock_email):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
        )
        self.submission.status = 'PENDING'
        self.submission.save()
        Review.update_all_submission_statuses()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'ACCEPTED')


class ReviewFormTest(TestCase):
    """Tests for ReviewForm and AssignReviewersForm."""

    def setUp(self):
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.reviewer_user = CustomUser.objects.create_user(
            email='reviewer@example.com', password='testpass123',
            first_name='Reviewer', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.chair_user = CustomUser.objects.create_user(
            email='chair@example.com', password='testpass123',
            first_name='Chair', last_name='User', country='US',
            organization='TestOrg', phone='3333333333', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.author_membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.reviewer_membership = Membership.objects.create(
            user=self.reviewer_user, conference=self.conference,
            role1='Reviewer', is_paid=True,
        )
        self.chair_membership = Membership.objects.create(
            user=self.chair_user, conference=self.conference,
            role1='Chair', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    def test_review_form_valid(self):
        form = ReviewForm(data={
            'comment': 'Good paper',
            'recommendation': 'ACCEPT',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_review_form_empty_comment_valid(self):
        form = ReviewForm(data={
            'comment': '',
            'recommendation': 'REJECT',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_review_form_no_recommendation_valid(self):
        """Recommendation field is blank/null allowed in the model."""
        form = ReviewForm(data={
            'comment': 'Needs work',
            'recommendation': '',
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_review_form_invalid_recommendation(self):
        form = ReviewForm(data={
            'comment': 'Comment',
            'recommendation': 'INVALID',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('recommendation', form.errors)

    def test_review_form_fields(self):
        form = ReviewForm()
        self.assertIn('comment', form.fields)
        self.assertIn('recommendation', form.fields)
        self.assertEqual(len(form.fields), 2)

    def test_assign_reviewers_form_excludes_author(self):
        form = AssignReviewersForm(
            conference=self.conference,
            submission=self.submission,
            current_user=self.chair_user,
        )
        qs = form.fields['reviewers'].queryset
        author_user_ids = qs.values_list('user__id', flat=True)
        self.assertNotIn(self.author.id, author_user_ids)

    def test_assign_reviewers_form_excludes_current_user(self):
        form = AssignReviewersForm(
            conference=self.conference,
            submission=self.submission,
            current_user=self.chair_user,
        )
        qs = form.fields['reviewers'].queryset
        user_ids = qs.values_list('user__id', flat=True)
        self.assertNotIn(self.chair_user.id, user_ids)

    def test_assign_reviewers_form_includes_reviewers(self):
        form = AssignReviewersForm(
            conference=self.conference,
            submission=self.submission,
            current_user=self.chair_user,
        )
        qs = form.fields['reviewers'].queryset
        user_ids = list(qs.values_list('user__id', flat=True))
        self.assertIn(self.reviewer_user.id, user_ids)

    def test_assign_reviewers_form_excludes_co_authors(self):
        co_author = CustomUser.objects.create_user(
            email='corev@example.com', password='testpass123',
            first_name='Co', last_name='Rev', country='US',
            organization='Org', phone='5555555555', occupation='faculty',
        )
        Membership.objects.create(
            user=co_author, conference=self.conference,
            role1='Reviewer', is_paid=True,
        )
        self.submission.co_author1 = co_author
        self.submission.save()
        form = AssignReviewersForm(
            conference=self.conference,
            submission=self.submission,
            current_user=self.chair_user,
        )
        qs = form.fields['reviewers'].queryset
        user_ids = list(qs.values_list('user__id', flat=True))
        self.assertNotIn(co_author.id, user_ids)

    def test_assign_reviewers_form_filters_by_conference(self):
        other_conf = Conference.objects.create(
            conference_name='Other Conf', conference_description='Other',
            start_date=date.today() + timedelta(days=60),
            end_date=date.today() + timedelta(days=62),
            location='Other City',
        )
        other_reviewer = CustomUser.objects.create_user(
            email='otherrev@example.com', password='testpass123',
            first_name='Other', last_name='Rev', country='US',
            organization='Org', phone='6666666666', occupation='faculty',
        )
        Membership.objects.create(
            user=other_reviewer, conference=other_conf,
            role1='Reviewer', is_paid=True,
        )
        form = AssignReviewersForm(
            conference=self.conference,
            submission=self.submission,
            current_user=self.chair_user,
        )
        qs = form.fields['reviewers'].queryset
        user_ids = list(qs.values_list('user__id', flat=True))
        self.assertNotIn(other_reviewer.id, user_ids)


class ChairReviewAssignmentsViewTest(TestCase):
    """Tests for chair_review_assignments view."""

    def setUp(self):
        self.client = Client()
        self.chair = CustomUser.objects.create_user(
            email='chair@example.com', password='testpass123',
            first_name='Chair', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.chair_membership = Membership.objects.create(
            user=self.chair, conference=self.conference,
            role1='Chair', is_paid=True,
        )
        self.author_membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    def test_chair_review_assignments_requires_login(self):
        url = reverse('chair_review_assignments')
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_chair_review_assignments_accessible(self):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('chair_review_assignments')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_chair_review_assignments_with_conference_selected(self):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('chair_review_assignments')
        resp = self.client.get(url, {'conference': self.conference.slug})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['selected_conference'], self.conference)
        self.assertEqual(resp.context['total_submissions'], 1)

    def test_chair_review_assignments_no_conference(self):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('chair_review_assignments')
        resp = self.client.get(url)
        self.assertIsNone(resp.context['selected_conference'])

    def test_staff_can_access_all_conferences(self):
        staff = CustomUser.objects.create_user(
            email='staff@example.com', password='testpass123',
            first_name='Staff', last_name='User', country='US',
            organization='Org', phone='4444444444', occupation='faculty',
            is_staff=True,
        )
        self.client.login(email=staff.email, password='testpass123')
        url = reverse('chair_review_assignments')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.conference, resp.context['available_conferences'])

    def test_non_chair_redirected(self):
        self.client.login(email=self.author.email, password='testpass123')
        url = reverse('chair_review_assignments')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)


class AssignReviewersViewTest(TestCase):
    """Tests for assign_reviewers_to_submission view."""

    def setUp(self):
        self.client = Client()
        self.chair = CustomUser.objects.create_user(
            email='chair@example.com', password='testpass123',
            first_name='Chair', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.reviewer_user = CustomUser.objects.create_user(
            email='reviewer@example.com', password='testpass123',
            first_name='Reviewer', last_name='User', country='US',
            organization='TestOrg', phone='2222222222', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.chair_membership = Membership.objects.create(
            user=self.chair, conference=self.conference,
            role1='Chair', is_paid=True,
        )
        self.author_membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.reviewer_membership = Membership.objects.create(
            user=self.reviewer_user, conference=self.conference,
            role1='Reviewer', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    @patch('review.views.send_reviewer_assignment')
    def test_assign_reviewers_get(self, mock_email):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['submission'], self.submission)

    @patch('review.views.send_reviewer_assignment')
    def test_assign_reviewers_post(self, mock_email):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.post(url, {
            'reviewers': [self.reviewer_membership.pk],
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Review.objects.filter(submission=self.submission).count(), 1)
        review = Review.objects.get(submission=self.submission)
        self.assertEqual(review.reviewer, self.reviewer_user)
        mock_email.assert_called_once()

    @patch('review.views.send_reviewer_assignment')
    def test_assign_reviewers_replaces_existing(self, mock_email):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer_user,
        )
        new_reviewer = CustomUser.objects.create_user(
            email='newrev@example.com', password='testpass123',
            first_name='New', last_name='Rev', country='US',
            organization='Org', phone='5555555555', occupation='faculty',
        )
        new_membership = Membership.objects.create(
            user=new_reviewer, conference=self.conference,
            role1='Reviewer', is_paid=True,
        )
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.post(url, {'reviewers': [new_membership.pk]})
        self.assertEqual(Review.objects.filter(submission=self.submission).count(), 1)
        self.assertEqual(
            Review.objects.get(submission=self.submission).reviewer, new_reviewer,
        )

    def test_assign_reviewers_non_chair_rejected(self):
        self.client.login(email=self.author.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    @patch('review.views.send_reviewer_assignment')
    def test_assign_reviewers_staff_allowed(self, mock_email):
        staff = CustomUser.objects.create_user(
            email='staff@example.com', password='testpass123',
            first_name='Staff', last_name='User', country='US',
            organization='Org', phone='4444444444', occupation='faculty',
            is_staff=True,
        )
        self.client.login(email=staff.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @patch('review.views.send_reviewer_assignment')
    def test_assign_no_reviewers_selected(self, mock_email):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.post(url, {})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Review.objects.filter(submission=self.submission).count(), 0)

    def test_assign_reviewers_404(self):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[99999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    @patch('review.views.send_reviewer_assignment')
    def test_available_reviewers_excludes_author(self, mock_email):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.get(url)
        available_user_ids = [r.user.id for r in resp.context['available_reviewers']]
        self.assertNotIn(self.author.id, available_user_ids)

    @patch('review.views.send_reviewer_assignment')
    def test_available_reviewers_excludes_current_user(self, mock_email):
        self.client.login(email=self.chair.email, password='testpass123')
        url = reverse('assign_reviewers_to_submission', args=[self.submission.pk])
        resp = self.client.get(url)
        available_user_ids = [r.user.id for r in resp.context['available_reviewers']]
        self.assertNotIn(self.chair.id, available_user_ids)


class ReviewerDashboardViewTest(TestCase):
    """Tests for reviewer_dashboard view."""

    def setUp(self):
        self.client = Client()
        self.reviewer = CustomUser.objects.create_user(
            email='reviewer@example.com', password='testpass123',
            first_name='Reviewer', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.author_membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    def test_reviewer_dashboard_requires_login(self):
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_reviewer_dashboard_accessible(self):
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_reviewer_dashboard_shows_pending_reviews(self):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertIn(review, resp.context['pending_reviews'])
        self.assertEqual(resp.context['total_reviews'], 1)

    @patch('submissions.emails.send_submission_decision')
    def test_reviewer_dashboard_shows_submitted_reviews(self, mock_email):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertIn(review, resp.context['submitted_reviews'])

    def test_reviewer_dashboard_completion_rate_zero(self):
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.context['completion_rate'], 0)

    @patch('submissions.emails.send_submission_decision')
    def test_reviewer_dashboard_completion_rate_100(self, mock_email):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.context['completion_rate'], 100)

    @patch('submissions.emails.send_submission_decision')
    def test_reviewer_dashboard_completion_rate_partial(self, mock_email):
        sub2 = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Paper 2',
            file=SimpleUploadedFile('p2.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        Review.objects.create(
            submission=sub2, reviewer=self.reviewer,
        )
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.context['completion_rate'], 50)

    def test_reviewer_dashboard_does_not_show_other_reviewers_reviews(self):
        other_reviewer = CustomUser.objects.create_user(
            email='other@example.com', password='testpass123',
            first_name='Other', last_name='Rev', country='US',
            organization='Org', phone='3333333333', occupation='faculty',
        )
        Review.objects.create(
            submission=self.submission, reviewer=other_reviewer,
        )
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('reviewer_dashboard')
        resp = self.client.get(url)
        self.assertEqual(resp.context['total_reviews'], 0)


class SubmitReviewViewTest(TestCase):
    """Tests for submit_review view."""

    def setUp(self):
        self.client = Client()
        self.reviewer = CustomUser.objects.create_user(
            email='reviewer@example.com', password='testpass123',
            first_name='Reviewer', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.other_reviewer = CustomUser.objects.create_user(
            email='other@example.com', password='testpass123',
            first_name='Other', last_name='Rev', country='US',
            organization='TestOrg', phone='2222222222', occupation='faculty',
        )
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.author_membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        self.review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )

    def test_submit_review_requires_login(self):
        url = reverse('submit_review', args=[self.review.pk])
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_submit_review_get(self):
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[self.review.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('form', resp.context)
        self.assertEqual(resp.context['review'], self.review)

    @patch('review.views.send_review_notification')
    def test_submit_review_post_success(self, mock_email):
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[self.review.pk])
        resp = self.client.post(url, {
            'comment': 'Excellent paper',
            'recommendation': 'ACCEPT',
        })
        self.assertRedirects(resp, reverse('reviewer_dashboard'))
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_submitted)
        self.assertEqual(self.review.recommendation, 'ACCEPT')
        self.assertEqual(self.review.comment, 'Excellent paper')
        self.assertIsNotNone(self.review.date_reviewed)
        mock_email.assert_called_once()

    def test_submit_review_wrong_reviewer(self):
        self.client.login(email=self.other_reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[self.review.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    @patch('review.views.send_review_notification')
    def test_submit_review_already_submitted(self, mock_email):
        self.review.is_submitted = True
        self.review.recommendation = 'ACCEPT'
        self.review.date_reviewed = timezone.now()
        self.review.save()
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[self.review.pk])
        resp = self.client.get(url)
        self.assertRedirects(resp, reverse('reviewer_dashboard'))

    def test_submit_review_404_nonexistent(self):
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[99999])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    @patch('review.views.send_review_notification')
    def test_submit_review_sets_is_submitted(self, mock_email):
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[self.review.pk])
        self.client.post(url, {
            'comment': 'Needs revision',
            'recommendation': 'REVISE',
        })
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_submitted)

    def test_submit_review_context_has_blind_review(self):
        self.conference.blind_review = True
        self.conference.save()
        self.client.login(email=self.reviewer.email, password='testpass123')
        url = reverse('submit_review', args=[self.review.pk])
        resp = self.client.get(url)
        self.assertTrue(resp.context['blind_review'])


class AuthorReviewsViewTest(TestCase):
    """Tests for author_reviews view."""

    def setUp(self):
        self.client = Client()
        self.author = CustomUser.objects.create_user(
            email='author@example.com', password='testpass123',
            first_name='Author', last_name='User', country='US',
            organization='TestOrg', phone='1234567890', occupation='faculty',
        )
        self.reviewer = CustomUser.objects.create_user(
            email='reviewer@example.com', password='testpass123',
            first_name='Reviewer', last_name='User', country='US',
            organization='TestOrg', phone='1111111111', occupation='faculty',
        )
        self.conference = Conference.objects.create(
            conference_name='Test Conference', conference_description='Desc',
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=32),
            location='Test City',
        )
        self.track = Track.objects.create(conference=self.conference, name='AI')
        self.author_membership = Membership.objects.create(
            user=self.author, conference=self.conference,
            role1='Author', is_paid=True,
        )
        self.submission = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Test Paper',
            file=SimpleUploadedFile('test.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )

    def test_author_reviews_requires_login(self):
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertNotEqual(resp.status_code, 200)

    def test_author_reviews_accessible(self):
        self.client.login(email=self.author.email, password='testpass123')
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @patch('submissions.emails.send_submission_decision')
    def test_author_reviews_shows_submitted_reviews(self, mock_email):
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
            date_reviewed=timezone.now(), comment='Great work',
        )
        self.client.login(email=self.author.email, password='testpass123')
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertIn(review, resp.context['reviews'])

    def test_author_reviews_excludes_unsubmitted(self):
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
        )
        self.client.login(email=self.author.email, password='testpass123')
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertEqual(resp.context['reviews'].count(), 0)

    @patch('submissions.emails.send_submission_decision')
    def test_author_reviews_counts(self, mock_email):
        reviewer2 = CustomUser.objects.create_user(
            email='rev2@example.com', password='testpass123',
            first_name='Rev', last_name='Two', country='US',
            organization='Org', phone='2222222222', occupation='faculty',
        )
        reviewer3 = CustomUser.objects.create_user(
            email='rev3@example.com', password='testpass123',
            first_name='Rev', last_name='Three', country='US',
            organization='Org', phone='3333333333', occupation='faculty',
        )
        Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        sub2 = Submissions.objects.create(
            membership=self.author_membership, track=self.track,
            paper_title='Paper 2',
            file=SimpleUploadedFile('p2.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        Review.objects.create(
            submission=sub2, reviewer=reviewer2,
            recommendation='REJECT', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        Review.objects.create(
            submission=sub2, reviewer=reviewer3,
            recommendation='REVISE', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        self.client.login(email=self.author.email, password='testpass123')
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertEqual(resp.context['accepted_count'], 1)
        self.assertEqual(resp.context['rejected_count'], 1)
        self.assertEqual(resp.context['revision_count'], 1)

    @patch('submissions.emails.send_submission_decision')
    def test_co_author_sees_reviews(self, mock_email):
        co_author = CustomUser.objects.create_user(
            email='coauthor@example.com', password='testpass123',
            first_name='Co', last_name='Author', country='US',
            organization='Org', phone='4444444444', occupation='faculty',
        )
        self.submission.co_author1 = co_author
        self.submission.save()
        review = Review.objects.create(
            submission=self.submission, reviewer=self.reviewer,
            recommendation='ACCEPT', is_submitted=True,
            date_reviewed=timezone.now(),
        )
        self.client.login(email=co_author.email, password='testpass123')
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertIn(review, resp.context['reviews'])

    def test_author_does_not_see_other_author_reviews(self):
        other_author = CustomUser.objects.create_user(
            email='other@example.com', password='testpass123',
            first_name='Other', last_name='Author', country='US',
            organization='Org', phone='5555555555', occupation='faculty',
        )
        self.client.login(email=other_author.email, password='testpass123')
        url = reverse('author_reviews')
        resp = self.client.get(url)
        self.assertEqual(resp.context['reviews'].count(), 0)
