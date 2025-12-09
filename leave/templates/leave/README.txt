# Jhietech Leave Management System Documentation

## Overview
The Jhietech Leave Management System is a web-based application designed to streamline the process of managing employee leave requests, approvals, and records. It provides an intuitive interface for both employees and administrators to handle leave efficiently.

## Features
- Employee leave application and tracking
- Admin leave approval and rejection
- Leave balance calculation
- Notification system for leave status updates
- User authentication and role-based access
- Dashboard for leave statistics

## Modules
1. **Employee Module**
   - Apply for leave
   - View leave history and status
   - Check leave balance

2. **Admin Module**
   - View all leave requests
   - Approve or reject leave applications
   - Manage employee leave records

## Installation
1. Clone the repository:
   ```
   git clone <repository-url>
   ```
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run migrations:
   ```
   python manage.py migrate
   ```
4. Start the server:
   ```
   python manage.py runserver
   ```

## Usage
- Employees log in to submit leave requests.
- Admins log in to review and manage requests.
- Leave status and balances are updated automatically.

## File Structure
- `leave/` - Main app directory
- `templates/leave/` - HTML templates for the leave system
- `models.py` - Database models for leave records
- `views.py` - Application logic and request handling
- `urls.py` - URL routing for leave management

## Support
For issues or feature requests, contact the Jhietech support team at support@jhietech.com.

## License
This project is licensed under the MIT License.
