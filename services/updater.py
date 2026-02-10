"""
Service for updating schedule data in the database.
"""
import logging
import hashlib
import json
from datetime import time
from sqlalchemy import select, delete, insert, text
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import schedule_controls_kb
from database.session import AsyncSessionLocal, get_db_session
from database.models import Class, Schedule, SystemMeta, User, Substitution, Teacher
from parser.nika_parser import NikaParser
from config import settings

logger = logging.getLogger(__name__)

async def run_update_cycle(bot=None):
    """
    Main update task.
    1. Fetch data
    2. Check hash
    3. Update DB
    4. Notify users (if bot instance provided)
    """
    logger.info("Starting update cycle...")
    parser = NikaParser()
    
    try:
        logger.info("Fetching schedule data from parser...")
        raw_data = await parser.fetch_schedule_data()
        if not raw_data:
            logger.warning("No data fetched from parser (parser returned None).")
            return
        
        logger.info(f"Successfully fetched data. Keys: {list(raw_data.keys())}")

        # Calculate hash
        # Use specific keys to avoid noise from dynamic timestamps/links in JS
        # Only hash the schedule and class structure
        content_to_hash = {
            "CLASSES": raw_data.get("CLASSES"),
            "CLASS_SCHEDULE": raw_data.get("CLASS_SCHEDULE"),
            "TEACHERS": raw_data.get("TEACHERS") 
        }
        data_str = json.dumps(content_to_hash, sort_keys=True)
        new_hash = hashlib.md5(data_str.encode('utf-8')).hexdigest()
        
        async with AsyncSessionLocal() as session:
            # Check old hash
            stmt = select(SystemMeta).where(SystemMeta.key == "schedule_hash")
            result = await session.execute(stmt)
            meta_obj = result.scalar_one_or_none()
            
            old_hash = meta_obj.value if meta_obj else ""
            
            if new_hash == old_hash:
                logger.info("Hash matches. No changes.")
                return
                
            logger.info(f"Hash mismatch ({old_hash} -> {new_hash}). Updating database...")
            
            # Perform Update
            await update_database(session, parser, raw_data)
            
            # Update Hash
            if not meta_obj:
                meta_obj = SystemMeta(key="schedule_hash", value=new_hash)
                session.add(meta_obj)
            else:
                meta_obj.value = new_hash
            await session.commit()
            
            logger.info("Database updated successfully.")
            
            # Notify
            if bot:
                await notify_subscribers(session, bot)

    except Exception as e:
        logger.exception(f"Update cycle failed: {e}")
    finally:
        await parser.close_session()

async def update_database(session: AsyncSession, parser: NikaParser, raw_data: dict):
    """
    Syncs classes and replaces schedule.
    """
    # 1. Sync Classes
    normalized_classes = parser.normalize_classes(raw_data)
    
    # Get existing classes to map external_id -> db_id
    stmt = select(Class)
    result = await session.execute(stmt)
    existing_classes = {c.external_id: c for c in result.scalars().all()}
    
    db_class_map = {} # external_id -> valid Class object
    
    for cls_data in normalized_classes:
        ext_id = cls_data['id']
        name = cls_data['name']
        grade = cls_data['grade']
        
        if ext_id in existing_classes:
            # Update name/grade if changed?
            db_cls = existing_classes[ext_id]
            if db_cls.name != name:
                db_cls.name = name
            if db_cls.grade_level != grade:
                db_cls.grade_level = grade
            db_class_map[ext_id] = db_cls
        else:
            new_cls = Class(name=name, external_id=ext_id, grade_level=grade)
            session.add(new_cls)
            # Flush to get ID?
            # We need to process all classes first.
            # Let's add them to map (will be transient until commit/flush)
            db_class_map[ext_id] = new_cls
    
    await session.flush() # Ensure new classes have IDs
    
    # Refresh map with IDs
    # Actually we can just rely on object ref
    
    # 1.5 Sync Teachers
    logger.info("Syncing teachers...")
    teachers_data = parser.normalize_teachers(raw_data)
    
    # Get existing teachers
    stmt = select(Teacher.external_id)
    result = await session.execute(stmt)
    existing_teacher_ids = set(result.scalars().all())
    
    new_teachers_list = []
    for t in teachers_data:
        if t["id"] not in existing_teacher_ids:
            new_teachers_list.append(Teacher(
                name=t["name"],
                external_id=t["id"]
            ))
            
    if new_teachers_list:
        session.add_all(new_teachers_list)
        logger.info(f"Added {len(new_teachers_list)} new teachers.")
    
    await session.flush()

    # 2. Update Schedule
    # Strategy: Wipe all schedules. Simple and effective for <10k rows.
    logger.info("Clearing old schedule entries...")
    await session.execute(delete(Schedule))
    
    schedule_data = parser.normalize_schedule(raw_data)
    
    # Create a map from external_id to internal DB ID for classes
    class_map = {cls.external_id: cls.id for cls in db_class_map.values()}

    # 5. Insert new schedule
    logger.info(f"Inserting {len(schedule_data)} schedule entries...")
    stmt = insert(Schedule).values([
        {
            "class_id": class_map.get(str(l.class_id)),
            "day_of_week": l.day,
            "lesson_number": l.number,
            "subject_name": l.subject,
            "teacher_name": l.teacher,
            "room_number": l.room,
            "is_substitution": False
        }
        for l in schedule_data
        if str(l.class_id) in class_map
    ])
    if len(schedule_data) > 0:
        await session.execute(stmt)

    # 6. Process Substitutions
    logger.info("Processing Substitutions...")
    subs_data = parser.normalize_substitutions(raw_data)
    
    # Clear old substitutions? Or just overwrite?
    # For simplicity, let's clear all substitutions for now as we re-fetch full data.
    # Ideally we only clear for the dates we fetched?
    # Nika export usually contains valid future subs.
    await session.execute(text("DELETE FROM substitutions"))
    
    if subs_data:
        # Prepare subs with mapped class_id
        valid_subs = []
        for sub in subs_data:
            internal_cid = class_map.get(str(sub["class_id"]))
            if internal_cid:
                sub["class_id"] = internal_cid
                valid_subs.append(sub)
        
        if valid_subs:
            stmt_subs = insert(Substitution).values(valid_subs)
            await session.execute(stmt_subs)
        logger.info(f"Inserted {len(valid_subs)} substitutions.")
        
    # Commit handled by caller (run_update_cycle)

async def notify_subscribers(session: AsyncSession, bot):
    """
    Sends notification to subscribed users.
    """
    stmt = select(User).where(User.notification_enabled == True)
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    count = 0
    for user in users:
        try:
            await bot.send_message(user.telegram_id, "🔔 Расписание обновилось! Проверьте изменения.")
            count += 1
        except Exception:
            # Blocked bot etc.
            pass
    logger.info(f"Sent notifications to {count} users.")
