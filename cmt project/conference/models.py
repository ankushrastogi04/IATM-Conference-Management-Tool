from django.db import models
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings

class Conference(models.Model):
    conference_name = models.CharField(max_length=200)
    conference_description = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    location = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)

    # Pricing
    early_bird_deadline = models.DateField(null=True, blank=True)
    member_discount_percent = models.PositiveIntegerField(default=10, help_text="Discount % for IATM members")

    # Submission settings
    submission_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for paper submissions")
    review_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline for reviewers to submit reviews")
    blind_review = models.BooleanField(default=False, help_text="Hide author info from reviewers")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.conference_name)
        super().save(*args, **kwargs)

    @property
    def is_early_bird(self):
        if self.early_bird_deadline:
            return timezone.now().date() <= self.early_bird_deadline
        return False

    @property
    def is_submission_open(self):
        if self.submission_deadline:
            return timezone.now() <= self.submission_deadline
        return True

    def __str__(self):
        return self.conference_name

    class Meta:
        verbose_name = "Conference"
        verbose_name_plural = "Conferences"
        ordering = ['start_date']


class RegistrationTier(models.Model):
    """Pricing tiers for conference registration (Early Bird, Student, Professional, Sponsor)."""
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='tiers')
    name = models.CharField(max_length=100)  # e.g., "Student", "Professional", "Sponsor"
    price = models.DecimalField(max_digits=10, decimal_places=2)
    early_bird_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('conference', 'name')
        ordering = ['price']

    def get_current_price(self, is_member=False):
        """Return the applicable price considering early bird and member discounts."""
        if self.conference.is_early_bird and self.early_bird_price:
            price = self.early_bird_price
        else:
            price = self.price

        if is_member and self.conference.member_discount_percent:
            discount = price * self.conference.member_discount_percent / 100
            price = price - discount

        return round(price, 2)

    def __str__(self):
        return f"{self.name} - {self.conference.conference_name} (${self.price})"

class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payments')
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='payments')
    tier = models.ForeignKey('RegistrationTier', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    paypal_order_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    paypal_payment_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    promo_code = models.ForeignKey('PromoCode', on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.conference.conference_name} - ${self.amount} ({self.status})"


class PromoCode(models.Model):
    DISCOUNT_TYPES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]

    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='promo_codes')
    code = models.CharField(max_length=50)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage (0-100) or fixed USD amount")
    max_uses = models.PositiveIntegerField(default=0, help_text="0 = unlimited")
    times_used = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('conference', 'code')

    def __str__(self):
        return f"{self.code} ({self.conference.conference_name})"

    @property
    def is_valid(self):
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.max_uses > 0 and self.times_used >= self.max_uses:
            return False
        return True

    def apply_discount(self, price):
        if not self.is_valid:
            return price
        if self.discount_type == 'percentage':
            discount = price * self.discount_value / 100
        else:
            discount = min(self.discount_value, price)
        return round(max(price - discount, 0), 2)


class Track(models.Model):
    conference = models.ForeignKey(Conference, on_delete=models.CASCADE, related_name='tracks')
    name = models.CharField(max_length=200)
    
    class Meta:
        unique_together = ('conference', 'name')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.conference.conference_name})"
