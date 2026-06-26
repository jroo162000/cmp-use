"""
Calendar & Scheduling - Google Calendar integration, reminders, event management
"""

import os
import datetime
# Google API libraries are heavy; import them lazily on first tool run (via _lazy(),
# invoked from the run wrapper below) instead of at module import.
Request = Credentials = InstalledAppFlow = build = HttpError = None

def _lazy():
    global Request, Credentials, InstalledAppFlow, build, HttpError
    if build is not None:
        return
    from google.auth.transport.requests import Request as _Req
    from google.oauth2.credentials import Credentials as _Creds
    from google_auth_oauthlib.flow import InstalledAppFlow as _Flow
    from googleapiclient.discovery import build as _build
    from googleapiclient.errors import HttpError as _HttpErr
    Request, Credentials, InstalledAppFlow, build, HttpError = _Req, _Creds, _Flow, _build, _HttpErr

from typing import Any, Dict
from ..tool_registry import Tool, register

# Google Calendar API scopes
SCOPES = ['https://www.googleapis.com/auth/calendar']

class CalendarManager:
    def __init__(self):
        self.calendar_service = None
        self.reminders = []

    def get_calendar_service(self):
        """Get authenticated Google Calendar API service"""
        if self.calendar_service:
            return self.calendar_service

        creds = None
        token_path = os.path.expanduser('~/.cmpuse/calendar_token.json')
        creds_path = os.path.expanduser('~/.cmpuse/calendar_credentials.json')

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
                    "Calendar not authorized (token missing/expired and silent refresh failed). "
                    "Run ava_google_auth.py once to re-authorize.")

            # Save refreshed credentials
            os.makedirs(os.path.dirname(token_path), exist_ok=True)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        self.calendar_service = build('calendar', 'v3', credentials=creds)
        return self.calendar_service

    def create_event(self, summary, start_time, end_time, description=None, location=None, attendees=None, all_day=False):
        """Create calendar event. If all_day=True, start_time/end_time should be YYYY-MM-DD and will be used as date fields."""
        service = self.get_calendar_service()

        if all_day:
            event = {
                'summary': summary,
                'start': { 'date': start_time },
                'end': { 'date': end_time },
            }
        else:
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time,
                    'timeZone': 'UTC',
                },
                'end': {
                    'dateTime': end_time,
                    'timeZone': 'UTC',
                },
            }

        if description:
            event['description'] = description
        if location:
            event['location'] = location
        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        try:
            event = service.events().insert(calendarId='primary', body=event).execute()
            return event
        except HttpError as error:
            raise Exception(f'Calendar API error: {error}')

    def list_events(self, time_min=None, time_max=None, max_results=10):
        """List upcoming calendar events"""
        service = self.get_calendar_service()

        if not time_min:
            time_min = datetime.datetime.utcnow().isoformat() + 'Z'

        try:
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            return events
        except HttpError as error:
            raise Exception(f'Calendar API error: {error}')

    def delete_event(self, event_id):
        """Delete calendar event"""
        service = self.get_calendar_service()

        try:
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except HttpError as error:
            raise Exception(f'Calendar API error: {error}')

    def update_event(self, event_id, **kwargs):
        """Update calendar event"""
        service = self.get_calendar_service()

        try:
            event = service.events().get(calendarId='primary', eventId=event_id).execute()

            # Update fields
            if 'summary' in kwargs:
                event['summary'] = kwargs['summary']
            if 'description' in kwargs:
                event['description'] = kwargs['description']
            if 'location' in kwargs:
                event['location'] = kwargs['location']
            if 'start_time' in kwargs:
                event['start']['dateTime'] = kwargs['start_time']
            if 'end_time' in kwargs:
                event['end']['dateTime'] = kwargs['end_time']

            updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            return updated_event
        except HttpError as error:
            raise Exception(f'Calendar API error: {error}')

calendar_manager = CalendarManager()

def _plan(args: Dict[str, Any]) -> Dict[str, Any]:
    action = args.get("action", "list_events")

    if action == "create_event":
        return {"preview": f"Create calendar event: {args.get('summary', 'New Event')}", "args": args}
    elif action == "list_events":
        return {"preview": "List upcoming calendar events", "args": args}
    elif action == "delete_event":
        return {"preview": f"Delete event {args.get('event_id')}", "args": args}
    elif action == "update_event":
        return {"preview": f"Update event {args.get('event_id')}", "args": args}
    else:
        return {"preview": f"Calendar action: {action}", "args": args}

