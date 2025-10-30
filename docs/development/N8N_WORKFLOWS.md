# Workflows N8N pour DisruptIQ

## 📋 Instructions d'Import

1. Ouvrez votre instance N8N
2. Cliquez sur "Import Workflow"
3. Collez le JSON du workflow souhaité
4. Configurez les credentials (Gmail, SMS, etc.)
5. Activez le workflow

---

## Workflow 1: Notification Voisins Urgence

```json
{
  "name": "DisruptIQ - Notification Voisins Urgence",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "notify-neighbors",
        "responseMode": "responseNode",
        "options": {}
      },
      "id": "webhook_trigger",
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "functionCode": "// Extraction des données du webhook\nconst data = $input.first().json;\nconst { address, apartment, issue, neighbors } = data;\n\n// Préparation du template email\nconst emailTemplate = `\nBonjour,\n\nNous vous informons qu'un ${issue === 'water_damage' ? 'dégât des eaux' : 'incident'} \na été signalé dans l'appartement ${apartment} de votre immeuble.\n\nAdresse : ${address}\n\nNous mettons tout en œuvre pour résoudre cette situation rapidement.\nUn professionnel interviendra dans les plus brefs délais.\n\nSi vous constatez des dommages dans votre appartement, \nmerci de nous contacter immédiatement.\n\nCordialement,\nVotre Syndic\n`;\n\nreturn neighbors.map(neighbor => ({\n  json: {\n    to: neighbor.email,\n    apartment: neighbor.apt,\n    subject: `🚨 Urgent - Incident immeuble ${address}`,\n    body: emailTemplate,\n    originalData: data\n  }\n}));"
      },
      "id": "prepare_emails",
      "name": "Prepare Emails",
      "type": "n8n-nodes-base.code",
      "typeVersion": 1,
      "position": [450, 300]
    },
    {
      "parameters": {
        "fromEmail": "syndic@example.com",
        "toEmail": "={{$json.to}}",
        "subject": "={{$json.subject}}",
        "text": "={{$json.body}}",
        "options": {
          "ccEmail": "archives@syndic.com"
        }
      },
      "id": "send_email",
      "name": "Send Email",
      "type": "n8n-nodes-base.gmail",
      "typeVersion": 2,
      "position": [650, 300]
    },
    {
      "parameters": {
        "operation": "append",
        "documentId": "YOUR_GOOGLE_SHEET_ID",
        "sheetName": "Urgences_Log",
        "columns": "A:E",
        "options": {},
        "dataStartRow": 2,
        "fieldsUi": {
          "values": [
            {
              "column": "A",
              "fieldValue": "={{new Date().toISOString()}}"
            },
            {
              "column": "B", 
              "fieldValue": "={{$node.webhook_trigger.json.address}}"
            },
            {
              "column": "C",
              "fieldValue": "={{$node.webhook_trigger.json.apartment}}"
            },
            {
              "column": "D",
              "fieldValue": "={{$node.webhook_trigger.json.issue}}"
            },
            {
              "column": "E",
              "fieldValue": "={{$json.to}}"
            }
          ]
        }
      },
      "id": "log_sheets",
      "name": "Log to Sheets",
      "type": "n8n-nodes-base.googleSheets",
      "typeVersion": 4,
      "position": [850, 300]
    },
    {
      "parameters": {
        "phoneNumber": "+33612345678",
        "message": "🚨 DisruptIQ: {{$node.webhook_trigger.json.neighbors.length}} voisins ont été prévenus pour l'incident {{$node.webhook_trigger.json.address}} Apt {{$node.webhook_trigger.json.apartment}}"
      },
      "id": "sms_notification",
      "name": "SMS Syndic",
      "type": "n8n-nodes-base.twilio",
      "typeVersion": 1,
      "position": [850, 450]
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={\"status\": \"success\", \"emails_sent\": {{$node.send_email.context.itemsCount}}, \"logged\": true, \"sms_sent\": true}",
        "options": {
          "responseCode": 200
        }
      },
      "id": "response",
      "name": "Webhook Response",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1050, 300]
    }
  ],
  "connections": {
    "webhook_trigger": {
      "main": [[{"node": "prepare_emails"}]]
    },
    "prepare_emails": {
      "main": [[{"node": "send_email"}]]
    },
    "send_email": {
      "main": [[
        {"node": "log_sheets"},
        {"node": "sms_notification"}
      ]]
    },
    "log_sheets": {
      "main": [[{"node": "response"}]]
    },
    "sms_notification": {
      "main": [[{"node": "response"}]]
    }
  }
}
```

