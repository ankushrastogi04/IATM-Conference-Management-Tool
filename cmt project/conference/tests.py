from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from conference.models import Conference, RegistrationTier, Payment, Track
from membership.models import Membership


# ---------------------------------------------------------------------------
# Helper mixin to reduce boilerplate across test classes
# ---------------------------------------------------------------------------
class ConferenceTestMixin:
    """Shared helpers for creating users and conferences in tests."""

    def create_user(self, email='testuser@example.com', password='testpass123',
                    first_name='Test', last_name='User', country='US',
                    organization='Test Org', phone='1234567890',
                    occupation='faculty', iatm_membership=False):
        return CustomUser.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            country=country,
            organization=organization,
            phone=phone,
            occupation=occupation,
            iatm_membership=iatm_membership,
        )

    def create_conference(self, **kwargs):
        defaults = {
            'conference_name': 'Test Conference',
            'conference_description': 'Test',
            'start_date': date.today() + timedelta(days=30),
            'end_date': date.today() + timedelta(days=32),
            'location': 'Test City',
        }
        defaults.update(kwargs)
        return Conference.objects.create(**defaults)


# ===========================================================================
# MODEL TESTS
# ===========================================================================


class ConferenceModelTests(ConferenceTestMixin, TestCase):
    """Tests for the Conference model."""

    def test_conference_creation(self):
        """Conference can be created with required fields."""
        conf = self.create_conference()
        self.assertEqual(conf.conference_name, 'Test Conference')
        self.assertEqual(conf.conference_description, 'Test')
        self.assertEqual(conf.location, 'Test City')
        self.assertIsNotNone(conf.created_at)
        self.assertIsNotNone(conf.updated_at)

    def test_str_representation(self):
        """__str__ returns the conference name."""
        conf = self.create_conference(conference_name='My Conference')
        self.assertEqual(str(conf), 'My Conference')

    # --- Slug auto-generation ---

    def test_slug_auto_generated_from_name(self):
        """Slug is automatically generated from conference_name on save."""
        conf = self.create_conference(conference_name='Annual Research Summit 2026')
        self.assertEqual(conf.slug, 'annual-research-summit-2026')

    def test_slug_auto_generated_handles_special_characters(self):
        """Slug generation strips special characters and spaces."""
        conf = self.create_conference(conference_name='AI & Machine Learning: 2026!')
        self.assertEqual(conf.slug, 'ai-machine-learning-2026')

    def test_slug_not_overwritten_on_update(self):
        """Once set, the slug is not changed when the model is re-saved."""
        conf = self.create_conference(conference_name='Original Name')
        original_slug = conf.slug
        conf.conference_name = 'Updated Name'
        conf.save()
        self.assertEqual(conf.slug, original_slug)

    def test_slug_can_be_set_manually(self):
        """If a slug is provided, it is used instead of auto-generating."""
        conf = self.create_conference(
            conference_name='Some Conference',
            slug='custom-slug',
        )
        self.assertEqual(conf.slug, 'custom-slug')

    # --- is_early_bird property ---

    def test_is_early_bird_true_when_before_deadline(self):
        """is_early_bird returns True when today is before the early_bird_deadline."""
        conf = self.create_conference(
            early_bird_deadline=date.today() + timedelta(days=10),
        )
        self.assertTrue(conf.is_early_bird)

    def test_is_early_bird_true_on_deadline_day(self):
        """is_early_bird returns True on the exact deadline date."""
        conf = self.create_conference(
            early_bird_deadline=date.today(),
        )
        self.assertTrue(conf.is_early_bird)

    def test_is_early_bird_false_after_deadline(self):
        """is_early_bird returns False after the early_bird_deadline has passed."""
        conf = self.create_conference(
            early_bird_deadline=date.today() - timedelta(days=1),
        )
        self.assertFalse(conf.is_early_bird)

    def test_is_early_bird_false_when_no_deadline(self):
        """is_early_bird returns False when no early_bird_deadline is set."""
        conf = self.create_conference()
        self.assertFalse(conf.is_early_bird)

    # --- is_submission_open property ---

    def test_is_submission_open_true_before_deadline(self):
        """is_submission_open returns True when current time is before submission_deadline."""
        conf = self.create_conference(
            submission_deadline=timezone.now() + timedelta(days=10),
        )
        self.assertTrue(conf.is_submission_open)

    def test_is_submission_open_false_after_deadline(self):
        """is_submission_open returns False after submission_deadline has passed."""
        conf = self.create_conference(
            submission_deadline=timezone.now() - timedelta(hours=1),
        )
        self.assertFalse(conf.is_submission_open)

    def test_is_submission_open_true_when_no_deadline(self):
        """is_submission_open returns True when no submission_deadline is set."""
        conf = self.create_conference()
        self.assertTrue(conf.is_submission_open)

    # --- Default values ---

    def test_default_member_discount_percent(self):
        """Default member_discount_percent is 10."""
        conf = self.create_conference()
        self.assertEqual(conf.member_discount_percent, 10)

    def test_default_blind_review(self):
        """Default blind_review is False."""
        conf = self.create_conference()
        self.assertFalse(conf.blind_review)

    def test_ordering_by_start_date(self):
        """Conferences are ordered by start_date (ascending)."""
        conf_later = self.create_conference(
            conference_name='Later Conf',
            start_date=date.today() + timedelta(days=60),
            end_date=date.today() + timedelta(days=62),
        )
        conf_earlier = self.create_conference(
            conference_name='Earlier Conf',
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=12),
        )
        conferences = list(Conference.objects.all())
        self.assertEqual(conferences[0], conf_earlier)
        self.assertEqual(conferences[1], conf_later)


