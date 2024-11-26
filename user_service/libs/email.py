import smtplib
from email.mime.text import MIMEText
from user.models import RoleModel
from django.conf import settings



class Email:

    def __init__(self, subject, body, client_ts):
        self.subject = subject
        self.body = body
        self.sender_email = settings.SYSTEM_EMAIL
        self.client_ts = client_ts
    


    def report_content_to_admins(self): 
        role_model = RoleModel(client=self.client_ts)       
        recipient_email = role_model.get_system_admin_emails()             
        if len(recipient_email) == 0:
            # No system admin. 
            return True
        
        message = MIMEText(self.body)
        message['Subject'] = self.subject
        message['From'] = self.sender_email
        message['To'] = ", ".join(recipient_email)

        try:            
            smtp_server = smtplib.SMTP(settings.EMAIL_SERVER_HOST, int(settings.EMAIL_SERVER_PORT))
            smtp_server.sendmail(self.sender_email, recipient_email, message.as_string())
            smtp_server.quit()
            return True
        except Exception as e:
            return False
