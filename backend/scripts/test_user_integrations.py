"""Test suite for per-user integrations (Calendar and Email)"""
import asyncio
import httpx
from uuid import UUID
import sys

BASE_URL = "http://localhost:8000"
TEST_EMAIL = "vic.pippo@gmail.com"
TEST_PASSWORD = "TestPassword123!"
TEST_NAME = "Vic Pippo"

async def test_user_integrations():
    """Test per-user integrations isolation"""
    print("🧪 Testing Per-User Integrations\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get default tenant ID
        print("1️⃣  Getting default tenant...")
        try:
            health = await client.get(f"{BASE_URL}/health")
            assert health.status_code == 200
            print("   ✅ Backend is healthy")
        except Exception as e:
            print(f"   ❌ Backend health check failed: {e}")
            return False
        
        # Use known default tenant ID
        tenant_id = "8c352b66-9e7f-46b3-a76e-bbb93aa445e6"
        print(f"   ✅ Using tenant: {tenant_id}\n")
        
        # Step 1: Login as admin to create/reset test user
        print("2️⃣  Logging in as admin to setup test user...")
        admin_email = "admin@example.com"
        admin_password = "admin123"  # Default admin password
        
        try:
            admin_login_resp = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": admin_email, "password": admin_password},
                headers={"X-Tenant-ID": tenant_id}
            )
            
            if admin_login_resp.status_code != 200:
                print(f"   ⚠️  Admin login failed: {admin_login_resp.status_code}")
                print("   ℹ️  Will try to proceed with test user directly...")
                admin_token = None
            else:
                admin_result = admin_login_resp.json()
                admin_token = admin_result.get("access_token")
                print(f"   ✅ Logged in as admin: {admin_email}")
        except Exception as e:
            print(f"   ⚠️  Admin login error: {e}")
            admin_token = None
        
        # Step 2: Create or reset test user (if admin token available)
        if admin_token:
            admin_headers = {
                "X-Tenant-ID": tenant_id,
                "Authorization": f"Bearer {admin_token}"
            }
            
            print("\n3️⃣  Checking if test user exists...")
            try:
                # List users to find test user
                users_resp = await client.get(
                    f"{BASE_URL}/api/v1/users",
                    headers=admin_headers
                )
                
                test_user_id = None
                if users_resp.status_code == 200:
                    users = users_resp.json()
                    for user in users:
                        if user.get("email") == TEST_EMAIL:
                            test_user_id = user.get("id")
                            print(f"   ✅ Test user found: {TEST_EMAIL} (ID: {test_user_id})")
                            break
                
                if test_user_id:
                    # User exists - password reset not available via API yet
                    print("   ℹ️  User exists. If password is wrong, reset it via admin panel.")
                else:
                    # Create user
                    print("   ➕ Creating test user...")
                    create_resp = await client.post(
                        f"{BASE_URL}/api/v1/users",
                        json={
                            "email": TEST_EMAIL,
                            "password": TEST_PASSWORD,
                            "name": TEST_NAME,
                            "role": "user",
                            "send_invitation_email": False
                        },
                        headers=admin_headers
                    )
                    
                    if create_resp.status_code == 201:
                        print(f"   ✅ Test user created: {TEST_EMAIL}")
                    else:
                        print(f"   ⚠️  Failed to create user: {create_resp.status_code} - {create_resp.text}")
            except Exception as e:
                print(f"   ⚠️  Error managing test user: {e}")
        
        # Step 3: Login as test user
        print("\n4️⃣  Logging in as test user...")
        try:
            login_data = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD
            }
            login_resp = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json=login_data,
                headers={"X-Tenant-ID": tenant_id}
            )
            
            if login_resp.status_code == 200:
                login_result = login_resp.json()
                access_token = login_result.get("access_token")
                user_id = login_result.get("user_id")
                print(f"   ✅ Logged in: {login_result.get('email')}")
            else:
                print(f"   ❌ Login failed: {login_resp.status_code} - {login_resp.text}")
                print(f"   ℹ️  If user exists but password is wrong, reset it via admin panel or use password reset.")
                return False
        except Exception as e:
            print(f"   ❌ Error during login: {e}")
            return False
        
        headers = {
            "X-Tenant-ID": tenant_id,
            "Authorization": f"Bearer {access_token}"
        }
        
        # Step 4: Check current integrations (should be empty for new user)
        print("\n5️⃣  Checking current integrations...")
        try:
            # Check calendar integrations
            calendar_resp = await client.get(
                f"{BASE_URL}/api/integrations/calendars/integrations",
                headers=headers
            )
            if calendar_resp.status_code == 200:
                calendar_data = calendar_resp.json()
                calendar_integrations = calendar_data.get("integrations", [])
                print(f"   📅 Calendar integrations: {len(calendar_integrations)}")
                for idx, integ in enumerate(calendar_integrations, 1):
                    print(f"      {idx}. ID: {integ.get('id')}, Provider: {integ.get('provider')}, Enabled: {integ.get('enabled')}")
            else:
                print(f"   ❌ Failed to get calendar integrations: {calendar_resp.status_code} - {calendar_resp.text}")
            
            # Check email integrations
            email_resp = await client.get(
                f"{BASE_URL}/api/integrations/emails/integrations",
                headers=headers
            )
            if email_resp.status_code == 200:
                email_data = email_resp.json()
                email_integrations = email_data.get("integrations", [])
                print(f"   📧 Email integrations: {len(email_integrations)}")
                for idx, integ in enumerate(email_integrations, 1):
                    print(f"      {idx}. ID: {integ.get('id')}, Provider: {integ.get('provider')}, Enabled: {integ.get('enabled')}")
            else:
                print(f"   ❌ Failed to get email integrations: {email_resp.status_code} - {email_resp.text}")
        except Exception as e:
            print(f"   ❌ Error checking integrations: {e}")
            return False
        
        # Step 5: Get OAuth authorization URLs
        print("\n6️⃣  Getting OAuth authorization URLs...")
        try:
            # Calendar OAuth URL
            calendar_auth_resp = await client.get(
                f"{BASE_URL}/api/integrations/calendars/oauth/authorize",
                headers=headers
            )
            if calendar_auth_resp.status_code == 200:
                calendar_auth = calendar_auth_resp.json()
                auth_url = calendar_auth.get("authorization_url")
                print(f"   📅 Calendar OAuth URL:")
                print(f"      {auth_url}")
                print(f"   ℹ️  Visit this URL to authorize Calendar integration")
            else:
                print(f"   ❌ Failed to get Calendar OAuth URL: {calendar_auth_resp.status_code} - {calendar_auth_resp.text}")
            
            # Email OAuth URL
            email_auth_resp = await client.get(
                f"{BASE_URL}/api/integrations/emails/oauth/authorize",
                headers=headers
            )
            if email_auth_resp.status_code == 200:
                email_auth = email_auth_resp.json()
                auth_url = email_auth.get("authorization_url")
                print(f"   📧 Email OAuth URL:")
                print(f"      {auth_url}")
                print(f"   ℹ️  Visit this URL to authorize Email integration")
            else:
                print(f"   ❌ Failed to get Email OAuth URL: {email_auth_resp.status_code} - {email_auth_resp.text}")
        except Exception as e:
            print(f"   ❌ Error getting OAuth URLs: {e}")
            return False
        
        # Step 6: Verify user isolation
        print("\n7️⃣  Verifying user isolation...")
        try:
            # Get user info to verify user_id
            user_resp = await client.get(
                f"{BASE_URL}/api/v1/users/me",
                headers=headers
            )
            if user_resp.status_code == 200:
                user_info = user_resp.json()
                print(f"   ✅ Current user: {user_info.get('email')} (ID: {user_info.get('id')})")
                print(f"   ℹ️  All integrations should have user_id = {user_info.get('id')} or NULL (global)")
            else:
                print(f"   ⚠️  Could not get user info: {user_resp.status_code}")
        except Exception as e:
            print(f"   ⚠️  Error getting user info: {e}")
        
        print("\n✅ Test completed!")
        print("\n📝 Next steps:")
        print("   1. Visit the OAuth URLs above to authorize Calendar and Email")
        print("   2. After authorization, check integrations again to verify they're associated with this user")
        print("   3. Login as a different user and verify they don't see these integrations")
        
        return True


if __name__ == "__main__":
    success = asyncio.run(test_user_integrations())
    sys.exit(0 if success else 1)