---

## Workflow 2: Envoi Emails Fournisseurs

```json
{
  "name": "DisruptIQ - Envoi Emails Fournisseurs",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "send-vendor-emails",
        "responseMode": "responseNode",
        "options": {
          "rawBody": false
        }
      },
      "id": "webhook",
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [200, 350]
    },
    {
      "parameters": {
        "functionCode": "// Récupération des données\nconst { email_content, recipients, metadata } = $input.first().json;\n\n// Personnalisation pour chaque fournisseur\nreturn recipients.map(recipient => {\n  const personalizedContent = email_content\n    .replace('{{vendor_name}}', recipient.name)\n    .replace('{{vendor_company}}', recipient.company);\n  \n  return {\n    json: {\n      to: recipient.email,\n      vendorName: recipient.name,\n      vendorCompany: recipient.company,\n      subject: metadata.subject || 'Demande de devis - Copropriété',\n      htmlBody: `\n        <div style=\"font-family: Arial, sans-serif; max-width: 600px;\">\n          ${personalizedContent}\n          <hr style=\"margin: 20px 0;\">\n          <p style=\"color: #666; font-size: 12px;\">\n            Ce message vous est envoyé via DisruptIQ - Système de gestion syndic\n          </p>\n        </div>\n      `,\n      trackingId: `${metadata.property_id}_${Date.now()}_${recipient.email}`,\n      propertyAddress: metadata.property_address\n    }\n  };\n});"
      },
      "id": "personalize",
      "name": "Personalize Emails",
      "type": "n8n-nodes-base.code",
      "typeVersion": 1,
      "position": [400, 350]
    },
    {
      "parameters": {
        "fromEmail": "={{$node.webhook.json.sender_email}}",
        "toEmail": "={{$json.to}}",
        "subject": "={{$json.subject}}",
        "emailType": "html",
        "htmlBody": "={{$json.htmlBody}}",
        "options": {
          "replyTo": "={{$node.webhook.json.reply_to}}",
          "allowUnauthorizedCerts": false
        }
      },
      "id": "gmail",
      "name": "Send via Gmail",
      "type": "n8n-nodes-base.gmail",
      "typeVersion": 2,
      "position": [600, 350]
    },
    {
      "parameters": {
        "batchSize": 5,
        "options": {}
      },
      "id": "batch",
      "name": "Batch Emails",
      "type": "n8n-nodes-base.splitInBatches",
      "typeVersion": 1,
      "position": [500, 250]
    },
    {
      "parameters": {
        "amount": 2,
        "unit": "seconds"
      },
      "id": "wait",
      "name": "Wait 2s",
      "type": "n8n-nodes-base.wait",
      "typeVersion": 1,
      "position": [700, 250]
    },
    {
      "parameters": {
        "operation": "create",
        "base": "appXXXXXXXXXXXXXX",
        "table": "Emails_Sent",
        "columns": {
          "Timestamp": "={{new Date().toISOString()}}",
          "Recipient": "={{$json.to}}",
          "Subject": "={{$json.subject}}",
          "Property": "={{$json.propertyAddress}}",
          "TrackingID": "={{$json.trackingId}}",
          "Status": "Sent",
          "VendorName": "={{$json.vendorName}}",
          "VendorCompany": "={{$json.vendorCompany}}"
        }
      },
      "id": "airtable",
      "name": "Log to Airtable",
      "type": "n8n-nodes-base.airtable",
      "typeVersion": 2,
      "position": [800, 350]
    },
    {
      "parameters": {
        "channel": "#syndic-notifications",
        "text": "📧 Emails fournisseurs envoyés",
        "attachments": [
          {
            "color": "#28a745",
            "title": "Campagne email terminée",
            "fields": {
              "values": [
                {
                  "short": true,
                  "title": "Nombre d'emails",
                  "value": "={{$items().length}}"
                },
                {
                  "short": true,
                  "title": "Propriété",
                  "value": "={{$node.webhook.json.metadata.property_address}}"
                },
                {
                  "short": false,
                  "title": "Objet",
                  "value": "={{$node.webhook.json.metadata.subject}}"
                }
              ]
            },
            "footer": "DisruptIQ"
          }
        ],
        "otherOptions": {}
      },
      "id": "slack",
      "name": "Notify Slack",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 1,
      "position": [1000, 350]
    },
    {
      "parameters": {
        "respondWith": "json",
        "responseBody": "={\n  \"status\": \"success\",\n  \"message\": \"Emails envoyés avec succès\",\n  \"details\": {\n    \"total_sent\": {{$items().length}},\n    \"recipients\": {{$node.personalize.json}},\n    \"timestamp\": \"{{new Date().toISOString()}}\"\n  }\n}",
        "options": {
          "responseCode": 200,
          "responseHeaders": {
            "entries": [
              {
                "name": "Content-Type",
                "value": "application/json"
              }
            ]
          }
        }
      },
      "id": "respond",
      "name": "Respond",
      "type": "n8n-nodes-base.respondToWebhook",
      "typeVersion": 1,
      "position": [1200, 350]
    }
  ],
  "connections": {
    "webhook": {
      "main": [[{"node": "personalize"}]]
    },
    "personalize": {
      "main": [[{"node": "batch"}]]
    },
    "batch": {
      "main": [[{"node": "gmail"}]]
    },
    "gmail": {
      "main": [[{"node": "airtable"}]]
    },
    "airtable": {
      "main": [[{"node": "wait"}]]
    },
    "wait": {
      "main": [[{"node": "batch"}]]
    },
    "slack": {
      "main": [[{"node": "respond"}]]
    }
  }
}
```

---

## Workflow 3: Archive Document avec Classification IA

```json
{
  "name": "DisruptIQ - Archive Document Intelligent",
  "nodes": [
    {
      "parameters": {
        "httpMethod": "POST",
        "path": "archive-document",
        "options": {}
      },
      "id": "webhook_start",
      "name": "Webhook Start",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1,
      "position": [250, 300]
    },
    {
      "parameters": {
        "url": "={{$json.document_url}}",
        "options": {
          "response": {
            "fullResponse": false,
            "responseFormat": "file"
          }
        }
      },
      "id": "download",
      "name": "Download Document",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 3,
      "position": [450, 300]
    },
    {
      "parameters": {
        "model": "gpt-4",
        "messages": {
          "values": [
            {
              "role": "system",
              "content": "Tu es un assistant spécialisé dans la classification de documents pour un syndic. Analyse le document et retourne un JSON avec: {\"category\": \"facture|contrat|courrier|pv_ag|autre\", \"vendor\": \"nom_fournisseur_si_applicable\", \"amount\": montant_si_facture, \"date\": \"date_document\", \"tags\": [\"tag1\", \"tag2\"], \"summary\": \"résumé en une ligne\"}"
            },
            {
              "role": "user",
              "content": "Analyse ce document:\n\n{{$json.extracted_text}}"
            }
          ]
        },
        "options": {
          "temperature": 0.1,
          "responseFormat": {
            "type": "json_object"
          }
        }
      },
      "id": "classify",
      "name": "Classify with GPT-4",
      "type": "n8n-nodes-base.openAi",
      "typeVersion": 1,
      "position": [650, 300]
    },
    {
      "parameters": {
        "resource": "file",
        "operation": "upload",
        "name": "={{$json.classification.category}}/{{$json.property_id}}_{{$json.classification.date}}_{{$json.original_filename}}",
        "parents": ["YOUR_DRIVE_FOLDER_ID"],
        "options": {
          "appProperties": {
            "property": [
              {
                "key": "category",
                "value": "={{$json.classification.category}}"
              },
              {
                "key": "vendor",
                "value": "={{$json.classification.vendor}}"
              },
              {
                "key": "amount",
                "value": "={{$json.classification.amount}}"
              },
              {
                "key": "property_id",
                "value": "={{$json.property_id}}"
              },
              {
                "key": "processed_by",
                "value": "DisruptIQ"
              }
            ]
          }
        }
      },
      "id": "gdrive",
      "name": "Upload to Drive",
      "type": "n8n-nodes-base.googleDrive",
      "typeVersion": 2,
      "position": [850, 300]
    },
    {
      "parameters": {
        "collection": "documents",
        "document": {
          "filename": "={{$json.original_filename}}",
          "category": "={{$json.classification.category}}",
          "vendor": "={{$json.classification.vendor}}",
          "amount": "={{$json.classification.amount}}",
          "document_date": "={{$json.classification.date}}",
          "tags": "={{$json.classification.tags}}",
          "summary": "={{$json.classification.summary}}",
          "property_id": "={{$json.property_id}}",
          "google_drive_id": "={{$json.drive_file_id}}",
          "processed_at": "={{new Date().toISOString()}}",
          "status": "archived"
        }
      },
      "id": "mongodb",
      "name": "Save to MongoDB",
      "type": "n8n-nodes-base.mongoDb",
      "typeVersion": 1,
      "position": [850, 450]
    },
    {
      "parameters": {
        "channel": "#documents",
        "text": "📄 Document archivé automatiquement",
        "attachments": [
          {
            "color": "#0084ff",
            "fields": {
              "values": [
                {
                  "title": "Fichier",
                  "value": "={{$json.original_filename}}",
                  "short": true
                },
                {
                  "title": "Catégorie",
                  "value": "={{$json.classification.category}}",
                  "short": true
                },
                {
                  "title": "Fournisseur",
                  "value": "={{$json.classification.vendor || 'N/A'}}",
                  "short": true
                },
                {
                  "title": "Montant",
                  "value": "={{$json.classification.amount || 'N/A'}}€",
                  "short": true
                },
                {
                  "title": "Résumé",
                  "value": "={{$json.classification.summary}}",
                  "short": false
                }
              ]
            }
          }
        ]
      },
      "id": "slack_notify",
      "name": "Slack Notify",
      "type": "n8n-nodes-base.slack",
      "typeVersion": 1,
      "position": [1050, 300]
    },
    {
      "parameters": {
        "conditions": {
          "options": {
            "caseSensitive": false,
            "leftValue": "",
            "typeValidation": "loose"
          },
          "combinator": "and",
          "conditions": [
            {
              "leftValue": "={{$json.classification.category}}",
              "rightValue": "facture",
              "operator": {
                "type": "string",
                "operation": "equals"
              }
            },
            {
              "leftValue": "={{$json.classification.amount}}",
              "rightValue": 1000,
              "operator": {
                "type": "number",
                "operation": "gt"
              }
            }
          ]
        }
      },
      "id": "if_large_invoice",
      "name": "If Large Invoice",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [1050, 450]
    },
    {
      "parameters": {
        "fromEmail": "alerts@syndic.com",
        "toEmail": "comptabilite@syndic.com",
        "subject": "⚠️ Facture importante à valider",
        "emailType": "html",
        "htmlBody": "=<h3>Une facture importante nécessite votre attention</h3>\n<p><strong>Fournisseur:</strong> {{$json.classification.vendor}}</p>\n<p><strong>Montant:</strong> {{$json.classification.amount}}€</p>\n<p><strong>Date:</strong> {{$json.classification.date}}</p>\n<p><strong>Résumé:</strong> {{$json.classification.summary}}</p>\n<p><a href=\"{{$json.drive_link}}\">Voir le document</a></p>"
      },
      "id": "alert_email",
      "name": "Alert Email",
      "type": "n8n-nodes-base.gmail",
      "typeVersion": 2,
      "position": [1250, 450]
    }
  ],
  "connections": {
    "webhook_start": {
      "main": [[{"node": "download"}]]
    },
    "download": {
      "main": [[{"node": "classify"}]]
    },
    "classify": {
      "main": [[
        {"node": "gdrive"},
        {"node": "mongodb"}
      ]]
    },
    "gdrive": {
      "main": [[{"node": "slack_notify"}]]
    },
    "mongodb": {
      "main": [[{"node": "if_large_invoice"}]]
    },
    "if_large_invoice": {
      "main": [
        [{"node": "alert_email"}],
        []
      ]
    }
  }
}
```

---

## 🔧 Configuration des Webhooks dans DisruptIQ

### Backend Python (FastAPI)
```python
# services/n8n_service.py
import httpx
import json
from typing import Dict, Any

