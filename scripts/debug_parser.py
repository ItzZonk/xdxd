
import asyncio
import logging
import sys
import json
from parser.nika_parser import NikaParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def main():
    parser = NikaParser()
    try:
        data = await parser.fetch_schedule_data()
        if data:
            logger.info("Successfully fetched data!")
            logger.info(f"Top level keys: {list(data.keys())}")
            
            # Save to file for inspection
            with open("debug_schedule_data.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("Saved data to debug_schedule_data.json")
            
                
            # Test Normalization
            logger.info("--- Testing Normalization ---")
            
            classes = parser.normalize_classes(data)
            logger.info(f"Normalized {len(classes)} classes.")
            if classes:
                logger.info(f"Sample class: {classes[0]}")
                
            lessons = parser.normalize_schedule(data)
            logger.info(f"Normalized {len(lessons)} lessons.")
            if lessons:
                logger.info(f"Sample lesson: {lessons[0]}")
        else:
            logger.error("Failed to fetch data.")
    finally:
        await parser.close_session()

if __name__ == "__main__":
    asyncio.run(main())
