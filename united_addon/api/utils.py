from datetime import timezone
import frappe
from bs4 import BeautifulSoup
from frappe.utils import cstr


# Start here to Supporting Functions
def gen_response(status, message, data=[]):
    if "session_expired" in frappe.response and frappe.response["session_expired"] == 1:
        message = "Session Expired.Please login again."
        status = 403
    frappe.response["http_status_code"] = status
    if status == 500:
        frappe.response["message"] = BeautifulSoup(str(message)).get_text()
    else:
        frappe.response["message"] = message
    frappe.response["data"] = data


def exception_handler(e):
    frappe.log_error(title="POS Mobile App Error", message=frappe.get_traceback())
    if hasattr(e, "http_status_code"):
        return gen_response(e.http_status_code, cstr(e))
    else:
        return gen_response(500, cstr(e))

