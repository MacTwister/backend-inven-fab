from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os.path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment
import qrcode
import base64
from io import BytesIO
import dotenv
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formataddr
import time
import logging

dotenv.load_dotenv()

# Define the scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Read the environment variables
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
RANGE_NAME = os.getenv("RANGE_NAME")
SHEET_REGISTERS = os.getenv("SHEET_REGISTERS")

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
TEMPLATE_ID = os.getenv('SENDGRID_TEMPLATE_ID')

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = 'token.json'

BASE_URL = os.getenv("BASE_URL")

sg = SendGridAPIClient(SENDGRID_API_KEY)


app = Flask(__name__)
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'


apiCache = {
    "response": None,
    "timestamp": 0
}
checkCache = {
    "response": None,
    "timestamp": 0
}


def get_credentials():
    return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)


def get_sheet():
    creds = get_credentials()
    return build("sheets", "v4", credentials=creds)


def get_values():   # Call the Sheets API
    try:
        service = get_sheet()
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME)
            .execute()
        )
        return result.get("values", []) # Return a list with the values from the spreadsheet
    except HttpError as error:
        print(f"An error occurred: {error}")
        return []

# With help from ChatGPT
def get_cached_values(force_refresh=False):
    cache_duration = 3600*6  # in seconds
    current_time = time.time()
    
    # Check if cached data is available and not expired, and force_refresh is not requested
    if not force_refresh and apiCache['response'] and (current_time - apiCache['timestamp'] < cache_duration):
        print("Using cached response")
        return apiCache['response']
    
    # Make the API call
    print("Fetching new data from API")
    response = get_values()

    if not response:
        return response

    # Update the cache with new response and current timestamp
    apiCache['response'] = response
    apiCache['timestamp'] = current_time

    return apiCache['response']

def get_spreadsheet_data(force_refresh=False):  # Get the values from the spreadsheet and return them as a JSON
    values = get_cached_values(force_refresh)
    if not values:
        return jsonify({"error": "No se encontraron datos."})
    else:
        headers = values[0]
        records = []

        for row in values[1:]:
            record = {header: value for header, value in zip(headers, row)}
            records.append(record)

        return jsonify(records)


def add_register(data):
    try:
        service = get_sheet()
        sheet = service.spreadsheets()

        code = data.get('code', '');

        if (code != '' and check_registered_code(code) == True):
            return False;

        items = data.get('items', [])
        items_str = ', '.join([f"{item['id']} (Qty: {item['quantity']})" for item in items])
        subtotal = data.get('subtotal', '')
        formData = data.get('formData', {})
        date  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = [
            formData.get('workshopTitle', ''),
            formData.get('name', ''),
            formData.get('email', ''),
            items_str,
            subtotal,
            date,
            code,
        ]

        body = {
            "values": [row]
        }
        result = sheet.values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=SHEET_REGISTERS,
            valueInputOption="RAW",
            body=body
        ).execute()

        # Force clear cache if new save
        checkCache['timestamp'] = 0;

        return result
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

def check_registered_code(code):
    cache_duration = 3600 # in seconds
    current_time = time.time()
    
    # Fetch column if not cached
    if not checkCache['response'] or (current_time - checkCache['timestamp'] > cache_duration):
        try:
            service = get_sheet()
            sheet = service.spreadsheets()

            # Use configured range to only fetch code column
            codeColumnRange = SHEET_REGISTERS.split("!")[0] + "!G:G";

            result = (
                sheet.values()
                .get(spreadsheetId=SPREADSHEET_ID, range=codeColumnRange)
                .execute()
            )

            rows = result.get("values", [])

            if not rows:
                return False

            checkCache['response'] = rows
            checkCache['timestamp'] = current_time
        except HttpError as error:
            print(f"An error occurred: {error}")
            return False

    for row in checkCache['response']:
        if len(row) > 0 and row[0] == code:
            return True;

    return False;
    

def send_email(body):
    from_email = Email(os.getenv('MAIL_FROM_ADDRESS'), os.getenv('MAIL_FROM_NAME'))
    to_email = To(body['formData']['email'])

    title = body['formData']['workshopTitle']
    trimmed_title = title[:20] + '...' if len(title) > 20 else title
    subject = f"Thank you for your materials selection for {trimmed_title}"

    # if TEMPLATE_ID:

    text_content = render_template('email_confirmation.txt', body=body)
    content = Content("text/plain", text_content)

    mail = Mail(from_email, to_email, subject, content)

    # Adds QR image as an attachment
    qr_image = generate_qr_base64(body)
    qr_img_base64 = base64.b64encode(qr_image).decode()
    attachment = Attachment()
    attachment.file_content = qr_img_base64
    attachment.file_type = "image/png"
    attachment.file_name = "qrcode.png"
    attachment.disposition = "attachment"
    attachment.content_id = "QR Code"
    mail.add_attachment(attachment)

    try:
        mail_json = mail.get()
        response = sg.client.mail.send.post(request_body=mail_json)
 
        print(response.status_code)
        print(response.body)
        print(response.headers)
        return response.status_code
    except Exception as e:
        logging.warning(e.body)
        return 500

def generate_qr_base64(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffered = BytesIO()
    img.save(buffered, format="PNG")

    return buffered.getvalue()

@app.route(f"/{BASE_URL}/items", methods=["GET"])
def get_items():
    values = get_cached_values()
    if not values:
        return jsonify({"error": "No se encontraron datos."})
    else:
        # The 'Items' column is the seventh column (index 6)
        items = values[6]
        return jsonify({"items": items})


# Return the values from the spreadsheet as a JSON
@app.route(f"/{BASE_URL}", methods=["GET"])
def get_data():
    return get_spreadsheet_data(force_refresh=request.args.get('force', 'false').lower() == 'true')

# Receive the form data and send it via email
@app.route(f"/{BASE_URL}/send-email", methods=["POST"])
def send_email_from_form():
    data = request.json

    if not data.get('code'):
        return jsonify({"status_code": 200, "message": "OK"}), 200

    result = add_register(data)

    if result == False:
        return jsonify({"status_code": 200, "message": "Saved already"})
    elif result is None:
        print("An error occurred while adding the data.")
        return jsonify({"status_code": 500, "message": "An error occurred"}), 500

    # Skip email if a "Nothing needed" request
    if 'items' in data and len(data['items']) > 0 and data['items'][0].get('id') == 'Nothing Please':
        return jsonify({"status_code": 202, "message": "Data saved"}), 202

    status_code = send_email(data)

    return jsonify({"status_code": status_code, "message": "Email sent successfully" if status_code == 202 else "Email not sent"}), status_code

@app.route(f"/{BASE_URL}/check/<code>", methods=["GET"])
def check_something(code):
    hasRegistered = check_registered_code(code)
    return jsonify({"status": hasRegistered})

if __name__ == "__main__":
    app.run(debug=True)
