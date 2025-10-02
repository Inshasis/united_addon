import frappe
from united_addon.api.utils import gen_response
from bs4 import BeautifulSoup
from frappe.utils import cstr, escape_html, get_url
from frappe.exceptions import AuthenticationError


# Login
@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        # Authenticate user
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
        
        # Fetch user details
        user = frappe.get_doc('User', frappe.session.user)
        
        # Check if user is linked to an employee
        if not frappe.db.exists('Employee', {'user_id': frappe.session.user}):
            frappe.local.response.http_status_code = 422
            frappe.local.response["message"] = "User is not linked to any employee. Please contact administrator."
            frappe.local.response["error_type"] = "no_employee_link"
            return
        
        # Get employee data
        emp_data = frappe.db.get_value('Employee', {'user_id': frappe.session.user}, 
                                       ['name', 'first_name', 'last_name', 'gender', 'date_of_birth', 
                                        'employee_name', 'designation', 'department'], as_dict=1)
        
        if not emp_data:
            frappe.local.response.http_status_code = 422
            frappe.local.response["message"] = "Employee data not found. Please contact administrator."
            frappe.local.response["error_type"] = "employee_not_found"
            return
        
        # Check if employee is linked to a sales partner
        if not frappe.db.exists('Sales Partner', {'custom_employee': emp_data.name}):
            frappe.local.response.http_status_code = 422
            frappe.local.response["message"] = "Employee is not linked to any sales partner. Please contact administrator."
            frappe.local.response["error_type"] = "no_sales_partner_link"
            return
        
        # Get sales partner data
        sales_partner_data = frappe.db.get_value('Sales Partner', {'custom_employee': emp_data.name}, 
                                                 ['name', 'partner_type'], as_dict=1)
        
        if not sales_partner_data:
            frappe.local.response.http_status_code = 422
            frappe.local.response["message"] = "Sales partner data not found. Please contact administrator."
            frappe.local.response["error_type"] = "sales_partner_not_found"
            return
        
        # Generate API key and secret
        api_generate = generate_keys(user)
        if not api_generate:
            frappe.local.response.http_status_code = 422
            frappe.local.response["message"] = "API Key Generation Failed"
            return
        
        # Handle image URL
        image_url = user.user_image or ""
        if image_url and image_url.startswith('/files'):
            image_url = get_url(image_url)
        
        # Prepare token
        token_string = f"{api_generate['api_key']}:{api_generate['api_secret']}"
        
        # Preparing the response
        frappe.response["user_details"] = {
            "first_name": escape_html(emp_data.first_name or ""),
            "last_name": escape_html(emp_data.last_name or ""),
            "gender": escape_html(emp_data.gender or ""),
            "birth_date": emp_data.date_of_birth or "",
            "email": frappe.session.user,
            "employee_name": emp_data.employee_name or "",
            "designation": emp_data.designation or "",
            "department": emp_data.department or "",
            "partner_type": sales_partner_data.partner_type or "",
            "employee_id": emp_data.name,
            "sales_partner_id": sales_partner_data.name,
            "image": image_url,
            "enabled": user.enabled
        }
        frappe.response["token"] = "Token " + token_string
        frappe.response["message"] = "Login successful"
        
    except AuthenticationError:
        frappe.local.response.http_status_code = 422
        frappe.local.response["message"] = "Invalid username or password"
        frappe.local.response["error_type"] = "authentication_error"
    except Exception as e:
        frappe.log_error(f"Login error: {str(e)}", "Custom Login")
        frappe.local.response.http_status_code = 500
        frappe.local.response["message"] = "Login failed due to an internal error"
        frappe.local.response["error_type"] = "internal_error"
    return


# Generate Key and Token
def generate_keys(user):
    try:
        api_secret = frappe.generate_hash(length=15)
        api_key = frappe.generate_hash(length=15)

        # Save the keys to the user
        user.api_key = api_key
        user.api_secret = api_secret
        user.save(ignore_permissions=True)
        frappe.db.commit()

        # Return the generated keys
        return {
            "api_key": api_key,
            "api_secret": api_secret
        }
    except Exception as e:
        frappe.log_error(f"API Key generation error: {str(e)}", "Generate Keys")
        return None