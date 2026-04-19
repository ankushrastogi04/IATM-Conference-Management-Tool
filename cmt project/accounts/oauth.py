import json
import urllib.request
import urllib.parse
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import login
from django.contrib import messages
from django.urls import reverse


def google_login(request):
    """Redirect to Google OAuth consent screen."""
    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        messages.error(request, "Google login is not configured.")
        return redirect('login')

    redirect_uri = request.build_absolute_uri(reverse('google_callback'))
    params = urllib.parse.urlencode({
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'access_type': 'offline',
        'prompt': 'select_account',
    })
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{params}')


def google_callback(request):
    """Handle Google OAuth callback."""
    from accounts.models import CustomUser

    code = request.GET.get('code')
    error = request.GET.get('error')

    if error or not code:
        messages.error(request, "Google login was cancelled or failed.")
        return redirect('login')

    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET
    redirect_uri = request.build_absolute_uri(reverse('google_callback'))

    # Exchange code for tokens
    try:
        token_data = urllib.parse.urlencode({
            'code': code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }).encode()

        token_req = urllib.request.Request(
            'https://oauth2.googleapis.com/token',
            data=token_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )
        with urllib.request.urlopen(token_req) as resp:
            tokens = json.loads(resp.read())

        access_token = tokens.get('access_token')
        if not access_token:
            messages.error(request, "Failed to authenticate with Google.")
            return redirect('login')

        # Get user info
        info_req = urllib.request.Request(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        with urllib.request.urlopen(info_req) as resp:
            user_info = json.loads(resp.read())

        email = user_info.get('email', '')
        if not email:
            messages.error(request, "Could not retrieve email from Google.")
            return redirect('login')

        # Find or create user
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            user = CustomUser.objects.create_user(
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                country='',
                organization='',
                phone='',
            )

        login(request, user)
        messages.success(request, f"Welcome, {user.first_name}!")
        return redirect('profile')

    except Exception as e:
        messages.error(request, f"Google login error: {str(e)}")
        return redirect('login')