def _run(args: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
    if dry_run:
        return {"status": "dry-run", "message": "Would perform calendar operation", "plan": _plan(args)}

    action = args.get("action", "list_events")

    try:
        if action == "create_event":
            # Accept flexible inputs: summary/title, start_time/end_time or start_date/end_date for all-day
            summary = args.get("summary") or args.get("title")
            all_day = bool(args.get("all_day", False))
            start_time = args.get("start_time")
            end_time = args.get("end_time")
            # Support all-day with dates
            if all_day and (not start_time or not end_time):
                start_date = args.get("start_date") or args.get("start")
                end_date = args.get("end_date") or args.get("end")
                if start_date and end_date:
                    start_time = start_date
                    end_time = end_date
            description = args.get("description")
            location = args.get("location")
            attendees = args.get("attendees", [])

            if not all([summary, start_time, end_time]):
                return {"status": "error", "message": "summary, start_time, and end_time required"}

            try:
                event = calendar_manager.create_event(summary, start_time, end_time, description, location, attendees, all_day=all_day)
                return {
                    "status": "ok",
                    "message": f"Event created: {summary}",
                    "event_id": event.get('id'),
                    "event_link": event.get('htmlLink')
                }
            except Exception as cal_error:
                return {
                    "status": "error",
                    "message": f"Calendar not configured or error: {str(cal_error)}",
                    "note": "To setup Calendar: Create OAuth2 credentials at console.cloud.google.com and save as ~/.cmpuse/calendar_credentials.json"
                }

        elif action == "list_events":
            time_min = args.get("time_min")
            time_max = args.get("time_max")
            max_results = args.get("max_results", 10)

            try:
                events = calendar_manager.list_events(time_min, time_max, max_results)

                event_list = []
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    event_list.append({
                        "id": event['id'],
                        "summary": event.get('summary', 'No Title'),
                        "start": start,
                        "end": event['end'].get('dateTime', event['end'].get('date')),
                        "location": event.get('location'),
                        "description": event.get('description'),
                        "link": event.get('htmlLink')
                    })

                return {
                    "status": "ok",
                    "events": event_list,
                    "count": len(event_list),
                    "message": f"Retrieved {len(event_list)} event(s)"
                }
            except Exception as cal_error:
                return {
                    "status": "error",
                    "message": f"Calendar not configured or error: {str(cal_error)}",
                    "note": "To setup Calendar: Create OAuth2 credentials at console.cloud.google.com and save as ~/.cmpuse/calendar_credentials.json"
                }

        elif action == "delete_event":
            event_id = args.get("event_id")

            if not event_id:
                return {"status": "error", "message": "event_id required"}

            calendar_manager.delete_event(event_id)
            return {"status": "ok", "message": f"Event {event_id} deleted"}

        elif action == "update_event":
            event_id = args.get("event_id")

            if not event_id:
                return {"status": "error", "message": "event_id required"}

            update_fields = {k: v for k, v in args.items() if k not in ['action', 'event_id']}
            event = calendar_manager.update_event(event_id, **update_fields)

            return {
                "status": "ok",
                "message": f"Event {event_id} updated",
                "event_link": event.get('htmlLink')
            }

        elif action == "get_today":
            # Get today's events
            today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min).isoformat() + 'Z'
            today_end = datetime.datetime.combine(datetime.date.today(), datetime.time.max).isoformat() + 'Z'

            events = calendar_manager.list_events(time_min=today_start, time_max=today_end, max_results=50)

            event_list = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                event_list.append({
                    "summary": event.get('summary', 'No Title'),
                    "start": start,
                    "location": event.get('location')
                })

            return {
                "status": "ok",
                "events": event_list,
                "count": len(event_list),
                "message": f"You have {len(event_list)} event(s) today"
            }

        elif action == "find_free_time":
            # Find free time slots today
            today_start = datetime.datetime.combine(datetime.date.today(), datetime.time(9, 0)).isoformat() + 'Z'
            today_end = datetime.datetime.combine(datetime.date.today(), datetime.time(17, 0)).isoformat() + 'Z'

            events = calendar_manager.list_events(time_min=today_start, time_max=today_end, max_results=50)

            # Simple free time calculation
            busy_times = [(e['start'].get('dateTime'), e['end'].get('dateTime')) for e in events if e.get('start', {}).get('dateTime')]

            return {
                "status": "ok",
                "busy_times": busy_times,
                "message": f"Found {len(busy_times)} busy slot(s) today"
            }

        else:
            return {"status": "error", "message": f"Unknown action: {action}"}

    except Exception as e:
        return {"status": "error", "message": f"Calendar ops error: {str(e)}"}

TOOL = Tool(
    name="calendar_ops",
    summary="Calendar & scheduling - create/list/update/delete Google Calendar events, find free time, check today's schedule",
    plan=_plan,
    run=lambda args, dry_run: (_lazy(), _run(args, dry_run))[1],
    permissions={"confirm": True}  # Calendar operations require confirmation
)

register(TOOL)
