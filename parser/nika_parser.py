"""
Core parser for processing NIKA-Soft schedule data.
Handles fetching, regex extraction, and data normalization.
"""
import re
import json
import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import aiohttp
from config import settings

logger = logging.getLogger(__name__)

@dataclass
class LessonRaw:
    class_id: str  # Note: Internal ID from NIKA, might need mapping
    day: int      # 0-6
    number: int   # 1-8
    subject: str
    teacher: str
    room: str


class NikaParser:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        # Browser headers to avoid some WAFs or bot detection
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,"
                      "image/avif,image/webp,*/*;q=0.8",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(headers=self.headers)
        return self.session

    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def fetch_schedule_data(self) -> Optional[Dict[str, Any]]:
        """
        Main entry point: fetches HTML, finds JS, extracts JSON.
        """
        session = await self._get_session()
        
        try:
            # 1. Fetch Main HTML
            logger.info(f"Fetching {settings.schedule_url}")
            async with session.get(settings.schedule_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch HTML. Status: {response.status}")
                    return None
                html_content = await response.text()

            # 2. Find JS file
            # Regex to find src="...nika_data...js"
            # Example: <script src="js/nika_data_123456.js"></script>
            # We look for something ending in .js that contains 'nika_data'
            script_pattern = r'src="([^"]*nika_data[^"]*\.js)"'
            match = re.search(script_pattern, html_content)
            
            if not match:
                logger.error("Could not find nika_data JS file in HTML.")
                logger.error(f"HTML snippet (first 1000 chars): {html_content[:1000]}")
                # Fallback idea: check if data is embedded directly? (Unlikely for NIKA)
                return None
            
            js_filename = match.group(1)
            # Handle relative paths if necessary. Usually NIKA puts them in same dir or subpath
            # js_filename might be "js/nika_data.js" or just "nika_data.js"
            # construct full URL
            # basic clean up of leading slashes if domain root is used
            if js_filename.startswith("/"):
                # URL is root relative.
                # Assuming settings.schedule_domain ends with /timetable/
                # We need base root actually.
                # Let's rely on standard URL joining if complex, but simple append works for relative
                # For now assuming relative to /timetable/ page path
                 data_url = "https://xn--64-vlclonee7j.xn--p1ai" + js_filename
            else:
                 # Relative to current path
                 data_url = settings.schedule_domain + js_filename

            logger.info(f"Found data file: {data_url}")

            # 3. Fetch JS Content
            async with session.get(data_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch JS data. Status: {response.status}")
                    return None
                js_content = await response.text()

            # 4. Extract JSON
            # Format is usually: var nika_data = { ... };
            # We strip the prefix and suffix.
            
            # Find the first '{' and the last '}'
            start_idx = js_content.find('{')
            end_idx = js_content.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error("Could not find JSON object in JS file.")
                return None
                
            json_str = js_content[start_idx:end_idx]
            
            # 5. Rough JSON cleanup/validation
            # Sometimes keys are not quoted in older JS.
            # Using regex to quote keys if needed: 
            # re.sub(r'(?<!")(\b\w+\b)(?!":)', r'"\1"', json_str) 
            # But usually standard json.loads fails on comments or trailing commas.
            # Let's try standard load first.
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Standard JSON decode failed: {e}. Attempting cleanup.")
                # Basic cleanup for hanging commas
                json_str_clean = re.sub(r',\s*}', '}', json_str)
                json_str_clean = re.sub(r',\s*]', ']', json_str_clean)
                data = json.loads(json_str_clean)
                
            return data

        except Exception as e:
            logger.exception(f"Parser error: {e}")
            return None

    def normalize_classes(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts class list from raw data.
        Returns list of dicts: {'id': 'class_id', 'name': '10A', 'grade': 10}
        """
        classes = []
        if "CLASSES" not in raw_data:
            return classes

        class_map = raw_data["CLASSES"]
        for cid, cname in class_map.items():
            # Filter out empty or zero classes if necessary
            if not cname or cname == "0": 
                # Sometimes 0 is used for hidden/system classes, but check if it has schedule
                pass
            
            # Try to parse grade level from name (e.g. "10A" -> 10)
            grade = 0
            match = re.search(r'\d+', str(cname))
            if match:
                grade = int(match.group())
            
            classes.append({
                "id": cid,
                "name": str(cname),
                "grade": grade
            })
            
        return classes

    def normalize_teachers(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts teacher list from raw data.
        """
        teachers = []
        if "TEACHERS" not in raw_data:
            return teachers
            
        teacher_map = raw_data["TEACHERS"]
        for tid, tname in teacher_map.items():
            if not tname:
                continue
                
            teachers.append({
                "id": tid,
                "name": str(tname)
            })
            
        return teachers

    def normalize_schedule(self, raw_data: Dict[str, Any]) -> List[LessonRaw]:
        """
        Flattens schedule into list of LessonRaw objects.
        """
        lessons: List[LessonRaw] = []
        
        if "CLASS_SCHEDULE" not in raw_data:
            return lessons
            
        # Dictionaries for lookups
        subjects = raw_data.get("SUBJECTS", {})
        teachers = raw_data.get("TEACHERS", {})
        rooms = raw_data.get("ROOMS", {})
        
        # Get the active schedule period (usually only one key, e.g., "60")
        schedule_periods = raw_data["CLASS_SCHEDULE"]
        if not schedule_periods:
            return lessons
            
        # Take the first available period
        period_key = list(schedule_periods.keys())[0]
        full_schedule = schedule_periods[period_key]
        
        # Iterate over each class's schedule
        for class_id, class_schedule in full_schedule.items():
            if not isinstance(class_schedule, dict):
                continue
                
            # Iterate over lesson slots (e.g., "101" -> Day 1, Lesson 1)
            for slot_key, slot_data in class_schedule.items():
                # Parse slot_key
                # Format appears to be DAA where D is Day (1-7) and AA is Lesson Number (01-15)
                # Ensure it's a digit string
                if not slot_key.isdigit():
                    continue
                    
                val_int = int(slot_key)
                day_num = val_int // 100  # 1 = Monday? Check DAY_NAMES
                lesson_num = val_int % 100
                
                # NIKA usually uses 1-7 for Mon-Sun.
                # Our specific format:
                # "101" -> Day 1.
                # Python datetime uses 0=Mon, 6=Sun.
                # So we verify DAY_NAMES order.
                # Usually DAY_NAMES[1] = "Monday".
                # Standardize to 0-6 (Mon-Sun).
                # If Nika Day 1 = Mon, then day = day_num - 1.
                
                # Extract details
                # slot_data = {'s': ['036'], 't': ['044'], 'r': ['005']}
                # Arrays imply possible multiple teachers/groups.
                
                sub_ids = slot_data.get("s", [])
                teach_ids = slot_data.get("t", [])
                room_ids = slot_data.get("r", [])
                
                # Helper to join multiple names
                def get_names(ids, lookup):
                    return ", ".join([str(lookup.get(i, i)) for i in ids if i])
                
                subj_name = get_names(sub_ids, subjects)
                teach_name = get_names(teach_ids, teachers)
                room_name = get_names(room_ids, rooms)
                
                # Nika lesson nums usually start at 1.
                
                lesson = LessonRaw(
                    class_id=class_id,
                    day=day_num - 1, # Normalize to 0-based
                    number=lesson_num,
                    subject=subj_name,
                    teacher=teach_name,
                    room=room_name
                )
                lessons.append(lesson)
                
        return lessons

    def normalize_substitutions(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses CLASS_EXCHANGE for substitutions.
        Returns list of dicts suitable for Substitution model.
        """
        subs = []
        if "CLASS_EXCHANGE" not in raw_data:
            return subs
            
        exchanges = raw_data["CLASS_EXCHANGE"] # {ClassID: {Date: {Lesson: Data}}}
        subjects = raw_data.get("SUBJECTS", {})
        teachers = raw_data.get("TEACHERS", {})
        rooms = raw_data.get("ROOMS", {})

        for class_id, date_map in exchanges.items():
            if not isinstance(date_map, dict):
                continue
                
            for date_str, lessons_map in date_map.items():
                # date_str is "20.01.2026"
                for slot_key, slot_data in lessons_map.items():
                    if not slot_key.isdigit():
                        continue
                        
                    lesson_num = int(slot_key)
                    
                    # Check for cancellation
                    is_cancelled = False
                    sub_ids = slot_data.get("s", [])
                    
                    if sub_ids == "F":
                        is_cancelled = True
                        subj_name = None
                        teach_name = None
                        room_name = None
                    else:
                         # Extract details
                        teach_ids = slot_data.get("t", [])
                        room_ids = slot_data.get("r", [])
                        
                        # Helper (duplicated from schedule norm, can be refactored)
                        def get_names(ids, lookup):
                            if isinstance(ids, list):
                                return ", ".join([str(lookup.get(i, i)) for i in ids if i])
                            return str(lookup.get(ids, ids)) # Handle single value case if malformed
                        
                        subj_name = get_names(sub_ids, subjects)
                        teach_name = get_names(teach_ids, teachers)
                        room_name = get_names(room_ids, rooms)

                    subs.append({
                        "class_id": class_id,
                        "date": date_str,
                        "lesson_number": lesson_num,
                        "subject_name": subj_name,
                        "teacher_name": teach_name,
                        "room_number": room_name,
                        "is_cancelled": is_cancelled
                    })
        return subs
