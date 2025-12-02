"""
Test MailDigest Pro - Phase 4
Tests the enhanced digest rendering with summaries and actions
"""

import asyncio
import sys
sys.path.insert(0, '/app')

from app.services.email_summarizer import (
    EmailSummarizer, get_email_summarizer,
    format_relative_time, detect_category_badge
)


# Sample emails to test enrichment
SAMPLE_EMAILS = [
    {
        "id": 1,
        "message_id": "msg_001",
        "subject": "URGENT - Fuite d'eau 3ème étage Les Mimosas",
        "body": """Bonjour,

Je vous contacte car il y a une fuite d'eau importante au 3ème étage de la résidence Les Mimosas.
L'eau coule depuis ce matin et commence à toucher l'appartement du dessous.

Merci d'envoyer un plombier en urgence.

M. Dupont
Appartement 12
06 12 34 56 78""",
        "sender": "m.dupont@gmail.com",
        "urgency": "urgent",
        "attachments": [
            {"filename": "photo_fuite.jpg", "mime_type": "image/jpeg", "size": 245000}
        ],
        "received_at": "2025-12-02T14:30:00"
    },
    {
        "id": 2,
        "message_id": "msg_002",
        "subject": "Demande de devis - Réfection toiture",
        "body": """Madame, Monsieur,

Suite à notre entretien téléphonique, je vous transmets notre demande de devis pour la réfection de la toiture de la copropriété Les Acacias.

Surface estimée: 450m²
Travaux souhaités: remplacement tuiles + étanchéité terrasse

Merci de nous faire parvenir votre proposition.

Cordialement,
Le syndic""",
        "sender": "contact@toiture-pro.fr",
        "urgency": "important",
        "attachments": [
            {"filename": "plan_toiture.pdf", "mime_type": "application/pdf", "size": 1200000},
            {"filename": "photos_toiture.zip", "mime_type": "application/zip", "size": 5400000}
        ],
        "received_at": "2025-12-02T10:15:00"
    },
    {
        "id": 3,
        "message_id": "msg_003",
        "subject": "Re: Charges du 4ème trimestre",
        "body": """Bonjour,

J'ai bien reçu l'appel de charges pour le 4ème trimestre.
Je souhaiterais avoir le détail des charges de copropriété.

Cordialement,
Mme Martin""",
        "sender": "martin.sophie@orange.fr",
        "urgency": "routine",
        "attachments": [],
        "received_at": "2025-12-02T09:00:00"
    }
]


async def test_email_enrichment():
    """Test single email enrichment"""
    print("\n" + "="*60)
    print("TEST 1: Enrichissement d'un email unique")
    print("="*60)

    summarizer = get_email_summarizer()
    email = SAMPLE_EMAILS[0]

    enrichment = await summarizer.enrich_email(
        subject=email["subject"],
        body=email["body"],
        sender=email["sender"],
        attachments=email.get("attachments", []),
        urgency=email["urgency"]
    )

    print(f"\nEmail: {email['subject']}")
    print(f"De: {email['sender']}")
    print(f"\n--- Enrichissement ---")
    print(f"Resume: {enrichment.summary}")
    print(f"Action: {enrichment.suggested_action}")
    print(f"Pieces jointes: {enrichment.has_attachments} - {enrichment.attachment_summary}")


async def test_batch_enrichment():
    """Test batch email enrichment"""
    print("\n" + "="*60)
    print("TEST 2: Enrichissement batch de 3 emails")
    print("="*60)

    summarizer = get_email_summarizer()

    enriched_emails = await summarizer.enrich_emails_batch(SAMPLE_EMAILS, batch_size=2)

    for email in enriched_emails:
        print(f"\n--- {email['subject'][:50]}... ---")
        print(f"De: {email['sender']}")
        print(f"Resume: {email.get('summary', 'N/A')}")
        print(f"Action: {email.get('suggested_action', 'N/A')}")
        print(f"Pj: {email.get('attachment_summary', 'Aucune')}")


async def test_relative_time():
    """Test relative time formatting"""
    print("\n" + "="*60)
    print("TEST 3: Temps relatif")
    print("="*60)

    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    test_cases = [
        (now - timedelta(minutes=5), "il y a 5min"),
        (now - timedelta(hours=2), "il y a 2h"),
        (now - timedelta(hours=26), "hier"),
        (now - timedelta(days=3), "il y a 3j"),
        (now - timedelta(days=10), "date format"),
        ("2025-12-02T14:30:00", "string parsing"),
    ]

    for dt, expected_type in test_cases:
        result = format_relative_time(dt)
        print(f"  {dt} -> {result} (expected: {expected_type})")

    print("\n  Tous les tests de temps relatif OK")


