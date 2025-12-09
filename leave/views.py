from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import logout
from .forms import UserRegisterForm, ProfileForm, UserProfileForm, StaffEmploymentForm
from .models import Profile
from django.contrib.auth.decorators import login_required
from .models import LeaveRequest, LeaveType
from .forms import LeaveRequestForm
from django.contrib.admin.views.decorators import staff_member_required
from django.db import IntegrityError, transaction
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.core.mail import send_mail, EmailMessage
from .models import AuthToken, LeaveAttachment, Notification, UserLeaveAllowance, UserLeaveTracker
from django.db import models

from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.template.loader import render_to_string
from django.conf import settings

# Create your views here.

def register_view(request):
    form = UserRegisterForm()
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create User and Profile
                    user = form.save(commit=False)
                    user.set_password(form.cleaned_data.get('password')) # Hash the password
                    user.save()

                    # Create Profile
                    profile = Profile.objects.create(
                        user=user,
                        id_number=form.cleaned_data.get('id_number'),
                        phone_number=form.cleaned_data.get('phone_number'),
                        gender=form.cleaned_data.get('gender')
                    )

                    # Initialize leave allowances and trackers
                    leave_types = LeaveType.objects.filter(is_active=True)
                    for leave_type in leave_types:
                        UserLeaveAllowance.objects.create(
                            user=user,
                            leave_type=leave_type,
                            allowed_days=leave_type.default_days
                        )
                        UserLeaveTracker.objects.create(
                            user=user,
                            leave_type=leave_type,
                            days_taken=0
                        )

                messages.success(request, f'Account created for {user.username}! You can now login.')
                return redirect('login')
            except IntegrityError:
                form.add_error(None, "This ID number or username is already registered. Please use a different one.")
    
    return render(request, 'leave/register.html', {
        'form': form,
    })
@login_required
def dashboard(request):
    # --- Ensure all leave allowances and trackers exist for the user ---
    user_gender = request.user.profile.gender
    leave_types = LeaveType.objects.filter(is_active=True).filter(
        models.Q(gender='A') | models.Q(gender=user_gender)
    )

    for leave_type in leave_types:
        # Check and create allowance
        allowance, created_allowance = UserLeaveAllowance.objects.get_or_create(
            user=request.user,
            leave_type=leave_type,
            defaults={'allowed_days': leave_type.default_days}
        )
        
        # Check and create tracker
        tracker, created_tracker = UserLeaveTracker.objects.get_or_create(
            user=request.user,
            leave_type=leave_type,
            defaults={'days_taken': 0}
        )

    # Get all leave requests made by this user (Newest first)
    my_leaves = LeaveRequest.objects.filter(user=request.user).order_by('-created_at')
    
    # Get the user's leave trackers, filtered by gender
    leave_trackers = UserLeaveTracker.objects.filter(
        user=request.user,
        leave_type__in=leave_types
    ).select_related('leave_type')
    
    # Send this data to the HTML template
    context = {
        'my_leaves': my_leaves,
        'leave_trackers': leave_trackers,
    }
    return render(request, 'leave/dashboard.html', context)

def send_notification(user, message, link=None, attachment=None, html_message=None):
    # Save notification to DB
    Notification.objects.create(user=user, message=message, link=link)
    # Send email
    email = EmailMessage(
        "Jhietech Leave Notification",
        message,
        settings.EMAIL_HOST_USER,
        [user.email],
    )
    if html_message:
        email.content_subtype = "html"  # Main content is HTML
        email.body = html_message
    if attachment: # This attachment is now strictly for non-HTML files, like actual PDFs.
        email.attach(attachment['filename'], attachment['content'], 'application/pdf')
    email.send(fail_silently=True)

def generate_approval_letter(leave_request):
    # Render approval letter as HTML and convert to PDF (simple HTML for now)
    html_content = render_to_string('leave/approval_letter.html', {'leave_request': leave_request})
    # For PDF, use a library like xhtml2pdf or WeasyPrint in production
    return html_content

