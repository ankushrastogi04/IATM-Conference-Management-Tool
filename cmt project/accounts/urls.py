from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import oauth as views_oauth

urlpatterns = [
    path('', views.home_redirect_view, name='home_redirect'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit', views.profile_edit_view, name='profile_edit'),
    path('logout/', views.logout_view, name='logout'),

    # Password change (logged-in users)
    path('password/change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change.html',
        success_url='/accounts/password/change/done/',
    ), name='password_change'),
    path('password/change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html',
    ), name='password_change_done'),

    # Password reset (forgot password)
    path('password/reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url='/accounts/password/reset/done/',
    ), name='password_reset'),
    path('password/reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url='/accounts/password/reset/complete/',
    ), name='password_reset_confirm'),
    path('password/reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),

    # GDPR / Privacy
    path('privacy/', views.privacy_policy_view, name='privacy_policy'),
    path('export-data/', views.export_my_data, name='export_my_data'),
    path('delete-account/', views.delete_my_account, name='delete_my_account'),

    # Google OAuth
    path('google/login/', views_oauth.google_login, name='google_login'),
    path('google/callback/', views_oauth.google_callback, name='google_callback'),
]