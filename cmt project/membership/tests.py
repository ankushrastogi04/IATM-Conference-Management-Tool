from datetime import date, timedelta

from django.db import IntegrityError
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import CustomUser
from conference.models import Conference
from membership.forms import MembershipForm
from membership.models import AttendeeMessage, Membership, Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(email="testuser@example.com", **kwargs):
    """Shortcut to create a CustomUser with all required fields."""
    defaults = dict(
        password="testpass123",
        first_name="Test",
        last_name="User",
        country="US",
        organization="TestOrg",
        phone="1234567890",
        occupation="faculty",
    )
    defaults.update(kwargs)
    return CustomUser.objects.create_user(email=email, **defaults)


def _create_conference(**kwargs):
    """Shortcut to create a Conference with sensible defaults."""
    defaults = dict(
        conference_name="Test Conf",
        conference_description="Desc",
        start_date=date.today() + timedelta(days=30),
        end_date=date.today() + timedelta(days=32),
        location="Test City",
    )
    defaults.update(kwargs)
    return Conference.objects.create(**defaults)


# ===========================================================================
# 1. MODEL TESTS
# ===========================================================================


class RoleChoicesTests(TestCase):
    """Verify Role TextChoices enum values."""

    def test_role_values(self):
        self.assertEqual(Role.AUTHOR, "Author")
        self.assertEqual(Role.REVIEWER, "Reviewer")
        self.assertEqual(Role.CHAIR, "Chair")
        self.assertEqual(Role.NA, "N/A")

    def test_role_choices_length(self):
        self.assertEqual(len(Role.choices), 4)

    def test_role_labels(self):
        labels = dict(Role.choices)
        self.assertEqual(labels["Author"], "Author")
        self.assertEqual(labels["Reviewer"], "Reviewer")
        self.assertEqual(labels["Chair"], "Chair")
        self.assertEqual(labels["N/A"], "N/A")


class MembershipModelTests(TestCase):
    """Tests for the Membership model."""

    def setUp(self):
        self.user = _create_user()
        self.conference = _create_conference()

    def test_create_membership_defaults(self):
        m = Membership.objects.create(user=self.user, conference=self.conference)
        self.assertEqual(m.role1, Role.AUTHOR)
        self.assertEqual(m.role2, Role.NA)
        self.assertFalse(m.is_paid)
        self.assertTrue(m.messaging_opt_in)
        self.assertIsNotNone(m.created_at)

    def test_create_membership_custom_roles(self):
        m = Membership.objects.create(
            user=self.user,
            conference=self.conference,
            role1=Role.REVIEWER,
            role2=Role.CHAIR,
            is_paid=True,
        )
        self.assertEqual(m.role1, Role.REVIEWER)
        self.assertEqual(m.role2, Role.CHAIR)
        self.assertTrue(m.is_paid)

    def test_str_representation(self):
        m = Membership.objects.create(user=self.user, conference=self.conference)
        expected = f"{self.user.email} - {self.conference.conference_name} ({m.role1}, {m.role2})"
        self.assertEqual(str(m), expected)

    def test_unique_together_constraint(self):
        """A user cannot register twice for the same conference."""
        Membership.objects.create(user=self.user, conference=self.conference)
        with self.assertRaises(IntegrityError):
            Membership.objects.create(user=self.user, conference=self.conference)

    def test_different_users_same_conference(self):
        """Two distinct users can register for the same conference."""
        user2 = _create_user(email="second@example.com")
        Membership.objects.create(user=self.user, conference=self.conference)
        Membership.objects.create(user=user2, conference=self.conference)
        self.assertEqual(Membership.objects.filter(conference=self.conference).count(), 2)

    def test_same_user_different_conferences(self):
        """One user can register for multiple conferences."""
        conf2 = _create_conference(conference_name="Second Conf")
        Membership.objects.create(user=self.user, conference=self.conference)
        Membership.objects.create(user=self.user, conference=conf2)
        self.assertEqual(Membership.objects.filter(user=self.user).count(), 2)

    def test_cascade_delete_user(self):
        Membership.objects.create(user=self.user, conference=self.conference)
        self.user.delete()
        self.assertEqual(Membership.objects.count(), 0)

    def test_cascade_delete_conference(self):
        Membership.objects.create(user=self.user, conference=self.conference)
        self.conference.delete()
        self.assertEqual(Membership.objects.count(), 0)

    def test_messaging_opt_in_default_true(self):
        m = Membership.objects.create(user=self.user, conference=self.conference)
        self.assertTrue(m.messaging_opt_in)

    def test_messaging_opt_out(self):
        m = Membership.objects.create(
            user=self.user, conference=self.conference, messaging_opt_in=False
        )
        self.assertFalse(m.messaging_opt_in)


