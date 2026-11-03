# Customer Relationship Management (CRM) System

A complete, fully functional, modern web application for centralized Customer Relationship Management (CRM) developed for an academic college demonstration project.

Built strictly using **Python 3**, **Flask**, and Python's built-in **SQLite3** database with a responsive **Bootstrap 5** frontend and interactive **Chart.js** data visualizations.

---

## 1. Project Overview & Features

This system provides a unified portal for organizations to track customer relationships, sales pipelines, service tickets, business reports, follow-up notifications, and customer feedback across 4 distinct organizational roles.

### Five Core Functional Modules

1. **Customer Management Module**
   - Customer registration with auto-generated unique Customer IDs (`CUST-1001`).
   - Unique email validation and duplicate customer prevention.
   - 360-degree Customer Profile page aggregating purchases, quotations, orders, support tickets, follow-ups, and feedback.
   - Comprehensive CRUD operations (Create, Read, Update, Delete with confirmation).
   - Multi-field search (name, ID, email, phone) and date-range filtering.
   - Pagination for large customer datasets.

2. **Sales Management Module**
   - **Sales Transactions & History:** Record deal amounts, products/services, sales rep, payment method, and dates.
   - **Quotations:** Create commercial quotations with dynamic line items, automated subtotal, 18% GST tax, and grand total calculations. Includes a print-ready quotation layout.
   - **Customer Orders:** Track order fulfillment progress (Pending &rarr; Processing &rarr; Completed), milestone dates, and delivery addresses.
   - Real-time gross revenue calculation and deal tracking.

3. **Customer Support Module**
   - Service request and complaint registration with auto-generated Ticket IDs (`TICK-1001`).
   - Priority levels: *Low*, *Medium*, *High* (SLA escalations).
   - Ticket categories: *Technical Support*, *Billing Issue*, *Product Quality*, *Delivery Delay*, *General Inquiry*, *Service Complaint*.
   - Ticket assignment to support staff.
   - Interactive conversation and response timeline (`complaint_responses`).
   - Resolution workflows and timestamped resolution notes.

4. **Report Management Module**
   - **8 Comprehensive Database Reports:**
     1. Customer Registration Report
     2. Sales Performance Report
     3. Employee Performance Report
     4. Customer Complaint Report
     5. Customer Purchase History (LTV) Report
     6. Revenue & Settlements Report
     7. Pending Orders Report
     8. Customer Satisfaction (CSAT) Report
   - Zero hardcoding: All metrics and charts calculated directly from SQLite SQL queries.
   - Filterable by date range, customer, and employee.
   - Instant downloadable **CSV Exports** (saved to `exports/` folder and streamed to browser).
   - Print-optimized layout (`@media print` clean report views).

5. **Notification and Feedback Module**
   - **Follow-up Reminders:** Schedule calls, demos, and reviews with customers; auto-flagging of overdue tasks.
   - **System Notifications:** In-app inbox and navbar unread counter for ticket assignments, order alerts, and follow-ups.
   - **Customer Feedback (CSAT):** 1-to-5 star rating picker, touchpoint aspects, customer reviews, and average satisfaction analytics.

---

## 2. User Roles & Access Control

The application implements four role dashboards and backend authorization enforcement:

| Role | Default Username | Default Password | Permissions |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Full access to all 5 modules, user administration, account activation/deactivation, system-wide metrics. |
| **Manager** | `manager` | `manager123` | Sales monitoring, employee performance rankings, order oversight, complaints tracking, business reports. |
| **Employee** | `employee` | `employee123` | Register/update customers, log sales, generate quotations & orders, schedule follow-ups. |
| **Support Staff** | `support` | `support123` | View customer tickets, register service requests, post responses, update status, resolve complaints. |

*Additional seeded employee:* `rajesh.sales` / `rajesh123`

---

## 3. Technology Stack

- **Backend:** Python 3, Flask 3.1
- **Database:** SQLite3 (Python built-in standard library)
- **Security:** Werkzeug password hashing (`pbkdf2:sha256`)
- **Frontend:** HTML5, CSS3, JavaScript (ES6), Bootstrap 5.3, Bootstrap Icons
- **Visualizations:** Chart.js 4.4
- **No external database server needed** (No MySQL, No PostgreSQL, No MongoDB, No XAMPP required).