class RegistrationTierModelTests(ConferenceTestMixin, TestCase):
    """Tests for the RegistrationTier model."""

    def setUp(self):
        self.conference = self.create_conference(
            early_bird_deadline=date.today() + timedelta(days=10),
            member_discount_percent=10,
        )
        self.tier = RegistrationTier.objects.create(
            conference=self.conference,
            name='Professional',
            price=Decimal('200.00'),
            early_bird_price=Decimal('150.00'),
            description='Professional registration',
            is_active=True,
        )

    def test_tier_creation(self):
        """RegistrationTier is created with correct attributes."""
        self.assertEqual(self.tier.name, 'Professional')
        self.assertEqual(self.tier.price, Decimal('200.00'))
        self.assertEqual(self.tier.early_bird_price, Decimal('150.00'))
        self.assertTrue(self.tier.is_active)
        self.assertEqual(self.tier.conference, self.conference)

    def test_str_representation(self):
        """__str__ includes tier name, conference name, and price."""
        expected = f"Professional - {self.conference.conference_name} ($200.00)"
        self.assertEqual(str(self.tier), expected)

    def test_unique_together_constraint(self):
        """Cannot create two tiers with the same name for the same conference."""
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            RegistrationTier.objects.create(
                conference=self.conference,
                name='Professional',
                price=Decimal('300.00'),
            )

    def test_same_tier_name_different_conferences(self):
        """Same tier name can exist in different conferences."""
        other_conference = self.create_conference(
            conference_name='Other Conference',
        )
        tier2 = RegistrationTier.objects.create(
            conference=other_conference,
            name='Professional',
            price=Decimal('250.00'),
        )
        self.assertEqual(tier2.name, 'Professional')
        self.assertEqual(RegistrationTier.objects.filter(name='Professional').count(), 2)

    # --- get_current_price ---

    def test_get_current_price_early_bird(self):
        """During early bird period, returns the early_bird_price."""
        price = self.tier.get_current_price(is_member=False)
        self.assertEqual(price, Decimal('150.00'))

    def test_get_current_price_early_bird_member_discount(self):
        """During early bird period with member discount, applies discount to early_bird_price."""
        price = self.tier.get_current_price(is_member=True)
        # 150 - 10% = 135
        self.assertEqual(price, Decimal('135.00'))

    def test_get_current_price_regular_after_early_bird(self):
        """After early bird period, returns the regular price."""
        self.conference.early_bird_deadline = date.today() - timedelta(days=1)
        self.conference.save()
        price = self.tier.get_current_price(is_member=False)
        self.assertEqual(price, Decimal('200.00'))

    def test_get_current_price_regular_member_discount(self):
        """After early bird, member discount applies to regular price."""
        self.conference.early_bird_deadline = date.today() - timedelta(days=1)
        self.conference.save()
        price = self.tier.get_current_price(is_member=True)
        # 200 - 10% = 180
        self.assertEqual(price, Decimal('180.00'))

    def test_get_current_price_no_early_bird_price_set(self):
        """When early_bird_price is None, uses regular price even during early bird."""
        tier_no_eb = RegistrationTier.objects.create(
            conference=self.conference,
            name='Student',
            price=Decimal('100.00'),
            early_bird_price=None,
        )
        price = tier_no_eb.get_current_price(is_member=False)
        self.assertEqual(price, Decimal('100.00'))

    def test_get_current_price_no_member_discount(self):
        """When member_discount_percent is 0, member gets the same price."""
        self.conference.member_discount_percent = 0
        self.conference.save()
        price = self.tier.get_current_price(is_member=True)
        # Early bird price with 0% discount => 150.00
        self.assertEqual(price, Decimal('150.00'))

    def test_get_current_price_custom_discount_percent(self):
        """Custom member_discount_percent (e.g. 20%) is applied correctly."""
        self.conference.member_discount_percent = 20
        self.conference.save()
        price = self.tier.get_current_price(is_member=True)
        # Early bird: 150 - 20% = 120
        self.assertEqual(price, Decimal('120.00'))

    def test_ordering_by_price(self):
        """Tiers are ordered by price ascending."""
        cheap_tier = RegistrationTier.objects.create(
            conference=self.conference,
            name='Student',
            price=Decimal('50.00'),
        )
        tiers = list(RegistrationTier.objects.filter(conference=self.conference))
        self.assertEqual(tiers[0], cheap_tier)
        self.assertEqual(tiers[1], self.tier)


