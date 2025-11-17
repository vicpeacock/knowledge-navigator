#!/usr/bin/env python3
"""
Verifica che tutti i modelli del database abbiano tenant_id e siano correttamente configurati per multi-tenancy.
"""
import sys
from pathlib import Path
import inspect
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.models.database import Base
import app.models.database as db_module

def check_model_has_tenant_id(model_class):
    """Verifica se un modello ha tenant_id"""
    if not hasattr(model_class, '__table__'):
        return None, "No __table__ attribute"
    
    table = model_class.__table__
    tenant_col = table.columns.get('tenant_id')
    
    if tenant_col is None:
        return False, "No tenant_id column"
    
    # Verifica che sia nullable=False (richiesto)
    is_nullable = tenant_col.nullable
    has_fk = any(isinstance(fk, ForeignKey) for fk in tenant_col.foreign_keys)
    
    return True, {
        "nullable": is_nullable,
        "has_foreign_key": has_fk,
        "type": str(tenant_col.type)
    }

def main():
    """Verifica tutti i modelli"""
    print("🔍 Verifica Multi-Tenancy nei Modelli del Database\n")
    
    # Trova tutti i modelli che ereditano da Base
    models = []
    for name, obj in inspect.getmembers(db_module):
        if (inspect.isclass(obj) and 
            issubclass(obj, Base) and 
            obj != Base and
            hasattr(obj, '__tablename__')):
            models.append((name, obj))
    
    print(f"Trovati {len(models)} modelli:\n")
    
    issues = []
    all_ok = True
    
    for model_name, model_class in sorted(models):
        has_tenant, info = check_model_has_tenant_id(model_class)
        
        if has_tenant is None:
            print(f"⚠️  {model_name}: {info}")
            continue
        
        if has_tenant:
            nullable = info.get("nullable", True)
            fk = info.get("has_foreign_key", False)
            
            if nullable:
                issues.append(f"{model_name}: tenant_id è nullable=True (dovrebbe essere False)")
                all_ok = False
                print(f"❌ {model_name}: tenant_id nullable=True")
            elif not fk:
                issues.append(f"{model_name}: tenant_id non ha foreign key a tenants")
                all_ok = False
                print(f"❌ {model_name}: tenant_id senza foreign key")
            else:
                print(f"✅ {model_name}: tenant_id configurato correttamente")
        else:
            # Verifica se è un modello che NON dovrebbe avere tenant_id
            # (es. Tenant stesso)
            if model_name == "Tenant":
                print(f"✅ {model_name}: Non richiede tenant_id (è il modello Tenant)")
            else:
                issues.append(f"{model_name}: {info}")
                all_ok = False
                print(f"❌ {model_name}: {info}")
    
    print("\n" + "="*60)
    if all_ok and not issues:
        print("✅ Tutti i modelli sono correttamente configurati per multi-tenancy!")
    else:
        print(f"❌ Trovati {len(issues)} problemi:")
        for issue in issues:
            print(f"   - {issue}")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