---

## 4. Database Architecture (`crm.db`)

The SQLite database file `crm.db` is created automatically on first run with foreign key integrity (`PRAGMA foreign_keys = ON;`) and performance indexes.

### Database Tables:
1. `users` &ndash; Authentication credentials, roles, email, active status.
2. `customers` &ndash; Customer codes, names, contact details, company, address.
3. `employees` &ndash; 1-to-1 extension with users for designations, departments, salary.
4. `sales` &ndash; Sales records, products, quantities, prices, payment methods.
5. `quotations` &ndash; Commercial proposals, validity dates, tax calculations.
6. `quotation_items` &ndash; Itemized product rows within quotations.
7. `orders` &ndash; Customer orders, completion dates, shipping addresses.
8. `order_items` &ndash; Line items inside customer orders.
9. `complaints` &ndash; Support tickets, priorities, categories, resolutions.
10. `complaint_responses` &ndash; Timeline of support staff responses.
11. `follow_ups` &ndash; Scheduled calls and reminder notifications.
12. `notifications` &ndash; User notifications and unread badges.
13. `feedback` &ndash; Customer ratings (1-5 stars) and reviews.

---

## 5. Execution Instructions (Windows)

### Prerequisites:
- Python 3.8+ installed on your system.

### Step 1: Open Terminal / PowerShell in the project directory
```powershell
cd c:\Users\new\OneDrive\Desktop\crm
```

### Step 2: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Start the CRM Application
```powershell
python app.py
```

### Step 4: Access the Application
Open your web browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 6. Project Directory Structure

```
crm/
├── app.py                     # Main Flask application and business routes
├── database.py                # Database schema, foreign keys, and sample data seeding
├── crm.db                     # Persistent SQLite database file
├── requirements.txt           # Minimal dependencies (Flask, Werkzeug)
├── README.md                  # Comprehensive project documentation
│
├── templates/                 # Jinja2 HTML templates
│   ├── base.html              # Modern responsive layout & sidebar
│   ├── login.html             # Login portal with quick-fill demo pills
│   ├── profile.html           # User profile management
│   ├── change_password.html   # Password update form
│   ├── admin_dashboard.html   # Administrator executive dashboard
│   ├── manager_dashboard.html # Manager operations dashboard
│   ├── employee_dashboard.html# Employee sales & tasks dashboard
│   ├── support_dashboard.html # Customer support & helpdesk dashboard
│   ├── customers.html         # Customer listing & search
│   ├── add_customer.html      # Customer registration form
│   ├── edit_customer.html     # Customer edit form
│   ├── customer_details.html  # 360-degree customer profile
│   ├── sales.html             # Sales history & deals
│   ├── add_sale.html          # Record new sale
│   ├── edit_sale.html         # Modify sale record
│   ├── quotations.html        # Quotation proposals list
│   ├── add_quotation.html     # Dynamic line-item quotation generator
│   ├── quotation_details.html # Printable quotation & invoice
│   ├── orders.html            # Customer orders list
│   ├── add_order.html         # Create customer order
│   ├── order_details.html     # Order tracking & timeline
│   ├── complaints.html        # Support ticket queue
│   ├── add_complaint.html     # Register service complaint
│   ├── complaint_details.html # Ticket conversation & resolution
│   ├── reports.html           # 8 Dynamic BI reports & analytics
│   ├── notifications.html     # Notification inbox
│   ├── follow_ups.html        # Follow-up reminders
│   ├── feedback.html          # CSAT reviews and rating breakdown
│   ├── add_feedback.html      # Star rating submission form
│   └── users.html             # User administration & role management
│
├── static/
│   ├── css/
│   │   └── style.css          # Modern enterprise stylesheet
│   ├── js/
│   │   └── script.js          # Interactive frontend calculators & controls
│   └── images/
│
└── exports/                   # Downloadable CSV report exports
```
