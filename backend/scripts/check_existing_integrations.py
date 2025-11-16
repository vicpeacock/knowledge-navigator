"""Script to check existing integrations and their user_id values"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from app.models.database import Integration, User, Tenant
from app.core.config import settings
from uuid import UUID


async def check_integrations():
    """Check existing integrations and their user_id values"""
    # Create database connection
    database_url = settings.database_url
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get default tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.schema_name == "tenant_default").limit(1)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            print("❌ Default tenant not found")
            return
        
        tenant_id = tenant.id
        print(f"✅ Using tenant: {tenant.name} (ID: {tenant_id})\n")
        
        # Get all integrations for this tenant
        result = await db.execute(
            select(Integration)
            .where(Integration.tenant_id == tenant_id)
            .order_by(Integration.service_type, Integration.provider)
        )
        integrations = result.scalars().all()
        
        print(f"📊 Found {len(integrations)} integration(s):\n")
        
        # Group by service type
        by_service = {}
        for integ in integrations:
            service_type = integ.service_type
            if service_type not in by_service:
                by_service[service_type] = []
            by_service[service_type].append(integ)
        
        for service_type, integs in by_service.items():
            print(f"🔹 {service_type.upper()}: {len(integs)} integration(s)")
            for integ in integs:
                user_id_str = str(integ.user_id) if integ.user_id else "NULL (global)"
                user_email = "N/A"
                if integ.user_id:
                    user_result = await db.execute(
                        select(User).where(User.id == integ.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        user_email = user.email
                
                print(f"   - ID: {integ.id}")
                print(f"     Provider: {integ.provider}")
                print(f"     Enabled: {integ.enabled}")
                print(f"     User ID: {user_id_str}")
                if integ.user_id:
                    print(f"     User Email: {user_email}")
                print()
        
        # Count integrations by user_id
        null_count = sum(1 for i in integrations if i.user_id is None)
        user_count = len(integrations) - null_count
        
        print(f"\n📈 Summary:")
        print(f"   - Global integrations (user_id = NULL): {null_count}")
        print(f"   - User-specific integrations: {user_count}")
        
        # Get admin user
        admin_result = await db.execute(
            select(User)
            .where(User.tenant_id == tenant_id, User.role == "admin")
            .limit(1)
        )
        admin = admin_result.scalar_one_or_none()
        
        if admin:
            print(f"\n👤 Admin user: {admin.email} (ID: {admin.id})")
            print(f"\n💡 Options:")
            print(f"   1. Assign all NULL integrations to admin user")
            print(f"   2. Delete all NULL integrations")
            print(f"   3. Keep NULL integrations as global (visible to all users)")
            print(f"\n   To assign to admin, run:")
            print(f"   python scripts/migrate_integrations_to_admin.py")
        
        await db.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_integrations())

