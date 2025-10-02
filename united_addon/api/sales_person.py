import frappe
from united_addon.api.utils import gen_response
from datetime import datetime, timedelta
from frappe.utils import flt



#User Dashboard
@frappe.whitelist()
def get_dashboard_data():
    try:
        # Get current user
        current_user = frappe.session.user
        
        # Step 1: Check active user and link to employee
        user_doc = frappe.get_doc("User", current_user)
        if not user_doc.enabled:
            return gen_response(400, "User is not active", {})
        
        # Fetch employee using sql to avoid as_dict issue
        employee_data = frappe.db.sql("""
            SELECT name, employee_name FROM `tabEmployee` 
            WHERE user_id = %s LIMIT 1
        """, (current_user,), as_dict=1)
        if not employee_data:
            return gen_response(400, "No active employee linked to user", {})
        
        employee = employee_data[0]
        
        # Step 2: Get Sales Partner linked to employee (assume Sales Partner has 'employee' field)
        sales_partner_data = frappe.db.sql("""
            SELECT name FROM `tabSales Partner` 
            WHERE custom_employee = %s LIMIT 1
        """, (employee.name,), as_dict=1)
        if not sales_partner_data:
            return gen_response(400, "No Sales Partner linked to employee", {})
        
        sales_partner = sales_partner_data[0].name
        
        sales_partner_doc = frappe.get_doc("Sales Partner", sales_partner)
        custom_earned_points = sales_partner_doc.custom_earned_points or 0
        
        # Step 3 & 4: Fetch last 10 ledger transactions for Sales Partner
        # Based on doctype structure: sales_partner, points (positive for credit, negative for debit?), date, sales_invoice (as narration)
        ledgers_data = frappe.db.sql("""
            SELECT name, date, points, sales_invoice FROM `tabSales Partner Points Ledgers`
            WHERE sales_partner = %s 
            ORDER BY date DESC 
            LIMIT 10
        """, (sales_partner,), as_dict=1)
        
        # Format ledgers: points as is (+ for credit, - for debit)
        formatted_ledgers = []
        for ledger in ledgers_data:
            name = ledger.name
            amount = ledger.points or 0
            narration = ledger.sales_invoice or ""
            ledger_type = "credit" if amount > 0 else "debit"
            formatted_ledgers.append({
                "transaction_id":name,
                "date": ledger.date,
                "sales_invoice": narration,
                "amount": amount,
                "type": ledger_type
            })
        
        # Prepare response data
        response_data = {
            "sales_partner": sales_partner,
            "available_points": custom_earned_points,
            "recent_transactions": formatted_ledgers
        }
        
        return gen_response(200, "Dashboard Data Fetched Successfully", response_data)
    
    except Exception as ex:
        frappe.log_error(frappe.get_traceback(), "User Dashboard Error")
        return gen_response(500, "Failed to fetch user dashboard data", str(ex))