@login_required
def apply_leave(request):
    user_profile = request.user.profile
    
    # Correctly filter leave types and trackers based on user's gender
    user_gender = user_profile.gender
    applicable_leave_types = LeaveType.objects.filter(is_active=True).filter(
        models.Q(gender='A') | models.Q(gender=user_gender)
    )
    leave_trackers = UserLeaveTracker.objects.filter(
        user=request.user,
        leave_type__in=applicable_leave_types
    ).select_related('leave_type')

    if user_profile.role == 'Staff' and not user_profile.department:
        messages.error(request, "You must be assigned to a Department before applying. Please contact Admin.")
        return redirect('dashboard')

    manager_name = "N/A"
    if user_profile.department:
        manager = Profile.objects.filter(role__in=['Line Manager', 'COO', 'CEO', 'Admin'], department=user_profile.department).first()
        if manager:
            manager_name = f"{manager.user.first_name} {manager.user.last_name}"

    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES, user=request.user, trackers=leave_trackers)
        if form.is_valid():
            leave_request = form.save(commit=False)
            leave_request.user = request.user
            leave_request.save()

            files = request.FILES.getlist('attachment')
            for f in files:
                LeaveAttachment.objects.create(
                    leave_request=leave_request,
                    file=f
                )

            if user_profile.role == 'Staff':
                leave_request.approval_level = 'Line Manager'
            elif user_profile.role in ['Line Manager', 'Admin']:
                leave_request.approval_level = 'COO'
            elif user_profile.role == 'COO':
                leave_request.approval_level = 'CEO'
            elif user_profile.role == 'CEO':
                leave_request.approval_level = 'Completed'
                leave_request.status = 'Approved'
            else:
                leave_request.approval_level = 'Line Manager'
            leave_request.save()

            next_role = leave_request.approval_level
            approver = Profile.objects.filter(role=next_role, department=user_profile.department).first()
            if approver:
                send_notification(
                    approver.user,
                    f"New leave request from {request.user.get_full_name()} requires your approval.",
                    link=reverse('approval_dashboard')
                )
            send_notification(
                request.user,
                f"Your leave request has been submitted and is pending {next_role} approval.",
                link=reverse('dashboard')
            )
            messages.success(request, 'Leave request submitted successfully!')
            return redirect('dashboard')
    else:
        form = LeaveRequestForm(user=request.user, trackers=leave_trackers)

    context = {
        'form': form,
        'manager_name': manager_name,
        'user_department': user_profile.department,
        'profile': user_profile,
        'leave_trackers': leave_trackers,
    }
    return render(request, 'leave/apply_leave.html', context)

@login_required
def approval_dashboard(request):
    user_profile = request.user.profile
    
    # Security: Regular Staff should NOT see this page
    if user_profile.role == 'Staff':
        messages.warning(request, "Access Denied: You do not have approval privileges.")
        return redirect('dashboard')

    pending_requests = []

    # --- Logic 1: Line Manager ---
    # Sees Pending requests, at 'Line Manager' level, ONLY from their own department
    if user_profile.role == 'Line Manager':
        pending_requests = LeaveRequest.objects.filter(
            status='Pending',
            approval_level='Line Manager',
            user__profile__department=user_profile.department 
        )

    # --- Logic 2: COO ---
    # Sees Pending requests at 'COO' level (Department doesn't matter here)
    elif user_profile.role == 'COO':
        pending_requests = LeaveRequest.objects.filter(
            status='Pending',
            approval_level='COO'
        )

    # --- Logic 3: CEO ---
    # Sees Pending requests at 'CEO' level
    elif user_profile.role == 'CEO':
        pending_requests = LeaveRequest.objects.filter(
            status='Pending',
            approval_level='CEO'
        )

    context = {
        'pending_requests': pending_requests,
        'profile': user_profile,  # Add this line to pass profile info to template
    }
    return render(request, 'leave/approval_dashboard.html', context)

