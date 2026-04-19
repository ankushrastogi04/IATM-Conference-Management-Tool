from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import login_form, CustomUserCreationForm, ProfileEditForm
from django.contrib.auth import authenticate, login, logout
from .models import CustomUser
from django.contrib import messages
from django.conf import settings as django_settings
from membership.models import Membership, Role
from django.db.models import Q

def login_view(request):
    if request.user.is_authenticated:
        return redirect('profile')

    form = login_form(request.POST or None, request=request)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('profile')

    return render(request, 'accounts/login.html', {
        'form': form,
        'google_oauth_enabled': bool(django_settings.GOOGLE_OAUTH_CLIENT_ID),
    })


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! You've successfully registered.")
            return redirect('profile')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def profile_view(request):
    return render(request, 'accounts/profile.html', {
        'user': request.user
    })


def profile_edit_view(request):
    if not request.user.is_authenticated:
        return redirect('login')
    form = ProfileEditForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Profile updated successfully.")
        return redirect('profile')
    return render(request, 'accounts/profile_edit.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')


def home_redirect_view(request):
    if request.user.is_authenticated:
        return redirect('profile')
    else:
        return redirect('login')


def privacy_policy_view(request):
    return render(request, 'accounts/privacy_policy.html')


@login_required
def export_my_data(request):
    """GDPR: Allow users to download all their personal data as JSON."""
    import json
    from django.http import HttpResponse
    from membership.models import Membership
    from conference.models import Payment

    user = request.user
    memberships = Membership.objects.filter(user=user).select_related('conference')
    payments = Payment.objects.filter(user=user).select_related('conference')

    data = {
        'personal_info': {
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'country': user.country,
            'organization': user.organization,
            'phone': user.phone,
            'occupation': user.get_occupation_display(),
            'iatm_membership': user.iatm_membership,
            'date_joined': user.date_joined.isoformat(),
        },
        'conference_registrations': [
            {
                'conference': m.conference.conference_name,
                'role1': m.role1,
                'role2': m.role2,
                'is_paid': m.is_paid,
                'registered_at': m.created_at.isoformat(),
            }
            for m in memberships
        ],
        'payments': [
            {
                'conference': p.conference.conference_name,
                'amount': str(p.amount),
                'currency': p.currency,
                'status': p.status,
                'date': p.created_at.isoformat(),
            }
            for p in payments
        ],
    }

    response = HttpResponse(
        json.dumps(data, indent=2, ensure_ascii=False),
        content_type='application/json',
    )
    response['Content-Disposition'] = f'attachment; filename="iatm_my_data_{user.id}.json"'
    return response


@login_required
def delete_my_account(request):
    """GDPR: Allow users to permanently delete their account and all associated data."""
    if request.method == 'POST':
        confirm = request.POST.get('confirm_email', '')
        if confirm == request.user.email:
            request.user.delete()
            logout(request)
            messages.success(request, "Your account and all associated data have been permanently deleted.")
            return redirect('login')
        else:
            messages.error(request, "Email confirmation did not match. Account was not deleted.")

    return render(request, 'accounts/delete_account.html')