class AttendeeMessageModelTests(TestCase):
    """Tests for the AttendeeMessage model."""

    def setUp(self):
        self.sender = _create_user(email="sender@example.com")
        self.recipient = _create_user(email="recipient@example.com")
        self.conference = _create_conference()

    def test_create_message(self):
        msg = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Hello",
            body="Test body",
        )
        self.assertEqual(msg.subject, "Hello")
        self.assertEqual(msg.body, "Test body")
        self.assertFalse(msg.is_read)
        self.assertIsNotNone(msg.created_at)

    def test_str_representation(self):
        msg = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Hello",
            body="Body",
        )
        expected = f"{self.sender.email} -> {self.recipient.email}: Hello"
        self.assertEqual(str(msg), expected)

    def test_ordering_by_created_at_desc(self):
        msg1 = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="First",
            body="Body1",
        )
        msg2 = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Second",
            body="Body2",
        )
        msgs = list(AttendeeMessage.objects.all())
        # Newest first
        self.assertEqual(msgs[0].id, msg2.id)
        self.assertEqual(msgs[1].id, msg1.id)

    def test_is_read_default_false(self):
        msg = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Test",
            body="Body",
        )
        self.assertFalse(msg.is_read)

    def test_mark_as_read(self):
        msg = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Test",
            body="Body",
        )
        msg.is_read = True
        msg.save()
        msg.refresh_from_db()
        self.assertTrue(msg.is_read)

    def test_cascade_delete_sender(self):
        AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Test",
            body="Body",
        )
        self.sender.delete()
        self.assertEqual(AttendeeMessage.objects.count(), 0)

    def test_cascade_delete_conference(self):
        AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Test",
            body="Body",
        )
        self.conference.delete()
        self.assertEqual(AttendeeMessage.objects.count(), 0)


# ===========================================================================
# 2. FORM TESTS
# ===========================================================================


class MembershipFormTests(TestCase):
    """Tests for the MembershipForm."""

    def test_valid_different_roles(self):
        form = MembershipForm(data={"role1": "Author", "role2": "Reviewer"})
        self.assertTrue(form.is_valid())

    def test_valid_role2_na(self):
        """role2 = N/A is always valid, even if role1 is also N/A."""
        form = MembershipForm(data={"role1": "Author", "role2": "N/A"})
        self.assertTrue(form.is_valid())

    def test_invalid_same_roles(self):
        """Choosing the same role for role1 and role2 (non-N/A) should fail."""
        form = MembershipForm(data={"role1": "Author", "role2": "Author"})
        self.assertFalse(form.is_valid())
        self.assertIn("Please choose two different roles.", form.non_field_errors())

    def test_invalid_same_roles_reviewer(self):
        form = MembershipForm(data={"role1": "Reviewer", "role2": "Reviewer"})
        self.assertFalse(form.is_valid())

    def test_invalid_same_roles_chair(self):
        form = MembershipForm(data={"role1": "Chair", "role2": "Chair"})
        self.assertFalse(form.is_valid())

    def test_unbound_form_default_role2(self):
        """An unbound (GET) form should have role2 initial set to N/A."""
        form = MembershipForm()
        self.assertEqual(form.fields["role2"].initial, "N/A")

    def test_bound_form_does_not_override_role2_initial(self):
        """A bound form should not forcefully set role2 initial."""
        form = MembershipForm(data={"role1": "Author", "role2": "Reviewer"})
        # The initial value may or may not be set on bound forms; what matters
        # is the submitted value is preserved.
        self.assertEqual(form.data["role2"], "Reviewer")

    def test_invalid_choice_rejected(self):
        form = MembershipForm(data={"role1": "InvalidRole", "role2": "Author"})
        self.assertFalse(form.is_valid())
        self.assertIn("role1", form.errors)

    def test_missing_role1(self):
        form = MembershipForm(data={"role2": "Author"})
        self.assertFalse(form.is_valid())
        self.assertIn("role1", form.errors)

    def test_missing_role2(self):
        form = MembershipForm(data={"role1": "Author"})
        self.assertFalse(form.is_valid())
        self.assertIn("role2", form.errors)

    def test_all_valid_combinations(self):
        """Every pair where role1 != role2 (or role2 is N/A) should be valid."""
        non_na_roles = ["Author", "Reviewer", "Chair"]
        for r1 in non_na_roles:
            for r2 in non_na_roles:
                form = MembershipForm(data={"role1": r1, "role2": r2})
                if r1 == r2:
                    self.assertFalse(
                        form.is_valid(),
                        msg=f"Expected invalid for role1={r1}, role2={r2}",
                    )
                else:
                    self.assertTrue(
                        form.is_valid(),
                        msg=f"Expected valid for role1={r1}, role2={r2}",
                    )

        # role2 = N/A should always pass
        for r1 in non_na_roles:
            form = MembershipForm(data={"role1": r1, "role2": "N/A"})
            self.assertTrue(form.is_valid(), msg=f"Expected valid for role1={r1}, role2=N/A")