class PaymentModelTests(ConferenceTestMixin, TestCase):
    """Tests for the Payment model."""

    def setUp(self):
        self.user = self.create_user()
        self.conference = self.create_conference()
        self.tier = RegistrationTier.objects.create(
            conference=self.conference,
            name='Professional',
            price=Decimal('200.00'),
        )

    def test_payment_creation(self):
        """Payment can be created with required fields."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            tier=self.tier,
            amount=Decimal('200.00'),
        )
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.conference, self.conference)
        self.assertEqual(payment.tier, self.tier)
        self.assertEqual(payment.amount, Decimal('200.00'))
        self.assertIsNotNone(payment.created_at)
        self.assertIsNotNone(payment.updated_at)

    def test_payment_default_status_is_pending(self):
        """Default payment status is 'pending'."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        self.assertEqual(payment.status, 'pending')

    def test_payment_default_currency_is_usd(self):
        """Default currency is 'USD'."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        self.assertEqual(payment.currency, 'USD')

    def test_payment_tier_nullable(self):
        """Payment can be created without a tier."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('50.00'),
            tier=None,
        )
        self.assertIsNone(payment.tier)

    def test_payment_str_representation(self):
        """__str__ includes user email, conference name, amount, and status."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('200.00'),
            status='completed',
        )
        result = str(payment)
        self.assertIn(self.user.email, result)
        self.assertIn(self.conference.conference_name, result)
        self.assertIn('200.00', result)
        self.assertIn('completed', result)

    def test_payment_status_transitions(self):
        """Payment status can be updated to any valid choice."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        for status_code, _ in Payment.PAYMENT_STATUS_CHOICES:
            payment.status = status_code
            payment.save()
            payment.refresh_from_db()
            self.assertEqual(payment.status, status_code)

    def test_payment_paypal_fields_nullable(self):
        """paypal_order_id and paypal_payment_id can be null."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        self.assertIsNone(payment.paypal_order_id)
        self.assertIsNone(payment.paypal_payment_id)

    def test_payment_paypal_order_id_unique(self):
        """paypal_order_id must be unique when set."""
        from django.db import IntegrityError
        Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
            paypal_order_id='ORDER-123',
        )
        with self.assertRaises(IntegrityError):
            Payment.objects.create(
                user=self.user,
                conference=self.conference,
                amount=Decimal('100.00'),
                paypal_order_id='ORDER-123',
            )

    def test_payment_ordering_by_created_at_desc(self):
        """Payments are ordered by created_at descending (most recent first)."""
        p1 = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        p2 = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('200.00'),
        )
        payments = list(Payment.objects.all())
        self.assertEqual(payments[0], p2)
        self.assertEqual(payments[1], p1)

    def test_payment_cascade_delete_user(self):
        """Deleting a user cascades to delete their payments."""
        Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.user.delete()
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_cascade_delete_conference(self):
        """Deleting a conference cascades to delete its payments."""
        Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.conference.delete()
        self.assertEqual(Payment.objects.count(), 0)

    def test_payment_tier_set_null_on_delete(self):
        """Deleting a tier sets the payment's tier to NULL."""
        payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            tier=self.tier,
            amount=Decimal('200.00'),
        )
        self.tier.delete()
        payment.refresh_from_db()
        self.assertIsNone(payment.tier)