class N8NService:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def trigger_neighbor_notification(
        self, 
        address: str,
        apartment: str,
        issue: str,
        neighbors: list
    ) -> Dict[str, Any]:
        """Déclenche le workflow de notification des voisins"""
        
        webhook_url = f"{self.base_url}/webhook/notify-neighbors"
        
        payload = {
            "address": address,
            "apartment": apartment,
            "issue": issue,
            "neighbors": neighbors,
            "timestamp": datetime.now().isoformat()
        }
        
        response = await self.client.post(
            webhook_url,
            json=payload
        )
        
        return response.json()
    
    async def send_vendor_emails(
        self,
        email_content: str,
        recipients: list,
        metadata: dict
    ) -> Dict[str, Any]:
        """Envoie des emails aux fournisseurs"""
        
        webhook_url = f"{self.base_url}/webhook/send-vendor-emails"
        
        payload = {
            "email_content": email_content,
            "recipients": recipients,
            "metadata": metadata,
            "sender_email": "syndic@example.com",
            "reply_to": "contact@syndic.com"
        }
        
        response = await self.client.post(
            webhook_url,
            json=payload
        )
        
        return response.json()
    
    async def archive_document(
        self,
        document_url: str,
        original_filename: str,
        property_id: str
    ) -> Dict[str, Any]:
        """Archive et classifie un document"""
        
        webhook_url = f"{self.base_url}/webhook/archive-document"
        
        payload = {
            "document_url": document_url,
            "original_filename": original_filename,
            "property_id": property_id
        }
        
        response = await self.client.post(
            webhook_url,
            json=payload
        )
        
        return response.json()
