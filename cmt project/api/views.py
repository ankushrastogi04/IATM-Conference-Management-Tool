from rest_framework import serializers as drf_serializers
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import CustomUser
from conference.models import Conference, RegistrationTier, Payment, Track
from membership.models import Membership
from submissions.models import Submissions
from review.models import Review
from schedule.models import Session, Speaker

from .serializers import (
    UserSerializer,
    UserProfileUpdateSerializer,
    ConferenceSerializer,
    ConferenceListSerializer,
    RegistrationTierSerializer,
    TrackSerializer,
    MembershipSerializer,
    SubmissionSerializer,
    SubmissionListSerializer,
    ReviewSerializer,
    SessionSerializer,
    SpeakerSerializer,
    PaymentSerializer,
)


class ConferenceViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve conferences."""
    queryset = Conference.objects.all()
    permission_classes = [IsAuthenticated]
    search_fields = ['conference_name', 'location']
    ordering_fields = ['start_date', 'end_date', 'conference_name']
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return ConferenceListSerializer
        return ConferenceSerializer


class TrackViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve tracks, filterable by conference."""
    queryset = Track.objects.all()
    serializer_class = TrackSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conference']
    search_fields = ['name']


class RegistrationTierViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve registration tiers, filterable by conference."""
    queryset = RegistrationTier.objects.filter(is_active=True)
    serializer_class = RegistrationTierSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conference']


class MembershipViewSet(viewsets.ReadOnlyModelViewSet):
    """List the current user's own memberships."""
    serializer_class = MembershipSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conference', 'role1', 'role2', 'is_paid']

    def get_queryset(self):
        return Membership.objects.filter(user=self.request.user).select_related('user', 'conference')


class SubmissionViewSet(viewsets.ModelViewSet):
    """
    List the current user's own submissions.
    Create is allowed for users with a paid membership.
    """
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'track', 'membership']
    search_fields = ['paper_title']
    ordering_fields = ['submission_date', 'paper_title', 'status']
    http_method_names = ['get', 'post', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return SubmissionListSerializer
        return SubmissionSerializer

    def get_queryset(self):
        return Submissions.objects.filter(
            membership__user=self.request.user
        ).select_related('membership', 'track', 'co_author1', 'co_author2', 'co_author3')

    def perform_create(self, serializer):
        membership = serializer.validated_data.get('membership')
        if membership.user != self.request.user:
            raise drf_serializers.ValidationError("You can only create submissions for your own memberships.")
        if not membership.is_paid:
            raise drf_serializers.ValidationError("You must have a paid membership to submit papers.")
        serializer.save()


class ReviewViewSet(viewsets.ModelViewSet):
    """List and update the current user's assigned reviews."""
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_submitted', 'recommendation']
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_queryset(self):
        return Review.objects.filter(
            reviewer=self.request.user
        ).select_related('submission', 'reviewer')


class SessionViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve sessions, filterable by conference, track, date, and type."""
    queryset = Session.objects.filter(is_published=True).select_related('conference', 'track').prefetch_related('speakers')
    serializer_class = SessionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conference', 'track', 'session_type']
    search_fields = ['title', 'description']
    ordering_fields = ['start_time', 'end_time', 'title']


class SpeakerViewSet(viewsets.ReadOnlyModelViewSet):
    """List and retrieve speakers."""
    queryset = Speaker.objects.all()
    serializer_class = SpeakerSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['first_name', 'last_name', 'organization']


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """List the current user's own payments."""
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['conference', 'status']
    ordering_fields = ['created_at', 'amount']

    def get_queryset(self):
        return Payment.objects.filter(user=self.request.user).select_related('conference', 'tier')


class UserProfileView(APIView):
    """Retrieve or partially update the current user's profile."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)
