import frappe
from united_addon.api.utils import gen_response
from bs4 import BeautifulSoup
from frappe.utils import cstr
from frappe.utils import escape_html
import json
import requests
from urllib.parse import urljoin


#Login
@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()
    except frappe.exceptions.AuthenticationError:
        frappe.local.response.http_status_code = 422
        frappe.local.response["message"] = "Invalid Details & Master User Not Login"
        return

    user = frappe.get_doc('User', frappe.session.user)
    emp = frappe.get_doc('Employee', {'user_id': frappe.session.user})
    sales_partner = frappe.get_doc('Sales Partner', {'custom_employee': emp.name})
    

    # Generate API key and secret
    api_generate = generate_keys(user)
    if not api_generate:  # Double-checking if key generation failed
        frappe.local.response.http_status_code = 500
        frappe.local.response["message"] = "Failed to generate API keys."
        return
    
    # Check Face Register doctype for submitted entry matching employee email
    
    token_string = f"{api_generate['api_key']}:{api_generate['api_secret']}"

    # Preparing the response
    frappe.response["user_details"] = {
        "first_name": escape_html(emp.first_name or ""),
        "last_name": escape_html(emp.last_name or ""),
        "gender": escape_html(emp.gender or "") or "",
        "birth_date": emp.date_of_birth or "",
        "email": emp.user_id or "",
        "employee_name": emp.employee_name or "",
        "designation": emp.designation or "",
        "department": emp.department or "",
        "partner_type":sales_partner.partner_type,
        "image": user.user_image or "",
        "enabled": user.enabled
    }
    frappe.response["token"] = "Token " + token_string
    return


# Generate Key and Token
def generate_keys(user):
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
