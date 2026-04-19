import json
from decimal import Decimal
from datetime import date

from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model

from accounts.models import CustomUser, CustomUserManager, Occupation
from accounts.forms import login_form, CustomUserCreationForm, ProfileEditForm
from accounts import views

User = get_user_model()

# Shared helper data for creating test users
USER_DATA = {
    'email': 'test@example.com',
    'password': 'testpass123',
    'first_name': 'Test',
    'last_name': 'User',
    'country': 'US',
    'organization': 'TestOrg',
    'phone': '1234567890',
    'occupation': 'faculty',
}


def create_test_user(**overrides):
    """Create and return a test user with default data, applying any overrides."""
    data = {**USER_DATA, **overrides}
    return User.objects.create_user(**data)


# ---------------------------------------------------------------------------
# MODEL TESTS
# ---------------------------------------------------------------------------

class CustomUserManagerTests(TestCase):
    """Tests for CustomUserManager.create_user and create_superuser."""

    def test_create_user_with_valid_data(self):
        user = create_test_user()
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.country, 'US')
        self.assertEqual(user.organization, 'TestOrg')
        self.assertEqual(user.phone, '1234567890')
        self.assertEqual(user.occupation, 'faculty')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_email_normalization(self):
        user = create_test_user(email='Test@EXAMPLE.COM')
        self.assertEqual(user.email, 'Test@example.com')

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError) as ctx:
            User.objects.create_user(email='', password='pass123')
        self.assertIn('Email', str(ctx.exception))

    def test_create_user_with_no_password(self):
        user = User.objects.create_user(
            email='nopass@example.com',
            first_name='No',
            last_name='Pass',
            country='UK',
            organization='Org',
            phone='0000000000',
            occupation='other',
        )
        self.assertFalse(user.has_usable_password())

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
            country='US',
            organization='AdminOrg',
            phone='9999999999',
            occupation='faculty',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.check_password('adminpass123'))

    def test_create_superuser_defaults(self):
        """create_superuser sets is_staff, is_superuser, is_active even if not passed."""
        admin = User.objects.create_superuser(
            email='admin2@example.com',
            password='adminpass123',
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_active)


class CustomUserModelTests(TestCase):
    """Tests for CustomUser model fields and configuration."""

    def test_username_field_is_email(self):
        self.assertEqual(CustomUser.USERNAME_FIELD, 'email')

    def test_username_is_none(self):
        self.assertIsNone(CustomUser.username)

    def test_required_fields(self):
        expected = ['first_name', 'last_name', 'country', 'organization', 'phone', 'occupation']
        self.assertEqual(CustomUser.REQUIRED_FIELDS, expected)

    def test_str_method(self):
        """CustomUser inherits AbstractUser.__str__, which returns the USERNAME_FIELD (email)."""
        user = create_test_user()
        self.assertEqual(str(user), user.email)

    def test_email_uniqueness(self):
        create_test_user()
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            create_test_user()

    def test_iatm_membership_default_false(self):
        user = create_test_user()
        self.assertFalse(user.iatm_membership)

    def test_occupation_choices(self):
        choices = [c[0] for c in Occupation.choices]
        self.assertIn('student_undergraduate', choices)
        self.assertIn('student_graduate', choices)
        self.assertIn('faculty', choices)
        self.assertIn('alumni', choices)
        self.assertIn('other', choices)

    def test_occupation_labels(self):
        self.assertEqual(Occupation.STUDENT_UNDERGRADUATE.label, 'Student - Undergraduate')
        self.assertEqual(Occupation.STUDENT_GRADUATE.label, 'Student - Graduate')
        self.assertEqual(Occupation.FACULTY.label, 'Faculty')
        self.assertEqual(Occupation.ALUMNI.label, 'Alumni')
        self.assertEqual(Occupation.OTHER.label, 'Other')

    def test_default_occupation(self):
        """The default occupation is student_undergraduate per the model field definition."""
        user = User.objects.create_user(
            email='default_occ@example.com',
            password='testpass123',
            first_name='Default',
            last_name='Occ',
            country='US',
            organization='Org',
            phone='1111111111',
        )
        self.assertEqual(user.occupation, 'student_undergraduate')

    def test_custom_manager_is_set(self):
        self.assertIsInstance(CustomUser.objects, CustomUserManager)


# ---------------------------------------------------------------------------
# FORM TESTS
# ---------------------------------------------------------------------------

