"""
CRM System Database Layer
SQLite3-based persistent storage with automatic table creation,
foreign key constraints, indexing, and realistic sample data seeding.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crm.db')


def get_db():
    """Returns a SQLite connection with Row factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initializes all database tables, constraints, indexes, and initial data."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin', 'manager', 'employee', 'support')),
        full_name TEXT NOT NULL,
        phone TEXT,
        department TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    );
    """)

    # 2. Customers Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        company_name TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        country TEXT DEFAULT 'India',
        postal_code TEXT,
        status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive', 'Lead')),
        notes TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 3. Employees Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        employee_code TEXT UNIQUE NOT NULL,
        designation TEXT NOT NULL,
        department TEXT NOT NULL,
        joining_date DATE NOT NULL,
        salary REAL DEFAULT 0.0,
        status TEXT DEFAULT 'Active' CHECK(status IN ('Active', 'Inactive')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 4. Sales Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sales_code TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        employee_id INTEGER,
        product_service_name TEXT NOT NULL,
        category TEXT,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'Completed' CHECK(status IN ('Pending', 'Processing', 'Completed', 'Cancelled')),
        payment_method TEXT DEFAULT 'Bank Transfer',
        sale_date DATE DEFAULT (DATE('now')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 5. Quotations Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quotation_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        created_by INTEGER,
        subject TEXT NOT NULL,
        subtotal REAL NOT NULL DEFAULT 0.0,
        tax_rate REAL DEFAULT 18.0,
        tax_amount REAL DEFAULT 0.0,
        grand_total REAL NOT NULL DEFAULT 0.0,
        valid_until DATE,
        status TEXT DEFAULT 'Draft' CHECK(status IN ('Draft', 'Sent', 'Accepted', 'Rejected')),
        terms_conditions TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 6. Quotation Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotation_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quotation_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        description TEXT,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        total REAL NOT NULL,
        FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE CASCADE
    );
    """)

    # 7. Orders Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        quotation_id INTEGER,
        assigned_to INTEGER,
        order_date DATE DEFAULT (DATE('now')),
        expected_completion_date DATE,
        total_amount REAL NOT NULL DEFAULT 0.0,
        status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Processing', 'Completed', 'Cancelled')),
        shipping_address TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (quotation_id) REFERENCES quotations(id) ON DELETE SET NULL,
        FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 8. Order Items Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        unit_price REAL NOT NULL,
        total REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    """)

    # 9. Complaints Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_number TEXT UNIQUE NOT NULL,
        customer_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Technical Support', 'Billing Issue', 'Product Quality', 'Delivery Delay', 'General Inquiry', 'Service Complaint')),
        priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
        status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open', 'In Progress', 'Resolved', 'Closed')),
        assigned_to INTEGER,
        created_by INTEGER,
        resolution_notes TEXT,
        resolved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 10. Complaint Responses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS complaint_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        complaint_id INTEGER NOT NULL,
        user_id INTEGER,
        response_text TEXT NOT NULL,
        status_update TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 11. Follow-ups Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS follow_ups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        user_id INTEGER,
        title TEXT NOT NULL,
        description TEXT,
        follow_up_date DATE NOT NULL,
        follow_up_time TEXT DEFAULT '10:00 AM',
        status TEXT DEFAULT 'Pending' CHECK(status IN ('Pending', 'Completed', 'Overdue')),
        outcome_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );
    """)

    # 12. Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        category TEXT DEFAULT 'general' CHECK(category IN ('follow_up', 'ticket', 'order', 'quotation', 'general', 'system')),
        link TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 13. Feedback Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        complaint_id INTEGER,
        rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
        service_aspect TEXT DEFAULT 'Overall Experience',
        comments TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
        FOREIGN KEY (complaint_id) REFERENCES complaints(id) ON DELETE SET NULL
    );
    """)

    # Create Performance Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_code ON customers(customer_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sales_employee ON sales(employee_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotations_number ON quotations(quotation_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_number ON orders(order_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_ticket ON complaints(ticket_number);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_followups_date ON follow_ups(follow_up_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read);")

    conn.commit()

    # Ensure default admin account exists
    ensure_admin_account(conn)

    # Seed sample demonstration data if database is fresh
    seed_sample_data(conn)

    conn.close()


def ensure_admin_account(conn):
    """Ensures the mandatory default administrator account exists."""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = 'admin';")
    admin = cursor.fetchone()
    if not admin:
        hashed_pw = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, full_name, phone, department, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1);
        """, (
            'admin',
            'admin@crmsystem.com',
            hashed_pw,
            'admin',
            'System Administrator',
            '+91 98765 43210',
            'Executive Management'
        ))
        conn.commit()


