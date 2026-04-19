from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.conf import settings as django_settings
from django.core.paginator import Paginator
from .models import Conference, Payment, RegistrationTier, PromoCode
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from submissions.emails import send_registration_confirmation

@login_required
def conference_list_view(request):
    conferences = Conference.objects.all()
    paginator = Paginator(conferences, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'conference/conference_list.html', {
        'conferences': page_obj,
        'page_obj': page_obj,
    })

@login_required
def conference_detail_view(request, slug):
    conference = get_object_or_404(Conference, slug=slug)
    return render(request, 'conference/conference_detail.html', {'conference': conference})

@login_required
def payment_checkout(request, slug):
    """Payment checkout - shows payment form and redirects to PayPal payment link."""
    conference = get_object_or_404(Conference, slug=slug)

    from membership.models import Membership
    try:
        membership = Membership.objects.get(user=request.user, conference=conference)
        if membership.is_paid:
            messages.info(request, f"You already have access to {conference.conference_name}.")
            return redirect('conference_detail', slug=slug)
    except Membership.DoesNotExist:
        membership = Membership.objects.create(
            user=request.user,
            conference=conference,
            is_paid=False
        )

    tiers = RegistrationTier.objects.filter(conference=conference, is_active=True)
    is_member = request.user.iatm_membership

    if tiers.exists():
        tier_pricing = []
        for tier in tiers:
            current_price = tier.get_current_price(is_member=is_member)
            tier_pricing.append({
                'tier': tier,
                'price': current_price,
                'original_price': tier.price,
                'is_discounted': current_price < float(tier.price),
            })
    else:
        tier_pricing = None

    if request.method == 'POST':
        selected_tier = None
        if tiers.exists():
            tier_id = request.POST.get('tier_id')
            if tier_id:
                selected_tier = get_object_or_404(RegistrationTier, id=tier_id, conference=conference)
                amount = selected_tier.get_current_price(is_member=is_member)
            else:
                messages.error(request, "Please select a registration tier.")
                return redirect('payment_checkout', slug=slug)
        else:
            if request.user.occupation in ['student_undergraduate', 'student_graduate']:
                amount = 50.00
            else:
                amount = 100.00

        # Apply promo code if provided
        promo_code_str = request.POST.get('promo_code', '').strip().upper()
        applied_promo = None
        if promo_code_str:
            try:
                promo = PromoCode.objects.get(conference=conference, code__iexact=promo_code_str)
                if promo.is_valid:
                    amount = promo.apply_discount(amount)
                    applied_promo = promo
                else:
                    messages.warning(request, "This promo code is no longer valid.")
            except PromoCode.DoesNotExist:
                messages.warning(request, "Invalid promo code.")

        # Create pending payment record
        payment = Payment.objects.create(
            user=request.user,
            conference=conference,
            tier=selected_tier,
            amount=amount,
            promo_code=applied_promo,
            status='pending'
        )

        # Increment promo code usage
        if applied_promo:
            applied_promo.times_used += 1
            applied_promo.save(update_fields=['times_used'])

        # Store payment info in session for when user returns
        request.session['pending_payment_id'] = payment.id
        request.session['conference_slug'] = slug

        # Redirect to PayPal NCP payment link
        paypal_link = django_settings.PAYPAL_PAYMENT_LINK
        return redirect(paypal_link)

    context = {
        'conference': conference,
        'membership': membership,
        'tier_pricing': tier_pricing,
        'is_member': is_member,
        'is_early_bird': conference.is_early_bird,
        'paypal_link': django_settings.PAYPAL_PAYMENT_LINK,
    }

    if not tier_pricing:
        if request.user.occupation in ['student_undergraduate', 'student_graduate']:
            context['amount'] = 50.00
            context['price_type'] = "Student"
        else:
            context['amount'] = 100.00
            context['price_type'] = "Regular"

    return render(request, 'conference/payment_checkout.html', context)

