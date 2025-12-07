from django import forms
from django.contrib.auth.models import User
from .models import Profile
from .models import LeaveRequest, LeaveType

class UserRegisterForm(forms.ModelForm):
    # Add fields that belong to the User model
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    # Add fields that belong to the Profile model
    id_number = forms.CharField(max_length=20, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password', 'confirm_password']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password != confirm_password:
            raise forms.ValidationError("Passwords do not match")
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email is already registered. Please use a different one.")
        return email
        
# Leave form   
from .models import LeaveRequest, LeaveType, UserLeaveTracker

class LeaveRequestForm(forms.ModelForm):
    start_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    attachment = forms.FileField(required=False)
    other_leave_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Enter custom leave type'})
    )

    class Meta:
        model = LeaveRequest
        fields = [
            'leave_type',
            'other_leave_type',
            'start_date',
            'end_date',
            'attachment',
            'reason'
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        trackers = kwargs.pop('trackers', None)
        super().__init__(*args, **kwargs)
        
        qs = LeaveType.objects.all()
        if self.user and hasattr(self.user, 'profile'):
            gender = self.user.profile.gender
            if gender == 'M':
                qs = qs.exclude(name__iexact='Maternity')
            elif gender == 'F':
                qs = qs.exclude(name__iexact='Paternity')
        
        self.fields['leave_type'].queryset = qs
        
        if trackers:
            self.fields['leave_type'].widget.attrs.update({'class': 'form-select'})
            choices = [('', '---------')]
            for tracker in trackers:
                choices.append(
                    (tracker.leave_type.id, f"{tracker.leave_type.name} ({tracker.remaining_days} days remaining)")
                )
            self.fields['leave_type'].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        leave_type = cleaned_data.get('leave_type')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if leave_type and start_date and end_date:
            requested_days = (end_date - start_date).days + 1
            
            tracker, _ = UserLeaveTracker.objects.get_or_create(
                user=self.user,
                leave_type=leave_type
            )
            
            if requested_days > tracker.remaining_days:
                raise forms.ValidationError(
                    f"You only have {tracker.remaining_days} days remaining for {leave_type.name} leave."
                )
        
        return cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['role']

class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    username = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    gender = forms.ChoiceField(choices=Profile.GENDER_CHOICES, required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    phone_number = forms.CharField(max_length=15, required=True, widget=forms.TextInput(attrs={'class': 'form-control'}))
    profile_photo = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Profile
        fields = ['gender', 'phone_number', 'profile_photo']

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['username'].initial = user.username
        if self.instance:
            self.fields['gender'].initial = self.instance.gender
            self.fields['phone_number'].initial = self.instance.phone_number
            self.fields['profile_photo'].initial = self.instance.profile_photo

    def save(self, user=None, commit=True):
        profile = super().save(commit=False)
        if user:
            user.first_name = self.cleaned_data['first_name']
            user.last_name = self.cleaned_data['last_name']
            user.email = self.cleaned_data['email']
            user.username = self.cleaned_data['username']
            if commit:
                user.save()
                profile.user = user
                profile.gender = self.cleaned_data['gender']
                profile.phone_number = self.cleaned_data['phone_number']
                if self.cleaned_data.get('profile_photo'):
                    profile.profile_photo = self.cleaned_data['profile_photo']
                profile.save()
        else:
            if commit:
                profile.save()
        return profile

class StaffEmploymentForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['role', 'department']
        widgets = {
            'role': forms.Select(choices=[
                ('Staff', 'Staff'),
                ('Line Manager', 'Line Manager'),
                ('COO', 'COO'),
                ('CEO', 'CEO'),
                ('Admin', 'Admin'),
            ]),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
        }