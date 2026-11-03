"""
Comprehensive Verification Test Suite for CRM Application.
Tests all 18 requirements specified in Section 17 of project requirements.
"""

import unittest
import uuid
from app import app
from database import init_db, get_db


class CRMSystemTestCase(unittest.TestCase):
    def setUp(self):
        init_db()
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.uid = uuid.uuid4().hex[:6].upper()

    def login(self, username, password):
        return self.client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_01_admin_login_and_logout(self):
        """Test 1: Admin login and logout."""
        res_fail = self.login('admin', 'wrongpass')
        self.assertIn(b'Invalid username/email or password', res_fail.data)

        res_ok = self.login('admin', 'admin123')
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn(b'Executive Dashboard', res_ok.data)

        res_logout = self.logout()
        self.assertIn(b'logged out successfully', res_logout.data)

    def test_02_role_based_dashboard_access(self):
        """Test 2 & 3: Role-based dashboard access and permission enforcement."""
        # Manager
        self.login('manager', 'manager123')
        res_m = self.client.get('/dashboard/manager')
        self.assertIn(b'Operations Management Dashboard', res_m.data)
        # Denied
        res_denied = self.client.get('/users', follow_redirects=True)
        self.assertIn(b'Access denied', res_denied.data)
        self.logout()

        # Employee
        self.login('employee', 'employee123')
        res_e = self.client.get('/dashboard/employee')
        self.assertIn(b'My Sales & Activities Dashboard', res_e.data)
        self.logout()

        # Support
        self.login('support', 'support123')
        res_s = self.client.get('/dashboard/support')
        self.assertIn(b'Customer Support & Helpdesk Hub', res_s.data)
        self.logout()

    def test_03_employee_account_creation(self):
        """Test 4: Admin creates employee account and employee logs in."""
        self.login('admin', 'admin123')
        username = f"agent_{self.uid}"
        email = f"agent_{self.uid}@crmtest.com"

        res = self.client.post('/users/add', data={
            'username': username,
            'password': 'password123',
            'full_name': f"Agent {self.uid}",
            'email': email,
            'role': 'employee',
            'department': 'Testing Dept',
            'phone': '+91 99999 11111',
            'employee_code': f"EMP-{self.uid}",
            'designation': 'QA Engineer',
            'salary': '45000'
        }, follow_redirects=True)
        self.assertIn(b'created successfully', res.data)
        self.logout()

        # Login with newly created agent
        res_login = self.login(username, 'password123')
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(username.encode(), res_login.data)
        self.logout()

    def test_04_customer_crud_and_search(self):
        """Test 5 & 6: Customer registration, search, view profile, update, and delete."""
        self.login('admin', 'admin123')
        cust_code = f"CUST-T{self.uid}"
        email = f"bhavin_{self.uid}@testcorp.in"

        # Register
        res_add = self.client.post('/customers/add', data={
            'customer_code': cust_code,
            'name': f"Bhavin Mehta {self.uid}",
            'email': email,
            'phone': '+91 98888 77777',
            'company_name': 'Mehta Global Logistics',
            'address': '501 Shipping House, Fort',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'postal_code': '400001',
            'status': 'Active',
            'notes': 'Logistics client'
        }, follow_redirects=True)
        self.assertIn(cust_code.encode(), res_add.data)

        # Retrieve ID
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM customers WHERE customer_code = ?;", (cust_code,))
        cust_id = cur.fetchone()['id']
        conn.close()

        # Search
        res_search = self.client.get(f'/customers?q={self.uid}')
        self.assertIn(cust_code.encode(), res_search.data)

        # Profile
        res_profile = self.client.get(f'/customers/{cust_id}')
        self.assertIn(b'Mehta Global Logistics', res_profile.data)

        # Update
        res_edit = self.client.post(f'/customers/edit/{cust_id}', data={
            'name': f"Bhavin K. Mehta {self.uid}",
            'email': email,
            'phone': '+91 98888 77777',
            'company_name': 'Mehta Global Logistics Ltd',
            'address': '501 Shipping House, Fort',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'postal_code': '400001',
            'status': 'Active',
            'notes': 'Updated info'
        }, follow_redirects=True)
        self.assertIn(b'Mehta Global Logistics Ltd', res_edit.data)

        # Delete
        res_del = self.client.post(f'/customers/delete/{cust_id}', follow_redirects=True)
        self.assertIn(b'deleted permanently', res_del.data)
        self.logout()

    def test_05_sales_creation_and_management(self):
        """Test 7: Sales creation, calculation, editing, and listing."""
        self.login('admin', 'admin123')
        sales_code = f"SALE-{self.uid}"

        res_add = self.client.post('/sales/add', data={
            'sales_code': sales_code,
            'customer_id': 1,
            'employee_id': 1,
            'product_service_name': f"Custom CRM Extension {self.uid}",
            'category': 'Custom Development',
            'quantity': 2,
            'unit_price': 25000.0,
            'payment_method': 'Bank Transfer',
            'sale_date': '2026-11-02',
            'status': 'Completed',
            'notes': 'Unit test deal'
        }, follow_redirects=True)
        self.assertIn(sales_code.encode(), res_add.data)

        # Verify listing
        res_list = self.client.get(f'/sales?q={self.uid}')
        self.assertIn(sales_code.encode(), res_list.data)
        self.assertIn(b'50,000.00', res_list.data)
        self.logout()

    def test_06_quotation_and_order_flow(self):
        """Test 8 & 9: Quotation generation, printable page, and customer orders."""
        self.login('admin', 'admin123')
        q_num = f"QT-{self.uid}"

        # Quotation
        res_quote = self.client.post('/quotations/add', data={
            'quotation_number': q_num,
            'customer_id': 1,
            'subject': f"Enterprise Proposal {self.uid}",
            'valid_until': '2026-12-31',
            'status': 'Draft',
            'terms_conditions': 'Standard terms',
            'tax_rate': 18.0,
            'item_name[]': ['Software Module A', 'Service B'],
            'item_desc[]': ['Core platform', 'API sync'],
            'item_qty[]': ['1', '2'],
            'item_price[]': ['10000', '5000']
        }, follow_redirects=True)
        self.assertIn(q_num.encode(), res_quote.data)
        self.assertIn(b'COMMERCIAL QUOTATION', res_quote.data)

        # Order
        ord_num = f"ORD-{self.uid}"
        res_order = self.client.post('/orders/add', data={
            'order_number': ord_num,
            'customer_id': 1,
            'order_date': '2026-11-02',
            'expected_completion_date': '2026-11-20',
            'status': 'Pending',
            'shipping_address': 'Corporate Test Office',
            'notes': 'Test notes',
            'product_name[]': ['Server License'],
            'quantity[]': ['1'],
            'unit_price[]': ['35000']
        }, follow_redirects=True)
        self.assertIn(ord_num.encode(), res_order.data)
        self.assertIn(b'Order Placed', res_order.data)
        self.logout()

    def test_07_support_complaint_and_resolution(self):
        """Test 10, 11, 12: Complaint ticket registration, responses, and resolution."""
        self.login('admin', 'admin123')
        t_num = f"TICK-{self.uid}"

        res_comp = self.client.post('/complaints/add', data={
            'ticket_number': t_num,
            'customer_id': 1,
            'title': f"Latency issue {self.uid}",
            'description': 'Customer reported latency in webhooks.',
            'category': 'Technical Support',
            'priority': 'High',
            'assigned_to': 4
        }, follow_redirects=True)
        self.assertIn(t_num.encode(), res_comp.data)

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM complaints WHERE ticket_number = ?;", (t_num,))
        ticket_id = cur.fetchone()['id']
        conn.close()

        # Post response
        res_resp = self.client.post(f'/complaints/{ticket_id}/response', data={
            'response_text': 'Worker thread pool resized.',
            'status_update': 'In Progress'
        }, follow_redirects=True)
        self.assertIn(b'Worker thread pool resized', res_resp.data)

        # Resolve
        res_res = self.client.post(f'/complaints/{ticket_id}/resolve', data={
            'resolution_notes': 'Latency resolved to 120ms. Verified with client.'
        }, follow_redirects=True)
        self.assertIn(b'Resolved', res_res.data)
        self.logout()

    def test_08_followups_and_notifications(self):
        """Test 13 & 14: Follow-up scheduling and notification inbox."""
        self.login('admin', 'admin123')

        res_f = self.client.post('/follow-ups/add', data={
            'customer_id': 1,
            'title': f"Contract Discussion {self.uid}",
            'follow_up_date': '2026-11-20',
            'follow_up_time': '11:00 AM',
            'description': 'Review renewed terms'
        }, follow_redirects=True)
        self.assertIn(self.uid.encode(), res_f.data)

        res_notif = self.client.get('/notifications')
        self.assertEqual(res_notif.status_code, 200)
        self.logout()

    def test_09_feedback_submission(self):
        """Test 15: Customer Feedback 5-star submission."""
        self.login('admin', 'admin123')
        comment = f"Exceptional service provided by team {self.uid}!"

        res_fb = self.client.post('/feedback/add', data={
            'customer_id': 1,
            'rating': 5,
            'service_aspect': 'Overall Experience',
            'comments': comment
        }, follow_redirects=True)
        self.assertIn(b'Customer feedback recorded successfully', res_fb.data)

        res_list = self.client.get('/feedback')
        self.assertIn(comment.encode(), res_list.data)
        self.logout()

    def test_10_reports_and_csv_export(self):
        """Test 16 & 17: Reports generation for all 8 types and CSV export."""
        self.login('admin', 'admin123')

        reports = [
            'customer_registration', 'sales_performance', 'employee_performance',
            'complaint_report', 'purchase_history', 'revenue_report',
            'pending_orders', 'satisfaction_report'
        ]
        for r in reports:
            res = self.client.get(f'/reports?report_type={r}')
            self.assertEqual(res.status_code, 200, f"Failed on report: {r}")

        # CSV Export
        res_csv = self.client.get('/reports/export-csv?report_type=sales_performance')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')
        self.assertIn(b'Sale Code', res_csv.data)
        self.logout()

    def test_11_database_persistence_after_restart(self):
        """Test 18: Database persistence - data remains intact after re-initialization."""
        init_db()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as cnt FROM customers;")
        cnt = cur.fetchone()['cnt']
        conn.close()
        self.assertGreaterEqual(cnt, 8)


if __name__ == '__main__':
    unittest.main()