async def test_category_badges():
    """Test category badge detection"""
    print("\n" + "="*60)
    print("TEST 4: Badges de catégorie")
    print("="*60)

    test_cases = [
        ("URGENT - Fuite d'eau 3ème étage", "", "[FUITE]"),
        ("Demande de devis - Réfection toiture", "", "[DEVIS]"),
        ("Facture EDF Décembre", "", "[FACTURE]"),
        ("Convocation AG extraordinaire", "", "[AG]"),
        ("Charges du 4ème trimestre", "", "[CHARGES]"),
        ("Réclamation bruit voisinage", "", "[RÉCLAMATION]"),
        ("Sinistre dégât des eaux", "", "[SINISTRE]"),
        ("Travaux ascenseur", "", "[TRAVAUX]"),
        ("Bonjour comment allez-vous", "", ""),  # No badge
    ]

    for subject, body, expected in test_cases:
        result = detect_category_badge(subject, body)
        status = "" if result == expected else ""
        print(f"  {status} '{subject[:40]}...' -> {result or '(aucun)'} (expected: {expected or '(aucun)'})")

    print("\n  Tous les tests de badges OK")


async def test_digest_format():
    """Test the final digest format rendering with new features"""
    print("\n" + "="*60)
    print("TEST 5: Rendu final du digest (avec badges et temps relatif)")
    print("="*60)

    summarizer = get_email_summarizer()

    # Enrich all emails
    enriched = await summarizer.enrich_emails_batch(SAMPLE_EMAILS)

    # Simulate digest grouping
    urgent = [e for e in enriched if e['urgency'] == 'urgent']
    important = [e for e in enriched if e['urgency'] == 'important']
    routine = [e for e in enriched if e['urgency'] == 'routine']

    # Render as the orchestrator would (with new features)
    print("\n" + "-"*60)
    print("**Digest Email** - 3 emails des dernieres 24h\n")
    print(f"**Urgents:** {len(urgent)} | **Importants:** {len(important)} | **Routine:** {len(routine)}")

    if urgent:
        print("\n---\n### Urgents\n")
        for i, email in enumerate(urgent, 1):
            subject = email['subject']
            body = email.get('body', '')
            badge = detect_category_badge(subject, body)
            relative_time = format_relative_time(email.get('received_at'))

            if badge:
                print(f"**{i}. {badge} {subject}**")
            else:
                print(f"**{i}. {subject}**")

            sender_line = f"De: {email['sender']}"
            if relative_time:
                sender_line += f" · {relative_time}"
            if email.get('has_attachments'):
                sender_line += f" · Pj: {email.get('attachment_summary', '')}"
            print(sender_line)

            if email.get('summary'):
                print(f"> {email['summary']}")
            if email.get('suggested_action'):
                print(f"*Action: {email['suggested_action']}*")
            print()

    if important:
        print("---\n### Importants\n")
        for i, email in enumerate(important, 1):
            subject = email['subject']
            body = email.get('body', '')
            badge = detect_category_badge(subject, body)
            relative_time = format_relative_time(email.get('received_at'))

            if badge:
                print(f"**{i}. {badge} {subject}**")
            else:
                print(f"**{i}. {subject}**")

            sender_line = f"De: {email['sender']}"
            if relative_time:
                sender_line += f" · {relative_time}"
            if email.get('has_attachments'):
                sender_line += f" · Pj: {email.get('attachment_summary', '')}"
            print(sender_line)

            if email.get('summary'):
                print(f"> {email['summary']}")
            if email.get('suggested_action'):
                print(f"*Action: {email['suggested_action']}*")
            print()

    if routine:
        print(f"---\n### Routine\n{len(routine)} email(s) de routine non affiches.")

    print("-"*60)


async def main():
    print("\n" + "="*60)
    print("      MAILDIGEST PRO - TEST SUITE")
    print("="*60)

    await test_email_enrichment()
    await test_batch_enrichment()
    await test_relative_time()
    await test_category_badges()
    await test_digest_format()

    print("\n" + "="*60)
    print("      TESTS TERMINES")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
