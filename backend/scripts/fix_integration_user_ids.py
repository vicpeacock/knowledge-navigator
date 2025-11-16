"""Script to fix integrations with user_id = NULL by assigning them to the correct user"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.database import Integration, User, Tenant
from app.core.config import settings
from uuid import UUID


async def fix_integrations():
    """Fix integrations with user_id = NULL by finding the user from the OAuth state"""
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
        
        # Get all integrations with user_id = NULL
        result = await db.execute(
            select(Integration)
            .where(
                Integration.tenant_id == tenant_id,
                Integration.user_id.is_(None),
                Integration.service_type.in_(["calendar", "email"])
            )
        )
        integrations = result.scalars().all()
        
        if not integrations:
            print("✅ No integrations with user_id = NULL found.")
            return
        
        print(f"📊 Found {len(integrations)} integration(s) with user_id = NULL:\n")
        
        # Get user vic.pippo@gmail.com
        user_result = await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == "vic.pippo@gmail.com"
            )
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ User vic.pippo@gmail.com not found")
            print("   Please create the user first or specify a different email")
            return
        
        print(f"👤 Found user: {user.email} (ID: {user.id})\n")
        
        for integ in integrations:
            print(f"   - {integ.service_type}/{integ.provider} (ID: {integ.id})")
        
        # Ask for confirmation
        print(f"\n⚠️  This will assign all {len(integrations)} integration(s) to user: {user.email}")
        response = input("   Continue? (yes/no): ").strip().lower()
        
        if response != "yes":
            print("❌ Operation cancelled")
            return
        
        # Update integrations
        updated_count = 0
        for integ in integrations:
            integ.user_id = user.id
            updated_count += 1
        
        await db.commit()
        
        print(f"\n✅ Successfully assigned {updated_count} integration(s) to user {user.email}")
        
        await db.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix_integrations())

