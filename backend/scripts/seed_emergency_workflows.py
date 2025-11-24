"""
Seed Emergency Workflows - V1

Creates the water_leak emergency workflow template in the database.
"""

import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import models
import sys
from pathlib import Path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.models.emergency_workflow import EmergencyWorkflow
from app.core.config import settings


WATER_LEAK_WORKFLOW = {
    "workflow_type": "water_leak",
    "workflow_name": "Dégât des eaux - Procédure standard",
    "metadata": {
        "estimated_duration_minutes": 15,
        "critical": True,
        "auto_execute": False,
        "version": 1
    },
    "steps": [
        {
            "step_id": 1,
            "step_order": 1,
            "action_type": "notify_owner",
            "title": "Notifier le propriétaire",
            "description": "Avertir immédiatement le copropriétaire du logement impacté",
            "requires_user_validation": True,
            "is_critical": True,
            "estimated_time_seconds": 30,
            "payload_template": {
                "email_subject": "🚨 Urgence : Dégât des eaux dans votre logement",
                "email_body_template": """Bonjour {{owner_name}},

Nous vous informons qu'un dégât des eaux a été détecté dans votre logement n°{{apartment_number}} situé au {{floor}}ème étage de {{building_name}}.

**Situation actuelle :**
{{incident_description}}

**Actions déjà prises :**
{{actions_taken}}

**Gravité :** {{severity}}

Nous vous demandons de nous contacter au plus vite pour coordonner l'intervention.

En cas d'urgence : [Numéro de téléphone du syndic]

Cordialement,
Le Syndic""",
                "recipient_source": "owner_from_SQL",
                "required_fields": ["owner_name", "apartment_number", "floor", "building_name", "incident_description", "actions_taken", "severity"]
            },
            "workflow_action": "send_email",
            "n8n_node_type": "email"
        },
        {
            "step_id": 2,
            "step_order": 2,
            "action_type": "notify_neighbors",
            "title": "Informer les voisins",
            "description": "Prévenir les copropriétaires des étages inférieurs ou adjacents d'un risque potentiel",
            "requires_user_validation": True,
            "is_critical": False,
            "estimated_time_seconds": 45,
            "payload_template": {
                "email_subject": "Information importante : Incident technique dans l'immeuble",
                "email_body_template": """Bonjour,

Nous vous informons qu'un incident technique (dégât des eaux) a été détecté au {{floor}}ème étage de {{building_name}}.

Par mesure de précaution, nous vous recommandons de surveiller votre logement, notamment les plafonds et murs adjacents.

Nous vous tiendrons informés de l'évolution de la situation et des mesures prises.

Si vous constatez la moindre anomalie, merci de nous contacter immédiatement.

Cordialement,
Le Syndic""",
                "recipient_source": "neighbors_from_SQL",
                "required_fields": ["floor", "building_name", "affected_floors"]
            },
            "workflow_action": "send_multi_channel_alert",
            "n8n_node_type": "multi_channel"
        },
        {
            "step_id": 3,
            "step_order": 3,
            "action_type": "contact_plumber",
            "title": "Contacter plombier d'urgence",
            "description": "Contacter le plombier partenaire ou un professionnel disponible",
            "requires_user_validation": True,
            "is_critical": True,
            "estimated_time_seconds": 60,
            "payload_template": {
                "email_subject": "🚨 URGENT - Intervention dégât des eaux requise",
                "email_body_template": """Bonjour,

Nous avons besoin d'une intervention urgente pour un dégât des eaux.

**Détails de l'intervention :**
- Adresse : {{building_address}}
- Bâtiment : {{building_name}}
- Étage : {{floor}}
- Appartement : {{apartment_number}}
- Type d'incident : {{incident_type}}
- Gravité : {{severity}}

**Description :**
{{incident_description}}

**Actions déjà prises :**
{{actions_taken}}

**Accès :** [Instructions d'accès au bâtiment]

Merci de nous confirmer votre disponibilité et votre heure d'arrivée estimée dans les plus brefs délais.

Cordialement,
Le Syndic

Contact : [Numéro du syndic]""",
                "recipient_source": "plumbers_sql_list",
                "sms_fallback": True,
                "required_fields": ["building_address", "building_name", "floor", "apartment_number", "incident_type", "incident_description", "severity", "actions_taken"]
            },
            "workflow_action": "send_email",
            "n8n_node_type": "email_sms"
        },
        {
            "step_id": 4,
            "step_order": 4,
            "action_type": "create_internal_ticket",
            "title": "Créer ticket de suivi",
            "description": "Créer un ticket dans le système de gestion pour traçabilité",
            "requires_user_validation": False,
            "is_critical": False,
            "estimated_time_seconds": 10,
            "payload_template": {
                "ticket_title": "🚨 Dégât des eaux - {{building_name}} - Appt {{apartment_number}}",
                "ticket_description": """**Type :** Urgence - Dégât des eaux
**Bâtiment :** {{building_name}}
**Étage :** {{floor}}
**Appartement :** {{apartment_number}}
**Signalé par :** {{reporter}}

**Description :**
{{incident_description}}

**Gravité :** {{severity}}

**Actions prises :**
{{actions_taken}}

**Notifications envoyées :**
- Propriétaire : {{owner_name}}
- Voisins étages {{affected_floors}}
- Plombier contacté

**Date/Heure :** {{timestamp}}""",
                "priority": "urgent",
                "category": "emergency_water",
                "required_fields": ["building_name", "floor", "apartment_number", "reporter", "incident_description", "severity", "actions_taken", "owner_name", "affected_floors"]
            },
            "workflow_action": "create_ticket",
            "n8n_node_type": "ticket_creation"
        },
        {
            "step_id": 5,
            "step_order": 5,
            "action_type": "schedule_followup",
            "title": "Planifier suivi 24h",
            "description": "Programmer une relance automatique pour vérifier l'avancement de la situation",
            "requires_user_validation": False,
            "is_critical": False,
            "estimated_time_seconds": 5,
            "payload_template": {
                "task_text": "Vérifier avancement intervention plombier + état du logement suite au dégât des eaux du {{floor}}ème étage, appart {{apartment_number}}",
                "scheduled_delay_hours": 24,
                "assigned_to": "{{user_id}}",
                "required_fields": ["floor", "apartment_number", "user_id"]
            },
            "workflow_action": "schedule_action",
            "n8n_node_type": "scheduler"
        }
    ],
    "success_criteria": {
        "critical_steps_completed": [1, 3],
        "minimum_completion_rate": 0.8
    }
}


