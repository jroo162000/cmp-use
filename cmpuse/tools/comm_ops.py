"""
Email & Communications - Gmail, Outlook, SMS via Twilio
"""

import os
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
# Google + Twilio libraries are heavy; import them lazily on first tool run (via
# _lazy(), invoked from the run wrapper below) instead of at module import.
Request = Credentials = InstalledAppFlow = build = HttpError = Client = None

def _lazy():
    global Request, Credentials, InstalledAppFlow, build, HttpError, Client
    if build is not None:
        return
    from google.auth.transport.requests import Request as _Req
    from google.oauth2.credentials import Credentials as _Creds
    from google_auth_oauthlib.flow import InstalledAppFlow as _Flow
    from googleapiclient.discovery import build as _build
    from googleapiclient.errors import HttpError as _HttpErr
    from twilio.rest import Client as _Client
    Request, Credentials, InstalledAppFlow, build, HttpError, Client = _Req, _Creds, _Flow, _build, _HttpErr, _Client
from typing import Any, Dict
from ..tool_registry import Tool, register

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send',
          'https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify']

# Twilio configuration (set via environment or config)
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

class CommunicationManager:
    def __init__(self):
        self.gmail_service = None
        self.twilio_client = None
        self.credentials = None

    def get_gmail_service(self):
        """Get authenticated Gmail API service"""
        if self.gmail_service:
            return self.gmail_service

        creds = None
        token_path = os.path.expanduser('~/.cmpuse/gmail_token.json')
        creds_path = os.path.expanduser('~/.cmpuse/gmail_credentials.json')

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            refreshed = False
            if creds and creds.expired and creds.refresh_token:
                import socket as _socket
                _old_to = _socket.getdefaulttimeout()
                _socket.setdefaulttimeout(20)  # bound a hung refresh, but allow a normal one
                try:
                    creds.refresh(Request())
                    refreshed = True
                except Exception:
                    refreshed = False
                finally:
                    _socket.setdefaulttimeout(_old_to)
            if not refreshed:
                # IMPORTANT: never launch an interactive browser login here. This runs
                # inside AVA's tool worker; run_local_server() would block and freeze
                # every tool call. Re-authorize once, out-of-band, via ava_google_auth.py.
                raise Exception(
                    "Gmail not authorized (token missing/expired and silent refresh failed). "
                    "Run ava_google_auth.py once to re-authorize.")

            # Save refreshed credentials
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        self.gmail_service = build('gmail', 'v1', credentials=creds)
        return self.gmail_service

    def get_twilio_client(self):
        """Get Twilio client"""
        if not self.twilio_client and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
            self.twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        return self.twilio_client

    def send_email_gmail(self, to, subject, body, attachments=None):
        """Send email via Gmail"""
        service = self.get_gmail_service()

        message = MIMEMultipart()
        message['to'] = to
        message['subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        # Add attachments
        if attachments:
            for file_path in attachments:
                with open(file_path, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
                    message.attach(part)

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        send_message = {'raw': raw_message}

        try:
            sent = service.users().messages().send(userId='me', body=send_message).execute()
            return sent
        except HttpError as error:
            raise Exception(f'Gmail API error: {error}')

    def read_emails_gmail(self, query='is:unread', max_results=10):
        """Read emails from Gmail"""
        service = self.get_gmail_service()

        try:
            results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
            messages = results.get('messages', [])

            emails = []
            for msg in messages:
                message = service.users().messages().get(userId='me', id=msg['id']).execute()
                headers = message['payload']['headers']

                email_data = {
                    'id': message['id'],
                    'threadId': message['threadId'],
                    'snippet': message.get('snippet', ''),
                    'from': next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown'),
                    'to': next((h['value'] for h in headers if h['name'] == 'To'), 'Unknown'),
                    'subject': next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject'),
                    'date': next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown')
                }

                emails.append(email_data)

            return emails
        except HttpError as error:
            raise Exception(f'Gmail API error: {error}')

    def reply_email_gmail(self, body, message_id=None, query=None):
        """Send a threaded reply (to the original sender) to an email.
        If message_id is omitted, replies to the most recent message matching `query`
        (default: most recent in the inbox)."""
        service = self.get_gmail_service()

        # Locate the message to reply to
        if not message_id:
            q = query or 'in:inbox'
            results = service.users().messages().list(userId='me', q=q, maxResults=1).execute()
            msgs = results.get('messages', [])
            if not msgs:
                raise Exception(f"No email found to reply to (query: {q})")
            message_id = msgs[0]['id']

        original = service.users().messages().get(
            userId='me', id=message_id, format='metadata',
            metadataHeaders=['From', 'Subject', 'Message-ID', 'References']
        ).execute()
        headers = original.get('payload', {}).get('headers', [])

        def hv(name):
            return next((h['value'] for h in headers if h['name'].lower() == name.lower()), '')

        to_addr = hv('From')          # reply goes to whoever sent the original
        subject = hv('Subject') or '(no subject)'
        orig_msgid = hv('Message-ID')
        references = hv('References')
        thread_id = original.get('threadId')
        if not to_addr:
            raise Exception("Could not determine the original sender to reply to")

        reply_subject = subject if subject.lower().startswith('re:') else f"Re: {subject}"
        msg = MIMEText(body, 'plain')
        msg['to'] = to_addr
        msg['subject'] = reply_subject
        if orig_msgid:
            msg['In-Reply-To'] = orig_msgid
            msg['References'] = (references + ' ' + orig_msgid).strip() if references else orig_msgid

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = service.users().messages().send(
            userId='me', body={'raw': raw, 'threadId': thread_id}
        ).execute()
        return {'sent_id': sent.get('id'), 'to': to_addr, 'subject': reply_subject, 'thread_id': thread_id}

    def send_sms(self, to, body):
        """Send SMS via Twilio"""
        client = self.get_twilio_client()

        if not client:
            raise Exception("Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables.")

        message = client.messages.create(
            body=body,
            from_=TWILIO_PHONE_NUMBER,
            to=to
        )

        return message

comm_manager = CommunicationManager()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "send_email")

    if action == "send_email":
        return {"preview": f"Send email to {args.get('to', 'recipient')}", "args": args}
    elif action == "read_emails":
        return {"preview": "Read recent emails", "args": args}
    elif action == "reply":
        return {"preview": "Reply to an email (to the original sender)", "args": args}
    elif action == "send_sms":
        return {"preview": f"Send SMS to {args.get('to', 'recipient')}", "args": args}
    else:
        return {"preview": f"Communication action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform communication operation", "plan": _plan(args)}

    action = args.get("action", "send_email")

    try:
        if action == "send_email":
            to = args.get("to")
            subject = args.get("subject", "Message from AVA")
            body = args.get("body", "")
            attachments = args.get("attachments", [])
            provider = args.get("provider", "gmail")

            if not to or not body:
                return {"status": "error", "message": "to and body required"}

            if provider == "gmail":
                try:
                    result = comm_manager.send_email_gmail(to, subject, body, attachments)
                    return {
                        "status": "ok",
                        "message": f"Email sent to {to}",
                        "message_id": result.get('id'),
                        "provider": "gmail"
                    }
                except Exception as gmail_error:
                    return {
                        "status": "error",
                        "message": f"Gmail not configured or error: {str(gmail_error)}",
                        "note": "To setup Gmail: Create OAuth2 credentials at console.cloud.google.com and save as ~/.cmpuse/gmail_credentials.json"
                    }
            else:
                return {"status": "error", "message": f"Unsupported email provider: {provider}"}

        elif action == "read_emails":
            query = args.get("query", "is:unread")
            max_results = args.get("max_results", 10)
            provider = args.get("provider", "gmail")

            if provider == "gmail":
                try:
                    emails = comm_manager.read_emails_gmail(query, max_results)
                    return {
                        "status": "ok",
                        "emails": emails,
                        "count": len(emails),
                        "message": f"Retrieved {len(emails)} email(s)"
                    }
                except Exception as gmail_error:
                    return {
                        "status": "error",
                        "message": f"Gmail not configured or error: {str(gmail_error)}",
                        "note": "To setup Gmail: Create OAuth2 credentials at console.cloud.google.com and save as ~/.cmpuse/gmail_credentials.json"
                    }
            else:
                return {"status": "error", "message": f"Unsupported email provider: {provider}"}

        elif action == "send_sms":
            to = args.get("to")
            body = args.get("body")

            if not to or not body:
                return {"status": "error", "message": "to and body required"}

            try:
                message = comm_manager.send_sms(to, body)
                return {
                    "status": "ok",
                    "message": f"SMS sent to {to}",
                    "message_sid": message.sid,
                    "provider": "twilio"
                }
            except Exception as sms_error:
                return {
                    "status": "error",
                    "message": f"Twilio not configured or error: {str(sms_error)}",
                    "note": "To setup SMS: Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables"
                }

        elif action == "mark_read":
            message_id = args.get("message_id")
            provider = args.get("provider", "gmail")

            if provider == "gmail":
                service = comm_manager.get_gmail_service()
                service.users().messages().modify(
                    userId='me',
                    id=message_id,
                    body={'removeLabelIds': ['UNREAD']}
                ).execute()

                return {"status": "ok", "message": f"Email {message_id} marked as read"}
            else:
                return {"status": "error", "message": f"Unsupported provider: {provider}"}

        elif action == "reply":
            body = args.get("body") or args.get("message") or args.get("text")
            message_id = args.get("message_id") or args.get("email_id") or args.get("id")
            query = args.get("query")
            provider = args.get("provider", "gmail")
            if not body:
                return {"status": "error", "message": "reply text (body) is required to send a reply"}
            if provider != "gmail":
                return {"status": "error", "message": f"Unsupported provider: {provider}"}
            try:
                r = comm_manager.reply_email_gmail(body, message_id=message_id, query=query)
                return {
                    "status": "ok",
                    "message": f"Reply sent to {r['to']} (subject: {r['subject']})",
                    "to": r["to"],
                    "subject": r["subject"],
                    "message_id": r["sent_id"],
                    "provider": "gmail"
                }
            except Exception as e:
                return {"status": "error", "message": f"Could not send reply: {str(e)}"}

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Communication ops error: {str(e)}"}

TOOL = Tool(
    name="comm_ops",
    summary=("Email & Communications. To REPLY to someone (e.g. 'reply to Trinity Logistics and say X'): "
             "use action=reply with query set to the person's name or email (e.g. query='trinity') and body set to your message — "
             "it finds that person's most recent email and replies to them in-thread. Prefer reply over send_email for any 'reply to <name>' request. "
             "To send a NEW email: action=send_email with to (full address) + subject + body. "
             "Also: action=read_emails (query optional), action=send_sms (Twilio), action=mark_read."),
    plan=_plan,
    run=lambda args, dry_run: (_lazy(), _run(args, dry_run))[1],
    permissions={"confirm": True}  # Sending communications requires confirmation
)

register(TOOL)