# A view to list all employees for the Admin/HR
@login_required
def employee_list(request):
    # Only Admin or CEO/COO should see this
    if request.user.profile.role in ['Staff']:
        return redirect('dashboard')
    # Allow Admin, CEO, COO
    if request.user.profile.role not in ['Admin', 'CEO', 'COO']:
        return redirect('dashboard')
    employees = Profile.objects.all().select_related('user')
    return render(request, 'leave/employee_list.html', {'employees': employees})

# A view to edit a specific employee
@login_required
def employee_edit(request, id):
    # Only Admin logic here
    profile = get_object_or_404(Profile, id=id)
    return render(request, 'leave/employee_edit.html')

@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, 'leave/profile.html', {
        'profile': profile,
        'user': request.user,
    })

@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save(user=request.user)
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile, user=request.user)
    return render(request, 'leave/edit_profile.html', {'form': form})

@login_required
def admin_dashboard(request):
    # Only Admin, CEO, COO should see this
    if request.user.profile.role not in ['Admin', 'CEO', 'COO']:
        return redirect('dashboard')
    employees = Profile.objects.select_related('user').all()
    return render(request, 'leave/admin_dashboard.html', {'employees': employees})

@staff_member_required
def fix_missing_allowances(request):
    """
    Admin view to fix missing UserLeaveAllowance and UserLeaveTracker records for all users.
    """
    if request.method == 'POST':
        users = User.objects.all()
        leave_types = LeaveType.objects.filter(is_active=True)
        
        fixed_count = 0
        for user in users:
            # Ensure the user has a profile, if not, skip or create a default one
            if not hasattr(user, 'profile'):
                # Handle users without profiles if necessary, e.g., create a default profile
                continue 

            user_gender = user.profile.gender

            for leave_type in leave_types:
                # Filter leave types by user's gender
                if leave_type.gender != 'A' and leave_type.gender != user_gender:
                    continue

                # Fix missing allowance
                allowance, created_allowance = UserLeaveAllowance.objects.get_or_create(
                    user=user,
                    leave_type=leave_type,
                    defaults={'allowed_days': leave_type.default_days}
                )
                if created_allowance:
                    fixed_count += 1

                # Fix missing tracker
                tracker, created_tracker = UserLeaveTracker.objects.get_or_create(
                    user=user,
                    leave_type=leave_type,
                    defaults={'days_taken': 0}
                )
                if created_tracker:
                    fixed_count += 1
        
        messages.success(request, f"Fixed {fixed_count} missing leave allowance/tracker records.")
        return redirect('admin_dashboard') # Redirect back to admin dashboard
    
    return render(request, 'leave/fix_allowances_confirm.html')

@login_required
def edit_employment(request, id):
    # Only Admin, CEO, COO should edit employment
    if request.user.profile.role not in ['Admin', 'CEO', 'COO']:
        return redirect('dashboard')
    profile = get_object_or_404(Profile, id=id)
    if request.method == 'POST':
        form = StaffEmploymentForm(request.POST, instance=profile)
        if form.is_valid():
            updated_profile = form.save(commit=False)
            role = form.cleaned_data.get('role')
            # Set department to None for COO, CEO, Admin
            if role in ['COO', 'CEO', 'Admin']:
                updated_profile.department = None
            updated_profile.save()
            return redirect('admin_dashboard')
    else:
        form = StaffEmploymentForm(instance=profile)
    return render(request, 'leave/edit_employment.html', {'form': form, 'profile': profile})

@login_required
def edit_staff(request, id):
    # Placeholder implementation
    # TODO: Implement staff editing logic
    return render(request, 'leave/edit_staff.html', {'staff_id': id})


