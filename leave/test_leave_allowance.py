from django.test import TestCase, Client
from django.contrib.auth.models import User
from leave.models import LeaveType, UserLeaveAllowance, UserLeaveTracker

class LeaveAllowanceTestCase(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username='testuser', password='password')
        
        # Create some leave types
        self.leave_type1 = LeaveType.objects.create(name='Annual', default_days=21)
        self.leave_type2 = LeaveType.objects.create(name='Sick', default_days=10)
        
        # Set up the client
        self.client = Client()
        self.client.login(username='testuser', password='password')

    def test_dashboard_creates_leave_allowances_and_trackers(self):
        # Initially, the user should not have any allowances or trackers
        self.assertEqual(UserLeaveAllowance.objects.filter(user=self.user).count(), 0)
        self.assertEqual(UserLeaveTracker.objects.filter(user=self.user).count(), 0)
        
        # Access the dashboard
        response = self.client.get('/dashboard/')
        
        # Check that the view was successful
        self.assertEqual(response.status_code, 200)
        
        # Now, the user should have allowances and trackers for all active leave types
        active_leave_types = LeaveType.objects.filter(is_active=True).count()
        self.assertEqual(UserLeaveAllowance.objects.filter(user=self.user).count(), active_leave_types)
        self.assertEqual(UserLeaveTracker.objects.filter(user=self.user).count(), active_leave_types)
        
        # Verify the created objects
        allowance1 = UserLeaveAllowance.objects.get(user=self.user, leave_type=self.leave_type1)
        self.assertEqual(allowance1.allowed_days, self.leave_type1.default_days)
        
        tracker1 = UserLeaveTracker.objects.get(user=self.user, leave_type=self.leave_type1)
        self.assertEqual(tracker1.days_taken, 0)
