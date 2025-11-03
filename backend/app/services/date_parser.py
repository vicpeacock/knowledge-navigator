"""
Natural language date parsing for calendar queries
Parses phrases like "domani", "prossima settimana", "il 15 marzo" into datetime ranges
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dateutil import parser as date_parser
import re
import locale


class DateParser:
    """Parse natural language date expressions"""
    
    def __init__(self):
        # Try to set Italian locale
        try:
            locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'it_IT')
            except:
                pass  # Use default locale
    
    def parse_query(self, query: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Parse a natural language query and return start_time, end_time
        Returns (start_time, end_time) or (None, None) if can't parse
        """
        query_lower = query.lower().strip()
        
        now = datetime.now()
        today_start = datetime(now.year, now.month, now.day)
        today_end = today_start + timedelta(days=1)
        
        # Patterns for common queries
        patterns = {
            # Today
            r'\boggi\b': (today_start, today_end),
            r'\btoday\b': (today_start, today_end),
            
            # Tomorrow
            r'\bdomani\b': (today_start + timedelta(days=1), today_start + timedelta(days=2)),
            r'\btomorrow\b': (today_start + timedelta(days=1), today_start + timedelta(days=2)),
            
            # This week
            r'\bquesta settimana\b': (today_start, today_start + timedelta(days=7)),
            r'\bthis week\b': (today_start, today_start + timedelta(days=7)),
            
            # Next week
            r'\bprossima settimana\b': (today_start + timedelta(days=7), today_start + timedelta(days=14)),
            r'\bnext week\b': (today_start + timedelta(days=7), today_start + timedelta(days=14)),
            
            # This month
            r'\bquesto mese\b': (today_start, today_start + timedelta(days=30)),
            r'\bthis month\b': (today_start, today_start + timedelta(days=30)),
            
            # Next month
            r'\bprossimo mese\b': (today_start + timedelta(days=30), today_start + timedelta(days=60)),
            r'\bnext month\b': (today_start + timedelta(days=30), today_start + timedelta(days=60)),
        }
        
        # Try pattern matching first
        for pattern, (start, end) in patterns.items():
            if re.search(pattern, query_lower):
                return (start, end)
        
        # Try to parse specific dates like "15 marzo", "marzo 15", "2024-03-15"
        date_match = re.search(r'\b(\d{1,2})\s*(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre|january|february|march|april|may|june|july|august|september|october|november|december)\b', query_lower)
        if date_match:
            try:
                day = int(date_match.group(1))
                month_str = date_match.group(2)
                months_it = {
                    'gennaio': 1, 'febbraio': 2, 'marzo': 3, 'aprile': 4,
                    'maggio': 5, 'giugno': 6, 'luglio': 7, 'agosto': 8,
                    'settembre': 9, 'ottobre': 10, 'novembre': 11, 'dicembre': 12
                }
                months_en = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                months = {**months_it, **months_en}
                month = months.get(month_str.lower())
                if month:
                    year = now.year
                    # If month is in the past this year, assume next year
                    if month < now.month or (month == now.month and day < now.day):
                        year = now.year + 1
                    start = datetime(year, month, day)
                    end = start + timedelta(days=1)
                    return (start, end)
            except:
                pass
        
        # Try ISO date format
        iso_match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', query)
        if iso_match:
            try:
                date_obj = datetime.strptime(iso_match.group(1), '%Y-%m-%d')
                return (date_obj, date_obj + timedelta(days=1))
            except:
                pass
        
        # Try relative days: "tra 3 giorni", "in 5 giorni"
        relative_match = re.search(r'\b(tra|in|fra)\s+(\d+)\s+giorni?\b', query_lower)
        if relative_match:
            days = int(relative_match.group(2))
            start = today_start + timedelta(days=days)
            end = start + timedelta(days=1)
            return (start, end)
        
        # Default: if query mentions events/appointments/meetings, return next 7 days
        if any(word in query_lower for word in ['evento', 'appuntamento', 'meeting', 'event', 'appointment']):
            return (today_start, today_start + timedelta(days=7))
        
        # Default: return None if can't parse
        return (None, None)
    
    def format_datetime(self, dt: datetime) -> str:
        """Format datetime for display"""
        return dt.strftime("%d/%m/%Y %H:%M")

