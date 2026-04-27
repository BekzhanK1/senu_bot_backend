#!/usr/bin/env python3
"""
Setup script to create the first admin user for SENU Bot.
Run this after running migrations to set up your first admin.
"""

import asyncio
import sys
from dotenv import load_dotenv

load_dotenv()


async def setup_admin():
    """Create the first admin user."""
    from database.db import init_db, add_user, create_mentor, assign_role_to_mentor, get_user
    
    print("=" * 60)
    print("SENU Bot - Admin Setup")
    print("=" * 60)
    print()
    
    # Initialize database
    print("Initializing database...")
    await init_db()
    print("✓ Database initialized")
    print()
    
    # Get admin details
    print("Enter admin details:")
    print("-" * 60)
    
    try:
        admin_telegram_id = int(input("Telegram ID (numeric): ").strip())
    except ValueError:
        print("❌ Error: Telegram ID must be a number")
        sys.exit(1)
    
    admin_username = input("Telegram username (without @, optional): ").strip() or None
    admin_name = input("Full name: ").strip()
    
    if not admin_name:
        print("❌ Error: Full name is required")
        sys.exit(1)
    
    display_name = input(f"Display name (default: {admin_name}): ").strip() or admin_name
    
    print()
    print("Creating admin user...")
    print("-" * 60)
    
    # Check if user already exists
    existing_user = await get_user(admin_telegram_id)
    if existing_user:
        print(f"ℹ User already exists: {existing_user.full_name}")
    else:
        # Create user
        await add_user(
            telegram_id=admin_telegram_id,
            username=admin_username,
            full_name=admin_name
        )
        print(f"✓ User created: {admin_name}")
    
    # Create mentor
    try:
        success = await create_mentor(
            user_id=admin_telegram_id,
            display_name=display_name
        )
        if success:
            print(f"✓ Mentor profile created: {display_name}")
        else:
            print("ℹ Mentor profile already exists")
    except Exception as e:
        print(f"⚠ Mentor creation: {e}")
    
    # Assign admin role
    try:
        await assign_role_to_mentor(admin_telegram_id, "admin")
        print("✓ Admin role assigned")
    except Exception as e:
        print(f"⚠ Role assignment: {e}")
    
    # Assign mentor role (for good measure)
    try:
        await assign_role_to_mentor(admin_telegram_id, "mentor")
        print("✓ Mentor role assigned")
    except Exception as e:
        print(f"⚠ Mentor role: {e}")
    
    print()
    print("=" * 60)
    print("✅ Setup Complete!")
    print("=" * 60)
    print()
    print(f"Admin user: {admin_name} (ID: {admin_telegram_id})")
    print(f"Roles: admin, mentor")
    print()
    print("Next steps:")
    print("1. Start the bot: python bot.py")
    print("2. Send /admin command in Telegram to verify access")
    print("3. Use the admin panel to manage content and users")
    print()
    print("For more information, see DYNAMIC_SYSTEM.md")
    print()


async def list_admins():
    """List all current admins."""
    from database.db import init_db, get_all_mentors, get_user_roles
    
    await init_db()
    
    print("=" * 60)
    print("Current Admins")
    print("=" * 60)
    print()
    
    mentors = await get_all_mentors()
    
    if not mentors:
        print("No mentors found.")
        return
    
    admin_count = 0
    for mentor, full_name, username in mentors:
        roles = await get_user_roles(mentor.user_id)
        role_names = [r["name"] for r in roles]
        
        if "admin" in role_names:
            admin_count += 1
            username_str = f"@{username}" if username else "—"
            print(f"• {full_name} ({username_str})")
            print(f"  ID: {mentor.user_id}")
            print(f"  Display: {mentor.display_name}")
            print(f"  Roles: {', '.join(role_names)}")
            print()
    
    if admin_count == 0:
        print("No admins found. Run 'python setup_admin.py' to create one.")
    else:
        print(f"Total admins: {admin_count}")
    print()


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        asyncio.run(list_admins())
    else:
        asyncio.run(setup_admin())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