@login_required
def delete_account(request, user_id):
    target_user = get_object_or_404(User, id=user_id)

    # Security check: A user can only delete their own account or an Admin/CEO/COO can delete any account
    if not request.user.is_superuser and request.user.profile.role not in ['Admin', 'CEO', 'COO'] and request.user != target_user:
        messages.error(request, "You do not have permission to delete this account.")
        return redirect('dashboard')

    if request.method == 'POST':
        # Admin/CEO/COO deleting another user
        if request.user != target_user:
            target_user.delete()
            messages.success(request, f"Account for {target_user.username} successfully deleted.")
            return redirect('admin_dashboard') # Redirect to staff list
        else: 
            logout(request) # Log out the user before deleting their session
            target_user.delete()
            messages.success(request, "Your account has been successfully deleted.")
            return redirect('login') # Redirect to login page

    # GET request for confirmation page
    context = {
        'target_user': target_user
    }
    return render(request, 'leave/delete_account_confirm.html', context)


def password_reset_request(request):
    error_message = None
    success_message = None
    if request.method == 'POST':
        email = request.POST.get('email')
        user = User.objects.filter(email=email).first()
        if user:
            token = get_random_string(64)
            expires = timezone.now() + timezone.timedelta(hours=1)
            AuthToken.objects.create(user=user, token=token, expires_at=expires)
            reset_link = request.build_absolute_uri(f"/reset-password/{token}/")
            send_mail(
                "Password Reset Request",
                f"Click the link to reset your password: {reset_link}",
                "noreply@example.com",
                [email],
            )
            success_message = "A password reset link has been sent to your email."
        else:
            error_message = "No account found with that email."
    return render(request, 'leave/password_reset_request.html', {
        'error_message': error_message,
        'success_message': success_message,
    })

def password_reset_confirm(request, token):
    error_message = None
    success_message = None
    auth_token = AuthToken.objects.filter(token=token, is_used=False).first()
    if not auth_token or auth_token.is_expired():
        error_message = "Invalid or expired token."
    elif request.method == 'POST':
        password = request.POST.get('password')
        confirm = request.POST.get('confirm_password')
        if password and password == confirm:
            auth_token.user.password = make_password(password)
            auth_token.user.save()
            auth_token.is_used = True
            auth_token.save()
            # Redirect to login after successful reset
            messages.success(request, "Your password has been reset successfully. Please login.")
            return redirect(reverse('login'))
        else:
            error_message = "Passwords do not match."
    return render(request, 'leave/password_reset_confirm.html', {
        'error_message': error_message,
        'success_message': success_message,
        'token': token,
    })

def role_required(allowed_roles):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated or request.user.profile.role not in allowed_roles:
                messages.warning(request, "Access denied.")
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

@login_required
def approve_request(request, req_id):
    leave_request = get_object_or_404(LeaveRequest, id=req_id)
    user_profile = request.user.profile
    if user_profile.role not in ['Line Manager', 'COO', 'CEO']:
        messages.error(request, "You do not have permission to approve this request.")
        return redirect('approval_dashboard')
    prev_level = leave_request.approval_level

    # Approval logic
    if leave_request.approval_level == 'Line Manager' and user_profile.role == 'Line Manager':
        leave_request.approval_level = 'COO'
        leave_request.line_manager_approval_date = timezone.now()
        leave_request.save()
        # Notify next approver
        next_approver = Profile.objects.filter(role='COO').first()
        if next_approver:
            send_notification(
                next_approver.user,
                f"Leave request #{leave_request.id} from {leave_request.user.get_full_name()} requires your approval.",
                link=reverse('approval_dashboard')
            )
        # Notify applicant
        send_notification(
            leave_request.user,
            f"Your leave request has been approved by Line Manager and is pending COO approval.",
            link=reverse('dashboard')
        )
    elif leave_request.approval_level == 'COO' and user_profile.role == 'COO':
        leave_request.approval_level = 'CEO'
        leave_request.coo_approval_date = timezone.now()
        leave_request.save()
        # Notify next approver
        next_approver = Profile.objects.filter(role='CEO').first()
        if next_approver:
            send_notification(
                next_approver.user,
                f"Leave request #{leave_request.id} from {leave_request.user.get_full_name()} requires your approval.",
                link=reverse('approval_dashboard')
            )
        # Notify applicant
        send_notification(
            leave_request.user,
            f"Your leave request has been approved by COO and is pending CEO approval.",
            link=reverse('dashboard')
        )
    elif leave_request.approval_level == 'CEO' and user_profile.role == 'CEO':
        leave_request.approval_level = 'Completed'
        leave_request.status = 'Approved'
        leave_request.ceo_approval_date = timezone.now()
        leave_request.save()

        # Deduct leave days from the tracker
        leave_tracker, created = UserLeaveTracker.objects.get_or_create(
            user=leave_request.user,
            leave_type=leave_request.leave_type
        )
        leave_tracker.days_taken += leave_request.total_days
        leave_tracker.save()

        # Generate approval letter
        approval_letter_html = generate_approval_letter(leave_request)
        # Notify applicant with approval letter as HTML body
        send_notification(
            leave_request.user,
            f"Your leave request has been fully approved. See below for your approval letter.",
            link=reverse('dashboard'),
            html_message=approval_letter_html
        )
    messages.success(request, "Leave request approved.")
    return redirect('approval_dashboard')