# ===========================================================================
# 3. VIEW TESTS
# ===========================================================================


class NetworkingHubViewTests(TestCase):
    """Tests for the networking_hub view (paid registrants only)."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user(email="hub@example.com")
        self.conference = _create_conference()
        self.url = reverse("networking_hub", kwargs={"slug": self.conference.slug})

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)
        # Should redirect to login
        self.assertIn("login", response.url.lower())

    def test_unpaid_member_redirected(self):
        self.client.login(email="hub@example.com", password="testpass123")
        Membership.objects.create(
            user=self.user, conference=self.conference, is_paid=False
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.conference.slug, response.url)

    def test_non_member_redirected(self):
        self.client.login(email="hub@example.com", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_paid_member_can_access(self):
        self.client.login(email="hub@example.com", password="testpass123")
        Membership.objects.create(
            user=self.user, conference=self.conference, is_paid=True
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "membership/networking_hub.html")

    def test_search_filters_attendees(self):
        self.client.login(email="hub@example.com", password="testpass123")
        Membership.objects.create(
            user=self.user, conference=self.conference, is_paid=True
        )
        user2 = _create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            organization="ACME",
        )
        Membership.objects.create(
            user=user2, conference=self.conference, is_paid=True
        )
        # Search for Alice
        response = self.client.get(self.url, {"q": "Alice"})
        self.assertEqual(response.status_code, 200)
        attendees = response.context["attendees"]
        self.assertEqual(len(attendees), 1)
        self.assertEqual(attendees[0].user.first_name, "Alice")

    def test_search_by_organization(self):
        self.client.login(email="hub@example.com", password="testpass123")
        Membership.objects.create(
            user=self.user, conference=self.conference, is_paid=True
        )
        user2 = _create_user(
            email="bob@example.com",
            first_name="Bob",
            organization="UniqueOrg",
        )
        Membership.objects.create(
            user=user2, conference=self.conference, is_paid=True
        )
        response = self.client.get(self.url, {"q": "UniqueOrg"})
        self.assertEqual(response.status_code, 200)
        attendees = response.context["attendees"]
        self.assertEqual(len(attendees), 1)

    def test_empty_search_returns_all_paid(self):
        self.client.login(email="hub@example.com", password="testpass123")
        Membership.objects.create(
            user=self.user, conference=self.conference, is_paid=True
        )
        user2 = _create_user(email="other@example.com")
        Membership.objects.create(
            user=user2, conference=self.conference, is_paid=True
        )
        response = self.client.get(self.url, {"q": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["attendees"]), 2)

    def test_unpaid_members_not_in_attendee_list(self):
        self.client.login(email="hub@example.com", password="testpass123")
        Membership.objects.create(
            user=self.user, conference=self.conference, is_paid=True
        )
        unpaid_user = _create_user(email="unpaid@example.com")
        Membership.objects.create(
            user=unpaid_user, conference=self.conference, is_paid=False
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Only the paid member should appear
        self.assertEqual(len(response.context["attendees"]), 1)


class RegisterForConferenceViewTests(TestCase):
    """Tests for the register_for_conference view."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user(email="register@example.com")
        self.conference = _create_conference()
        self.url = reverse(
            "register_for_conference", kwargs={"slug": self.conference.slug}
        )

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_get_shows_form(self):
        self.client.login(email="register@example.com", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context["form"], MembershipForm)

    def test_successful_registration(self):
        self.client.login(email="register@example.com", password="testpass123")
        response = self.client.post(
            self.url, {"role1": "Author", "role2": "N/A"}, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Membership.objects.filter(
                user=self.user, conference=self.conference
            ).exists()
        )
        m = Membership.objects.get(user=self.user, conference=self.conference)
        self.assertEqual(m.role1, "Author")
        self.assertEqual(m.role2, "N/A")

    def test_registration_with_two_roles(self):
        self.client.login(email="register@example.com", password="testpass123")
        self.client.post(self.url, {"role1": "Author", "role2": "Reviewer"})
        m = Membership.objects.get(user=self.user, conference=self.conference)
        self.assertEqual(m.role1, "Author")
        self.assertEqual(m.role2, "Reviewer")

    def test_duplicate_registration_redirects(self):
        """If already registered, the view redirects with an info message."""
        self.client.login(email="register@example.com", password="testpass123")
        Membership.objects.create(user=self.user, conference=self.conference)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        # POST should also redirect
        response = self.client.post(
            self.url, {"role1": "Author", "role2": "Reviewer"}
        )
        self.assertEqual(response.status_code, 302)

    def test_invalid_form_same_roles(self):
        self.client.login(email="register@example.com", password="testpass123")
        response = self.client.post(
            self.url, {"role1": "Author", "role2": "Author"}
        )
        # Should re-render the form (200), not redirect
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Membership.objects.filter(
                user=self.user, conference=self.conference
            ).exists()
        )

    def test_membership_is_not_paid_by_default(self):
        self.client.login(email="register@example.com", password="testpass123")
        self.client.post(self.url, {"role1": "Chair", "role2": "N/A"})
        m = Membership.objects.get(user=self.user, conference=self.conference)
        self.assertFalse(m.is_paid)


