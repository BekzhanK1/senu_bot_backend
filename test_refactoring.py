"""
Quick test script to verify refactoring works correctly.
Run this after refactoring to ensure everything is functional.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_imports():
    """Test that all new modules can be imported."""
    print("Testing imports...")
    
    try:
        from services.notification_service import NotificationService
        from services.request_service import RequestService
        from services.meeting_service import MeetingService
        from services.broadcast_service import BroadcastService
        from services.audit_service import AuditService
        from services.container import ServiceContainer, init_services, get_services
        print("✅ Services import OK")
    except ImportError as e:
        print(f"❌ Services import failed: {e}")
        return False
    
    try:
        from routers.requests_router import router as requests_router
        from routers.admin_router import router as admin_router
        from routers.meetings_router import router as meetings_router
        from routers.settings_router import router as settings_router
        print("✅ Routers import OK")
    except ImportError as e:
        print(f"❌ Routers import failed: {e}")
        return False
    
    try:
        from utils.security import (
            verify_internal_token,
            verify_admin_access,
            verify_mentor_access,
            rate_limit,
            RateLimiter,
        )
        print("✅ Security utils import OK")
    except ImportError as e:
        print(f"❌ Security utils import failed: {e}")
        return False
    
    try:
        from api_server import create_api_app
        print("✅ API server import OK")
    except ImportError as e:
        print(f"❌ API server import failed: {e}")
        return False
    
    return True


async def test_service_container():
    """Test service container initialization."""
    print("\nTesting service container...")
    
    try:
        from unittest.mock import Mock
        from aiogram import Bot
        from services.container import init_services, get_services
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        
        # Initialize services
        container = init_services(mock_bot)
        print("✅ Service container initialized")
        
        # Test getting services
        services = get_services()
        assert services is container
        print("✅ get_services() works")
        
        # Test service properties
        assert services.notification_service is not None
        print("✅ notification_service accessible")
        
        assert services.request_service is not None
        print("✅ request_service accessible")
        
        assert services.meeting_service is not None
        print("✅ meeting_service accessible")
        
        assert services.broadcast_service is not None
        print("✅ broadcast_service accessible")
        
        assert services.audit_service is not None
        print("✅ audit_service accessible")
        
        return True
    except Exception as e:
        print(f"❌ Service container test failed: {e}")
        return False


async def test_rate_limiter():
    """Test rate limiter functionality."""
    print("\nTesting rate limiter...")
    
    try:
        from utils.security import RateLimiter
        
        limiter = RateLimiter(max_requests=3, window_seconds=1)
        
        # Should allow first 3 requests
        assert limiter.check_rate_limit("test_key") is True
        assert limiter.check_rate_limit("test_key") is True
        assert limiter.check_rate_limit("test_key") is True
        print("✅ Rate limiter allows requests within limit")
        
        # Should block 4th request
        assert limiter.check_rate_limit("test_key") is False
        print("✅ Rate limiter blocks requests over limit")
        
        # Wait for window to expire
        await asyncio.sleep(1.1)
        
        # Should allow again
        assert limiter.check_rate_limit("test_key") is True
        print("✅ Rate limiter resets after window")
        
        return True
    except Exception as e:
        print(f"❌ Rate limiter test failed: {e}")
        return False


async def test_api_app_creation():
    """Test API app can be created."""
    print("\nTesting API app creation...")
    
    try:
        from unittest.mock import Mock
        from aiogram import Bot
        from api_server import create_api_app
        from services.container import init_services
        
        # Create mock bot
        mock_bot = Mock(spec=Bot)
        
        # Initialize services first
        init_services(mock_bot)
        
        # Create app
        app = create_api_app(mock_bot)
        print("✅ API app created successfully")
        
        # Check routes are registered
        routes = [route.path for route in app.routes]
        
        assert "/health" in routes
        print("✅ Health endpoint registered")
        
        # Check some key endpoints exist
        api_routes = [r for r in routes if r.startswith("/api/")]
        assert len(api_routes) > 0
        print(f"✅ {len(api_routes)} API routes registered")
        
        return True
    except Exception as e:
        print(f"❌ API app creation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("REFACTORING VERIFICATION TESTS")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Imports", await test_imports()))
    results.append(("Service Container", await test_service_container()))
    results.append(("Rate Limiter", await test_rate_limiter()))
    results.append(("API App Creation", await test_api_app_creation()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name:.<40} {status}")
    
    all_passed = all(result[1] for result in results)
    
    print("=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED! Refactoring is working correctly.")
        print("\nYou can now:")
        print("1. Run 'python bot.py' to start the bot")
        print("2. Test API endpoints with curl or Postman")
        print("3. Verify frontend still works")
    else:
        print("⚠️  SOME TESTS FAILED! Please review the errors above.")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
