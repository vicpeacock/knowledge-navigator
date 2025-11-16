"""Script to migrate existing integrations (user_id = NULL) to admin user"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from app.models.database import Integration, User, Tenant
from app.core.config import settings


async def migrate_integrations():
    """Migrate integrations with user_id = NULL to admin user"""
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
        
        # Get admin user
        admin_result = await db.execute(
            select(User)
            .where(User.tenant_id == tenant_id, User.role == "admin")
            .limit(1)
        )
        admin = admin_result.scalar_one_or_none()
        
        if not admin:
            print("❌ Admin user not found")
            return
        
        print(f"👤 Admin user: {admin.email} (ID: {admin.id})\n")
        
        # Get all integrations with user_id = NULL
        result = await db.execute(
            select(Integration)
            .where(
                Integration.tenant_id == tenant_id,
                Integration.user_id.is_(None)
            )
        )
        integrations = result.scalars().all()
        
        if not integrations:
            print("✅ No integrations with user_id = NULL found. Nothing to migrate.")
            return
        
        print(f"📊 Found {len(integrations)} integration(s) to migrate:\n")
        
        for integ in integrations:
            print(f"   - {integ.service_type}/{integ.provider} (ID: {integ.id})")
        
        # Ask for confirmation
        print(f"\n⚠️  This will assign all {len(integrations)} integration(s) to admin user: {admin.email}")
        response = input("   Continue? (yes/no): ").strip().lower()
        
        if response != "yes":
            print("❌ Migration cancelled")
            return
        
        # Update integrations
        updated_count = 0
        for integ in integrations:
            integ.user_id = admin.id
            updated_count += 1
        
        await db.commit()
        
        print(f"\n✅ Successfully migrated {updated_count} integration(s) to admin user")
        print(f"   Admin user ({admin.email}) now owns these integrations")
        print(f"   Other users will not see these integrations anymore")
        
        await db.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_integrations())