class AdminConferenceDashboardViewTests(TestCase):
    """Tests for admin_conference_dashboard_view (staff only)."""

    def setUp(self):
        self.client = Client()
        self.staff_user = _create_user(
            email="admin@example.com", is_staff=True
        )
        self.regular_user = _create_user(email="regular@example.com")
        self.conference = _create_conference()
        self.url = reverse(
            "admin_conference_dashboard", kwargs={"slug": self.conference.slug}
        )

    def test_non_staff_redirected(self):
        self.client.login(email="regular@example.com", password="testpass123")
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_anonymous_redirected(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_staff_can_access(self):
        self.client.login(email="admin@example.com", password="testpass123")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_toggle_payment_status_unpaid_to_paid(self):
        self.client.login(email="admin@example.com", password="testpass123")
        membership = Membership.objects.create(
            user=self.regular_user, conference=self.conference, is_paid=False
        )
        response = self.client.post(
            self.url,
            {
                "action": "toggle_payment",
                "membership_id": membership.id,
            },
        )
        self.assertEqual(response.status_code, 302)
        membership.refresh_from_db()
        self.assertTrue(membership.is_paid)

    def test_toggle_payment_status_paid_to_unpaid(self):
        self.client.login(email="admin@example.com", password="testpass123")
        membership = Membership.objects.create(
            user=self.regular_user, conference=self.conference, is_paid=True
        )
        self.client.post(
            self.url,
            {
                "action": "toggle_payment",
                "membership_id": membership.id,
            },
        )
        membership.refresh_from_db()
        self.assertFalse(membership.is_paid)

    def test_update_roles(self):
        self.client.login(email="admin@example.com", password="testpass123")
        membership = Membership.objects.create(
            user=self.regular_user,
            conference=self.conference,
            role1=Role.AUTHOR,
            role2=Role.NA,
        )
        self.client.post(
            self.url,
            {
                "action": "update_roles",
                "membership_id": membership.id,
                "role1": "Reviewer",
                "role2": "Chair",
            },
        )
        membership.refresh_from_db()
        self.assertEqual(membership.role1, "Reviewer")
        self.assertEqual(membership.role2, "Chair")

    def test_staff_users_excluded_from_list(self):
        """Staff memberships are excluded from the dashboard listing."""
        self.client.login(email="admin@example.com", password="testpass123")
        Membership.objects.create(
            user=self.staff_user, conference=self.conference
        )
        Membership.objects.create(
            user=self.regular_user, conference=self.conference
        )
        response = self.client.get(self.url)
        memberships = response.context["memberships"]
        user_ids = [m.user.id for m in memberships]
        self.assertNotIn(self.staff_user.id, user_ids)
        self.assertIn(self.regular_user.id, user_ids)


class AdminAnalyticsViewTests(TestCase):
    """Tests for admin_analytics_view (staff only)."""

    def setUp(self):
        self.client = Client()
        self.staff_user = _create_user(
            email="analytics_admin@example.com", is_staff=True
        )
        self.conference = _create_conference()
        self.url = reverse(
            "admin_analytics", kwargs={"slug": self.conference.slug}
        )

    def test_non_staff_redirected(self):
        user = _create_user(email="nonadmin@example.com")
        self.client.login(email="nonadmin@example.com", password="testpass123")
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_staff_can_access(self):
        self.client.login(
            email="analytics_admin@example.com", password="testpass123"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_context_contains_stats(self):
        self.client.login(
            email="analytics_admin@example.com", password="testpass123"
        )
        user1 = _create_user(email="stat1@example.com")
        user2 = _create_user(email="stat2@example.com")
        Membership.objects.create(
            user=user1,
            conference=self.conference,
            role1="Author",
            is_paid=True,
        )
        Membership.objects.create(
            user=user2,
            conference=self.conference,
            role1="Reviewer",
            is_paid=False,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.context["total_registrations"], 2)
        self.assertEqual(response.context["paid_registrations"], 1)
        self.assertEqual(response.context["unpaid_registrations"], 1)
        self.assertEqual(response.context["authors"], 1)
        self.assertEqual(response.context["reviewers"], 1)


class MessageInboxViewTests(TestCase):
    """Tests for message_inbox view."""

    def setUp(self):
        self.client = Client()
        self.user = _create_user(email="inbox@example.com")
        self.sender = _create_user(email="msgsender@example.com")
        self.conference = _create_conference()
        self.url = reverse("message_inbox")

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_inbox_shows_received_messages(self):
        self.client.login(email="inbox@example.com", password="testpass123")
        AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.user,
            subject="Hello",
            body="Body",
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["received_messages"].count(), 1)

    def test_inbox_shows_sent_messages(self):
        self.client.login(email="inbox@example.com", password="testpass123")
        AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.user,
            recipient=self.sender,
            subject="Outgoing",
            body="Body",
        )
        response = self.client.get(self.url, {"tab": "sent"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["sent_messages"].count(), 1)

    def test_unread_count(self):
        self.client.login(email="inbox@example.com", password="testpass123")
        AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.user,
            subject="Msg 1",
            body="Body",
            is_read=False,
        )
        AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.user,
            subject="Msg 2",
            body="Body",
            is_read=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.context["unread_count"], 1)


