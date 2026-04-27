#!/usr/bin/env python3
"""
Script to fix migration state when database is partially migrated.
This checks what tables/columns exist and stamps the appropriate migration.
"""

import asyncio
import sys
from sqlalchemy import text, inspect
from database.db import engine


async def check_database_state():
    """Check what tables and columns exist in the database."""
    async with engine.connect() as conn:
        # Check if alembic_version table exists
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'alembic_version'
            );
        """))
        has_alembic = result.scalar()
        
        if has_alembic:
            result = await conn.execute(text("SELECT version_num FROM alembic_version"))
            current_version = result.scalar()
            print(f"✓ Alembic version table exists. Current version: {current_version}")
            return current_version
        else:
            print("✗ No alembic_version table found")
        
        # Check what tables exist
        result = await conn.execute(text("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """))
        tables = [row[0] for row in result.fetchall()]
        print(f"\nExisting tables: {', '.join(tables)}")
        
        # Check users table columns
        if 'users' in tables:
            result = await conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'users' 
                ORDER BY ordinal_position;
            """))
            columns = [row[0] for row in result.fetchall()]
            print(f"\nUsers table columns: {', '.join(columns)}")
            
            # Determine which migration to stamp based on what exists
            has_locale = 'locale' in columns
            has_roles = 'roles' in tables
            has_mentor_events = 'mentor_events' in tables
            has_meeting_bookings = 'meeting_bookings' in tables
            has_app_settings = 'app_settings' in tables
            has_dynamic_content = 'dynamic_content' in tables
            
            print(f"\nMigration state analysis:")
            print(f"  v2_core_001 (user columns + mentors): {'✓' if has_locale and has_roles else '✗'}")
            print(f"  v2_core_002 (mentor_events): {'✓' if has_mentor_events else '✗'}")
            print(f"  v2_core_003 (meeting_bookings): {'✓' if has_meeting_bookings else '✗'}")
            print(f"  v2_core_004 (app_settings): {'✓' if has_app_settings else '✗'}")
            print(f"  v2_core_005 (dynamic_content): {'✓' if has_dynamic_content else '✗'}")
            
            # Determine which version to stamp
            if has_dynamic_content:
                return 'v2_core_005'
            elif has_app_settings:
                return 'v2_core_004'
            elif has_meeting_bookings:
                return 'v2_core_003'
            elif has_mentor_events:
                return 'v2_core_002'
            elif has_locale and has_roles:
                return 'v2_core_001'
            else:
                return None
        
        return None


async def stamp_version(version):
    """Stamp the database with a specific migration version."""
    async with engine.connect() as conn:
        # Create alembic_version table if it doesn't exist
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS alembic_version (
                version_num VARCHAR(32) NOT NULL,
                CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
            );
        """))
        
        # Delete any existing version
        await conn.execute(text("DELETE FROM alembic_version"))
        
        # Insert new version
        await conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": version}
        )
        
        await conn.commit()
        print(f"\n✓ Database stamped with version: {version}")


async def main():
    print("=" * 60)
    print("SENU Bot - Migration State Fixer")
    print("=" * 60)
    print()
    
    try:
        current_version = await check_database_state()
        
        if current_version:
            print(f"\n✓ Database is already at version: {current_version}")
            print("\nYou can now run: alembic upgrade head")
            return
        
        print("\n" + "=" * 60)
        print("Recommended action:")
        print("=" * 60)
        
        # Check what version to stamp
        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'dynamic_content';
            """))
            has_dynamic = result.scalar()
            
            if has_dynamic:
                stamp_to = 'v2_core_005'
            else:
                result = await conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' AND table_name = 'app_settings';
                """))
                has_settings = result.scalar()
                
                if has_settings:
                    stamp_to = 'v2_core_004'
                else:
                    result = await conn.execute(text("""
                        SELECT table_name FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'meeting_bookings';
                    """))
                    has_bookings = result.scalar()
                    
                    if has_bookings:
                        stamp_to = 'v2_core_003'
                    else:
                        result = await conn.execute(text("""
                            SELECT table_name FROM information_schema.tables 
                            WHERE table_schema = 'public' AND table_name = 'mentor_events';
                        """))
                        has_events = result.scalar()
                        
                        if has_events:
                            stamp_to = 'v2_core_002'
                        else:
                            result = await conn.execute(text("""
                                SELECT column_name FROM information_schema.columns 
                                WHERE table_name = 'users' AND column_name = 'locale';
                            """))
                            has_locale = result.scalar()
                            
                            if has_locale:
                                stamp_to = 'v2_core_001'
                            else:
                                stamp_to = None
        
        if stamp_to:
            print(f"\nStamp database to version: {stamp_to}")
            response = input("\nProceed? (yes/no): ").strip().lower()
            
            if response == 'yes':
                await stamp_version(stamp_to)
                print("\n✓ Done! Now run: alembic upgrade head")
            else:
                print("\nCancelled.")
        else:
            print("\nDatabase appears to be empty or in an unknown state.")
            print("You can run: alembic upgrade head")
            print("(It will create all tables from scratch)")
    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
