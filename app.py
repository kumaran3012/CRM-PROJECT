"""
Customer Relationship Management (CRM) System - Web Application
Built with Python 3, Flask, and SQLite.
"""

import os
import csv
import io
from datetime import datetime, date, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, Response, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash

from database import get_db, init_db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'crm_super_secret_session_key_2026_academic')

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
os.makedirs(EXPORTS_DIR, exist_ok=True)


# ==============================================================================
# Authentication & Authorization Helpers / Decorators
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please sign in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please sign in to access this page.', 'warning')
                return redirect(url_for('login'))
            user_role = session.get('role')
            if user_role not in allowed_roles:
                flash(f'Access denied. Your role ({user_role}) is not authorized for this resource.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.context_processor
def inject_global_context():
    """Injects unread notifications count, today date, and common variables into all templates."""
    context = {
        'today': date.today().isoformat(),
        'unread_notifications_count': 0
    }
    if 'user_id' in session:
        conn = get_db()
        cursor = conn.cursor()
        user_id = session.get('user_id')
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM notifications
            WHERE (user_id = ? OR user_id IS NULL) AND is_read = 0;
        """, (user_id,))
        row = cursor.fetchone()
        context['unread_notifications_count'] = row['cnt'] if row else 0
        conn.close()
    return context


# ==============================================================================
# Authentication Routes
# ==============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        login_input = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not login_input or not password:
            flash('Please enter both username/email and password.', 'danger')
            return render_template('login.html')

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM users
            WHERE (username = ? OR email = ?) AND is_active = 1;
        """, (login_input, login_input))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['full_name'] = user['full_name']

            # Update last login timestamp
            cursor.execute("UPDATE users SET last_login = ? WHERE id = ?;", (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['id']))
            conn.commit()
            conn.close()

            flash(f"Welcome back, {user['full_name']}!", 'success')
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            flash('Invalid username/email or password, or account deactivated.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    conn = get_db()
    cursor = conn.cursor()
    user_id = session['user_id']

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        department = request.form.get('department', '').strip()

        if not full_name or not email:
            flash('Full Name and Email are required fields.', 'danger')
        else:
            # Check duplicate email
            cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?;", (email, user_id))
            if cursor.fetchone():
                flash('This email address is already in use by another account.', 'danger')
            else:
                cursor.execute("""
                    UPDATE users SET full_name = ?, email = ?, phone = ?, department = ?
                    WHERE id = ?;
                """, (full_name, email, phone, department, user_id))
                conn.commit()
                session['full_name'] = full_name
                flash('Profile updated successfully.', 'success')

    cursor.execute("SELECT * FROM users WHERE id = ?;", (user_id,))
    user = cursor.fetchone()

    cursor.execute("SELECT * FROM employees WHERE user_id = ?;", (user_id,))
    emp_info = cursor.fetchone()
    conn.close()

    return render_template('profile.html', user=user, employee_info=emp_info, active_page='profile')


@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_pw or not new_pw:
            flash('All password fields are required.', 'danger')
        elif len(new_pw) < 6:
            flash('New password must be at least 6 characters long.', 'danger')
        elif new_pw != confirm_pw:
            flash('New passwords do not match.', 'danger')
        else:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash FROM users WHERE id = ?;", (session['user_id'],))
            user = cursor.fetchone()

            if user and check_password_hash(user['password_hash'], current_pw):
                hashed = generate_password_hash(new_pw)
                cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?;", (hashed, session['user_id']))
                conn.commit()
                conn.close()
                flash('Password changed successfully.', 'success')
                return redirect(url_for('profile'))
            else:
                conn.close()
                flash('Current password is incorrect.', 'danger')

    return render_template('change_password.html', active_page='change_password')


# ==============================================================================
# User Administration (Admin Only)
# ==============================================================================

@app.route('/users')
@role_required('admin')
def users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, e.employee_code, e.designation, e.salary
        FROM users u
        LEFT JOIN employees e ON u.id = e.user_id
        ORDER BY u.created_at DESC;
    """)
    user_list = cursor.fetchall()
    conn.close()
    return render_template('users.html', users=user_list, active_page='users')


@app.route('/users/add', methods=['POST'])
@role_required('admin')
def add_user():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role', 'employee')
    department = request.form.get('department', '').strip()
    phone = request.form.get('phone', '').strip()
    emp_code = request.form.get('employee_code', '').strip()
    designation = request.form.get('designation', '').strip()
    salary = float(request.form.get('salary', 0.0) or 0.0)

    if not username or not password or not email or not full_name:
        flash('Username, password, email, and full name are required.', 'danger')
        return redirect(url_for('users'))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?;", (username, email))
    if cursor.fetchone():
        conn.close()
        flash('Username or email already exists in system.', 'danger')
        return redirect(url_for('users'))

    hashed_pw = generate_password_hash(password)
    cursor.execute("""
        INSERT INTO users (username, email, password_hash, role, full_name, phone, department, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1);
    """, (username, email, hashed_pw, role, full_name, phone, department))
    new_user_id = cursor.lastrowid

    if not emp_code:
        emp_code = f"EMP-{new_user_id + 100}"
    if not designation:
        designation = f"{role.capitalize()} Specialist"

    cursor.execute("""
        INSERT INTO employees (user_id, employee_code, designation, department, joining_date, salary, status)
        VALUES (?, ?, ?, ?, ?, ?, 'Active');
    """, (new_user_id, emp_code, designation, department, date.today().isoformat(), salary))

    conn.commit()
    conn.close()
    flash(f"User account '{username}' created successfully.", 'success')
    return redirect(url_for('users'))


@app.route('/users/edit/<int:id>', methods=['POST'])
@role_required('admin')
def edit_user(id):
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip()
    role = request.form.get('role')
    department = request.form.get('department', '').strip()
    phone = request.form.get('phone', '').strip()
    new_password = request.form.get('new_password', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT username, role FROM users WHERE id = ?;", (id,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        flash('User account not found.', 'danger')
        return redirect(url_for('users'))

    # Prevent changing role of master admin
    if target['username'] == 'admin':
        role = 'admin'

    if new_password:
        hashed = generate_password_hash(new_password)
        cursor.execute("""
            UPDATE users SET full_name = ?, email = ?, role = ?, department = ?, phone = ?, password_hash = ?
            WHERE id = ?;
        """, (full_name, email, role, department, phone, hashed, id))
    else:
        cursor.execute("""
            UPDATE users SET full_name = ?, email = ?, role = ?, department = ?, phone = ?
            WHERE id = ?;
        """, (full_name, email, role, department, phone, id))

    conn.commit()
    conn.close()
    flash('User account updated successfully.', 'success')
    return redirect(url_for('users'))


@app.route('/users/toggle-status/<int:id>', methods=['POST'])
@role_required('admin')
def toggle_user_status(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT username, is_active FROM users WHERE id = ?;", (id,))
    u = cursor.fetchone()
    if u:
        if u['username'] == 'admin':
            flash('Cannot deactivate master administrator account.', 'danger')
        else:
            new_status = 0 if u['is_active'] == 1 else 1
            cursor.execute("UPDATE users SET is_active = ? WHERE id = ?;", (new_status, id))
            conn.commit()
            flash(f"User account status updated to {'Active' if new_status else 'Deactivated'}.", 'info')
    conn.close()
    return redirect(url_for('users'))


# ==============================================================================
# Dashboards
# ==============================================================================

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role', 'employee')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'manager':
        return redirect(url_for('manager_dashboard'))
    elif role == 'support':
        return redirect(url_for('support_dashboard'))
    else:
        return redirect(url_for('employee_dashboard'))


@app.route('/dashboard/admin')
@role_required('admin')
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # 1. KPI Statistics
    cursor.execute("SELECT COUNT(*) as cnt FROM customers;")
    total_customers = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM customers WHERE status = 'Active';")
    active_customers = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE is_active = 1;")
    total_employees = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount), 0.0) as rev FROM sales;")
    s_row = cursor.fetchone()
    total_sales = s_row['cnt']
    total_revenue = s_row['rev']

    cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status IN ('Pending', 'Processing');")
    pending_orders = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE status = 'Open';")
    open_complaints = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE status = 'Resolved';")
    resolved_complaints = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM follow_ups WHERE status = 'Pending';")
    pending_followups = cursor.fetchone()['cnt']

    cursor.execute("SELECT COALESCE(AVG(rating), 5.0) as avg_rate FROM feedback;")
    avg_satisfaction = cursor.fetchone()['avg_rate']

    stats = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_employees': total_employees,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'pending_orders': pending_orders,
        'open_complaints': open_complaints,
        'resolved_complaints': resolved_complaints,
        'pending_followups': pending_followups,
        'avg_satisfaction': round(avg_satisfaction, 1)
    }

    # 2. Monthly Revenue Chart Data (Current Year)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_rev_dict = {f"{i:02d}": 0.0 for i in range(1, 13)}
    cursor.execute("""
        SELECT strftime('%m', sale_date) as month, SUM(total_amount) as total
        FROM sales
        WHERE strftime('%Y', sale_date) = '2026'
        GROUP BY month;
    """)
    for r in cursor.fetchall():
        if r['month'] in monthly_rev_dict:
            monthly_rev_dict[r['month']] = round(r['total'], 2)

    monthly_revenue_labels = months
    monthly_revenue_values = [monthly_rev_dict[f"{i:02d}"] for i in range(1, 13)]

    # 3. Complaint Status Chart Data
    ticket_status_labels = ['Open', 'In Progress', 'Resolved', 'Closed']
    ticket_status_counts = []
    for st in ticket_status_labels:
        cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE status = ?;", (st,))
        ticket_status_counts.append(cursor.fetchone()['cnt'])

    # 4. Recent Lists
    cursor.execute("SELECT * FROM customers ORDER BY created_at DESC LIMIT 5;")
    recent_customers = cursor.fetchall()

    cursor.execute("""
        SELECT s.*, c.name as customer_name
        FROM sales s
        JOIN customers c ON s.customer_id = c.id
        ORDER BY s.sale_date DESC LIMIT 5;
    """)
    recent_sales = cursor.fetchall()

    cursor.execute("""
        SELECT comp.*, c.name as customer_name
        FROM complaints comp
        JOIN customers c ON comp.customer_id = c.id
        ORDER BY comp.created_at DESC LIMIT 5;
    """)
    recent_complaints = cursor.fetchall()

    cursor.execute("""
        SELECT f.*, c.name as customer_name
        FROM follow_ups f
        JOIN customers c ON f.customer_id = c.id
        WHERE f.status != 'Completed'
        ORDER BY f.follow_up_date ASC LIMIT 5;
    """)
    pending_followups_list = cursor.fetchall()

    cursor.execute("""
        SELECT fb.*, c.name as customer_name
        FROM feedback fb
        JOIN customers c ON fb.customer_id = c.id
        ORDER BY fb.created_at DESC LIMIT 3;
    """)
    recent_feedback = cursor.fetchall()

    conn.close()

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        monthly_revenue_labels=monthly_revenue_labels,
        monthly_revenue_values=monthly_revenue_values,
        ticket_status_labels=ticket_status_labels,
        ticket_status_counts=ticket_status_counts,
        recent_customers=recent_customers,
        recent_sales=recent_sales,
        recent_complaints=recent_complaints,
        pending_followups_list=pending_followups_list,
        recent_feedback=recent_feedback,
        active_page='dashboard'
    )


@app.route('/dashboard/manager')
@role_required('admin', 'manager')
def manager_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM customers;")
    total_customers = cursor.fetchone()['cnt']
    cursor.execute("SELECT COUNT(*) as cnt FROM customers WHERE status = 'Active';")
    active_customers = cursor.fetchone()['cnt']
    cursor.execute("SELECT COALESCE(SUM(total_amount), 0.0) as rev FROM sales;")
    total_revenue = cursor.fetchone()['rev']
    cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = 'Pending';")
    pending_orders = cursor.fetchone()['cnt']
    cursor.execute("SELECT COALESCE(AVG(rating), 5.0) as avg_rate FROM feedback;")
    avg_satisfaction = cursor.fetchone()['avg_rate']

    stats = {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'total_revenue': total_revenue,
        'pending_orders': pending_orders,
        'avg_satisfaction': round(avg_satisfaction, 1)
    }

    # Employee Sales Performance
    cursor.execute("""
        SELECT u.id, u.full_name, u.role, u.department, e.designation,
               COUNT(s.id) as total_sales_count,
               COALESCE(SUM(s.total_amount), 0.0) as total_revenue
        FROM users u
        LEFT JOIN employees e ON u.id = e.user_id
        LEFT JOIN sales s ON u.id = s.employee_id
        WHERE u.is_active = 1
        GROUP BY u.id
        ORDER BY total_revenue DESC;
    """)
    employee_perf = cursor.fetchall()

    # Order Status Breakdown
    order_status_labels = ['Pending', 'Processing', 'Completed', 'Cancelled']
    order_status_counts = []
    for st in order_status_labels:
        cursor.execute("SELECT COUNT(*) as cnt FROM orders WHERE status = ?;", (st,))
        order_status_counts.append(cursor.fetchone()['cnt'])

    # Recent Orders
    cursor.execute("""
        SELECT o.*, c.name as customer_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        ORDER BY o.order_date DESC LIMIT 5;
    """)
    recent_orders = cursor.fetchall()

    # High Priority Complaints
    cursor.execute("""
        SELECT comp.*, c.name as customer_name
        FROM complaints comp
        JOIN customers c ON comp.customer_id = c.id
        WHERE comp.priority = 'High' AND comp.status != 'Closed'
        ORDER BY comp.created_at DESC LIMIT 5;
    """)
    high_priority_complaints = cursor.fetchall()

    conn.close()

    return render_template(
        'manager_dashboard.html',
        stats=stats,
        employee_perf=employee_perf,
        order_status_labels=order_status_labels,
        order_status_counts=order_status_counts,
        recent_orders=recent_orders,
        high_priority_complaints=high_priority_complaints,
        active_page='dashboard'
    )


@app.route('/dashboard/employee')
@role_required('admin', 'employee', 'manager')
def employee_dashboard():
    conn = get_db()
    cursor = conn.cursor()
    user_id = session.get('user_id')

    cursor.execute("SELECT COALESCE(SUM(total_amount), 0.0) as rev, COUNT(*) as cnt FROM sales WHERE employee_id = ?;", (user_id,))
    s_row = cursor.fetchone()
    my_revenue = s_row['rev']
    my_sales_count = s_row['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM quotations WHERE created_by = ?;", (user_id,))
    my_quotations_count = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM follow_ups WHERE user_id = ? AND status != 'Completed';", (user_id,))
    my_followups_count = cursor.fetchone()['cnt']

    cursor.execute("""
        SELECT f.*, c.name as customer_name
        FROM follow_ups f
        JOIN customers c ON f.customer_id = c.id
        WHERE f.user_id = ? AND f.status != 'Completed'
        ORDER BY f.follow_up_date ASC LIMIT 5;
    """, (user_id,))
    my_followups = cursor.fetchall()

    cursor.execute("""
        SELECT s.*, c.name as customer_name
        FROM sales s
        JOIN customers c ON s.customer_id = c.id
        WHERE s.employee_id = ?
        ORDER BY s.sale_date DESC LIMIT 5;
    """, (user_id,))
    my_recent_sales = cursor.fetchall()

    conn.close()

    return render_template(
        'employee_dashboard.html',
        my_revenue=my_revenue,
        my_sales_count=my_sales_count,
        my_quotations_count=my_quotations_count,
        my_followups_count=my_followups_count,
        my_followups=my_followups,
        my_recent_sales=my_recent_sales,
        active_page='dashboard'
    )


@app.route('/dashboard/support')
@role_required('admin', 'support', 'manager')
def support_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints;")
    total_complaints = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE status = 'Open';")
    open_complaints = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE status = 'In Progress';")
    in_progress = cursor.fetchone()['cnt']

    cursor.execute("SELECT COUNT(*) as cnt FROM complaints WHERE status = 'Resolved';")
    resolved = cursor.fetchone()['cnt']

    support_stats = {
        'total_complaints': total_complaints,
        'open_complaints': open_complaints,
        'in_progress_complaints': in_progress,
        'resolved_complaints': resolved
    }

    cursor.execute("""
        SELECT comp.*, c.name as customer_name, c.phone as customer_phone, u.full_name as assigned_name
        FROM complaints comp
        JOIN customers c ON comp.customer_id = c.id
        LEFT JOIN users u ON comp.assigned_to = u.id
        WHERE comp.status IN ('Open', 'In Progress')
        ORDER BY CASE comp.priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END, comp.created_at DESC
        LIMIT 10;
    """)
    active_tickets = cursor.fetchall()

    cursor.execute("""
        SELECT fb.*, c.name as customer_name
        FROM feedback fb
        JOIN customers c ON fb.customer_id = c.id
        ORDER BY fb.created_at DESC LIMIT 5;
    """)
    recent_feedback = cursor.fetchall()

    conn.close()

    return render_template(
        'support_dashboard.html',
        support_stats=support_stats,
        active_tickets=active_tickets,
        recent_feedback=recent_feedback,
        active_page='dashboard'
    )


# ==============================================================================
# MODULE 1: CUSTOMER MANAGEMENT
# ==============================================================================

@app.route('/customers')
@login_required
def customers():
    search_query = request.args.get('q', '').strip()
    selected_status = request.args.get('status', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    page = int(request.args.get('page', 1))
    per_page = 10

    conn = get_db()
    cursor = conn.cursor()

    # Base query
    query = "SELECT * FROM customers WHERE 1=1"
    params = []

    if search_query:
        query += " AND (name LIKE ? OR customer_code LIKE ? OR email LIKE ? OR phone LIKE ? OR company_name LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard, wildcard])

    if selected_status:
        query += " AND status = ?"
        params.append(selected_status)

    if start_date:
        query += " AND DATE(created_at) >= ?"
        params.append(start_date)

    if end_date:
        query += " AND DATE(created_at) <= ?"
        params.append(end_date)

    # Count total for pagination
    count_query = query.replace("SELECT *", "SELECT COUNT(*) as cnt")
    cursor.execute(count_query, params)
    total_records = cursor.fetchone()['cnt']
    total_pages = max(1, (total_records + per_page - 1) // per_page)
    offset = (page - 1) * per_page

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
    params.extend([per_page, offset])

    cursor.execute(query, params)
    customer_list = cursor.fetchall()

    # Customer Statistics
    cursor.execute("SELECT COUNT(*) as total FROM customers;")
    total_cnt = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as active FROM customers WHERE status = 'Active';")
    active_cnt = cursor.fetchone()['active']
    cursor.execute("SELECT COUNT(*) as leads FROM customers WHERE status = 'Lead';")
    leads_cnt = cursor.fetchone()['leads']
    cursor.execute("SELECT COUNT(*) as this_month FROM customers WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now');")
    this_month_cnt = cursor.fetchone()['this_month']

    stats = {
        'total': total_cnt,
        'active': active_cnt,
        'leads': leads_cnt,
        'this_month': this_month_cnt
    }

    conn.close()

    return render_template(
        'customers.html',
        customers=customer_list,
        stats=stats,
        search_query=search_query,
        selected_status=selected_status,
        start_date=start_date,
        end_date=end_date,
        current_page=page,
        total_pages=total_pages,
        total_records=total_records,
        active_page='customers'
    )


@app.route('/customers/add', methods=['GET', 'POST'])
@role_required('admin', 'manager', 'employee')
def add_customer():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        customer_code = request.form.get('customer_code', '').strip()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company_name = request.form.get('company_name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        status = request.form.get('status', 'Active')
        notes = request.form.get('notes', '').strip()

        if not name or not email or not phone:
            flash('Customer Name, Email, and Phone are mandatory.', 'danger')
        else:
            # Check unique email
            cursor.execute("SELECT id FROM customers WHERE email = ?;", (email,))
            if cursor.fetchone():
                flash(f"A customer with email '{email}' is already registered.", 'danger')
            else:
                cursor.execute("""
                    INSERT INTO customers (customer_code, name, email, phone, company_name, address, city, state, postal_code, status, notes, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (customer_code, name, email, phone, company_name, address, city, state, postal_code, status, notes, session.get('user_id')))
                conn.commit()
                new_id = cursor.lastrowid
                conn.close()
                flash(f"Customer '{name}' ({customer_code}) registered successfully.", 'success')
                return redirect(url_for('customer_details', id=new_id))

    # Auto-generate next customer code
    cursor.execute("SELECT id FROM customers ORDER BY id DESC LIMIT 1;")
    last_row = cursor.fetchone()
    next_num = (last_row['id'] + 1001) if last_row else 1001
    next_code = f"CUST-{next_num}"
    conn.close()

    return render_template('add_customer.html', next_code=next_code, active_page='customers')


@app.route('/customers/<int:id>')
@login_required
def customer_details(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.*, u.full_name as creator_name
        FROM customers c
        LEFT JOIN users u ON c.created_by = u.id
        WHERE c.id = ?;
    """, (id,))
    customer = cursor.fetchone()

    if not customer:
        conn.close()
        flash('Customer record not found.', 'danger')
        return redirect(url_for('customers'))

    # Associated Sales History
    cursor.execute("SELECT * FROM sales WHERE customer_id = ? ORDER BY sale_date DESC;", (id,))
    sales = cursor.fetchall()

    # Associated Quotations
    cursor.execute("""
        SELECT q.*, u.full_name as created_by_name
        FROM quotations q
        LEFT JOIN users u ON q.created_by = u.id
        WHERE q.customer_id = ?
        ORDER BY q.created_at DESC;
    """, (id,))
    quotations = cursor.fetchall()

    # Associated Orders
    cursor.execute("SELECT * FROM orders WHERE customer_id = ? ORDER BY order_date DESC;", (id,))
    orders = cursor.fetchall()

    # Associated Complaints
    cursor.execute("SELECT * FROM complaints WHERE customer_id = ? ORDER BY created_at DESC;", (id,))
    complaints = cursor.fetchall()

    # Associated Follow-ups
    cursor.execute("""
        SELECT f.*, u.full_name as user_name
        FROM follow_ups f
        LEFT JOIN users u ON f.user_id = u.id
        WHERE f.customer_id = ?
        ORDER BY f.follow_up_date DESC;
    """, (id,))
    follow_ups = cursor.fetchall()

    # Associated Feedback
    cursor.execute("SELECT * FROM feedback WHERE customer_id = ? ORDER BY created_at DESC;", (id,))
    feedback = cursor.fetchall()

    # Purchase Stats
    cursor.execute("""
        SELECT COALESCE(SUM(total_amount), 0.0) as total_spend, COUNT(*) as total_orders
        FROM sales WHERE customer_id = ? AND status = 'Completed';
    """, (id,))
    purchase_stats = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as open_cnt FROM complaints WHERE customer_id = ? AND status != 'Resolved';", (id,))
    open_complaints_count = cursor.fetchone()['open_cnt']

    cursor.execute("SELECT AVG(rating) as avg_r FROM feedback WHERE customer_id = ?;", (id,))
    avg_r_row = cursor.fetchone()
    customer_rating = avg_r_row['avg_r'] if avg_r_row and avg_r_row['avg_r'] else None

    conn.close()

    return render_template(
        'customer_details.html',
        customer=customer,
        sales=sales,
        quotations=quotations,
        orders=orders,
        complaints=complaints,
        follow_ups=follow_ups,
        feedback=feedback,
        purchase_stats=purchase_stats,
        open_complaints_count=open_complaints_count,
        customer_rating=customer_rating,
        active_page='customers'
    )


@app.route('/customers/edit/<int:id>', methods=['GET', 'POST'])
@role_required('admin', 'manager', 'employee')
def edit_customer(id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        company_name = request.form.get('company_name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        status = request.form.get('status', 'Active')
        notes = request.form.get('notes', '').strip()

        if not name or not email or not phone:
            flash('Customer Name, Email, and Phone are required.', 'danger')
        else:
            # Check duplicate email
            cursor.execute("SELECT id FROM customers WHERE email = ? AND id != ?;", (email, id))
            if cursor.fetchone():
                flash(f"Email '{email}' is already used by another customer.", 'danger')
            else:
                cursor.execute("""
                    UPDATE customers
                    SET name = ?, email = ?, phone = ?, company_name = ?, address = ?, city = ?, state = ?, postal_code = ?, status = ?, notes = ?, updated_at = ?
                    WHERE id = ?;
                """, (name, email, phone, company_name, address, city, state, postal_code, status, notes, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), id))
                conn.commit()
                conn.close()
                flash('Customer information updated successfully.', 'success')
                return redirect(url_for('customer_details', id=id))

    cursor.execute("SELECT * FROM customers WHERE id = ?;", (id,))
    customer = cursor.fetchone()
    conn.close()

    if not customer:
        flash('Customer not found.', 'danger')
        return redirect(url_for('customers'))

    return render_template('edit_customer.html', customer=customer, active_page='customers')


@app.route('/customers/delete/<int:id>', methods=['POST'])
@role_required('admin', 'manager')
def delete_customer(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM customers WHERE id = ?;", (id,))
    c = cursor.fetchone()
    if c:
        cursor.execute("DELETE FROM customers WHERE id = ?;", (id,))
        conn.commit()
        flash(f"Customer '{c['name']}' and associated records deleted permanently.", 'info')
    conn.close()
    return redirect(url_for('customers'))


# ==============================================================================
# MODULE 2: SALES MANAGEMENT
# ==============================================================================

@app.route('/sales')
@role_required('admin', 'manager', 'employee')
def sales():
    search_query = request.args.get('q', '').strip()
    customer_id = request.args.get('customer_id', '').strip()
    employee_id = request.args.get('employee_id', '').strip()
    status = request.args.get('status', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT s.*, c.name as customer_name, c.company_name, u.full_name as employee_name
        FROM sales s
        JOIN customers c ON s.customer_id = c.id
        LEFT JOIN users u ON s.employee_id = u.id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (s.sales_code LIKE ? OR s.product_service_name LIKE ? OR c.name LIKE ?)"
        w = f"%{search_query}%"
        params.extend([w, w, w])

    if customer_id:
        query += " AND s.customer_id = ?"
        params.append(customer_id)

    if employee_id:
        query += " AND s.employee_id = ?"
        params.append(employee_id)

    if status:
        query += " AND s.status = ?"
        params.append(status)

    query += " ORDER BY s.sale_date DESC, s.id DESC;"

    cursor.execute(query, params)
    sales_list = cursor.fetchall()

    # Sales Statistics
    cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount), 0.0) as rev, COALESCE(AVG(total_amount), 0.0) as avg_val FROM sales;")
    total_stats = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount), 0.0) as rev FROM sales WHERE status = 'Completed';")
    completed_stats = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as cnt FROM sales WHERE status IN ('Pending', 'Processing');")
    pending_cnt = cursor.fetchone()['cnt']

    stats = {
        'total_sales': total_stats['cnt'],
        'total_revenue': total_stats['rev'],
        'avg_sale': total_stats['avg_val'],
        'completed_sales': completed_stats['cnt'],
        'completed_revenue': completed_stats['rev'],
        'pending_sales': pending_cnt
    }

    # Dropdown lists
    cursor.execute("SELECT id, name FROM customers ORDER BY name ASC;")
    customers_list = cursor.fetchall()

    cursor.execute("SELECT id, full_name FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees_list = cursor.fetchall()

    conn.close()

    return render_template(
        'sales.html',
        sales=sales_list,
        stats=stats,
        customers_list=customers_list,
        employees_list=employees_list,
        search_query=search_query,
        selected_customer=customer_id,
        selected_employee=employee_id,
        selected_status=status,
        active_page='sales'
    )


@app.route('/sales/add', methods=['GET', 'POST'])
@role_required('admin', 'manager', 'employee')
def add_sale():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        sales_code = request.form.get('sales_code', '').strip()
        customer_id = request.form.get('customer_id')
        employee_id = request.form.get('employee_id') or session.get('user_id')
        prod_name = request.form.get('product_service_name', '').strip()
        category = request.form.get('category', 'Software License')
        quantity = int(request.form.get('quantity', 1))
        unit_price = float(request.form.get('unit_price', 0.0))
        total_amount = round(quantity * unit_price, 2)
        payment_method = request.form.get('payment_method', 'Bank Transfer')
        sale_date = request.form.get('sale_date', date.today().isoformat())
        status = request.form.get('status', 'Completed')
        notes = request.form.get('notes', '').strip()

        if not customer_id or not prod_name or quantity <= 0:
            flash('Customer, Product/Service Name, and positive Quantity are required.', 'danger')
        else:
            cursor.execute("""
                INSERT INTO sales (sales_code, customer_id, employee_id, product_service_name, category, quantity, unit_price, total_amount, status, payment_method, sale_date, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (sales_code, customer_id, employee_id, prod_name, category, quantity, unit_price, total_amount, status, payment_method, sale_date, notes))
            conn.commit()
            conn.close()
            flash(f"Sale record '{sales_code}' logged successfully.", 'success')
            return redirect(url_for('sales'))

    # Next sales code
    cursor.execute("SELECT id FROM sales ORDER BY id DESC LIMIT 1;")
    last_sale = cursor.fetchone()
    next_code = f"SALE-{(last_sale['id'] + 1001) if last_sale else 1001}"

    cursor.execute("SELECT id, name, customer_code, company_name FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, full_name, role, department FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees = cursor.fetchall()

    selected_cust = request.args.get('customer_id')
    selected_customer_id = int(selected_cust) if selected_cust and selected_cust.isdigit() else None

    conn.close()

    return render_template(
        'add_sale.html',
        next_sales_code=next_code,
        customers=customers,
        employees=employees,
        selected_customer_id=selected_customer_id,
        active_page='sales'
    )


@app.route('/sales/edit/<int:id>', methods=['GET', 'POST'])
@role_required('admin', 'manager', 'employee')
def edit_sale(id):
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        employee_id = request.form.get('employee_id')
        prod_name = request.form.get('product_service_name', '').strip()
        category = request.form.get('category')
        quantity = int(request.form.get('quantity', 1))
        unit_price = float(request.form.get('unit_price', 0.0))
        total_amount = round(quantity * unit_price, 2)
        payment_method = request.form.get('payment_method')
        sale_date = request.form.get('sale_date')
        status = request.form.get('status')
        notes = request.form.get('notes', '').strip()

        cursor.execute("""
            UPDATE sales
            SET customer_id = ?, employee_id = ?, product_service_name = ?, category = ?, quantity = ?, unit_price = ?, total_amount = ?, status = ?, payment_method = ?, sale_date = ?, notes = ?
            WHERE id = ?;
        """, (customer_id, employee_id, prod_name, category, quantity, unit_price, total_amount, status, payment_method, sale_date, notes, id))
        conn.commit()
        conn.close()
        flash('Sale transaction updated successfully.', 'success')
        return redirect(url_for('sales'))

    cursor.execute("SELECT * FROM sales WHERE id = ?;", (id,))
    sale = cursor.fetchone()
    if not sale:
        conn.close()
        flash('Sale record not found.', 'danger')
        return redirect(url_for('sales'))

    cursor.execute("SELECT id, name, customer_code FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, full_name, role, department FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees = cursor.fetchall()

    conn.close()
    return render_template('edit_sale.html', sale=sale, customers=customers, employees=employees, active_page='sales')


@app.route('/sales/delete/<int:id>', methods=['POST'])
@role_required('admin', 'manager')
def delete_sale(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE id = ?;", (id,))
    conn.commit()
    conn.close()
    flash('Sale record deleted successfully.', 'info')
    return redirect(url_for('sales'))


# ==============================================================================
# QUOTATIONS SUB-MODULE
# ==============================================================================

@app.route('/quotations')
@role_required('admin', 'manager', 'employee')
def quotations():
    status = request.args.get('status', '').strip()
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT q.*, c.name as customer_name, c.company_name, u.full_name as created_by_name
        FROM quotations q
        JOIN customers c ON q.customer_id = c.id
        LEFT JOIN users u ON q.created_by = u.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND q.status = ?"
        params.append(status)

    query += " ORDER BY q.created_at DESC;"
    cursor.execute(query, params)
    quote_list = cursor.fetchall()

    # Stats
    cursor.execute("SELECT COUNT(*) as total, COALESCE(SUM(grand_total), 0.0) as pipe_val FROM quotations;")
    tot_row = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) as accepted FROM quotations WHERE status = 'Accepted';")
    acc_row = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) as sent FROM quotations WHERE status = 'Sent';")
    sent_row = cursor.fetchone()

    stats = {
        'total': tot_row['total'],
        'total_pipeline_val': tot_row['pipe_val'],
        'accepted': acc_row['accepted'],
        'sent': sent_row['sent']
    }

    conn.close()
    return render_template('quotations.html', quotations=quote_list, stats=stats, selected_status=status, active_page='quotations')


@app.route('/quotations/add', methods=['GET', 'POST'])
@role_required('admin', 'manager', 'employee')
def add_quotation():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        q_num = request.form.get('quotation_number', '').strip()
        customer_id = request.form.get('customer_id')
        subject = request.form.get('subject', '').strip()
        valid_until = request.form.get('valid_until')
        status = request.form.get('status', 'Draft')
        terms = request.form.get('terms_conditions', '').strip()
        tax_rate = float(request.form.get('tax_rate', 18.0) or 18.0)

        item_names = request.form.getlist('item_name[]')
        item_descs = request.form.getlist('item_desc[]')
        item_qtys = request.form.getlist('item_qty[]')
        item_prices = request.form.getlist('item_price[]')

        subtotal = 0.0
        line_items = []
        for i in range(len(item_names)):
            iname = item_names[i].strip()
            if not iname:
                continue
            idesc = item_descs[i].strip() if i < len(item_descs) else ''
            iqty = int(item_qtys[i]) if i < len(item_qtys) and item_qtys[i] else 1
            iprice = float(item_prices[i]) if i < len(item_prices) and item_prices[i] else 0.0
            itotal = round(iqty * iprice, 2)
            subtotal += itotal
            line_items.append((iname, idesc, iqty, iprice, itotal))

        tax_amount = round((subtotal * tax_rate) / 100.0, 2)
        grand_total = round(subtotal + tax_amount, 2)

        cursor.execute("""
            INSERT INTO quotations (quotation_number, customer_id, created_by, subject, subtotal, tax_rate, tax_amount, grand_total, valid_until, status, terms_conditions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (q_num, customer_id, session.get('user_id'), subject, subtotal, tax_rate, tax_amount, grand_total, valid_until, status, terms))
        new_qid = cursor.lastrowid

        for iname, idesc, iqty, iprice, itot in line_items:
            cursor.execute("""
                INSERT INTO quotation_items (quotation_id, item_name, description, quantity, unit_price, total)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (new_qid, iname, idesc, iqty, iprice, itot))

        conn.commit()
        conn.close()
        flash(f"Quotation '{q_num}' generated successfully.", 'success')
        return redirect(url_for('quotation_details', id=new_qid))

    cursor.execute("SELECT id FROM quotations ORDER BY id DESC LIMIT 1;")
    last_q = cursor.fetchone()
    next_num = f"QT-2026-{(last_q['id'] + 1):03d}" if last_q else "QT-2026-001"

    cursor.execute("SELECT id, name, customer_code, company_name FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    default_valid = (date.today() + timedelta(days=30)).isoformat()

    selected_cust = request.args.get('customer_id')
    selected_customer_id = int(selected_cust) if selected_cust and selected_cust.isdigit() else None

    conn.close()

    return render_template(
        'add_quotation.html',
        next_quote_number=next_num,
        customers=customers,
        default_valid_until=default_valid,
        selected_customer_id=selected_customer_id,
        active_page='quotations'
    )


@app.route('/quotations/<int:id>')
@role_required('admin', 'manager', 'employee')
def quotation_details(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT q.*, c.name as customer_name, c.company_name, c.email as customer_email,
               c.phone as customer_phone, c.address as customer_address, c.city as customer_city,
               c.state as customer_state, c.postal_code as customer_postal,
               u.full_name as created_by_name
        FROM quotations q
        JOIN customers c ON q.customer_id = c.id
        LEFT JOIN users u ON q.created_by = u.id
        WHERE q.id = ?;
    """, (id,))
    quotation = cursor.fetchone()

    if not quotation:
        conn.close()
        flash('Quotation record not found.', 'danger')
        return redirect(url_for('quotations'))

    cursor.execute("SELECT * FROM quotation_items WHERE quotation_id = ?;", (id,))
    items = cursor.fetchall()

    conn.close()

    return render_template('quotation_details.html', quotation=quotation, items=items, active_page='quotations')


@app.route('/quotations/<int:id>/status', methods=['POST'])
@role_required('admin', 'manager', 'employee')
def update_quotation_status(id):
    new_status = request.form.get('status')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE quotations SET status = ?, updated_at = ? WHERE id = ?;", (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), id))
    conn.commit()
    conn.close()
    flash(f"Quotation status updated to '{new_status}'.", 'success')
    return redirect(url_for('quotation_details', id=id))


@app.route('/quotations/<int:id>/delete', methods=['POST'])
@role_required('admin', 'manager')
def delete_quotation(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM quotations WHERE id = ?;", (id,))
    conn.commit()
    conn.close()
    flash('Quotation deleted successfully.', 'info')
    return redirect(url_for('quotations'))


# ==============================================================================
# CUSTOMER ORDERS SUB-MODULE
# ==============================================================================

@app.route('/orders')
@role_required('admin', 'manager', 'employee')
def orders():
    status = request.args.get('status', '').strip()
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT o.*, c.name as customer_name, c.company_name, u.full_name as assigned_name
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN users u ON o.assigned_to = u.id
        WHERE 1=1
    """
    params = []
    if status:
        query += " AND o.status = ?"
        params.append(status)

    query += " ORDER BY o.order_date DESC, o.id DESC;"
    cursor.execute(query, params)
    order_list = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM orders;")
    tot_cnt = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as completed FROM orders WHERE status = 'Completed';")
    comp_cnt = cursor.fetchone()['completed']
    cursor.execute("SELECT COUNT(*) as proc FROM orders WHERE status = 'Processing';")
    proc_cnt = cursor.fetchone()['proc']
    cursor.execute("SELECT COUNT(*) as pend FROM orders WHERE status = 'Pending';")
    pend_cnt = cursor.fetchone()['pend']

    stats = {
        'total': tot_cnt,
        'completed': comp_cnt,
        'processing': proc_cnt,
        'pending': pend_cnt
    }

    conn.close()
    return render_template('orders.html', orders=order_list, stats=stats, selected_status=status, active_page='orders')


@app.route('/orders/add', methods=['GET', 'POST'])
@role_required('admin', 'manager', 'employee')
def add_order():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        order_num = request.form.get('order_number', '').strip()
        customer_id = request.form.get('customer_id')
        assigned_to = request.form.get('assigned_to') or session.get('user_id')
        order_date = request.form.get('order_date', date.today().isoformat())
        expected_comp = request.form.get('expected_completion_date')
        status = request.form.get('status', 'Pending')
        shipping_addr = request.form.get('shipping_address', '').strip()
        notes = request.form.get('notes', '').strip()

        prod_names = request.form.getlist('product_name[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')

        total_amount = 0.0
        line_items = []
        for i in range(len(prod_names)):
            pname = prod_names[i].strip()
            if not pname:
                continue
            qty = int(quantities[i]) if i < len(quantities) and quantities[i] else 1
            price = float(unit_prices[i]) if i < len(unit_prices) and unit_prices[i] else 0.0
            tot = round(qty * price, 2)
            total_amount += tot
            line_items.append((pname, qty, price, tot))

        cursor.execute("""
            INSERT INTO orders (order_number, customer_id, assigned_to, order_date, expected_completion_date, total_amount, status, shipping_address, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (order_num, customer_id, assigned_to, order_date, expected_comp, total_amount, status, shipping_addr, notes))
        new_oid = cursor.lastrowid

        for pname, qty, price, tot in line_items:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_name, quantity, unit_price, total)
                VALUES (?, ?, ?, ?, ?);
            """, (new_oid, pname, qty, price, tot))

        conn.commit()
        conn.close()
        flash(f"Order '{order_num}' created successfully.", 'success')
        return redirect(url_for('order_details', id=new_oid))

    cursor.execute("SELECT id FROM orders ORDER BY id DESC LIMIT 1;")
    last_o = cursor.fetchone()
    next_num = f"ORD-2026-{(last_o['id'] + 1):03d}" if last_o else "ORD-2026-001"

    cursor.execute("SELECT id, name, customer_code, company_name FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, full_name, department, role FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees = cursor.fetchall()

    default_completion = (date.today() + timedelta(days=14)).isoformat()

    selected_cust = request.args.get('customer_id')
    selected_customer_id = int(selected_cust) if selected_cust and selected_cust.isdigit() else None

    conn.close()

    return render_template(
        'add_order.html',
        next_order_number=next_num,
        customers=customers,
        employees=employees,
        default_completion=default_completion,
        selected_customer_id=selected_customer_id,
        active_page='orders'
    )


@app.route('/orders/<int:id>')
@role_required('admin', 'manager', 'employee')
def order_details(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT o.*, c.name as customer_name, c.company_name, c.email as customer_email,
               c.phone as customer_phone, u.full_name as assigned_name, q.quotation_number
        FROM orders o
        JOIN customers c ON o.customer_id = c.id
        LEFT JOIN users u ON o.assigned_to = u.id
        LEFT JOIN quotations q ON o.quotation_id = q.id
        WHERE o.id = ?;
    """, (id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash('Order not found.', 'danger')
        return redirect(url_for('orders'))

    cursor.execute("SELECT * FROM order_items WHERE order_id = ?;", (id,))
    items = cursor.fetchall()

    conn.close()
    return render_template('order_details.html', order=order, items=items, active_page='orders')


@app.route('/orders/<int:id>/status', methods=['POST'])
@role_required('admin', 'manager', 'employee')
def update_order_status(id):
    new_status = request.form.get('status')
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ?;", (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), id))
    conn.commit()
    conn.close()
    flash(f"Order status updated to '{new_status}'.", 'success')
    return redirect(url_for('order_details', id=id))


@app.route('/orders/<int:id>/delete', methods=['POST'])
@role_required('admin', 'manager')
def delete_order(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders WHERE id = ?;", (id,))
    conn.commit()
    conn.close()
    flash('Order deleted successfully.', 'info')
    return redirect(url_for('orders'))


# ==============================================================================
# MODULE 3: CUSTOMER SUPPORT & COMPLAINT MANAGEMENT
# ==============================================================================

@app.route('/complaints')
@login_required
def complaints():
    search_query = request.args.get('q', '').strip()
    status = request.args.get('status', '').strip()
    priority = request.args.get('priority', '').strip()
    category = request.args.get('category', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT comp.*, c.name as customer_name, c.company_name, u.full_name as assigned_name
        FROM complaints comp
        JOIN customers c ON comp.customer_id = c.id
        LEFT JOIN users u ON comp.assigned_to = u.id
        WHERE 1=1
    """
    params = []

    if search_query:
        query += " AND (comp.ticket_number LIKE ? OR comp.title LIKE ? OR c.name LIKE ?)"
        w = f"%{search_query}%"
        params.extend([w, w, w])

    if status:
        query += " AND comp.status = ?"
        params.append(status)

    if priority:
        query += " AND comp.priority = ?"
        params.append(priority)

    if category:
        query += " AND comp.category = ?"
        params.append(category)

    query += " ORDER BY comp.created_at DESC;"

    cursor.execute(query, params)
    complaints_list = cursor.fetchall()

    # Metrics
    cursor.execute("SELECT COUNT(*) as total FROM complaints;")
    tot_cnt = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) as open_cnt FROM complaints WHERE status = 'Open';")
    open_cnt = cursor.fetchone()['open_cnt']
    cursor.execute("SELECT COUNT(*) as in_prog FROM complaints WHERE status = 'In Progress';")
    in_prog_cnt = cursor.fetchone()['in_prog']
    cursor.execute("SELECT COUNT(*) as resolved FROM complaints WHERE status = 'Resolved';")
    res_cnt = cursor.fetchone()['resolved']
    cursor.execute("SELECT COUNT(*) as high_pri FROM complaints WHERE priority = 'High' AND status != 'Resolved';")
    high_pri_cnt = cursor.fetchone()['high_pri']

    stats = {
        'total': tot_cnt,
        'open': open_cnt,
        'in_progress': in_prog_cnt,
        'resolved': res_cnt,
        'high_priority': high_pri_cnt
    }

    conn.close()

    return render_template(
        'complaints.html',
        complaints=complaints_list,
        stats=stats,
        search_query=search_query,
        selected_status=status,
        selected_priority=priority,
        selected_category=category,
        active_page='complaints'
    )


@app.route('/complaints/add', methods=['GET', 'POST'])
@login_required
def add_complaint():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        ticket_num = request.form.get('ticket_number', '').strip()
        customer_id = request.form.get('customer_id')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', 'Technical Support')
        priority = request.form.get('priority', 'Medium')
        assigned_to = request.form.get('assigned_to') or None

        if not customer_id or not title or not description:
            flash('Customer, Title, and Problem Description are required.', 'danger')
        else:
            cursor.execute("""
                INSERT INTO complaints (ticket_number, customer_id, title, description, category, priority, status, assigned_to, created_by)
                VALUES (?, ?, ?, ?, ?, ?, 'Open', ?, ?);
            """, (ticket_num, customer_id, title, description, category, priority, assigned_to, session.get('user_id')))
            new_ticket_id = cursor.lastrowid

            # Create notification for assigned employee
            if assigned_to:
                cursor.execute("""
                    INSERT INTO notifications (user_id, title, message, category, link)
                    VALUES (?, ?, ?, 'ticket', ?);
                """, (assigned_to, f"New Ticket Assigned: {ticket_num}", f"You have been assigned to ticket '{title}'", f"/complaints/{new_ticket_id}"))

            conn.commit()
            conn.close()
            flash(f"Support ticket '{ticket_num}' registered successfully.", 'success')
            return redirect(url_for('complaint_details', id=new_ticket_id))

    cursor.execute("SELECT id FROM complaints ORDER BY id DESC LIMIT 1;")
    last_comp = cursor.fetchone()
    next_num = f"TICK-{(last_comp['id'] + 1001) if last_comp else 1001}"

    cursor.execute("SELECT id, name, customer_code, company_name FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, full_name, department, role FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees = cursor.fetchall()

    selected_cust = request.args.get('customer_id')
    selected_customer_id = int(selected_cust) if selected_cust and selected_cust.isdigit() else None

    conn.close()

    return render_template(
        'add_complaint.html',
        next_ticket_number=next_num,
        customers=customers,
        employees=employees,
        selected_customer_id=selected_customer_id,
        active_page='complaints'
    )


@app.route('/complaints/<int:id>')
@login_required
def complaint_details(id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT comp.*, c.name as customer_name, c.company_name, c.email as customer_email,
               c.phone as customer_phone, c.city as customer_city,
               creator.full_name as creator_name, assigned.full_name as assigned_name
        FROM complaints comp
        JOIN customers c ON comp.customer_id = c.id
        LEFT JOIN users creator ON comp.created_by = creator.id
        LEFT JOIN users assigned ON comp.assigned_to = assigned.id
        WHERE comp.id = ?;
    """, (id,))
    complaint = cursor.fetchone()

    if not complaint:
        conn.close()
        flash('Complaint ticket not found.', 'danger')
        return redirect(url_for('complaints'))

    cursor.execute("""
        SELECT cr.*, u.full_name as responder_name, u.role as responder_role
        FROM complaint_responses cr
        LEFT JOIN users u ON cr.user_id = u.id
        WHERE cr.complaint_id = ?
        ORDER BY cr.created_at ASC;
    """, (id,))
    responses = cursor.fetchall()

    cursor.execute("SELECT id, full_name, department, role FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees = cursor.fetchall()

    conn.close()

    return render_template(
        'complaint_details.html',
        complaint=complaint,
        responses=responses,
        employees=employees,
        active_page='complaints'
    )


@app.route('/complaints/<int:id>/response', methods=['POST'])
@login_required
def add_complaint_response(id):
    response_text = request.form.get('response_text', '').strip()
    status_update = request.form.get('status_update', '').strip()

    if not response_text:
        flash('Response text cannot be empty.', 'danger')
        return redirect(url_for('complaint_details', id=id))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO complaint_responses (complaint_id, user_id, response_text, status_update)
        VALUES (?, ?, ?, ?);
    """, (id, session.get('user_id'), response_text, status_update if status_update else None))

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if status_update:
        if status_update == 'Resolved':
            cursor.execute("UPDATE complaints SET status = ?, resolution_notes = ?, resolved_at = ?, updated_at = ? WHERE id = ?;",
                           (status_update, response_text, now_str, now_str, id))
        else:
            cursor.execute("UPDATE complaints SET status = ?, updated_at = ? WHERE id = ?;", (status_update, now_str, id))
    else:
        cursor.execute("UPDATE complaints SET updated_at = ? WHERE id = ?;", (now_str, id))

    conn.commit()
    conn.close()

    flash('Support response posted successfully.', 'success')
    return redirect(url_for('complaint_details', id=id))


@app.route('/complaints/<int:id>/resolve', methods=['POST'])
@role_required('admin', 'support', 'manager')
def resolve_complaint(id):
    resolution_notes = request.form.get('resolution_notes', '').strip()
    if not resolution_notes:
        flash('Resolution summary notes are required.', 'danger')
        return redirect(url_for('complaint_details', id=id))

    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        UPDATE complaints
        SET status = 'Resolved', resolution_notes = ?, resolved_at = ?, updated_at = ?
        WHERE id = ?;
    """, (resolution_notes, now_str, now_str, id))

    # Add response record
    cursor.execute("""
        INSERT INTO complaint_responses (complaint_id, user_id, response_text, status_update)
        VALUES (?, ?, ?, 'Resolved');
    """, (id, session.get('user_id'), f"Ticket marked as Resolved: {resolution_notes}"))

    conn.commit()
    conn.close()

    flash('Ticket has been successfully resolved.', 'success')
    return redirect(url_for('complaint_details', id=id))


@app.route('/complaints/<int:id>/settings', methods=['POST'])
@role_required('admin', 'support', 'manager')
def update_complaint_settings(id):
    assigned_to = request.form.get('assigned_to') or None
    priority = request.form.get('priority', 'Medium')
    status = request.form.get('status', 'Open')

    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        UPDATE complaints
        SET assigned_to = ?, priority = ?, status = ?, updated_at = ?
        WHERE id = ?;
    """, (assigned_to, priority, status, now_str, id))

    conn.commit()
    conn.close()

    flash('Ticket settings updated successfully.', 'success')
    return redirect(url_for('complaint_details', id=id))


@app.route('/complaints/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_complaint(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM complaints WHERE id = ?;", (id,))
    conn.commit()
    conn.close()
    flash('Complaint ticket deleted permanently.', 'info')
    return redirect(url_for('complaints'))


# ==============================================================================
# MODULE 4: REPORT MANAGEMENT
# ==============================================================================

@app.route('/reports')
@role_required('admin', 'manager', 'employee')
def reports():
    report_type = request.args.get('report_type', 'sales_performance')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    employee_id = request.args.get('employee_id', '')
    customer_id = request.args.get('customer_id', '')

    data = build_report_data(report_type, start_date, end_date, employee_id, customer_id)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees_list = cursor.fetchall()
    cursor.execute("SELECT id, name FROM customers ORDER BY name ASC;")
    customers_list = cursor.fetchall()
    conn.close()

    return render_template(
        'reports.html',
        selected_report=report_type,
        start_date=start_date,
        end_date=end_date,
        selected_employee=employee_id,
        selected_customer=customer_id,
        employees_list=employees_list,
        customers_list=customers_list,
        current_timestamp=datetime.now().strftime('%Y-%m-%d %H:%M'),
        active_page='reports',
        **data
    )


@app.route('/reports/export-csv')
@role_required('admin', 'manager', 'employee')
def export_report_csv():
    report_type = request.args.get('report_type', 'sales_performance')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    employee_id = request.args.get('employee_id', '')
    customer_id = request.args.get('customer_id', '')

    data = build_report_data(report_type, start_date, end_date, employee_id, customer_id)

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)

    # Header Row
    headers = [col['label'] for col in data['table_columns']]
    writer.writerow(headers)

    # Data Rows
    for row in data['table_rows']:
        writer.writerow([row.get(col['key'], '') for col in data['table_columns']])

    csv_content = output.getvalue()
    output.close()

    # Save a physical copy to exports/
    filename = f"CRM_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(csv_content)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


def build_report_data(report_type, start_date, end_date, employee_id, customer_id):
    """Calculates live reports from SQLite database records without hardcoding."""
    conn = get_db()
    cursor = conn.cursor()

    report_title = "Business Report"
    summary_cards = []
    table_columns = []
    table_rows = []
    chart_config = None

    # Date filters helper
    date_filter = ""
    date_params = []
    if start_date:
        date_filter += " AND DATE(created_at) >= ?"
        date_params.append(start_date)
    if end_date:
        date_filter += " AND DATE(created_at) <= ?"
        date_params.append(end_date)

    # 1. Customer Registration Report
    if report_type == 'customer_registration':
        report_title = "Customer Registration & Growth Report"
        cursor.execute("SELECT COUNT(*) as total FROM customers;")
        total_cust = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as active FROM customers WHERE status = 'Active';")
        active_cust = cursor.fetchone()['active']
        cursor.execute("SELECT COUNT(*) as leads FROM customers WHERE status = 'Lead';")
        leads_cust = cursor.fetchone()['leads']

        summary_cards = [
            {'label': 'Total Customers', 'value': total_cust, 'color': 'primary', 'subtext': 'All registered clients'},
            {'label': 'Active Clients', 'value': active_cust, 'color': 'success', 'subtext': 'Operational accounts'},
            {'label': 'Prospective Leads', 'value': leads_cust, 'color': 'warning', 'subtext': 'Sales pipeline opportunities'}
        ]

        table_columns = [
            {'label': 'Customer Code', 'key': 'customer_code', 'align': 'left'},
            {'label': 'Customer Name', 'key': 'name', 'align': 'left'},
            {'label': 'Company', 'key': 'company_name', 'align': 'left'},
            {'label': 'Email Address', 'key': 'email', 'align': 'left'},
            {'label': 'City', 'key': 'city', 'align': 'left'},
            {'label': 'Status', 'key': 'status', 'align': 'center'},
            {'label': 'Registration Date', 'key': 'reg_date', 'align': 'center'}
        ]

        q = "SELECT * FROM customers WHERE 1=1"
        p = []
        if start_date:
            q += " AND DATE(created_at) >= ?"
            p.append(start_date)
        if end_date:
            q += " AND DATE(created_at) <= ?"
            p.append(end_date)
        if customer_id:
            q += " AND id = ?"
            p.append(customer_id)
        q += " ORDER BY created_at DESC;"

        cursor.execute(q, p)
        for r in cursor.fetchall():
            table_rows.append({
                'customer_code': r['customer_code'],
                'name': r['name'],
                'company_name': r['company_name'] or '—',
                'email': r['email'],
                'city': r['city'] or '—',
                'status': r['status'],
                'reg_date': r['created_at'][:10]
            })

        chart_config = {
            'type': 'bar',
            'title': 'Customer Account Status Distribution',
            'labels': ['Active', 'Lead', 'Inactive'],
            'datasets': [{
                'label': 'Accounts',
                'data': [active_cust, leads_cust, total_cust - (active_cust + leads_cust)],
                'backgroundColor': ['#10b981', '#f59e0b', '#94a3b8']
            }]
        }

    # 2. Sales Performance Report
    elif report_type == 'sales_performance':
        report_title = "Sales Performance & Transactions Report"
        q_stats = "SELECT COUNT(*) as cnt, COALESCE(SUM(total_amount), 0.0) as rev FROM sales WHERE 1=1"
        p_stats = []
        if start_date:
            q_stats += " AND sale_date >= ?"
            p_stats.append(start_date)
        if end_date:
            q_stats += " AND sale_date <= ?"
            p_stats.append(end_date)
        if employee_id:
            q_stats += " AND employee_id = ?"
            p_stats.append(employee_id)
        if customer_id:
            q_stats += " AND customer_id = ?"
            p_stats.append(customer_id)

        cursor.execute(q_stats, p_stats)
        s_row = cursor.fetchone()
        tot_cnt = s_row['cnt']
        tot_rev = s_row['rev']
        avg_deal = (tot_rev / tot_cnt) if tot_cnt > 0 else 0.0

        summary_cards = [
            {'label': 'Total Deals', 'value': tot_cnt, 'color': 'primary', 'subtext': 'Transactions recorded'},
            {'label': 'Total Revenue', 'value': f"₹{tot_rev:,.2f}", 'color': 'success', 'subtext': 'Aggregate value'},
            {'label': 'Average Deal Size', 'value': f"₹{avg_deal:,.2f}", 'color': 'info', 'subtext': 'Per closed transaction'}
        ]

        table_columns = [
            {'label': 'Sale Code', 'key': 'sales_code', 'align': 'left'},
            {'label': 'Customer', 'key': 'customer_name', 'align': 'left'},
            {'label': 'Product / Service', 'key': 'product', 'align': 'left'},
            {'label': 'Quantity', 'key': 'quantity', 'align': 'center'},
            {'label': 'Unit Price', 'key': 'unit_price', 'align': 'right'},
            {'label': 'Total Amount', 'key': 'total', 'align': 'right'},
            {'label': 'Sale Date', 'key': 'sale_date', 'align': 'center'},
            {'label': 'Sales Rep', 'key': 'rep', 'align': 'left'}
        ]

        q = """
            SELECT s.*, c.name as customer_name, u.full_name as rep_name
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            LEFT JOIN users u ON s.employee_id = u.id
            WHERE 1=1
        """
        p = []
        if start_date:
            q += " AND s.sale_date >= ?"
            p.append(start_date)
        if end_date:
            q += " AND s.sale_date <= ?"
            p.append(end_date)
        if employee_id:
            q += " AND s.employee_id = ?"
            p.append(employee_id)
        if customer_id:
            q += " AND s.customer_id = ?"
            p.append(customer_id)
        q += " ORDER BY s.sale_date DESC;"

        cursor.execute(q, p)
        for r in cursor.fetchall():
            table_rows.append({
                'sales_code': r['sales_code'],
                'customer_name': r['customer_name'],
                'product': r['product_service_name'],
                'quantity': r['quantity'],
                'unit_price': f"₹{r['unit_price']:,.2f}",
                'total': f"₹{r['total_amount']:,.2f}",
                'sale_date': r['sale_date'],
                'rep': r['rep_name'] or 'Unassigned'
            })

        # Top product categories chart
        cursor.execute("""
            SELECT category, SUM(total_amount) as cat_rev
            FROM sales
            GROUP BY category
            ORDER BY cat_rev DESC LIMIT 5;
        """)
        cats = cursor.fetchall()
        chart_config = {
            'type': 'bar',
            'title': 'Revenue by Product / Service Category (₹)',
            'labels': [c['category'] or 'Other' for c in cats],
            'datasets': [{
                'label': 'Revenue (₹)',
                'data': [round(c['cat_rev'], 2) for c in cats],
                'backgroundColor': '#2563eb'
            }]
        }

    # 3. Employee Performance Report
    elif report_type == 'employee_performance':
        report_title = "Employee & Team Performance Report"
        table_columns = [
            {'label': 'Employee Code', 'key': 'code', 'align': 'left'},
            {'label': 'Full Name', 'key': 'name', 'align': 'left'},
            {'label': 'Role / Designation', 'key': 'role', 'align': 'left'},
            {'label': 'Department', 'key': 'department', 'align': 'left'},
            {'label': 'Deals Closed', 'key': 'deals', 'align': 'center'},
            {'label': 'Total Revenue', 'key': 'revenue', 'align': 'right'},
            {'label': 'Tickets Resolved', 'key': 'resolved_tickets', 'align': 'center'}
        ]

        cursor.execute("""
            SELECT u.id, u.full_name, u.role, u.department, e.employee_code, e.designation,
                   COUNT(DISTINCT s.id) as deals_count,
                   COALESCE(SUM(s.total_amount), 0.0) as revenue_sum,
                   COUNT(DISTINCT comp.id) as tickets_count
            FROM users u
            LEFT JOIN employees e ON u.id = e.user_id
            LEFT JOIN sales s ON u.id = s.employee_id
            LEFT JOIN complaints comp ON u.id = comp.assigned_to AND comp.status = 'Resolved'
            WHERE u.is_active = 1
            GROUP BY u.id
            ORDER BY revenue_sum DESC;
        """)
        employees_data = cursor.fetchall()

        emp_names = []
        emp_revs = []
        total_team_rev = 0.0

        for emp in employees_data:
            total_team_rev += emp['revenue_sum']
            emp_names.append(emp['full_name'])
            emp_revs.append(round(emp['revenue_sum'], 2))
            table_rows.append({
                'code': emp['employee_code'] or '—',
                'name': emp['full_name'],
                'role': emp['designation'] or emp['role'].capitalize(),
                'department': emp['department'] or '—',
                'deals': emp['deals_count'],
                'revenue': f"₹{emp['revenue_sum']:,.2f}",
                'resolved_tickets': emp['tickets_count']
            })

        summary_cards = [
            {'label': 'Total Active Employees', 'value': len(employees_data), 'color': 'primary', 'subtext': 'Staff evaluated'},
            {'label': 'Total Team Revenue', 'value': f"₹{total_team_rev:,.2f}", 'color': 'success', 'subtext': 'Across all employees'},
            {'label': 'Top Producer', 'value': emp_names[0] if emp_names else 'N/A', 'color': 'purple', 'subtext': f"₹{emp_revs[0]:,.2f}" if emp_revs else ''}
        ]

        chart_config = {
            'type': 'bar',
            'title': 'Sales Revenue by Employee (₹)',
            'labels': emp_names,
            'datasets': [{
                'label': 'Revenue Generated',
                'data': emp_revs,
                'backgroundColor': '#7c3aed'
            }]
        }

    # 4. Customer Complaint Report
    elif report_type == 'complaint_report':
        report_title = "Customer Support & Complaints Report"
        cursor.execute("SELECT COUNT(*) as total FROM complaints;")
        tot_c = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) as res FROM complaints WHERE status = 'Resolved';")
        res_c = cursor.fetchone()['res']
        cursor.execute("SELECT COUNT(*) as open FROM complaints WHERE status IN ('Open', 'In Progress');")
        open_c = cursor.fetchone()['open']

        summary_cards = [
            {'label': 'Total Complaints', 'value': tot_c, 'color': 'primary', 'subtext': 'All recorded tickets'},
            {'label': 'Resolved Complaints', 'value': res_c, 'color': 'success', 'subtext': 'Successfully solved'},
            {'label': 'Pending Tickets', 'value': open_c, 'color': 'danger', 'subtext': 'Currently in triage/progress'}
        ]

        table_columns = [
            {'label': 'Ticket #', 'key': 'ticket_number', 'align': 'left'},
            {'label': 'Customer', 'key': 'customer_name', 'align': 'left'},
            {'label': 'Complaint Title', 'key': 'title', 'align': 'left'},
            {'label': 'Category', 'key': 'category', 'align': 'left'},
            {'label': 'Priority', 'key': 'priority', 'align': 'center'},
            {'label': 'Status', 'key': 'status', 'align': 'center'},
            {'label': 'Submitted Date', 'key': 'created_at', 'align': 'center'},
            {'label': 'Assigned To', 'key': 'assigned', 'align': 'left'}
        ]

        cursor.execute("""
            SELECT comp.*, c.name as customer_name, u.full_name as assigned_name
            FROM complaints comp
            JOIN customers c ON comp.customer_id = c.id
            LEFT JOIN users u ON comp.assigned_to = u.id
            ORDER BY comp.created_at DESC;
        """)
        for r in cursor.fetchall():
            table_rows.append({
                'ticket_number': r['ticket_number'],
                'customer_name': r['customer_name'],
                'title': r['title'],
                'category': r['category'],
                'priority': r['priority'],
                'status': r['status'],
                'created_at': r['created_at'][:10],
                'assigned': r['assigned_name'] or 'Unassigned'
            })

        # Complaints by category
        cursor.execute("SELECT category, COUNT(*) as cnt FROM complaints GROUP BY category;")
        cats = cursor.fetchall()
        chart_config = {
            'type': 'doughnut',
            'title': 'Complaints by Issue Category',
            'labels': [c['category'] for c in cats],
            'datasets': [{
                'data': [c['cnt'] for c in cats],
                'backgroundColor': ['#3b82f6', '#f59e0b', '#ef4444', '#10b981', '#8b5cf6', '#06b6d4']
            }]
        }

    # 5. Customer Purchase History Report
    elif report_type == 'purchase_history':
        report_title = "Customer Lifetime Value (LTV) & Purchase History Report"
        table_columns = [
            {'label': 'Customer ID', 'key': 'customer_code', 'align': 'left'},
            {'label': 'Customer Name', 'key': 'customer_name', 'align': 'left'},
            {'label': 'Company', 'key': 'company', 'align': 'left'},
            {'label': 'Total Deals', 'key': 'deals_count', 'align': 'center'},
            {'label': 'Total Lifetime Value', 'key': 'ltv', 'align': 'right'},
            {'label': 'Average Order Value', 'key': 'aov', 'align': 'right'},
            {'label': 'Account Status', 'key': 'status', 'align': 'center'}
        ]

        cursor.execute("""
            SELECT c.id, c.customer_code, c.name, c.company_name, c.status,
                   COUNT(s.id) as deals_count,
                   COALESCE(SUM(s.total_amount), 0.0) as ltv
            FROM customers c
            LEFT JOIN sales s ON c.id = s.customer_id
            GROUP BY c.id
            ORDER BY ltv DESC;
        """)
        ltv_rows = cursor.fetchall()
        grand_ltv = 0.0
        for row in ltv_rows:
            grand_ltv += row['ltv']
            cnt = row['deals_count']
            aov = (row['ltv'] / cnt) if cnt > 0 else 0.0
            table_rows.append({
                'customer_code': row['customer_code'],
                'customer_name': row['name'],
                'company': row['company_name'] or '—',
                'deals_count': cnt,
                'ltv': f"₹{row['ltv']:,.2f}",
                'aov': f"₹{aov:,.2f}",
                'status': row['status']
            })

        summary_cards = [
            {'label': 'Total Customer LTV', 'value': f"₹{grand_ltv:,.2f}", 'color': 'success', 'subtext': 'Cumulative lifetime sales'},
            {'label': 'Paying Customers', 'value': sum(1 for r in ltv_rows if r['deals_count'] > 0), 'color': 'primary', 'subtext': f"Out of {len(ltv_rows)} total clients"},
            {'label': 'Top Client Spend', 'value': f"₹{ltv_rows[0]['ltv']:,.2f}" if ltv_rows else '₹0.00', 'color': 'purple', 'subtext': ltv_rows[0]['name'] if ltv_rows else ''}
        ]

        chart_config = {
            'type': 'bar',
            'title': 'Top 5 Customer Accounts by Lifetime Value (₹)',
            'labels': [r['name'] for r in ltv_rows[:5]],
            'datasets': [{
                'label': 'Total Spend (₹)',
                'data': [round(r['ltv'], 2) for r in ltv_rows[:5]],
                'backgroundColor': '#10b981'
            }]
        }

    # 6. Revenue Report
    elif report_type == 'revenue_report':
        report_title = "Comprehensive Revenue & Settlements Report"
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0.0) as gross FROM sales;")
        gross_rev = cursor.fetchone()['gross']
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0.0) as comp FROM sales WHERE status = 'Completed';")
        comp_rev = cursor.fetchone()['comp']
        cursor.execute("SELECT COALESCE(SUM(total_amount), 0.0) as pend FROM sales WHERE status IN ('Pending', 'Processing');")
        pend_rev = cursor.fetchone()['pend']

        summary_cards = [
            {'label': 'Total Gross Revenue', 'value': f"₹{gross_rev:,.2f}", 'color': 'primary', 'subtext': 'All recorded sales'},
            {'label': 'Settled Revenue', 'value': f"₹{comp_rev:,.2f}", 'color': 'success', 'subtext': 'Completed transactions'},
            {'label': 'Pending Settlements', 'value': f"₹{pend_rev:,.2f}", 'color': 'warning', 'subtext': 'Awaiting final payment/delivery'}
        ]

        table_columns = [
            {'label': 'Sale Code', 'key': 'code', 'align': 'left'},
            {'label': 'Customer', 'key': 'customer', 'align': 'left'},
            {'label': 'Payment Method', 'key': 'payment', 'align': 'left'},
            {'label': 'Amount', 'key': 'amount', 'align': 'right'},
            {'label': 'Sale Date', 'key': 'date', 'align': 'center'},
            {'label': 'Status', 'key': 'status', 'align': 'center'}
        ]

        cursor.execute("""
            SELECT s.*, c.name as customer_name
            FROM sales s
            JOIN customers c ON s.customer_id = c.id
            ORDER BY s.sale_date DESC;
        """)
        for s in cursor.fetchall():
            table_rows.append({
                'code': s['sales_code'],
                'customer': s['customer_name'],
                'payment': s['payment_method'],
                'amount': f"₹{s['total_amount']:,.2f}",
                'date': s['sale_date'],
                'status': s['status']
            })

        # Payment methods chart
        cursor.execute("SELECT payment_method, SUM(total_amount) as m_rev FROM sales GROUP BY payment_method;")
        pays = cursor.fetchall()
        chart_config = {
            'type': 'pie',
            'title': 'Revenue Distribution by Payment Method (₹)',
            'labels': [p['payment_method'] for p in pays],
            'datasets': [{
                'data': [round(p['m_rev'], 2) for p in pays],
                'backgroundColor': ['#2563eb', '#10b981', '#f59e0b', '#7c3aed', '#64748b']
            }]
        }

    # 7. Pending Orders Report
    elif report_type == 'pending_orders':
        report_title = "Pending & Processing Orders Fulfillment Report"
        cursor.execute("SELECT COUNT(*) as pend_cnt, COALESCE(SUM(total_amount), 0.0) as pend_val FROM orders WHERE status = 'Pending';")
        pend_row = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) as proc_cnt, COALESCE(SUM(total_amount), 0.0) as proc_val FROM orders WHERE status = 'Processing';")
        proc_row = cursor.fetchone()

        summary_cards = [
            {'label': 'Pending Fulfillment', 'value': pend_row['pend_cnt'], 'color': 'warning', 'subtext': f"₹{pend_row['pend_val']:,.2f} order value"},
            {'label': 'In Deployment', 'value': proc_row['proc_cnt'], 'color': 'primary', 'subtext': f"₹{proc_row['proc_val']:,.2f} order value"},
            {'label': 'Total Pipeline In-Flight', 'value': f"₹{(pend_row['pend_val'] + proc_row['proc_val']):,.2f}", 'color': 'success', 'subtext': 'Pending completion'}
        ]

        table_columns = [
            {'label': 'Order #', 'key': 'order_num', 'align': 'left'},
            {'label': 'Customer', 'key': 'customer', 'align': 'left'},
            {'label': 'Order Date', 'key': 'odate', 'align': 'center'},
            {'label': 'Expected Date', 'key': 'cdate', 'align': 'center'},
            {'label': 'Total Amount', 'key': 'amount', 'align': 'right'},
            {'label': 'Assigned Rep', 'key': 'rep', 'align': 'left'},
            {'label': 'Status', 'key': 'status', 'align': 'center'}
        ]

        cursor.execute("""
            SELECT o.*, c.name as customer_name, u.full_name as rep_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LEFT JOIN users u ON o.assigned_to = u.id
            WHERE o.status IN ('Pending', 'Processing')
            ORDER BY o.expected_completion_date ASC;
        """)
        for o in cursor.fetchall():
            table_rows.append({
                'order_num': o['order_number'],
                'customer': o['customer_name'],
                'odate': o['order_date'],
                'cdate': o['expected_completion_date'] or '—',
                'amount': f"₹{o['total_amount']:,.2f}",
                'rep': o['rep_name'] or 'Unassigned',
                'status': o['status']
            })

        chart_config = {
            'type': 'doughnut',
            'title': 'Active Order Fulfillment Status',
            'labels': ['Pending', 'Processing'],
            'datasets': [{
                'data': [pend_row['pend_cnt'], proc_row['proc_cnt']],
                'backgroundColor': ['#f59e0b', '#3b82f6']
            }]
        }

    # 8. Customer Satisfaction Report
    else:
        report_title = "Customer Satisfaction & Feedback (CSAT) Report"
        cursor.execute("SELECT COUNT(*) as cnt, COALESCE(AVG(rating), 5.0) as avg_r FROM feedback;")
        fb_stats = cursor.fetchone()
        avg_score = fb_stats['avg_r']

        cursor.execute("SELECT COUNT(*) as five_star FROM feedback WHERE rating = 5;")
        five_star = cursor.fetchone()['five_star']

        summary_cards = [
            {'label': 'Average CSAT Score', 'value': f"{avg_score:.1f} / 5.0", 'color': 'warning', 'subtext': 'Overall customer rating'},
            {'label': 'Total Reviews', 'value': fb_stats['cnt'], 'color': 'primary', 'subtext': 'Submissions received'},
            {'label': '5-Star Reviews', 'value': five_star, 'color': 'success', 'subtext': f"{((five_star / fb_stats['cnt']) * 100):.0f}% top ratings" if fb_stats['cnt'] > 0 else '100%'}
        ]

        table_columns = [
            {'label': 'Customer', 'key': 'customer', 'align': 'left'},
            {'label': 'Rating', 'key': 'rating', 'align': 'center'},
            {'label': 'Touchpoint Aspect', 'key': 'aspect', 'align': 'left'},
            {'label': 'Review Comments', 'key': 'comments', 'align': 'left'},
            {'label': 'Submission Date', 'key': 'date', 'align': 'center'}
        ]

        cursor.execute("""
            SELECT fb.*, c.name as customer_name
            FROM feedback fb
            JOIN customers c ON fb.customer_id = c.id
            ORDER BY fb.created_at DESC;
        """)
        for fb in cursor.fetchall():
            table_rows.append({
                'customer': fb['customer_name'],
                'rating': f"{fb['rating']} / 5 Stars",
                'aspect': fb['service_aspect'],
                'comments': fb['comments'],
                'date': fb['created_at'][:10]
            })

        # Star breakdown chart
        cursor.execute("SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating ORDER BY rating ASC;")
        star_counts = {i: 0 for i in range(1, 6)}
        for r in cursor.fetchall():
            star_counts[r['rating']] = r['cnt']

        chart_config = {
            'type': 'bar',
            'title': 'Customer Rating Breakdown (1 to 5 Stars)',
            'labels': ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars'],
            'datasets': [{
                'label': 'Reviews Count',
                'data': [star_counts[i] for i in range(1, 6)],
                'backgroundColor': ['#ef4444', '#f97316', '#eab308', '#3b82f6', '#10b981']
            }]
        }

    conn.close()

    return {
        'report_title': report_title,
        'summary_cards': summary_cards,
        'table_columns': table_columns,
        'table_rows': table_rows,
        'chart_config': chart_config
    }


# ==============================================================================
# MODULE 5: NOTIFICATIONS & FEEDBACK
# ==============================================================================

@app.route('/notifications')
@login_required
def notifications():
    filter_unread = request.args.get('unread') == '1'
    conn = get_db()
    cursor = conn.cursor()
    user_id = session.get('user_id')

    query = "SELECT * FROM notifications WHERE (user_id = ? OR user_id IS NULL)"
    params = [user_id]
    if filter_unread:
        query += " AND is_read = 0"

    query += " ORDER BY created_at DESC;"
    cursor.execute(query, params)
    notifs = cursor.fetchall()
    conn.close()

    return render_template('notifications.html', notifications=notifs, filter_unread=filter_unread, active_page='notifications')


@app.route('/notifications/mark-read/<int:id>', methods=['POST'])
@login_required
def mark_notification_read(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?;", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('notifications'))


@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? OR user_id IS NULL;", (session.get('user_id'),))
    conn.commit()
    conn.close()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('notifications'))


# Follow-up Reminders
@app.route('/follow-ups')
@login_required
def follow_ups():
    selected_status = request.args.get('status', '').strip()
    conn = get_db()
    cursor = conn.cursor()

    # Automatically mark overdue pending follow-ups
    today_str = date.today().isoformat()
    cursor.execute("UPDATE follow_ups SET status = 'Overdue' WHERE follow_up_date < ? AND status = 'Pending';", (today_str,))
    conn.commit()

    query = """
        SELECT f.*, c.name as customer_name, c.company_name, u.full_name as user_name
        FROM follow_ups f
        JOIN customers c ON f.customer_id = c.id
        LEFT JOIN users u ON f.user_id = u.id
        WHERE 1=1
    """
    params = []
    if selected_status:
        query += " AND f.status = ?"
        params.append(selected_status)

    query += " ORDER BY f.follow_up_date ASC, f.id ASC;"
    cursor.execute(query, params)
    f_list = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as pend FROM follow_ups WHERE status = 'Pending';")
    p_cnt = cursor.fetchone()['pend']
    cursor.execute("SELECT COUNT(*) as od FROM follow_ups WHERE status = 'Overdue';")
    od_cnt = cursor.fetchone()['od']
    cursor.execute("SELECT COUNT(*) as up FROM follow_ups WHERE follow_up_date >= ? AND status = 'Pending';", (today_str,))
    up_cnt = cursor.fetchone()['up']
    cursor.execute("SELECT COUNT(*) as comp FROM follow_ups WHERE status = 'Completed';")
    comp_cnt = cursor.fetchone()['comp']

    stats = {
        'pending': p_cnt,
        'overdue': od_cnt,
        'upcoming': up_cnt,
        'completed': comp_cnt
    }

    cursor.execute("SELECT id, name, customer_code FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, full_name, department, role FROM users WHERE is_active = 1 ORDER BY full_name ASC;")
    employees = cursor.fetchall()

    conn.close()

    return render_template(
        'follow_ups.html',
        follow_ups=f_list,
        stats=stats,
        customers=customers,
        employees=employees,
        selected_status=selected_status,
        active_page='follow_ups'
    )


@app.route('/follow-ups/add', methods=['POST'])
@login_required
def add_follow_up():
    customer_id = request.form.get('customer_id')
    user_id = request.form.get('user_id') or session.get('user_id')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    f_date = request.form.get('follow_up_date')
    f_time = request.form.get('follow_up_time', '10:00 AM')

    if not customer_id or not title or not f_date:
        flash('Customer, Title, and Date are required.', 'danger')
        return redirect(url_for('follow_ups'))

    status = 'Overdue' if f_date < date.today().isoformat() else 'Pending'

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO follow_ups (customer_id, user_id, title, description, follow_up_date, follow_up_time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?);
    """, (customer_id, user_id, title, description, f_date, f_time, status))

    # Add notification
    cursor.execute("""
        INSERT INTO notifications (user_id, title, message, category, link)
        VALUES (?, ?, ?, 'follow_up', '/follow-ups');
    """, (user_id, f"Follow-up Scheduled: {title}", f"Reminder on {f_date} at {f_time} for customer."))

    conn.commit()
    conn.close()

    flash('Follow-up scheduled successfully.', 'success')
    return redirect(url_for('follow_ups'))


@app.route('/follow-ups/<int:id>/status', methods=['POST'])
@login_required
def update_follow_up_status(id):
    status = request.form.get('status', 'Completed')
    outcome_notes = request.form.get('outcome_notes', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE follow_ups SET status = ?, outcome_notes = ? WHERE id = ?;
    """, (status, outcome_notes, id))
    conn.commit()
    conn.close()

    flash('Follow-up activity marked as completed.', 'success')
    return redirect(url_for('follow_ups'))


@app.route('/follow-ups/<int:id>/delete', methods=['POST'])
@login_required
def delete_follow_up(id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM follow_ups WHERE id = ?;", (id,))
    conn.commit()
    conn.close()
    flash('Follow-up deleted.', 'info')
    return redirect(url_for('follow_ups'))


# Customer Feedback
@app.route('/feedback')
@login_required
def feedback():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fb.*, c.name as customer_name, c.company_name, comp.ticket_number
        FROM feedback fb
        JOIN customers c ON fb.customer_id = c.id
        LEFT JOIN complaints comp ON fb.complaint_id = comp.id
        ORDER BY fb.created_at DESC;
    """)
    feedback_list = cursor.fetchall()

    cursor.execute("SELECT COALESCE(AVG(rating), 5.0) as avg_rate FROM feedback;")
    avg_rating = cursor.fetchone()['avg_rate']

    cursor.execute("SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating;")
    rating_counts = {r['rating']: r['cnt'] for r in cursor.fetchall()}

    conn.close()

    return render_template(
        'feedback.html',
        feedback_list=feedback_list,
        avg_rating=round(avg_rating, 1),
        rating_counts=rating_counts,
        active_page='feedback'
    )


@app.route('/feedback/add', methods=['GET', 'POST'])
@login_required
def add_feedback():
    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        complaint_id = request.form.get('complaint_id') or None
        rating = int(request.form.get('rating', 5))
        aspect = request.form.get('service_aspect', 'Overall Experience')
        comments = request.form.get('comments', '').strip()

        if not customer_id or not comments:
            flash('Customer selection and comments are required.', 'danger')
        else:
            cursor.execute("""
                INSERT INTO feedback (customer_id, complaint_id, rating, service_aspect, comments)
                VALUES (?, ?, ?, ?, ?);
            """, (customer_id, complaint_id, rating, aspect, comments))
            conn.commit()
            conn.close()
            flash('Customer feedback recorded successfully. Thank you!', 'success')
            return redirect(url_for('feedback'))

    cursor.execute("SELECT id, name, customer_code, company_name FROM customers ORDER BY name ASC;")
    customers = cursor.fetchall()

    cursor.execute("SELECT id, ticket_number, title FROM complaints ORDER BY created_at DESC LIMIT 20;")
    tickets = cursor.fetchall()

    selected_cust = request.args.get('customer_id')
    selected_customer_id = int(selected_cust) if selected_cust and selected_cust.isdigit() else None

    conn.close()

    return render_template(
        'add_feedback.html',
        customers=customers,
        tickets=tickets,
        selected_customer_id=selected_customer_id,
        active_page='feedback'
    )


# ==============================================================================
# Application Startup Entrypoint
# ==============================================================================

if __name__ == '__main__':
    # Initialize SQLite database automatically on startup
    init_db()

    print("=" * 65)
    print("  CUSTOMER RELATIONSHIP MANAGEMENT (CRM) SYSTEM")
    print("  Academic Project Demonstration Server")
    print("  Application URL: http://127.0.0.1:5000")
    print("  Default Admin Login: admin / admin123")
    print("  Manager Login:       manager / manager123")
    print("  Employee Login:      employee / employee123")
    print("  Support Login:       support / support123")
    print("=" * 65)

    app.run(host='127.0.0.1', port=5000, debug=True)