class TrackModelTests(ConferenceTestMixin, TestCase):
    """Tests for the Track model."""

    def setUp(self):
        self.conference = self.create_conference()

    def test_track_creation(self):
        """Track can be created with a conference and name."""
        track = Track.objects.create(
            conference=self.conference,
            name='Artificial Intelligence',
        )
        self.assertEqual(track.name, 'Artificial Intelligence')
        self.assertEqual(track.conference, self.conference)

    def test_str_representation(self):
        """__str__ includes track name and conference name."""
        track = Track.objects.create(
            conference=self.conference,
            name='Machine Learning',
        )
        self.assertEqual(str(track), f'Machine Learning ({self.conference.conference_name})')

    def test_unique_together_constraint(self):
        """Cannot create two tracks with the same name in the same conference."""
        from django.db import IntegrityError
        Track.objects.create(conference=self.conference, name='AI')
        with self.assertRaises(IntegrityError):
            Track.objects.create(conference=self.conference, name='AI')

    def test_same_track_name_different_conferences(self):
        """Same track name can exist in different conferences."""
        other_conf = self.create_conference(conference_name='Other Conference')
        Track.objects.create(conference=self.conference, name='AI')
        Track.objects.create(conference=other_conf, name='AI')
        self.assertEqual(Track.objects.filter(name='AI').count(), 2)

    def test_ordering_by_name(self):
        """Tracks are ordered alphabetically by name."""
        Track.objects.create(conference=self.conference, name='Zeta Track')
        Track.objects.create(conference=self.conference, name='Alpha Track')
        tracks = list(Track.objects.filter(conference=self.conference))
        self.assertEqual(tracks[0].name, 'Alpha Track')
        self.assertEqual(tracks[1].name, 'Zeta Track')

    def test_cascade_delete_conference(self):
        """Deleting a conference cascades to delete its tracks."""
        Track.objects.create(conference=self.conference, name='Track A')
        Track.objects.create(conference=self.conference, name='Track B')
        self.assertEqual(Track.objects.count(), 2)
        self.conference.delete()
        self.assertEqual(Track.objects.count(), 0)