async def seed_workflows():
    """Seed emergency workflows into database"""
    print("🌱 Seeding emergency workflows...")

    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=True
    )

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        # Check if workflow already exists
        from sqlalchemy import select, and_
        query = select(EmergencyWorkflow).where(
            and_(
                EmergencyWorkflow.tenant_id == "default",
                EmergencyWorkflow.workflow_type == "water_leak",
                EmergencyWorkflow.is_active == True
            )
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  Workflow 'water_leak' already exists (ID: {existing.id})")
            print(f"   Usage count: {existing.usage_count}")
            print(f"   Created: {existing.created_at}")

            # Update if needed
            overwrite = input("Overwrite? (y/n): ")
            if overwrite.lower() == 'y':
                existing.checklist = WATER_LEAK_WORKFLOW
                existing.workflow_name = WATER_LEAK_WORKFLOW["workflow_name"]
                await session.commit()
                print("✅ Workflow updated!")
            else:
                print("⏭️  Skipping...")
        else:
            # Create new workflow
            new_workflow = EmergencyWorkflow(
                tenant_id="default",
                workflow_type="water_leak",
                workflow_name=WATER_LEAK_WORKFLOW["workflow_name"],
                checklist=WATER_LEAK_WORKFLOW,
                is_active=True,
                created_by="seed_script",
                usage_count=0
            )

            session.add(new_workflow)
            await session.commit()
            await session.refresh(new_workflow)

            print(f"✅ Workflow 'water_leak' created! (ID: {new_workflow.id})")
            print(f"   Name: {new_workflow.workflow_name}")
            print(f"   Steps: {len(WATER_LEAK_WORKFLOW['steps'])}")

    await engine.dispose()
    print("\n🎉 Seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed_workflows())
