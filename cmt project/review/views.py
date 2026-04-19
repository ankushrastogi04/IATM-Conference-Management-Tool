from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator

from submissions.models import Submissions
from membership.models import Membership, Role
from conference.models import Conference
from .models import Review
from .forms import ReviewForm, AssignReviewersForm
from submissions.emails import send_reviewer_assignment, send_review_notification


@staff_member_required
def debug_reviewers(request, conference_id):
    """Temporary debug view to check reviewer data"""
    try:
        conference = Conference.objects.get(id=conference_id)
        
        # Get all memberships for this conference
        all_memberships = Membership.objects.filter(conference=conference).select_related('user')
        
        # Get reviewers specifically
        reviewers = Membership.objects.filter(
            conference=conference
        ).filter(
            Q(role1='Reviewer') | Q(role2='Reviewer')
        ).select_related('user')
        
        # Get chairs
        chairs = Membership.objects.filter(
            conference=conference
        ).filter(
            Q(role1='Chair') | Q(role2='Chair')
        ).select_related('user')
        
        debug_data = {
            'conference': conference.conference_name,
            'total_memberships': all_memberships.count(),
            'reviewers_count': reviewers.count(),
            'chairs_count': chairs.count(),
            'all_memberships': [
                {
                    'user': f"{m.user.get_full_name()} ({m.user.email})",
                    'role1': m.role1,
                    'role2': m.role2,
                } for m in all_memberships
            ],
            'reviewers': [
                {
                    'user': f"{m.user.get_full_name()} ({m.user.email})",
                    'role1': m.role1,
                    'role2': m.role2,
                } for m in reviewers
            ],
            'chairs': [
                {
                    'user': f"{m.user.get_full_name()} ({m.user.email})",
                    'role1': m.role1,
                    'role2': m.role2,
                } for m in chairs
            ]
        }
        
        return JsonResponse(debug_data)
        
    except Conference.DoesNotExist:
        return JsonResponse({'error': 'Conference not found'}, status=404)


@login_required
def chair_review_assignments(request):
    """Chair dashboard for managing review assignments"""
    # Ensure user is staff or a chair of at least one conference
    if not request.user.is_staff:
        is_any_chair = Membership.objects.filter(user=request.user).filter(
            Q(role1='Chair') | Q(role2='Chair')
        ).exists()
        if not is_any_chair:
            messages.error(request, "You must be a conference chair or staff to access review assignments.")
            return redirect('user_dashboard')

    # Get conferences where user is chair or staff
    if request.user.is_staff:
        chair_memberships = Membership.objects.filter(
            Q(role1='Chair') | Q(role2='Chair')
        )
        chair_conferences = [m.conference for m in chair_memberships]
        # Staff can see all conferences
        available_conferences = list(Conference.objects.all())
    else:
        chair_memberships = Membership.objects.filter(user=request.user).filter(
            Q(role1='Chair') | Q(role2='Chair')
        )
        chair_conferences = [m.conference for m in chair_memberships]
        available_conferences = chair_conferences

    # Get selected conference
    selected_slug = request.GET.get('conference')
    selected_conference = None
    submissions = Submissions.objects.none()
    tracks = []

    if selected_slug:
        selected_conference = next((c for c in available_conferences if c.slug == selected_slug), None)
        if selected_conference:
            submissions = Submissions.objects.filter(
                membership__conference=selected_conference
            ).select_related('membership__user', 'track').prefetch_related('reviews').order_by('-submission_date')
            tracks = selected_conference.tracks.all()

    # Group submissions by track for better organization
    submissions_by_track = {}
    if selected_conference:
        for track in tracks:
            track_submissions = submissions.filter(track=track)
            submissions_by_track[track] = track_submissions

    # Get unassigned submissions
    unassigned_submissions = submissions.filter(reviews__isnull=True) if selected_conference else Submissions.objects.none()

    # Calculate total submissions count
    total_submissions = submissions.count() if selected_conference else 0

    # Paginate the flat submissions list
    paginator = Paginator(submissions, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'chair_conferences': chair_conferences,
        'available_conferences': available_conferences,
        'selected_conference': selected_conference,
        'submissions_by_track': submissions_by_track,
        'unassigned_submissions': unassigned_submissions,
        'tracks': tracks,
        'total_submissions': total_submissions,
        'submissions': page_obj,
        'page_obj': page_obj,
    }
    return render(request, 'review/chair_review_assignments.html', context)

