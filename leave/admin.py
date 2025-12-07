from django.contrib import admin
from .models import Profile, LeaveType, LeaveRequest, UserLeaveAllowance, UserLeaveTracker

# Register your models here.
admin.site.register(Profile)
admin.site.register(LeaveType)
admin.site.register(LeaveRequest)

@admin.register(UserLeaveAllowance)
class UserLeaveAllowanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'allowed_days')

@admin.register(UserLeaveTracker)
class UserLeaveTrackerAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'days_taken')