def seed_sample_data(conn):
    """Inserts realistic sample demonstration data if database does not have customers yet."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM customers;")
    count = cursor.fetchone()['cnt']
    if count > 0:
        # Already seeded
        return

    # 1. Create Sample Users / Employees
    users_data = [
        ('manager', 'sarah.manager@crmsystem.com', 'manager123', 'manager', 'Sarah Jenkins', '+91 98765 00001', 'Sales Management', 'EMP-101', 'Senior Sales Manager', '2023-01-15', 85000.0),
        ('employee', 'david.sales@crmsystem.com', 'employee123', 'employee', 'David Miller', '+91 98765 00002', 'Direct Sales', 'EMP-102', 'Sales Executive', '2023-06-01', 52000.0),
        ('support', 'emily.support@crmsystem.com', 'support123', 'support', 'Emily Watson', '+91 98765 00003', 'Customer Support', 'EMP-103', 'Lead Support Specialist', '2023-03-20', 48000.0),
        ('rajesh.sales', 'rajesh.kumar@crmsystem.com', 'rajesh123', 'employee', 'Rajesh Kumar', '+91 98765 00004', 'Enterprise Sales', 'EMP-104', 'Account Executive', '2024-02-10', 55000.0)
    ]

    user_ids = {}
    # Fetch admin id
    cursor.execute("SELECT id FROM users WHERE username = 'admin';")
    admin_row = cursor.fetchone()
    admin_id = admin_row['id'] if admin_row else 1
    user_ids['admin'] = admin_id

    for uname, email, pw, role, fname, phone, dept, emp_code, desig, join_date, sal in users_data:
        cursor.execute("SELECT id FROM users WHERE username = ?;", (uname,))
        existing = cursor.fetchone()
        if not existing:
            hpw = generate_password_hash(pw)
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, role, full_name, phone, department, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1);
            """, (uname, email, hpw, role, fname, phone, dept))
            u_id = cursor.lastrowid
            cursor.execute("""
                INSERT INTO employees (user_id, employee_code, designation, department, joining_date, salary, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Active');
            """, (u_id, emp_code, desig, dept, join_date, sal))
            user_ids[uname] = u_id
        else:
            user_ids[uname] = existing['id']

    manager_id = user_ids.get('manager', admin_id)
    employee_id = user_ids.get('employee', admin_id)
    support_id = user_ids.get('support', admin_id)
    rajesh_id = user_ids.get('rajesh.sales', admin_id)

    # Also register admin in employees table if not present
    cursor.execute("SELECT id FROM employees WHERE user_id = ?;", (admin_id,))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO employees (user_id, employee_code, designation, department, joining_date, salary, status)
            VALUES (?, 'EMP-100', 'CRM Chief Administrator', 'Executive Management', '2022-01-01', 120000.0, 'Active');
        """, (admin_id,))

    # 2. Seed 8 Sample Customers
    customers_data = [
        ('CUST-1001', 'Aarav Sharma', 'aarav.sharma@apextech.com', '+91 98234 56789', 'Apex Tech Solutions Pvt Ltd', '42, Cyber Hub, DLF Phase 2', 'Gurugram', 'Haryana', '122002', 'Active', 'Strategic enterprise client for Cloud CRM.'),
        ('CUST-1002', 'Priya Sundaram', 'priya.sundaram@medicare.org', '+91 98451 23456', 'MediCare Diagnostics Group', '15, Richmond Road', 'Bengaluru', 'Karnataka', '560025', 'Active', 'Healthcare partner looking for patient portal integration.'),
        ('CUST-1003', 'Vikramaditya Roy', 'vikram.roy@finserve.in', '+91 98112 34567', 'Roy & Partners Financial Services', '88, Park Street, Camac Area', 'Kolkata', 'West Bengal', '700016', 'Active', 'Annual maintenance and software license contract.'),
        ('CUST-1004', 'Ananya Patel', 'ananya.p@shoppera.com', '+91 99099 87654', 'Shoppera Retail Chains Ltd', '302, CG Road, Navrangpura', 'Ahmedabad', 'Gujarat', '380009', 'Active', 'Omnichannel retail customer with multi-store license.'),
        ('CUST-1005', 'Rohan Deshmukh', 'rohan.d@logixware.com', '+91 97654 32109', 'LogixWare Freight & Logistics', '7B, MIDC Industrial Area, Andheri East', 'Mumbai', 'Maharashtra', '400093', 'Active', 'Supply chain automation and customer notification system.'),
        ('CUST-1006', 'Meera Nambiar', 'meera.nambiar@greenvalley.edu', '+91 94471 23890', 'Green Valley International Academy', 'Sector 14, Ring Road', 'Kochi', 'Kerala', '682024', 'Lead', 'Inquiring about student relationship CRM modules.'),
        ('CUST-1007', 'Karthik Subramaniam', 'karthik.sub@zenithbuild.in', '+91 98840 12345', 'Zenith Infrastructure & Realty', '55, Anna Salai, Teynampet', 'Chennai', 'Tamil Nadu', '600018', 'Active', 'Real estate CRM client for lead tracking & booking.'),
        ('CUST-1008', 'Sneha Kapoor', 'sneha.kapoor@novabrand.com', '+91 99100 88776', 'NovaBrand Marketing & Media', '104, Barakhamba Road, Connaught Place', 'New Delhi', 'Delhi', '110001', 'Inactive', 'Renewal pending review for Q3.')
    ]

    customer_ids = []
    for code, name, email, phone, comp, addr, city, state, postal, status, notes in customers_data:
        cursor.execute("""
            INSERT INTO customers (customer_code, name, email, phone, company_name, address, city, state, postal_code, status, notes, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (code, name, email, phone, comp, addr, city, state, postal, status, notes, employee_id))
        customer_ids.append(cursor.lastrowid)

    # 3. Seed 10 Sample Sales Records
    sales_data = [
        ('SALE-1001', customer_ids[0], employee_id, 'Cloud CRM Enterprise Annual License', 'Software License', 1, 150000.0, 150000.0, 'Completed', 'Bank Transfer', '2026-09-10', 'Full deployment completed with 50 user seats.'),
        ('SALE-1002', customer_ids[1], employee_id, 'Healthcare Portal Integration Module', 'Custom Development', 1, 85000.0, 85000.0, 'Completed', 'Credit Card', '2026-09-18', 'Connected with internal hospital management DB.'),
        ('SALE-1003', customer_ids[2], rajesh_id, 'Financial Compliance & Security Suite', 'Software License', 1, 120000.0, 120000.0, 'Completed', 'Bank Transfer', '2026-09-25', 'Includes dual-factor authentication and audit logging.'),
        ('SALE-1004', customer_ids[3], employee_id, 'POS Multi-Store Sync Connector', 'Add-on Module', 4, 18000.0, 72000.0, 'Completed', 'UPI / Online', '2026-10-02', 'Sync connector licenses for 4 retail branches.'),
        ('SALE-1005', customer_ids[4], rajesh_id, 'Fleet Tracking & Dispatch CRM Addon', 'Software License', 1, 95000.0, 95000.0, 'Completed', 'Cheque', '2026-10-08', 'Includes GPS mapping and real-time alerts.'),
        ('SALE-1006', customer_ids[6], employee_id, 'Real Estate Lead Management Suite', 'Software License', 1, 110000.0, 110000.0, 'Completed', 'Bank Transfer', '2026-10-15', 'Full pipeline automation for property sales.'),
        ('SALE-1007', customer_ids[0], rajesh_id, 'Advanced Business Analytics Dashboard', 'Add-on Module', 1, 45000.0, 45000.0, 'Completed', 'Bank Transfer', '2026-10-20', 'Custom reporting module with live KPIs.'),
        ('SALE-1008', customer_ids[1], employee_id, 'Dedicated 24/7 SLA Premium Support', 'Service Package', 1, 35000.0, 35000.0, 'Completed', 'UPI / Online', '2026-10-24', 'Annual support retainer package.'),
        ('SALE-1009', customer_ids[4], employee_id, 'Mobile CRM App Licenses (15 seats)', 'Software License', 15, 2500.0, 37500.0, 'Processing', 'Bank Transfer', '2026-10-28', 'Deployment ongoing for field agents.'),
        ('SALE-1010', customer_ids[2], manager_id, 'Dedicated Cloud Backup & Archiving', 'Cloud Service', 1, 28000.0, 28000.0, 'Pending', 'Bank Transfer', '2026-11-01', 'Awaiting final sign-off from IT director.')
    ]

    for scode, cid, eid, prod, cat, qty, price, total, status, pay_m, sdate, notes in sales_data:
        cursor.execute("""
            INSERT INTO sales (sales_code, customer_id, employee_id, product_service_name, category, quantity, unit_price, total_amount, status, payment_method, sale_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (scode, cid, eid, prod, cat, qty, price, total, status, pay_m, sdate, notes))

    # 4. Seed 5 Sample Quotations (with items)
    quotations_data = [
        ('QT-2026-001', customer_ids[0], employee_id, 'Annual Enterprise Support & Cloud Migration', 180000.0, 18.0, 32400.0, 212400.0, '2026-12-01', 'Accepted', 'Net 30 payment terms upon installation.', [
            ('Enterprise Cloud Migration', 'Data extraction, ETL pipeline and validation', 1, 100000.0, 100000.0),
            ('24/7 Priority Support Retainer', 'Dedicated support engineer with 1hr SLA', 1, 80000.0, 80000.0)
        ]),
        ('QT-2026-002', customer_ids[5], rajesh_id, 'Campus Student Portal CRM Package', 95000.0, 18.0, 17100.0, 112100.0, '2026-11-20', 'Sent', '50% advance on approval, remaining upon delivery.', [
            ('Student Inquiry & Admissions CRM', 'Multi-channel form capture and student journey', 1, 65000.0, 65000.0),
            ('SMS & Email Gateway Integration', 'Automated fee and admission notifications', 1, 30000.0, 30000.0)
        ]),
        ('QT-2026-003', customer_ids[3], employee_id, 'Omnichannel WhatsApp Commerce Integration', 50000.0, 18.0, 9000.0, 59000.0, '2026-11-25', 'Draft', 'Includes 1 year Meta API integration connector.', [
            ('WhatsApp Business API Connector', 'Catalog sharing and order tracking via WhatsApp', 1, 35000.0, 35000.0),
            ('Staff Training & Documentation', 'Interactive training for 10 customer service agents', 1, 15000.0, 15000.0)
        ]),
        ('QT-2026-004', customer_ids[6], manager_id, 'Property Sales Pipeline & Document Vault', 130000.0, 18.0, 23400.0, 153400.0, '2026-12-15', 'Accepted', 'Includes AWS S3 document encryption and digital signing.', [
            ('Lead Pipeline & Property Booking Engine', 'Workflow for unit allotment and customer KYC', 1, 90000.0, 90000.0),
            ('Encrypted Document Storage Vault', 'Secure KYC and legal deed repository', 1, 40000.0, 40000.0)
        ]),
        ('QT-2026-005', customer_ids[7], rajesh_id, 'Annual Marketing Automation Upgrade', 75000.0, 18.0, 13500.0, 88500.0, '2026-10-30', 'Rejected', 'Rejected due to client internal budget freeze for Q4.', [
            ('Marketing Campaign Builder', 'Drip campaign manager with A/B testing', 1, 55000.0, 55000.0),
            ('Social Media Lead Webhook Integration', 'Direct leads ingestion from Instagram & LinkedIn', 1, 20000.0, 20000.0)
        ])
    ]

    for qnum, cid, cb, subj, subtotal, trate, tamt, gtotal, vuntil, status, terms, items in quotations_data:
        cursor.execute("""
            INSERT INTO quotations (quotation_number, customer_id, created_by, subject, subtotal, tax_rate, tax_amount, grand_total, valid_until, status, terms_conditions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (qnum, cid, cb, subj, subtotal, trate, tamt, gtotal, vuntil, status, terms))
        qid = cursor.lastrowid
        for iname, idesc, iqty, iuprice, itotal in items:
            cursor.execute("""
                INSERT INTO quotation_items (quotation_id, item_name, description, quantity, unit_price, total)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (qid, iname, idesc, iqty, iuprice, itotal))

    # 5. Seed 5 Sample Orders (with items)
    orders_data = [
        ('ORD-2026-001', customer_ids[0], 1, employee_id, '2026-10-12', '2026-11-15', 212400.0, 'Processing', 'Apex Tech Cyber Hub, Floor 4, Gurugram', 'Priority enterprise delivery with SLA check.', [
            ('Cloud Server Setup & Migration Suite', 1, 100000.0, 100000.0),
            ('Annual 24/7 Support Contract', 1, 80000.0, 80000.0),
            ('Tax (GST 18%)', 1, 32400.0, 32400.0)
        ]),
        ('ORD-2026-002', customer_ids[1], None, employee_id, '2026-10-20', '2026-11-10', 100300.0, 'Completed', 'MediCare Diagnostics, 15 Richmond Road, Bengaluru', 'All tests completed and verified by IT head.', [
            ('Laboratory Report Integration Plugin', 1, 85000.0, 85000.0),
            ('GST Tax Component', 1, 15300.0, 15300.0)
        ]),
        ('ORD-2026-003', customer_ids[3], None, rajesh_id, '2026-10-28', '2026-11-20', 84960.0, 'Processing', 'Shoppera Central Warehouse, Navrangpura, Ahmedabad', 'Installation team scheduled on site.', [
            ('Store POS Sync Adapters', 4, 18000.0, 72000.0),
            ('GST 18%', 1, 12960.0, 12960.0)
        ]),
        ('ORD-2026-004', customer_ids[4], None, manager_id, '2026-11-01', '2026-11-25', 112100.0, 'Pending', 'LogixWare MIDC Compound, Andheri East, Mumbai', 'Pending final security clearance certificate.', [
            ('Fleet Dispatch Optimization System', 1, 95000.0, 95000.0),
            ('GST 18%', 1, 17100.0, 17100.0)
        ]),
        ('ORD-2026-005', customer_ids[6], 4, employee_id, '2026-10-22', '2026-11-05', 153400.0, 'Completed', 'Zenith Realty Tower, Anna Salai, Chennai', 'Sign-off received from Vice President of Sales.', [
            ('Property Booking Engine', 1, 90000.0, 90000.0),
            ('Digital Vault Security Module', 1, 40000.0, 40000.0),
            ('GST 18%', 1, 23400.0, 23400.0)
        ])
    ]

    for onum, cid, qid, at, odate, cdate, tot, stat, ship, notes, oitems in orders_data:
        cursor.execute("""
            INSERT INTO orders (order_number, customer_id, quotation_id, assigned_to, order_date, expected_completion_date, total_amount, status, shipping_address, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (onum, cid, qid, at, odate, cdate, tot, stat, ship, notes))
        oid = cursor.lastrowid
        for pname, qty, price, itot in oitems:
            cursor.execute("""
                INSERT INTO order_items (order_id, product_name, quantity, unit_price, total)
                VALUES (?, ?, ?, ?, ?);
            """, (oid, pname, qty, price, itot))

    # 6. Seed 5 Sample Complaints with Responses
    complaints_data = [
        ('TICK-1001', customer_ids[0], 'API Timeout during high volume batch sync', 'Our inventory synchronization script experienced HTTP 504 timeouts at 3:00 PM today during scheduled sync.', 'Technical Support', 'High', 'In Progress', support_id, employee_id, [
            (support_id, 'Investigating gateway timeout logs. Scaled up worker connection pool by 50%.', 'In Progress'),
            (support_id, 'Patch applied to staging. Requesting client IT team to test with sample 5,000 SKU batch.', 'In Progress')
        ]),
        ('TICK-1002', customer_ids[1], 'Discrepancy in monthly maintenance tax invoice', 'The invoice generated on Oct 24 displays 18% GST calculation on exempt diagnostic connector services.', 'Billing Issue', 'Medium', 'Resolved', support_id, employee_id, [
            (support_id, 'Reviewed invoice #INV-8891 with finance department. Credit note issued for difference.', 'Resolved')
        ]),
        ('TICK-1003', customer_ids[3], 'Mobile CRM app crashes on Android 14 devices', 'Two field executives reported the app closes immediately after submitting an offline customer order.', 'Product Quality', 'High', 'Open', support_id, rajesh_id, []),
        ('TICK-1004', customer_ids[4], 'Delayed dispatch of hardware security tokens', 'Security dongles for logistics coordinators were promised within 3 business days; today is day 5.', 'Delivery Delay', 'Low', 'Resolved', support_id, manager_id, [
            (support_id, 'BlueDart tracking number BD782910 shared with client. Delivered safely on Nov 1.', 'Resolved')
        ]),
        ('TICK-1005', customer_ids[2], 'Request for custom GST e-way bill export template', 'Need an additional export format compatible with government NIC e-way bill Excel schema.', 'General Inquiry', 'Medium', 'In Progress', support_id, manager_id, [
            (support_id, 'Requirement forwarded to dev team. Template prototype ready for preview.', 'In Progress')
        ])
    ]

    for tnum, cid, title, desc, cat, prio, stat, assigned, cby, resps in complaints_data:
        res_note = 'Issue investigated and resolved satisfactorily.' if stat == 'Resolved' else None
        res_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if stat == 'Resolved' else None
        cursor.execute("""
            INSERT INTO complaints (ticket_number, customer_id, title, description, category, priority, status, assigned_to, created_by, resolution_notes, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (tnum, cid, title, desc, cat, prio, stat, assigned, cby, res_note, res_at))
        cid_ticket = cursor.lastrowid
        for resp_uid, rtext, s_upd in resps:
            cursor.execute("""
                INSERT INTO complaint_responses (complaint_id, user_id, response_text, status_update)
                VALUES (?, ?, ?, ?);
            """, (cid_ticket, resp_uid, rtext, s_upd))

    # 7. Seed 5 Follow-up Reminders
    followups_data = [
        (customer_ids[0], employee_id, 'Quarterly SLA review meeting with Apex Tech CTO', 'Present quarterly performance statistics and discuss upcoming cloud database migration.', '2026-11-05', '11:00 AM', 'Pending', None),
        (customer_ids[1], employee_id, 'Check satisfaction on newly deployed diagnostic module', 'Follow up with Dr. Priya regarding report download speeds and physician feedback.', '2026-10-25', '03:30 PM', 'Completed', 'Client confirmed reports generate in under 2 seconds. Extremely satisfied.'),
        (customer_ids[5], rajesh_id, 'Demo session for Green Valley Academy Academic Council', 'Present multi-campus student admission pipeline CRM to management board.', '2026-11-08', '02:00 PM', 'Pending', None),
        (customer_ids[3], employee_id, 'Review Android app patch with Shoppera store managers', 'Ensure new build fixes crash issue and verify offline order syncing.', '2026-10-31', '04:00 PM', 'Overdue', 'Rescheduled due to client Diwali sales rush.'),
        (customer_ids[6], manager_id, 'Contract extension meeting for Zenith Tower Phase 2', 'Review commercial terms for adding 25 new real estate agent licenses.', '2026-11-12', '10:30 AM', 'Pending', None)
    ]

    for cid, uid, title, desc, fdate, ftime, stat, onotes in followups_data:
        cursor.execute("""
            INSERT INTO follow_ups (customer_id, user_id, title, description, follow_up_date, follow_up_time, status, outcome_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (cid, uid, title, desc, fdate, ftime, stat, onotes))

    # 8. Seed 5 Customer Feedback Records
    feedback_data = [
        (customer_ids[0], 1, 5, 'Overall Experience', 'Outstanding platform and great account management. Our team sales productivity rose by 35% within 3 months.'),
        (customer_ids[1], 2, 5, 'Support Speed', 'Emily and the support desk resolved our billing tax discrepancy swiftly and smoothly.'),
        (customer_ids[2], None, 4, 'Product Quality', 'The financial audit logs are robust. Would love to see more one-click CSV export options for audits.'),
        (customer_ids[4], 4, 4, 'Sales Process', 'Rajesh guided us seamlessly through quotation and deployment. Hardware token arrival was slightly delayed but resolved.'),
        (customer_ids[6], None, 5, 'Overall Experience', 'Superb real estate CRM pipeline! Tracking prospective property buyers has never been this organized.')
    ]

    for cid, comp_id, rating, aspect, comments in feedback_data:
        cursor.execute("""
            INSERT INTO feedback (customer_id, complaint_id, rating, service_aspect, comments)
            VALUES (?, ?, ?, ?, ?);
        """, (cid, comp_id, rating, aspect, comments))

    # 9. Seed Initial Notifications
    notifications_data = [
        (employee_id, 'Upcoming Follow-up Today', 'Meeting scheduled with Apex Tech CTO for Quarterly SLA Review.', 'follow_up', '/follow-ups', 0),
        (support_id, 'New High Priority Ticket #TICK-1003', 'Shoppera Retail reported mobile app crash on Android 14.', 'ticket', '/complaints', 0),
        (manager_id, 'Pending Order Needs Approval #ORD-2026-004', 'LogixWare order total of Rs 1,12,100 awaiting final sign-off.', 'order', '/orders', 0),
        (rajesh_id, 'Quotation Sent #QT-2026-002', 'Quotation sent to Green Valley International Academy.', 'quotation', '/quotations', 1),
        (admin_id, 'System Alert: Overdue Follow-up', 'Shoppera Retail Android patch review is currently overdue.', 'system', '/follow-ups', 0)
    ]

    for uid, title, msg, cat, link, is_read in notifications_data:
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, category, link, is_read)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (uid, title, msg, cat, link, is_read))

    conn.commit()


if __name__ == '__main__':
    print("Initializing CRM Database...")
    init_db()
    print("CRM Database initialized successfully.")