@login_required
def assign_reviewers_to_submission(request, submission_id):
    """Assign reviewers to a specific submission"""
    submission = get_object_or_404(Submissions, id=submission_id)
    conference = submission.membership.conference

    # Check if user is chair for this conference or staff
    if not request.user.is_staff:
        is_chair = Membership.objects.filter(
            user=request.user,
            conference=conference
        ).filter(
            Q(role1='Chair') | Q(role2='Chair')
        ).exists()
        if not is_chair:
            messages.error(request, "You don't have permission to assign reviewers for this conference.")
            return redirect('chair_review_assignments')

    if request.method == 'POST':
        # Get selected reviewer IDs from the form
        selected_reviewer_ids = request.POST.getlist('reviewers')
        
        if selected_reviewer_ids:
            # Get the membership objects for the selected reviewers
            selected_reviewers = Membership.objects.filter(
                id__in=selected_reviewer_ids,
                conference=conference
            ).filter(
                Q(role1='Reviewer') | Q(role2='Reviewer')
            )
            
            # Remove existing assignments for this submission
            Review.objects.filter(submission=submission).delete()
            
            # Create new review assignments and notify reviewers
            for reviewer_membership in selected_reviewers:
                review = Review.objects.create(
                    submission=submission,
                    reviewer=reviewer_membership.user
                )
                send_reviewer_assignment(review, request)

            messages.success(request, f"Successfully assigned {len(selected_reviewers)} reviewer(s) to '{submission.paper_title}'")
        else:
            messages.warning(request, "No reviewers were selected.")
        
        return redirect('chair_review_assignments')
    else:
        # Get currently assigned reviewers
        current_reviewers = Review.objects.filter(submission=submission).values_list('reviewer', flat=True)
        current_reviewer_ids = set(current_reviewers)
        
        # Get available reviewers directly (same logic as in form)
        available_reviewers = Membership.objects.filter(
            conference=conference
        ).filter(
            Q(role1='Reviewer') | Q(role2='Reviewer')
        ).select_related('user')
        
        # Exclude the submission author and current user (chair) from reviewer options
        excluded_users = set()
        # Exclude the main author
        excluded_users.add(submission.membership.user.id)
        # Exclude co-authors if they exist
        if submission.co_author1:
            excluded_users.add(submission.co_author1.id)
        if submission.co_author2:
            excluded_users.add(submission.co_author2.id)
        if submission.co_author3:
            excluded_users.add(submission.co_author3.id)
        
        # Exclude current user
        excluded_users.add(request.user.id)
        
        # Filter out excluded users
        if excluded_users:
            available_reviewers = available_reviewers.exclude(user__id__in=excluded_users)
        


    context = {
        'submission': submission,
        'conference': conference,
        'current_reviewers': Review.objects.filter(submission=submission).select_related('reviewer'),
        'available_reviewers': available_reviewers,  # Pass reviewers directly to template
        'current_reviewer_ids': current_reviewer_ids,  # Pass current reviewer IDs for pre-selection
    }
    return render(request, 'review/assign_reviewers.html', context)

@login_required
def reviewer_dashboard(request):
    """Dashboard for reviewers to see their assigned reviews"""
    # Reviews assigned to this reviewer and not submitted yet
    pending_reviews = Review.objects.filter(
        reviewer=request.user, 
        is_submitted=False
    ).select_related('submission__membership__conference', 'submission__track').order_by('date_assigned')

    # Submitted reviews
    submitted_reviews = Review.objects.filter(
        reviewer=request.user, 
        is_submitted=True
    ).select_related('submission__membership__conference', 'submission__track').order_by('-date_reviewed')

    # Annotate blind review flag on each review
    for review in pending_reviews:
        review.is_blind = review.submission.membership.conference.blind_review
    for review in submitted_reviews:
        review.is_blind = review.submission.membership.conference.blind_review

    # Calculate stats
    total_reviews = pending_reviews.count() + submitted_reviews.count()
    completion_rate = round((submitted_reviews.count() / total_reviews * 100) if total_reviews > 0 else 0)

    context = {
        'pending_reviews': pending_reviews,
        'submitted_reviews': submitted_reviews,
        'total_reviews': total_reviews,
        'completion_rate': completion_rate,
    }
    return render(request, 'review/reviewer_dashboard.html', context)

@login_required
def submit_review(request, review_id):
    """Submit a review for a submission"""
    review = get_object_or_404(Review, id=review_id, reviewer=request.user)
    submission = review.submission

    if review.is_submitted:
        messages.warning(request, "This review has already been submitted.")
        return redirect('reviewer_dashboard')

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            review = form.save(commit=False)
            review.is_submitted = True
            review.date_reviewed = timezone.now()
            review.save()
            send_review_notification(review, request)

            messages.success(request, "Review submitted successfully.")
            return redirect('reviewer_dashboard')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ReviewForm(instance=review)

    conference = submission.membership.conference
    context = {
        'form': form,
        'submission': submission,
        'review': review,
        'blind_review': conference.blind_review,
    }
    return render(request, 'review/submit_review.html', context)

@login_required
def author_reviews(request):
    """View for authors to see reviews of their submissions"""
    # Get all submissions by this user (including co-authored)
    submissions = Submissions.objects.filter(
        Q(membership__user=request.user) | 
        Q(co_author1=request.user) | 
        Q(co_author2=request.user) | 
        Q(co_author3=request.user)
    )

    # Get all reviews for these submissions
    reviews = Review.objects.filter(
        submission__in=submissions,
        is_submitted=True
    ).select_related('submission__membership__conference', 'reviewer').order_by('-date_reviewed')

    # Calculate review counts
    accepted_count = reviews.filter(recommendation='ACCEPT').count()
    rejected_count = reviews.filter(recommendation='REJECT').count()
    revision_count = reviews.filter(recommendation='REVISE').count()

    context = {
        'reviews': reviews,
        'accepted_count': accepted_count,
        'rejected_count': rejected_count,
        'revision_count': revision_count,
    }
    return render(request, 'review/author_reviews.html', context)
