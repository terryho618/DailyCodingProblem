import os
import pickle
import re
# Gmail API utils
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
# for encoding/decoding messages in base64
from base64 import urlsafe_b64decode, urlsafe_b64encode
# for dealing with attachement MIME types
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from mimetypes import guess_type as guess_mime_type
from discord import SyncWebhook
from datetime import date, timedelta

# Request all access (permission to read/send/receive emails, manage the inbox, and more)
SCOPES = ['https://mail.google.com/']
our_email = '' #include your email in the quotes
today = date.today()

# prompts user to log-in and store and refresh tokens
def gmail_authenticate():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)
    return build('gmail', 'v1', credentials=creds)

#get the Gmail API service
service = gmail_authenticate()

def search_messages(service, query):
    #search your inbox

    result = service.users().messages().list(userId='me',q=query).execute()
    messages = [ ]
    if 'messages' in result:
        messages.extend(result['messages'])
    while 'nextPageToken' in result:
        page_token = result['nextPageToken']
        result = service.users().messages().list(userId='me',q=query, pageToken=page_token).execute()
        if 'messages' in result:
            messages.extend(result['messages'])
    return messages


def parse_parts(service, parts, message):
    #parses through email with regex

    if parts:
        for part in parts:
            filename = part.get("filename")
            mimeType = part.get("mimeType")
            body = part.get("body")
            data = body.get("data")
            file_size = body.get("size")
            part_headers = part.get("headers")
            if part.get("parts"):
                # recursively call this function when we see that a part
                # has parts inside
                parse_parts(service, part.get("parts"), message)
            if mimeType == "text/plain":
                # if the email part is text plain
                if data:
                    text = urlsafe_b64decode(data).decode()
                    # print(text)
                    company = re.search(r'This problem was asked by (.*?)\.', text).group(1)
                    message = re.search(r'This problem was asked by (.*?)\.\s*([\s\S]*?)\s*--------------------------------------------------', text).group(2)
                    return message, company

def difficulty(service,message):
    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    payload = msg['payload']
    headers = payload.get("headers")
    if headers:
        for header in headers:
            name = header.get("name")
            value = header.get("value")
            if name.lower() == "subject":
                diff = re.search(r'(?<=\[).+?(?=\])', value).group(0)
                return diff


def read_message(service, message):
    #grabs the contents of the emails
    #returns the body of the email

    msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
    # parts can be the message body, or attachments
    payload = msg['payload']
    headers = payload.get("headers")
    parts = payload.get("parts")
    if headers:
        # this section prints email basic info & creates a folder for the email
        for header in headers:
            name = header.get("name")
            value = header.get("value")

    result = parse_parts(service, parts, message)
    return result


def disc_message(service, message):
    #include the discord webhook url in the quotes
    webhook = SyncWebhook.from_url("")
    webhook.send(message)


today = date.today()
yesterday = today - timedelta(1)

formatted_date = " after:"+yesterday.strftime("%Y/%m/%d") +" before:"+today.strftime("%Y/%m/%d")

message = "Good morning! Here's your coding interview problem for today."

while True:
    result = search_messages(service, (message, formatted_date))
    difficult = difficulty(service, result[0])
    read = read_message(service, result[0])

    s = "Problem of the Day (" + today.strftime("%m/%d/%Y") +") asked by " + read[1] + " ["+ difficult+ "]"
    s +="\n" + "-"*54 + "\n" + "```" + "\n"
    s += read[0]
    s += "```"
    if result:
        # print(s)
        disc_message(service, s)
        break

#credit: https://www.thepythoncode.com/article/use-gmail-api-in-python