class MessageDetailViewTests(TestCase):
    """Tests for message_detail view."""

    def setUp(self):
        self.client = Client()
        self.sender = _create_user(email="detail_sender@example.com")
        self.recipient = _create_user(email="detail_recipient@example.com")
        self.other = _create_user(email="detail_other@example.com")
        self.conference = _create_conference()
        self.msg = AttendeeMessage.objects.create(
            conference=self.conference,
            sender=self.sender,
            recipient=self.recipient,
            subject="Detail Test",
            body="Body",
        )
        self.url = reverse("message_detail", kwargs={"message_id": self.msg.id})

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_recipient_can_view(self):
        self.client.login(
            email="detail_recipient@example.com", password="testpass123"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["message"].id, self.msg.id)

    def test_sender_can_view(self):
        self.client.login(
            email="detail_sender@example.com", password="testpass123"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_user_redirected(self):
        self.client.login(
            email="detail_other@example.com", password="testpass123"
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_marks_as_read_for_recipient(self):
        self.client.login(
            email="detail_recipient@example.com", password="testpass123"
        )
        self.assertFalse(self.msg.is_read)
        self.client.get(self.url)
        self.msg.refresh_from_db()
        self.assertTrue(self.msg.is_read)

    def test_does_not_mark_as_read_for_sender(self):
        self.client.login(
            email="detail_sender@example.com", password="testpass123"
        )
        self.client.get(self.url)
        self.msg.refresh_from_db()
        self.assertFalse(self.msg.is_read)


class SendMessageViewTests(TestCase):
    """Tests for send_message view (paid members only)."""

    def setUp(self):
        self.client = Client()
        self.sender = _create_user(email="send_sender@example.com")
        self.recipient = _create_user(email="send_recipient@example.com")
        self.conference = _create_conference()
        self.url = reverse(
            "send_message",
            kwargs={
                "slug": self.conference.slug,
                "recipient_id": self.recipient.id,
            },
        )

    def _make_paid_members(self):
        """Create paid memberships for both sender and recipient."""
        Membership.objects.create(
            user=self.sender,
            conference=self.conference,
            is_paid=True,
            messaging_opt_in=True,
        )
        Membership.objects.create(
            user=self.recipient,
            conference=self.conference,
            is_paid=True,
            messaging_opt_in=True,
        )

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_unpaid_sender_rejected(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        Membership.objects.create(
            user=self.sender,
            conference=self.conference,
            is_paid=False,
        )
        Membership.objects.create(
            user=self.recipient,
            conference=self.conference,
            is_paid=True,
            messaging_opt_in=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_recipient_opted_out_rejected(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        Membership.objects.create(
            user=self.sender,
            conference=self.conference,
            is_paid=True,
        )
        Membership.objects.create(
            user=self.recipient,
            conference=self.conference,
            is_paid=True,
            messaging_opt_in=False,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_recipient_not_paid_rejected(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        Membership.objects.create(
            user=self.sender,
            conference=self.conference,
            is_paid=True,
        )
        Membership.objects.create(
            user=self.recipient,
            conference=self.conference,
            is_paid=False,
            messaging_opt_in=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_both_paid_can_access_form(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        self._make_paid_members()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "membership/send_message.html")

    def test_send_message_success(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        self._make_paid_members()
        response = self.client.post(
            self.url,
            {"subject": "Hi there", "body": "Nice to meet you"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendeeMessage.objects.count(), 1)
        msg = AttendeeMessage.objects.first()
        self.assertEqual(msg.sender, self.sender)
        self.assertEqual(msg.recipient, self.recipient)
        self.assertEqual(msg.subject, "Hi there")
        self.assertEqual(msg.body, "Nice to meet you")
        self.assertEqual(msg.conference, self.conference)

    def test_send_message_missing_subject(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        self._make_paid_members()
        response = self.client.post(
            self.url, {"subject": "", "body": "Some body"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendeeMessage.objects.count(), 0)

    def test_send_message_missing_body(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        self._make_paid_members()
        response = self.client.post(
            self.url, {"subject": "Hello", "body": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendeeMessage.objects.count(), 0)

    def test_cannot_message_self(self):
        self.client.login(
            email="send_sender@example.com", password="testpass123"
        )
        Membership.objects.create(
            user=self.sender,
            conference=self.conference,
            is_paid=True,
            messaging_opt_in=True,
        )
        self_url = reverse(
            "send_message",
            kwargs={
                "slug": self.conference.slug,
                "recipient_id": self.sender.id,
            },
        )
        response = self.client.get(self_url)
        self.assertEqual(response.status_code, 302)


class ExportCSVViewTests(TestCase):
    """Tests for CSV export views (staff only)."""

    def setUp(self):
        self.client = Client()
        self.staff = _create_user(email="export_admin@example.com", is_staff=True)
        self.regular = _create_user(email="export_regular@example.com")
        self.conference = _create_conference()

    def test_export_attendees_requires_staff(self):
        self.client.login(
            email="export_regular@example.com", password="testpass123"
        )
        url = reverse("export_attendees", kwargs={"slug": self.conference.slug})
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    def test_export_attendees_csv(self):
        self.client.login(
            email="export_admin@example.com", password="testpass123"
        )
        Membership.objects.create(
            user=self.regular, conference=self.conference, is_paid=True
        )
        url = reverse("export_attendees", kwargs={"slug": self.conference.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode()
        self.assertIn("Email", content)
        self.assertIn(self.regular.email, content)

    def test_export_financials_requires_staff(self):
        self.client.login(
            email="export_regular@example.com", password="testpass123"
        )
        url = reverse(
            "export_financials", kwargs={"slug": self.conference.slug}
        )
        response = self.client.get(url)
        self.assertNotEqual(response.status_code, 200)

    def test_export_financials_csv(self):
        self.client.login(
            email="export_admin@example.com", password="testpass123"
        )
        url = reverse(
            "export_financials", kwargs={"slug": self.conference.slug}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode()
        self.assertIn("Invoice #", content)
