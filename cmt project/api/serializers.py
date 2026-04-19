from rest_framework import serializers

from accounts.models import CustomUser
from conference.models import Conference, RegistrationTier, Payment, Track
from membership.models import Membership
from submissions.models import Submissions
from review.models import Review
from schedule.models import Session, Speaker


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'organization', 'country', 'occupation']
        read_only_fields = fields


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'email', 'first_name', 'last_name', 'organization', 'country', 'occupation']
        read_only_fields = ['id', 'email']


class ConferenceSerializer(serializers.ModelSerializer):
    is_early_bird = serializers.BooleanField(read_only=True)
    is_submission_open = serializers.BooleanField(read_only=True)

    class Meta:
        model = Conference
        fields = '__all__'
        read_only_fields = ['slug', 'created_at', 'updated_at']


class ConferenceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conference
        fields = ['id', 'conference_name', 'slug', 'start_date', 'end_date', 'location']


class RegistrationTierSerializer(serializers.ModelSerializer):
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = RegistrationTier
        fields = '__all__'

    def get_current_price(self, obj):
        return obj.get_current_price(is_member=False)


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = ['id', 'name', 'conference']


class MembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ['id', 'user', 'conference', 'role1', 'role2', 'is_paid']


class SubmissionSerializer(serializers.ModelSerializer):
    co_author1 = UserSerializer(read_only=True)
    co_author2 = UserSerializer(read_only=True)
    co_author3 = UserSerializer(read_only=True)

    class Meta:
        model = Submissions
        fields = [
            'id', 'paper_title', 'status', 'submission_date',
            'track', 'membership', 'file',
            'co_author1', 'co_author2', 'co_author3',
        ]
        read_only_fields = ['status', 'submission_date']


class SubmissionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submissions
        fields = ['id', 'paper_title', 'status', 'submission_date']


class ReviewSerializer(serializers.ModelSerializer):
    reviewer = UserSerializer(read_only=True)

    class Meta:
        model = Review
        fields = [
            'id', 'submission', 'reviewer', 'comment',
            'recommendation', 'date_reviewed', 'is_submitted',
        ]
        read_only_fields = ['submission', 'reviewer', 'date_reviewed']


class SpeakerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Speaker
        fields = ['id', 'first_name', 'last_name', 'organization', 'bio', 'title']


class SessionSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.IntegerField(read_only=True)
    speakers = SpeakerSerializer(many=True, read_only=True)

    class Meta:
        model = Session
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'conference', 'tier', 'amount', 'currency', 'status', 'created_at']
        read_only_fields = fields
