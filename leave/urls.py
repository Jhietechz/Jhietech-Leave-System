from django.urls import path
from . import views as leave_views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', leave_views.dashboard, name='dashboard'),
    path('register/', leave_views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='leave/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='leave/logout.html'), name='logout'),
    path('apply/', leave_views.apply_leave, name='apply_leave'),
    path('approvals/', leave_views.approval_dashboard, name='approval_dashboard'),
    path('staff/', leave_views.employee_list, name='employee_list'),
    path('staff/edit/<int:id>/', leave_views.edit_staff, name='edit_staff'),
    path('profile/', leave_views.profile_view, name='profile'),
    path('profile/edit/', leave_views.edit_profile, name='edit_profile'),
    path('staff-dashboard/', leave_views.admin_dashboard, name='admin_dashboard'),
    path('staff-dashboard/edit/<int:id>/', leave_views.edit_employment, name='edit_employment'),
    path('fix-allowances/', leave_views.fix_missing_allowances, name='fix_missing_allowances'),
    path('password-reset/', leave_views.password_reset_request, name='password_reset_request'),
    path('reset-password/<str:token>/', leave_views.password_reset_confirm, name='password_reset_confirm'),
    path('approve-request/<int:req_id>/', leave_views.approve_request, name='approve_request'),
    path('reject-request/<int:req_id>/', leave_views.reject_request, name='reject_request'),
    path('notifications/', leave_views.notifications_view, name='notifications'),
    path('notifications/mark-as-read/<int:notification_id>/', leave_views.mark_as_read, name='mark_notification_as_read'),
    path('notifications/mark-all-as-read/', leave_views.mark_all_as_read, name='mark_all_notifications_as_read'),
    path('delete-account/<int:user_id>/', leave_views.delete_account, name='delete_account'),
]