@login_required
def reject_request(request, req_id):
    leave_request = get_object_or_404(LeaveRequest, id=req_id)
    user_profile = request.user.profile

    # Security check
    if user_profile.role not in ['Line Manager', 'COO', 'CEO']:
        messages.error(request, "You do not have permission to reject this request.")
        return redirect('approval_dashboard')

    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', 'No reason provided.')
        
        leave_request.status = 'Rejected'
        leave_request.rejection_reason = rejection_reason
        leave_request.save()

        # Notify applicant
        send_notification(
            leave_request.user,
            f"Your leave request has been rejected by {user_profile.role}. Reason: {rejection_reason}",
            link=reverse('dashboard')
        )
        
        messages.success(request, "Leave request has been rejected.")
        return redirect('approval_dashboard')

    # Redirect if not a POST request
    return redirect('approval_dashboard')


@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
    read_notifications = Notification.objects.filter(user=request.user, is_read=True).order_by('-created_at')
    profile = request.user.profile
    return render(request, 'leave/notifications.html', {
        'notifications': notifications,
        'read_notifications': read_notifications,
        'profile': profile
    })

@login_required
def mark_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('notifications')


@login_required
def mark_all_as_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications')


@login_required
def leave_records(request):
    # Ensure only authorized roles can access this page
    if request.user.profile.role == 'Staff':
        messages.warning(request, "You are not authorized to view this page.")
        return redirect('dashboard')

    leave_requests = LeaveRequest.objects.select_related('user__profile', 'leave_type').order_by('-created_at')

    # Filtering logic
    status_filter = request.GET.get('status')
    employee_filter = request.GET.get('employee')

    if status_filter:
        leave_requests = leave_requests.filter(status=status_filter)
    
    if employee_filter:
        leave_requests = leave_requests.filter(
            models.Q(user__first_name__icontains=employee_filter) |
            models.Q(user__last_name__icontains=employee_filter)
        )

    context = {
        'leave_requests': leave_requests,
        'profile': request.user.profile,
    }
    return render(request, 'leave/leave_records.html', context)

@login_required
def leave_request_detail(request, req_id):
    # Ensure only authorized roles can access this page
    if request.user.profile.role == 'Staff':
        messages.warning(request, "You are not authorized to view this page.")
        return redirect('dashboard')

    leave_request = get_object_or_404(
        LeaveRequest.objects.select_related(
            'user__profile', 'leave_type'
        ).prefetch_related('attachments'),
        id=req_id
    )

    context = {
        'leave_request': leave_request,
        'profile': request.user.profile,
    }
    return render(request, 'leave/leave_request_detail.html', context)