@login_required
def payment_success(request, slug):
    """Handle return from PayPal - mark payment as awaiting confirmation."""
    conference = get_object_or_404(Conference, slug=slug)

    pending_payment_id = request.session.get('pending_payment_id')
    conference_slug = request.session.get('conference_slug')

    if pending_payment_id and conference_slug == slug:
        try:
            payment = Payment.objects.get(id=pending_payment_id, user=request.user)
            if payment.status == 'pending':
                payment.status = 'completed'
                payment.save()

                # Mark membership as paid
                from membership.models import Membership
                try:
                    membership = Membership.objects.get(user=request.user, conference=conference)
                    membership.is_paid = True
                    membership.save()
                    send_registration_confirmation(request.user, conference, membership, request=request)
                except Membership.DoesNotExist:
                    pass

                messages.success(request, f"Payment confirmed! You now have access to {conference.conference_name}.")
        except Payment.DoesNotExist:
            messages.error(request, "Payment record not found.")
    else:
        messages.error(request, "Invalid payment session.")

    # Clear session data
    request.session.pop('pending_payment_id', None)
    request.session.pop('conference_slug', None)

    return redirect('conference_detail', slug=slug)

@login_required
def payment_cancel(request, slug):
    """Handle cancelled PayPal payment."""
    conference = get_object_or_404(Conference, slug=slug)

    pending_payment_id = request.session.get('pending_payment_id')
    if pending_payment_id:
        try:
            payment = Payment.objects.get(id=pending_payment_id, user=request.user)
            payment.status = 'cancelled'
            payment.save()
        except Payment.DoesNotExist:
            pass

    request.session.pop('pending_payment_id', None)
    request.session.pop('conference_slug', None)

    messages.info(request, "Payment was cancelled. You can try again anytime.")
    return redirect('conference_detail', slug=slug)


@login_required
def user_dashboard(request):
    """User dashboard showing registrations, payments, submissions, and personalized schedule."""
    from membership.models import Membership
    from submissions.models import Submissions
    from schedule.models import Session
    from django.db.models import Q
    from django.utils import timezone

    memberships = Membership.objects.filter(user=request.user).select_related('conference')
    payments = Payment.objects.filter(user=request.user, status='completed').select_related('conference', 'tier')
    submissions = Submissions.objects.filter(
        Q(membership__user=request.user) |
        Q(co_author1=request.user) |
        Q(co_author2=request.user) |
        Q(co_author3=request.user)
    ).select_related('membership__conference', 'track').distinct()

    paid_conferences = memberships.filter(is_paid=True).values_list('conference_id', flat=True)
    upcoming_sessions = Session.objects.filter(
        conference_id__in=paid_conferences,
        is_published=True,
        end_time__gte=timezone.now(),
    ).select_related('conference', 'track').prefetch_related('speakers').order_by('start_time')[:10]

    from schedule.models import Attendance
    past_paid_memberships = memberships.filter(
        is_paid=True,
        conference__end_date__lt=timezone.now().date(),
    )
    certificate_memberships = []
    for m in past_paid_memberships:
        attendance_count = Attendance.objects.filter(user=request.user, session__conference=m.conference).count()
        if attendance_count > 0:
            certificate_memberships.append({'membership': m, 'sessions_attended': attendance_count})

    context = {
        'memberships': memberships,
        'payments': payments,
        'submissions': submissions,
        'upcoming_sessions': upcoming_sessions,
        'certificate_memberships': certificate_memberships,
    }
    return render(request, 'conference/user_dashboard.html', context)


@login_required
def download_invoice(request, payment_id):
    """Download PDF invoice for a completed payment."""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user, status='completed')

    from .invoice import generate_invoice_pdf
    buffer = generate_invoice_pdf(payment)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="IATM_Invoice_{payment.id:06d}.pdf"'
    return response


@login_required
def download_certificate(request, membership_id):
    """Download attendance certificate PDF for a completed conference."""
    from membership.models import Membership
    from schedule.models import Attendance

    membership = get_object_or_404(Membership, id=membership_id, user=request.user, is_paid=True)

    from django.utils import timezone
    if membership.conference.end_date >= timezone.now().date():
        messages.error(request, "Certificates are available after the conference ends.")
        return redirect('user_dashboard')

    attendance_count = Attendance.objects.filter(
        user=request.user, session__conference=membership.conference
    ).count()
    if attendance_count == 0:
        messages.error(request, "No session attendance recorded for this conference.")
        return redirect('user_dashboard')

    from .certificate import generate_certificate_pdf
    buffer = generate_certificate_pdf(request.user, membership.conference, attendance_count)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"IATM_Certificate_{membership.conference.slug}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