# ===========================================================================
# VIEW TESTS
# ===========================================================================


@override_settings(
    PAYPAL_PAYMENT_LINK='https://www.paypal.com/ncp/payment/TEST',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ConferenceListViewTests(ConferenceTestMixin, TestCase):
    """Tests for the conference_list_view."""

    def setUp(self):
        self.client = Client()
        self.user = self.create_user()
        self.url = reverse('conference_list')

    def test_redirect_if_not_logged_in(self):
        """Unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_accessible_when_logged_in(self):
        """Authenticated users can access the conference list."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        """View renders conference/conference_list.html."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'conference/conference_list.html')

    def test_lists_all_conferences(self):
        """All conferences are passed in context."""
        self.create_conference(conference_name='Conference A')
        self.create_conference(conference_name='Conference B')
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['conferences']), 2)

    def test_empty_list_when_no_conferences(self):
        """Context contains empty queryset when there are no conferences."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['conferences']), 0)


@override_settings(
    PAYPAL_PAYMENT_LINK='https://www.paypal.com/ncp/payment/TEST',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ConferenceDetailViewTests(ConferenceTestMixin, TestCase):
    """Tests for the conference_detail_view."""

    def setUp(self):
        self.client = Client()
        self.user = self.create_user()
        self.conference = self.create_conference()
        self.url = reverse('conference_detail', kwargs={'slug': self.conference.slug})

    def test_redirect_if_not_logged_in(self):
        """Unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_accessible_when_logged_in(self):
        """Authenticated users can access the detail page."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        """View renders conference/conference_detail.html."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'conference/conference_detail.html')

    def test_context_contains_conference(self):
        """The correct conference object is in context."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['conference'], self.conference)

    def test_404_for_invalid_slug(self):
        """Non-existent slug returns 404."""
        self.client.login(email='testuser@example.com', password='testpass123')
        url = reverse('conference_detail', kwargs={'slug': 'does-not-exist'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


@override_settings(
    PAYPAL_PAYMENT_LINK='https://www.paypal.com/ncp/payment/TEST',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PaymentCheckoutViewTests(ConferenceTestMixin, TestCase):
    """Tests for the payment_checkout view."""

    def setUp(self):
        self.client = Client()
        self.user = self.create_user()
        self.conference = self.create_conference(
            early_bird_deadline=date.today() + timedelta(days=10),
            member_discount_percent=10,
        )
        self.tier = RegistrationTier.objects.create(
            conference=self.conference,
            name='Professional',
            price=Decimal('200.00'),
            early_bird_price=Decimal('150.00'),
            is_active=True,
        )
        self.url = reverse('payment_checkout', kwargs={'slug': self.conference.slug})

    def test_redirect_if_not_logged_in(self):
        """Unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_get_shows_checkout_page(self):
        """GET request renders the checkout page."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'conference/payment_checkout.html')

    def test_get_creates_membership_if_not_exists(self):
        """GET creates an unpaid Membership if one does not exist."""
        self.client.login(email='testuser@example.com', password='testpass123')
        self.assertFalse(Membership.objects.filter(user=self.user, conference=self.conference).exists())
        self.client.get(self.url)
        membership = Membership.objects.get(user=self.user, conference=self.conference)
        self.assertFalse(membership.is_paid)

    def test_get_redirects_if_already_paid(self):
        """GET redirects to conference detail if the user has already paid."""
        Membership.objects.create(
            user=self.user,
            conference=self.conference,
            is_paid=True,
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.conference.slug, response.url)

    def test_get_context_contains_tier_pricing(self):
        """GET includes tier_pricing in context when tiers exist."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn('tier_pricing', response.context)
        self.assertIsNotNone(response.context['tier_pricing'])
        self.assertEqual(len(response.context['tier_pricing']), 1)

    def test_get_context_without_tiers(self):
        """GET shows flat pricing when no tiers exist for the conference."""
        RegistrationTier.objects.all().delete()
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIsNone(response.context['tier_pricing'])
        self.assertIn('amount', response.context)

    def test_get_flat_price_student(self):
        """GET shows $50 for student users when no tiers exist."""
        RegistrationTier.objects.all().delete()
        student_user = self.create_user(
            email='student@example.com',
            occupation='student_undergraduate',
        )
        self.client.login(email='student@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['amount'], 50.00)
        self.assertEqual(response.context['price_type'], 'Student')

    def test_get_flat_price_non_student(self):
        """GET shows $100 for non-student users when no tiers exist."""
        RegistrationTier.objects.all().delete()
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.context['amount'], 100.00)
        self.assertEqual(response.context['price_type'], 'Regular')

    def test_post_creates_pending_payment_with_tier(self):
        """POST with a valid tier creates a pending Payment."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.post(self.url, {'tier_id': self.tier.id})
        self.assertEqual(Payment.objects.count(), 1)
        payment = Payment.objects.first()
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.conference, self.conference)
        self.assertEqual(payment.tier, self.tier)
        self.assertEqual(payment.status, 'pending')

    def test_post_payment_amount_early_bird(self):
        """POST uses the early bird price during the early bird period."""
        self.client.login(email='testuser@example.com', password='testpass123')
        self.client.post(self.url, {'tier_id': self.tier.id})
        payment = Payment.objects.first()
        # user.iatm_membership is False, so no member discount, but early bird applies
        self.assertEqual(payment.amount, Decimal('150.00'))

    def test_post_payment_amount_early_bird_member(self):
        """POST applies member discount on top of early bird price."""
        member_user = self.create_user(
            email='member@example.com',
            iatm_membership=True,
        )
        self.client.login(email='member@example.com', password='testpass123')
        self.client.post(self.url, {'tier_id': self.tier.id})
        payment = Payment.objects.first()
        # 150 - 10% = 135
        self.assertEqual(payment.amount, Decimal('135.00'))

    def test_post_redirects_to_paypal(self):
        """POST redirects to the PayPal payment link."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.post(self.url, {'tier_id': self.tier.id})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://www.paypal.com/ncp/payment/TEST')

    def test_post_stores_payment_id_in_session(self):
        """POST stores the pending payment ID in the session."""
        self.client.login(email='testuser@example.com', password='testpass123')
        self.client.post(self.url, {'tier_id': self.tier.id})
        payment = Payment.objects.first()
        session = self.client.session
        self.assertEqual(session['pending_payment_id'], payment.id)
        self.assertEqual(session['conference_slug'], self.conference.slug)

    def test_post_without_tier_id_redirects_back(self):
        """POST without a tier_id when tiers exist redirects back to checkout."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 302)
        self.assertIn('payment', response.url)
        self.assertEqual(Payment.objects.count(), 0)

    def test_post_without_tiers_student_price(self):
        """POST without tiers charges $50 for students."""
        RegistrationTier.objects.all().delete()
        student_user = self.create_user(
            email='student@example.com',
            occupation='student_graduate',
        )
        self.client.login(email='student@example.com', password='testpass123')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.first()
        self.assertEqual(payment.amount, Decimal('50.00'))
        self.assertIsNone(payment.tier)

    def test_post_without_tiers_regular_price(self):
        """POST without tiers charges $100 for non-students."""
        RegistrationTier.objects.all().delete()
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.first()
        self.assertEqual(payment.amount, Decimal('100.00'))

    def test_404_for_invalid_conference_slug(self):
        """Checkout returns 404 for a non-existent conference slug."""
        self.client.login(email='testuser@example.com', password='testpass123')
        url = reverse('payment_checkout', kwargs={'slug': 'nonexistent'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


@override_settings(
    PAYPAL_PAYMENT_LINK='https://www.paypal.com/ncp/payment/TEST',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PaymentSuccessViewTests(ConferenceTestMixin, TestCase):
    """Tests for the payment_success view."""

    def setUp(self):
        self.client = Client()
        self.user = self.create_user()
        self.conference = self.create_conference()
        self.membership = Membership.objects.create(
            user=self.user,
            conference=self.conference,
            is_paid=False,
        )
        self.payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
            status='pending',
        )
        self.url = reverse('payment_success', kwargs={'slug': self.conference.slug})

    def test_redirect_if_not_logged_in(self):
        """Unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_marks_payment_as_completed(self):
        """Payment status is updated to 'completed' on success."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        self.client.get(self.url)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'completed')

    def test_marks_membership_as_paid(self):
        """Membership is_paid is set to True on payment success."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        self.client.get(self.url)
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.is_paid)

    def test_redirects_to_conference_detail(self):
        """After processing, redirects to conference detail."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        expected_url = reverse('conference_detail', kwargs={'slug': self.conference.slug})
        self.assertEqual(response.url, expected_url)

    def test_clears_session_data(self):
        """Session keys are cleared after processing."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        self.client.get(self.url)
        session = self.client.session
        self.assertNotIn('pending_payment_id', session)
        self.assertNotIn('conference_slug', session)

    def test_no_update_without_session_data(self):
        """Payment is not updated if session data is missing."""
        self.client.login(email='testuser@example.com', password='testpass123')
        self.client.get(self.url)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_no_update_with_wrong_slug_in_session(self):
        """Payment is not updated if session slug does not match URL slug."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = 'wrong-slug'
        session.save()

        self.client.get(self.url)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_does_not_re_complete_already_completed_payment(self):
        """An already completed payment is not processed again."""
        self.payment.status = 'completed'
        self.payment.save()
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        self.client.get(self.url)
        self.payment.refresh_from_db()
        # Status stays completed, but the if-branch is not re-entered
        self.assertEqual(self.payment.status, 'completed')

    def test_handles_nonexistent_payment_id(self):
        """View handles a session with a non-existent payment ID gracefully."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = 99999
        session['conference_slug'] = self.conference.slug
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_payment_from_different_user_not_updated(self):
        """A payment belonging to another user is not updated."""
        other_user = self.create_user(email='other@example.com')
        other_payment = Payment.objects.create(
            user=other_user,
            conference=self.conference,
            amount=Decimal('100.00'),
            status='pending',
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = other_payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        self.client.get(self.url)
        other_payment.refresh_from_db()
        # Payment.objects.get filters by user=request.user, so it won't find another user's payment
        self.assertEqual(other_payment.status, 'pending')


@override_settings(
    PAYPAL_PAYMENT_LINK='https://www.paypal.com/ncp/payment/TEST',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PaymentCancelViewTests(ConferenceTestMixin, TestCase):
    """Tests for the payment_cancel view."""

    def setUp(self):
        self.client = Client()
        self.user = self.create_user()
        self.conference = self.create_conference()
        self.payment = Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
            status='pending',
        )
        self.url = reverse('payment_cancel', kwargs={'slug': self.conference.slug})

    def test_redirect_if_not_logged_in(self):
        """Unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_marks_payment_as_cancelled(self):
        """Payment status is updated to 'cancelled'."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session.save()

        self.client.get(self.url)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'cancelled')

    def test_redirects_to_conference_detail(self):
        """After cancellation, redirects to conference detail page."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        expected_url = reverse('conference_detail', kwargs={'slug': self.conference.slug})
        self.assertEqual(response.url, expected_url)

    def test_clears_session_data(self):
        """Session keys are cleared after cancellation."""
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = self.payment.id
        session['conference_slug'] = self.conference.slug
        session.save()

        self.client.get(self.url)
        session = self.client.session
        self.assertNotIn('pending_payment_id', session)
        self.assertNotIn('conference_slug', session)

    def test_no_payment_in_session(self):
        """View handles missing session payment ID gracefully."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        # Payment status unchanged since it was never referenced
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_cancel_does_not_affect_other_users_payment(self):
        """A cancel request does not affect another user's payment."""
        other_user = self.create_user(email='other@example.com')
        other_payment = Payment.objects.create(
            user=other_user,
            conference=self.conference,
            amount=Decimal('100.00'),
            status='pending',
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        session = self.client.session
        session['pending_payment_id'] = other_payment.id
        session.save()

        self.client.get(self.url)
        other_payment.refresh_from_db()
        # Payment.objects.get filters by user=request.user, so other user's payment is untouched
        self.assertEqual(other_payment.status, 'pending')

    def test_404_for_invalid_conference_slug(self):
        """Cancel returns 404 for a non-existent conference slug."""
        self.client.login(email='testuser@example.com', password='testpass123')
        url = reverse('payment_cancel', kwargs={'slug': 'nonexistent'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


@override_settings(
    PAYPAL_PAYMENT_LINK='https://www.paypal.com/ncp/payment/TEST',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class UserDashboardViewTests(ConferenceTestMixin, TestCase):
    """Tests for the user_dashboard view."""

    def setUp(self):
        self.client = Client()
        self.user = self.create_user()
        self.conference = self.create_conference()
        self.url = reverse('user_dashboard')

    def test_redirect_if_not_logged_in(self):
        """Unauthenticated users are redirected to login."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_accessible_when_logged_in(self):
        """Authenticated users can access the dashboard."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_uses_correct_template(self):
        """View renders conference/user_dashboard.html."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'conference/user_dashboard.html')

    def test_context_contains_memberships(self):
        """Dashboard context includes the user's memberships."""
        Membership.objects.create(
            user=self.user,
            conference=self.conference,
            is_paid=True,
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn('memberships', response.context)
        self.assertEqual(response.context['memberships'].count(), 1)

    def test_context_contains_completed_payments(self):
        """Dashboard context includes only completed payments."""
        Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
            status='completed',
        )
        Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('50.00'),
            status='pending',
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn('payments', response.context)
        self.assertEqual(response.context['payments'].count(), 1)
        self.assertEqual(response.context['payments'].first().status, 'completed')

    def test_context_contains_submissions(self):
        """Dashboard context includes the submissions key."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn('submissions', response.context)

    def test_context_contains_upcoming_sessions(self):
        """Dashboard context includes the upcoming_sessions key."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn('upcoming_sessions', response.context)

    def test_context_contains_certificate_memberships(self):
        """Dashboard context includes the certificate_memberships key."""
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        self.assertIn('certificate_memberships', response.context)

    def test_only_shows_own_memberships(self):
        """Dashboard only shows the logged-in user's memberships, not others'."""
        other_user = self.create_user(email='other@example.com')
        Membership.objects.create(
            user=self.user,
            conference=self.conference,
            is_paid=True,
        )
        other_conf = self.create_conference(conference_name='Other Conf')
        Membership.objects.create(
            user=other_user,
            conference=other_conf,
            is_paid=True,
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        memberships = response.context['memberships']
        self.assertEqual(memberships.count(), 1)
        self.assertEqual(memberships.first().user, self.user)

    def test_only_shows_own_payments(self):
        """Dashboard only shows the logged-in user's completed payments."""
        other_user = self.create_user(email='other@example.com')
        Payment.objects.create(
            user=self.user,
            conference=self.conference,
            amount=Decimal('100.00'),
            status='completed',
        )
        Payment.objects.create(
            user=other_user,
            conference=self.conference,
            amount=Decimal('200.00'),
            status='completed',
        )
        self.client.login(email='testuser@example.com', password='testpass123')
        response = self.client.get(self.url)
        payments = response.context['payments']
        self.assertEqual(payments.count(), 1)
        self.assertEqual(payments.first().user, self.user)
