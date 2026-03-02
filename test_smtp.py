import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from pathlib import Path

# Load env
base_dir = Path(__file__).resolve().parent.parent
env_path = base_dir / '.env'
load_dotenv(env_path)

host = os.getenv('EMAIL_HOST')
port = int(os.getenv('EMAIL_PORT', 465))
user = os.getenv('EMAIL_HOST_USER')
password = os.getenv('EMAIL_HOST_PASSWORD')
use_tls = os.getenv('EMAIL_USE_TLS', 'False').lower() == 'true'
use_ssl = os.getenv('EMAIL_USE_SSL', 'False').lower() == 'true'

print(f"Connecting to {host}:{port} (SSL: {use_ssl}, TLS: {use_tls})")
print(f"User: {user}")

try:
    if use_ssl:
        server = smtplib.SMTP_SSL(host, port)
    else:
        server = smtplib.SMTP(host, port)
        if use_tls:
            server.starttls()
            
    server.login(user, password)
    
    msg = MIMEMultipart()
    msg['From'] = user
    msg['To'] = "greymatter.ga@gmail.com"
    msg['Subject'] = "SMTP Test"
    msg.attach(MIMEText("Test message", 'plain'))
    
    server.send_message(msg)
    server.quit()
    print("Email sent successfully!")
except Exception as e:
    print(f"SMTP Error: {e}")