#Get Transaction
@frappe.whitelist(allow_guest=False, methods="POST")
def get_transaction():
    try:
        # Get input from JSON request
        input_data = frappe.request.json or {}
        from_date = input_data.get('from_date', '').strip()
        to_date = input_data.get('to_date', '').strip()
        search_name = input_data.get('name', '').strip()
        trans_type = input_data.get('type', '').strip().lower()
        
        # Safe int conversion for pagination
        def safe_int(value, default):
            try:
                if value:
                    return int(value)
            except (ValueError, TypeError):
                pass
            return default
        
        page = max(1, safe_int(input_data.get('page'), 1))
        limit = max(1, safe_int(input_data.get('limit'), 25))
        
        # Get current user
        current_user = frappe.session.user
        
        # Step 1: Check active user and link to employee
        user_doc = frappe.get_doc("User", current_user)
        if not user_doc.enabled:
            return gen_response(400, "User is not active", {})
        
        # Fetch employee using sql
        employee_data = frappe.db.sql("""
            SELECT name, employee_name FROM `tabEmployee` 
            WHERE user_id = %s LIMIT 1
        """, (current_user,), as_dict=1)
        if not employee_data:
            return gen_response(400, "No active employee linked to user", {})
        
        employee = employee_data[0]
        
        # Step 2: Get Sales Partner linked to employee (assume Sales Partner has 'employee' field)
        sales_partner_data = frappe.db.sql("""
            SELECT name FROM `tabSales Partner` 
            WHERE custom_employee = %s LIMIT 1
        """, (employee.name,), as_dict=1)
        if not sales_partner_data:
            return gen_response(400, "No Sales Partner linked to employee", {})
        
        sales_partner = sales_partner_data[0].name
        
        # Build dynamic query for count
        count_query = """
            SELECT COUNT(*) as total FROM `tabSales Partner Points Ledgers`
            WHERE sales_partner = %s
        """
        count_params = [sales_partner]
        
        # Date filter: if both provided, use BETWEEN; else no date filter
        if from_date and to_date:
            count_query += " AND date BETWEEN %s AND %s"
            count_params.extend([from_date, to_date])
        
        # Type filter: credit (points > 0), debit (points < 0)
        if trans_type == 'credit':
            count_query += " AND points > 0"
        elif trans_type == 'debit':
            count_query += " AND points < 0"
        
        # Name search filter: LIKE on name OR sales_invoice
        if search_name:
            count_query += " AND (name LIKE %s OR sales_invoice LIKE %s)"
            search_param = f"%{search_name}%"
            count_params.extend([search_param, search_param])
        
        # Execute count query
        total_result = frappe.db.sql(count_query, tuple(count_params), as_dict=1)
        total_count = total_result[0].total if total_result else 0
        
        # Build dynamic query for data
        query = """
            SELECT name, date, points, sales_invoice FROM `tabSales Partner Points Ledgers`
            WHERE sales_partner = %s
        """
        params = [sales_partner]
        
        # Date filter: if both provided, use BETWEEN; else no date filter
        if from_date and to_date:
            query += " AND date BETWEEN %s AND %s"
            params.extend([from_date, to_date])
        
        # Type filter: credit (points > 0), debit (points < 0)
        if trans_type == 'credit':
            query += " AND points > 0"
        elif trans_type == 'debit':
            query += " AND points < 0"
        
        # Name search filter: LIKE on name OR sales_invoice
        if search_name:
            query += " AND (name LIKE %s OR sales_invoice LIKE %s)"
            search_param = f"%{search_name}%"
            params.extend([search_param, search_param])
        
        # Order by date DESC
        query += " ORDER BY date DESC LIMIT %s OFFSET %s"
        offset = (page - 1) * limit
        params.extend([limit, offset])
        
        # Execute query
        ledgers_data = frappe.db.sql(query, tuple(params), as_dict=1)
        
        # Format ledgers
        formatted_ledgers = []
        for ledger in ledgers_data:
            amount = ledger.points or 0
            narration = ledger.sales_invoice or ""
            ledger_type = "credit" if amount > 0 else "debit"
            formatted_ledgers.append({
                "transaction_id": ledger.name,
                "date": ledger.date,
                "amount": amount,
                "sales_invoice": narration,
                "type": ledger_type
            })
        
        # Prepare response data
        response_data = {
            "sales_partner": sales_partner,
            "transactions": formatted_ledgers
            # "pagination": {
            #     "page": page,
            #     "limit": limit,
            #     "total": total_count,
            #     "total_pages": (total_count + limit - 1) // limit if limit > 0 else 0
            # }
        }
        
        return gen_response(200, "Transaction Data Fetched Successfully", response_data)
    
    except Exception as ex:
        frappe.log_error(frappe.get_traceback(), "Transaction Fetch Error")
        return gen_response(500, "Failed to fetch transaction data", str(ex))