class LoginFormTests(TestCase):
    """Tests for the login_form."""

    def setUp(self):
        self.user = create_test_user()

    def test_valid_login(self):
        form = login_form(data={
            'email': 'test@example.com',
            'password': 'testpass123',
        })
        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user(), self.user)

    def test_invalid_password(self):
        form = login_form(data={
            'email': 'test@example.com',
            'password': 'wrongpassword',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid email or password', str(form.errors))

    def test_invalid_email(self):
        form = login_form(data={
            'email': 'nonexistent@example.com',
            'password': 'testpass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('Invalid email or password', str(form.errors))

    def test_missing_email(self):
        form = login_form(data={
            'email': '',
            'password': 'testpass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_missing_password(self):
        form = login_form(data={
            'email': 'test@example.com',
            'password': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_get_user_returns_none_before_validation(self):
        form = login_form(data={
            'email': 'test@example.com',
            'password': 'testpass123',
        })
        # Before calling is_valid, get_user should return None
        self.assertIsNone(form.get_user())

    def test_get_user_returns_none_for_invalid_credentials(self):
        form = login_form(data={
            'email': 'test@example.com',
            'password': 'wrong',
        })
        form.is_valid()
        self.assertIsNone(form.get_user())

    def test_accepts_request_kwarg(self):
        """The form accepts an optional 'request' keyword argument."""
        form = login_form(data={
            'email': 'test@example.com',
            'password': 'testpass123',
        }, request=None)
        self.assertTrue(form.is_valid())

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        form = login_form(data={
            'email': 'test@example.com',
            'password': 'testpass123',
        })
        self.assertFalse(form.is_valid())


class CustomUserCreationFormTests(TestCase):
    """Tests for CustomUserCreationForm (registration)."""

    def get_valid_data(self, **overrides):
        data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'country': 'Canada',
            'organization': 'NewOrg',
            'phone': '5551234567',
            'occupation': 'student_graduate',
            'password1': 'securePass789!',
            'password2': 'securePass789!',
        }
        data.update(overrides)
        return data

    def test_valid_registration_form(self):
        form = CustomUserCreationForm(data=self.get_valid_data())
        self.assertTrue(form.is_valid())

    def test_saves_user(self):
        form = CustomUserCreationForm(data=self.get_valid_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'New')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.country, 'Canada')
        self.assertEqual(user.organization, 'NewOrg')
        self.assertEqual(user.phone, '5551234567')
        self.assertEqual(user.occupation, 'student_graduate')
        self.assertTrue(user.check_password('securePass789!'))

    def test_password_mismatch(self):
        form = CustomUserCreationForm(data=self.get_valid_data(
            password2='differentpassword',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_missing_email(self):
        form = CustomUserCreationForm(data=self.get_valid_data(email=''))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_duplicate_email(self):
        create_test_user()
        form = CustomUserCreationForm(data=self.get_valid_data(
            email='test@example.com',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_missing_first_name(self):
        form = CustomUserCreationForm(data=self.get_valid_data(first_name=''))
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    def test_missing_last_name(self):
        form = CustomUserCreationForm(data=self.get_valid_data(last_name=''))
        self.assertFalse(form.is_valid())
        self.assertIn('last_name', form.errors)

    def test_missing_country(self):
        form = CustomUserCreationForm(data=self.get_valid_data(country=''))
        self.assertFalse(form.is_valid())
        self.assertIn('country', form.errors)

    def test_missing_organization(self):
        form = CustomUserCreationForm(data=self.get_valid_data(organization=''))
        self.assertFalse(form.is_valid())
        self.assertIn('organization', form.errors)

    def test_missing_phone(self):
        form = CustomUserCreationForm(data=self.get_valid_data(phone=''))
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_invalid_occupation_choice(self):
        form = CustomUserCreationForm(data=self.get_valid_data(occupation='invalid_choice'))
        self.assertFalse(form.is_valid())
        self.assertIn('occupation', form.errors)

    def test_weak_password_rejected(self):
        form = CustomUserCreationForm(data=self.get_valid_data(
            password1='123',
            password2='123',
        ))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_form_meta_model(self):
        self.assertEqual(CustomUserCreationForm.Meta.model, CustomUser)

    def test_form_meta_fields(self):
        expected = ['email', 'first_name', 'last_name', 'country', 'organization', 'phone', 'occupation']
        self.assertEqual(list(CustomUserCreationForm.Meta.fields), expected)


class ProfileEditFormTests(TestCase):
    """Tests for ProfileEditForm."""

    def setUp(self):
        self.user = create_test_user()

    def test_valid_edit(self):
        form = ProfileEditForm(data={
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '9876543210',
            'country': 'UK',
            'organization': 'NewOrg',
            'occupation': 'alumni',
        }, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.first_name, 'Updated')
        self.assertEqual(user.last_name, 'Name')
        self.assertEqual(user.phone, '9876543210')
        self.assertEqual(user.country, 'UK')
        self.assertEqual(user.organization, 'NewOrg')
        self.assertEqual(user.occupation, 'alumni')

    def test_form_meta_fields(self):
        expected = ['first_name', 'last_name', 'phone', 'country', 'organization', 'occupation']
        self.assertEqual(list(ProfileEditForm.Meta.fields), expected)

    def test_email_not_editable(self):
        """ProfileEditForm should NOT allow changing the email."""
        self.assertNotIn('email', ProfileEditForm.Meta.fields)

    def test_password_not_editable(self):
        """ProfileEditForm should NOT expose password fields."""
        form = ProfileEditForm(instance=self.user)
        self.assertNotIn('password', form.fields)
        self.assertNotIn('password1', form.fields)
        self.assertNotIn('password2', form.fields)

    def test_missing_first_name_invalid(self):
        form = ProfileEditForm(data={
            'first_name': '',
            'last_name': 'Name',
            'phone': '1234567890',
            'country': 'US',
            'organization': 'Org',
            'occupation': 'faculty',
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)

    def test_missing_last_name_invalid(self):
        form = ProfileEditForm(data={
            'first_name': 'First',
            'last_name': '',
            'phone': '1234567890',
            'country': 'US',
            'organization': 'Org',
            'occupation': 'faculty',
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('last_name', form.errors)

    def test_invalid_occupation_rejected(self):
        form = ProfileEditForm(data={
            'first_name': 'First',
            'last_name': 'Last',
            'phone': '1234567890',
            'country': 'US',
            'organization': 'Org',
            'occupation': 'not_a_choice',
        }, instance=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('occupation', form.errors)

    def test_preserves_unedited_fields(self):
        """Saving the form should not affect fields not in the form (like email)."""
        original_email = self.user.email
        form = ProfileEditForm(data={
            'first_name': 'Changed',
            'last_name': 'User',
            'phone': '1234567890',
            'country': 'US',
            'organization': 'TestOrg',
            'occupation': 'faculty',
        }, instance=self.user)
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.email, original_email)


# ---------------------------------------------------------------------------
# URL RESOLUTION TESTS
# ---------------------------------------------------------------------------

class URLResolutionTests(TestCase):
    """Tests that each URL name resolves to the correct view function."""

    def test_login_url_resolves(self):
        url = reverse('login')
        self.assertEqual(resolve(url).func, views.login_view)

    def test_register_url_resolves(self):
        url = reverse('register')
        self.assertEqual(resolve(url).func, views.register_view)

    def test_profile_url_resolves(self):
        url = reverse('profile')
        self.assertEqual(resolve(url).func, views.profile_view)

    def test_profile_edit_url_resolves(self):
        url = reverse('profile_edit')
        self.assertEqual(resolve(url).func, views.profile_edit_view)

    def test_logout_url_resolves(self):
        url = reverse('logout')
        self.assertEqual(resolve(url).func, views.logout_view)

    def test_home_redirect_url_resolves(self):
        url = reverse('home_redirect')
        self.assertEqual(resolve(url).func, views.home_redirect_view)

    def test_privacy_policy_url_resolves(self):
        url = reverse('privacy_policy')
        self.assertEqual(resolve(url).func, views.privacy_policy_view)

    def test_export_my_data_url_resolves(self):
        url = reverse('export_my_data')
        self.assertEqual(resolve(url).func, views.export_my_data)

    def test_delete_my_account_url_resolves(self):
        url = reverse('delete_my_account')
        self.assertEqual(resolve(url).func, views.delete_my_account)

    def test_login_url_path(self):
        url = reverse('login')
        self.assertIn('accounts/login', url)

    def test_register_url_path(self):
        url = reverse('register')
        self.assertIn('accounts/register', url)


# ---------------------------------------------------------------------------
# VIEW TESTS
# ---------------------------------------------------------------------------

class LoginViewTests(TestCase):
    """Tests for login_view."""

    def setUp(self):
        self.client = Client()
        self.user = create_test_user()
        self.login_url = reverse('login')
        self.profile_url = reverse('profile')

    def test_login_page_get(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertIn('form', response.context)

    def test_login_success_redirects_to_profile(self):
        response = self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'testpass123',
        })
        self.assertRedirects(response, self.profile_url)

    def test_login_success_authenticates_user(self):
        self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'testpass123',
        })
        response = self.client.get(self.profile_url)
        self.assertEqual(response.wsgi_request.user, self.user)

    def test_login_invalid_credentials(self):
        response = self.client.post(self.login_url, {
            'email': 'test@example.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')
        self.assertTrue(response.wsgi_request.user.is_anonymous)

    def test_authenticated_user_redirected_from_login(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.login_url)
        self.assertRedirects(response, self.profile_url)

    def test_login_with_empty_form(self):
        response = self.client.post(self.login_url, {
            'email': '',
            'password': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')


class RegisterViewTests(TestCase):
    """Tests for register_view."""

    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register')
        self.profile_url = reverse('profile')

    def get_valid_registration_data(self, **overrides):
        data = {
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'country': 'Canada',
            'organization': 'NewOrg',
            'phone': '5551234567',
            'occupation': 'student_graduate',
            'password1': 'securePass789!',
            'password2': 'securePass789!',
        }
        data.update(overrides)
        return data

    def test_register_page_get(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')
        self.assertIn('form', response.context)

    def test_register_success_creates_user(self):
        data = self.get_valid_registration_data()
        self.client.post(self.register_url, data)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    def test_register_success_redirects_to_profile(self):
        data = self.get_valid_registration_data()
        response = self.client.post(self.register_url, data)
        self.assertRedirects(response, self.profile_url)

    def test_register_success_auto_login(self):
        data = self.get_valid_registration_data()
        self.client.post(self.register_url, data)
        response = self.client.get(self.profile_url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.email, 'newuser@example.com')

    def test_register_invalid_data_shows_form(self):
        data = self.get_valid_registration_data(email='')
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/register.html')
        self.assertFalse(User.objects.filter(first_name='New').exists())

    def test_register_password_mismatch(self):
        data = self.get_valid_registration_data(password2='differentpassword')
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='newuser@example.com').exists())

    def test_register_duplicate_email(self):
        create_test_user()
        data = self.get_valid_registration_data(email='test@example.com')
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email='test@example.com').count(), 1)

    def test_register_success_message(self):
        data = self.get_valid_registration_data()
        response = self.client.post(self.register_url, follow=True)
        # Without valid data, no message; re-test with valid data
        response = self.client.post(self.register_url, data, follow=True)
        messages_list = list(response.context['messages'])
        # The view adds a success message on registration
        success_messages = [m for m in messages_list if m.level_tag == 'success']
        self.assertTrue(len(success_messages) > 0)


class ProfileViewTests(TestCase):
    """Tests for profile_view and profile_edit_view."""

    def setUp(self):
        self.client = Client()
        self.user = create_test_user()
        self.profile_url = reverse('profile')
        self.profile_edit_url = reverse('profile_edit')

    def test_profile_view_authenticated(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile.html')
        self.assertIn('user', response.context)

    def test_profile_edit_redirects_unauthenticated(self):
        response = self.client.get(self.profile_edit_url)
        # profile_edit_view manually redirects to 'login' if not authenticated
        self.assertRedirects(response, reverse('login'))

    def test_profile_edit_get_authenticated(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.profile_edit_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile_edit.html')
        self.assertIn('form', response.context)

    def test_profile_edit_post_valid_data(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.profile_edit_url, {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '9876543210',
            'country': 'UK',
            'organization': 'NewOrg',
            'occupation': 'alumni',
        })
        self.assertRedirects(response, self.profile_url)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
        self.assertEqual(self.user.phone, '9876543210')
        self.assertEqual(self.user.country, 'UK')
        self.assertEqual(self.user.organization, 'NewOrg')
        self.assertEqual(self.user.occupation, 'alumni')

    def test_profile_edit_post_invalid_data(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.profile_edit_url, {
            'first_name': '',
            'last_name': 'Name',
            'phone': '9876543210',
            'country': 'UK',
            'organization': 'NewOrg',
            'occupation': 'alumni',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/profile_edit.html')
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Test')  # unchanged

    def test_profile_edit_preserves_email(self):
        """Editing profile should not change the user's email."""
        self.client.login(email='test@example.com', password='testpass123')
        self.client.post(self.profile_edit_url, {
            'first_name': 'Changed',
            'last_name': 'User',
            'phone': '1234567890',
            'country': 'US',
            'organization': 'TestOrg',
            'occupation': 'faculty',
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'test@example.com')

    def test_profile_edit_success_message(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.profile_edit_url, {
            'first_name': 'Updated',
            'last_name': 'Name',
            'phone': '9876543210',
            'country': 'UK',
            'organization': 'NewOrg',
            'occupation': 'alumni',
        }, follow=True)
        messages_list = list(response.context['messages'])
        self.assertTrue(any('Profile updated' in str(m) for m in messages_list))

    def test_profile_edit_form_pre_populated(self):
        """The edit form should be pre-populated with the user's current data."""
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.profile_edit_url)
        form = response.context['form']
        self.assertEqual(form.initial.get('first_name') or form.instance.first_name, 'Test')
        self.assertEqual(form.initial.get('last_name') or form.instance.last_name, 'User')


class LogoutViewTests(TestCase):
    """Tests for logout_view."""

    def setUp(self):
        self.client = Client()
        self.user = create_test_user()
        self.logout_url = reverse('logout')
        self.login_url = reverse('login')

    def test_logout_redirects_to_login(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)

    def test_logout_clears_session(self):
        self.client.login(email='test@example.com', password='testpass123')
        self.client.get(self.logout_url)
        response = self.client.get(reverse('profile'))
        self.assertTrue(response.wsgi_request.user.is_anonymous)

    def test_logout_unauthenticated_user(self):
        """Logging out when not logged in should still redirect to login."""
        response = self.client.get(self.logout_url)
        self.assertRedirects(response, self.login_url)


class HomeRedirectViewTests(TestCase):
    """Tests for home_redirect_view."""

    def setUp(self):
        self.client = Client()
        self.user = create_test_user()
        self.home_url = reverse('home_redirect')

    def test_authenticated_redirects_to_profile(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.home_url)
        self.assertRedirects(response, reverse('profile'))

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(self.home_url)
        self.assertRedirects(response, reverse('login'))


class PrivacyPolicyViewTests(TestCase):
    """Tests for privacy_policy_view."""

    def test_privacy_policy_page(self):
        response = self.client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/privacy_policy.html')

    def test_privacy_policy_accessible_without_login(self):
        """Privacy policy should be publicly accessible."""
        client = Client()
        response = client.get(reverse('privacy_policy'))
        self.assertEqual(response.status_code, 200)


class ExportMyDataViewTests(TestCase):
    """Tests for export_my_data (GDPR data export)."""

    def setUp(self):
        self.client = Client()
        self.user = create_test_user()
        self.export_url = reverse('export_my_data')

    def test_export_requires_login(self):
        response = self.client.get(self.export_url)
        # @login_required redirects to /accounts/login/ by default
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_export_returns_json(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_export_content_disposition(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('.json', response['Content-Disposition'])
        self.assertIn(str(self.user.id), response['Content-Disposition'])

    def test_export_contains_personal_info(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        data = json.loads(response.content)
        personal = data['personal_info']
        self.assertEqual(personal['email'], 'test@example.com')
        self.assertEqual(personal['first_name'], 'Test')
        self.assertEqual(personal['last_name'], 'User')
        self.assertEqual(personal['country'], 'US')
        self.assertEqual(personal['organization'], 'TestOrg')
        self.assertEqual(personal['phone'], '1234567890')
        self.assertEqual(personal['occupation'], 'Faculty')
        self.assertFalse(personal['iatm_membership'])
        self.assertIn('date_joined', personal)

    def test_export_contains_registrations_key(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        data = json.loads(response.content)
        self.assertIn('conference_registrations', data)
        self.assertIsInstance(data['conference_registrations'], list)

    def test_export_contains_payments_key(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        data = json.loads(response.content)
        self.assertIn('payments', data)
        self.assertIsInstance(data['payments'], list)

    def test_export_empty_registrations_and_payments(self):
        """A user with no memberships or payments should get empty lists."""
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        data = json.loads(response.content)
        self.assertEqual(data['conference_registrations'], [])
        self.assertEqual(data['payments'], [])

    def test_export_with_membership_data(self):
        """When a user has conference memberships, they appear in the export."""
        from conference.models import Conference
        from membership.models import Membership

        conf = Conference.objects.create(
            conference_name='Test Conf 2026',
            conference_description='A test conference',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            location='New York',
        )
        Membership.objects.create(
            user=self.user,
            conference=conf,
            role1='Author',
            role2='N/A',
            is_paid=True,
        )
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        data = json.loads(response.content)
        self.assertEqual(len(data['conference_registrations']), 1)
        reg = data['conference_registrations'][0]
        self.assertEqual(reg['conference'], 'Test Conf 2026')
        self.assertEqual(reg['role1'], 'Author')
        self.assertTrue(reg['is_paid'])

    def test_export_with_payment_data(self):
        """When a user has payments, they appear in the export."""
        from conference.models import Conference, Payment

        conf = Conference.objects.create(
            conference_name='Test Conf 2026',
            conference_description='A test conference',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            location='New York',
        )
        Payment.objects.create(
            user=self.user,
            conference=conf,
            amount=Decimal('150.00'),
            currency='USD',
            status='completed',
        )
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.export_url)
        data = json.loads(response.content)
        self.assertEqual(len(data['payments']), 1)
        pmt = data['payments'][0]
        self.assertEqual(pmt['conference'], 'Test Conf 2026')
        self.assertEqual(pmt['amount'], '150.00')
        self.assertEqual(pmt['currency'], 'USD')
        self.assertEqual(pmt['status'], 'completed')


class DeleteMyAccountViewTests(TestCase):
    """Tests for delete_my_account (GDPR account deletion)."""

    def setUp(self):
        self.client = Client()
        self.user = create_test_user()
        self.delete_url = reverse('delete_my_account')
        self.login_url = reverse('login')

    def test_delete_requires_login(self):
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_delete_get_shows_confirmation_page(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.get(self.delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/delete_account.html')

    def test_delete_post_with_correct_email(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.delete_url, {
            'confirm_email': 'test@example.com',
        })
        self.assertRedirects(response, self.login_url)
        self.assertFalse(User.objects.filter(email='test@example.com').exists())

    def test_delete_post_with_wrong_email(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.delete_url, {
            'confirm_email': 'wrong@example.com',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())

    def test_delete_post_with_empty_email(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.delete_url, {
            'confirm_email': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())

    def test_delete_post_without_confirm_email_field(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.delete_url, {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='test@example.com').exists())

    def test_delete_logs_out_user(self):
        self.client.login(email='test@example.com', password='testpass123')
        self.client.post(self.delete_url, {
            'confirm_email': 'test@example.com',
        })
        response = self.client.get(reverse('profile'))
        self.assertTrue(response.wsgi_request.user.is_anonymous)

    def test_delete_success_message(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.delete_url, {
            'confirm_email': 'test@example.com',
        }, follow=True)
        messages_list = list(response.context['messages'])
        self.assertTrue(any('permanently deleted' in str(m) for m in messages_list))

    def test_delete_wrong_email_error_message(self):
        self.client.login(email='test@example.com', password='testpass123')
        response = self.client.post(self.delete_url, {
            'confirm_email': 'wrong@example.com',
        })
        messages_list = list(response.wsgi_request._messages)
        self.assertTrue(any('did not match' in str(m) for m in messages_list))

    def test_delete_cascades_related_data(self):
        """Deleting the account should also remove related memberships and payments."""
        from conference.models import Conference, Payment
        from membership.models import Membership

        conf = Conference.objects.create(
            conference_name='Test Conf',
            conference_description='Desc',
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 3),
            location='NYC',
        )
        Membership.objects.create(user=self.user, conference=conf)
        Payment.objects.create(
            user=self.user,
            conference=conf,
            amount=Decimal('100.00'),
        )

        self.client.login(email='test@example.com', password='testpass123')
        self.client.post(self.delete_url, {
            'confirm_email': 'test@example.com',
        })

        self.assertFalse(User.objects.filter(email='test@example.com').exists())
        self.assertFalse(Membership.objects.filter(user=self.user.pk).exists())
        self.assertFalse(Payment.objects.filter(user=self.user.pk).exists())