```

---

## 📝 Variables d'Environnement N8N

Ajoutez dans votre `.env`:

```bash
# N8N Configuration
N8N_WEBHOOK_BASE_URL=https://n8n.votre-domaine.com
N8N_WEBHOOK_AUTH_TOKEN=your_secret_token_here

# Webhook Endpoints
N8N_WEBHOOK_NOTIFY_NEIGHBORS=/webhook/notify-neighbors
N8N_WEBHOOK_SEND_EMAILS=/webhook/send-vendor-emails  
N8N_WEBHOOK_ARCHIVE_DOC=/webhook/archive-document

# Timeout and Retry
N8N_TIMEOUT=30
N8N_MAX_RETRIES=3
```

---

## 🚀 Test des Workflows

### Test avec cURL

```bash
# Test notification voisins
curl -X POST https://n8n.votre-domaine.com/webhook/notify-neighbors \
  -H "Content-Type: application/json" \
  -d '{
    "address": "15 rue Victor Hugo",
    "apartment": "23",
    "issue": "water_damage",
    "neighbors": [
      {"apt": "22", "email": "test@example.com"},
      {"apt": "24", "email": "test2@example.com"}
    ]
  }'

# Test envoi emails fournisseurs
curl -X POST https://n8n.votre-domaine.com/webhook/send-vendor-emails \
  -H "Content-Type: application/json" \
  -d '{
    "email_content": "Bonjour {{vendor_name}}, nous sollicitons un devis...",
    "recipients": [
      {"email": "vendor1@example.com", "name": "Entreprise A", "company": "Peinture Pro"}
    ],
    "metadata": {
      "subject": "Demande de devis",
      "property_address": "15 rue Victor Hugo",
      "property_id": "PROP_001"
    }
  }'
```

---

## 🎯 Checklist d'Intégration

- [ ] Créer compte N8N (self-hosted ou cloud)
- [ ] Importer les 3 workflows
- [ ] Configurer les credentials:
  - [ ] Gmail/SMTP
  - [ ] Google Drive
  - [ ] Google Sheets
  - [ ] Slack (optionnel)
  - [ ] Twilio SMS (optionnel)
- [ ] Tester chaque webhook individuellement
- [ ] Configurer les URLs dans DisruptIQ
- [ ] Activer les workflows
- [ ] Monitorer les logs

---

**Note**: Remplacez tous les placeholders (YOUR_GOOGLE_SHEET_ID, etc.) par vos vraies valeurs avant utilisation.
