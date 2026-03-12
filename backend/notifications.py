import os
from twilio.rest import Client

# Twilio Configuration
# In production, these should be environment variables
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'AC_TEST_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', 'TEST_TOKEN')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '+1234567890')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '+1234567890')

def send_absence_notification(parent_phone, student_name, class_name):
    """Sends an SMS notification to parents about student absence."""
    if not parent_phone or parent_phone == 'N/A':
        return False, "Invalid phone number"

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_body = f"Vidyalaya AI Alert: Your ward {student_name} ({class_name}) is ABSENT today. Please contact the school office for details."
        
        # Sending SMS
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=parent_phone
        )
        
        print(f"[INFO] Notification sent to {parent_phone} for {student_name}. SID: {message.sid}")
        return True, message.sid
    except Exception as e:
        print(f"[ERROR] Failed to send notification: {e}")
        return False, str(e)

def send_whatsapp_notification(parent_phone, student_name, class_name):
    """Sends a WhatsApp notification to parents about student absence."""
    if not parent_phone or parent_phone == 'N/A':
        return False, "Invalid phone number"

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        message_body = f"Vidyalaya AI Alert: Your ward {student_name} ({class_name}) is ABSENT today. Please contact the school office for details."
        
        # Sending WhatsApp (Note: Requires Twilio WhatsApp approval)
        message = client.messages.create(
            body=message_body,
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            to=f"whatsapp:{parent_phone}"
        )
        
        print(f"[INFO] WhatsApp sent to {parent_phone} for {student_name}. SID: {message.sid}")
        return True, message.sid
    except Exception as e:
        print(f"[ERROR] Failed to send WhatsApp: {e}")
        return False, str(e)
