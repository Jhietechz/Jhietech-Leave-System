from django.db import models
from django.contrib.auth.models import User
from datetime import date
from django.conf import settings
from django.utils import timezone

# --- 1. Leave Type Model ---
class LeaveType(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('A', 'All'),
    )
    name = models.CharField(max_length=50) # e.g. Annual, Sick, Maternity
    default_days = models.PositiveIntegerField() # e.g. 21, 30, 90
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default='A')
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.default_days} days)"

# --- 2. Employee Profile Model ---
class Profile(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
    )
    
    ROLE_CHOICES = (
        ('Staff', 'Staff'),
        ('Line Manager', 'Line Manager'),
        ('COO', 'COO'),
        ('CEO', 'CEO'),
        ('Admin', 'Admin'),
    )

    # Link to Django's built-in User
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    
    # Custom Fields
    employee_id = models.CharField(max_length=20, unique=True, blank=True)
    id_number = models.CharField(max_length=20, unique=True)
    phone_number = models.CharField(max_length=15)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    department = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Staff')
    profile_photo = models.ImageField(upload_to='profile_pics/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.employee_id}"
    
    def save(self, *args, **kwargs):
        if not self.employee_id and self.user.id:
            self.employee_id = f"EMP_{self.user.id + 1000}" 
        super().save(*args, **kwargs)

# --- 3. User-Specific Leave Allowance ---
class UserLeaveAllowance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_allowances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    allowed_days = models.PositiveIntegerField()

    class Meta:
        unique_together = ('user', 'leave_type')

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name}: {self.allowed_days} days"

# --- 4. User Leave Tracker ---
class UserLeaveTracker(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_tracker')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    days_taken = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'leave_type')

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name}: {self.days_taken} days taken"

    @property
    def remaining_days(self):
        allowance, _ = UserLeaveAllowance.objects.get_or_create(
            user=self.user, 
            leave_type=self.leave_type,
            defaults={'allowed_days': self.leave_type.default_days}
        )
        return allowance.allowed_days - self.days_taken

# --- 3. Leave Application Model ---
class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    )

    APPROVAL_LEVEL_CHOICES = (
        ('Line Manager', 'Line Manager'),
        ('COO', 'COO'),
        ('CEO', 'CEO'),
        ('Completed', 'Completed'), # Workflow finished
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, null=True, blank=True)
    other_leave_type = models.CharField(max_length=50, blank=True, null=True)

    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    # attachment = models.FileField(upload_to='leave_attachments/', null=True, blank=True)
    
    # Tracking the Workflow
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='Pending')
    approval_level = models.CharField(max_length=20, choices=APPROVAL_LEVEL_CHOICES, default='Line Manager')
    
    # Audit Trail (Who approved what)
    line_manager_approval_date = models.DateTimeField(null=True, blank=True)
    coo_approval_date = models.DateTimeField(null=True, blank=True)
    ceo_approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.leave_type.name} ({self.total_days} days)"

    @property
    def total_days(self):
        """Calculates total days (Simple calculation for now)"""
        if self.end_date and self.start_date:
            delta = self.end_date - self.start_date
            return delta.days + 1 # +1 to include the start day
        return 0

# --- 4. Auth Token Model ---
class AuthToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    retry_count = models.IntegerField(default=0)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.user.username} - {self.token}"

# --- 5. Leave Attachment Model ---
class LeaveAttachment(models.Model):
    leave_request = models.ForeignKey('LeaveRequest', related_name='attachments', on_delete=models.CASCADE)
    file = models.FileField(upload_to='leave_attachments/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.leave_request} ({self.file.name})"

# --- 6. Notification Model ---
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.URLField(blank=True, null=True)  # Optional: link to relevant page

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:30]}"