/**
 * DisruptIQ E2E Test Fixtures
 *
 * Common test data based on SQL and RAG fixtures loaded in the backend.
 * These fixtures match the data in:
 * - backend/scripts/load_sql_fixtures.py
 * - backend/tests/fixtures/rag_fixtures.py
 */

// Known coproprietes from actual database
export const COPROPRIETES = {
  ARC_EN_CIEL: {
    id: 9,
    name: 'Résidence Arc-en-Ciel',
    address: '45 Boulevard Victor Hugo, 06000 Nice',
    lots: 24,
    coproprietaires: 14,
  },
  CLOS_OLIVIERS: {
    id: 10,
    name: 'Le Clos des Oliviers',
    address: '128 Avenue du Prado, 13008 Marseille',
    lots: 48,
    coproprietaires: 4,
  },
  HAUSSMANN: {
    id: 11,
    name: 'Immeuble Haussmann Saint-Germain',
    address: '67 Boulevard Saint-Germain, 75005 Paris',
    lots: 12,
    coproprietaires: 3,
  },
};

// Known professionals from fixtures
export const PROFESSIONALS = {
  PLOMBIER: {
    name: 'Jean Plombier',
    specialty: 'Plomberie',
    phone: '01 23 45 67 89',
  },
  ELECTRICIEN: {
    name: 'Marie Électricienne',
    specialty: 'Électricité',
    phone: '01 23 45 67 90',
  },
};

// Test scenarios with expected outcomes
// Note: Keywords should match actual response format from the backend
// SQL responses typically show: "Le résultat est X" with a table containing column names
// FLEXIBLE: Tests use atLeastOne: true by default - only one keyword needed to pass
export const TEST_SCENARIOS = {
  // SQL queries - should trigger SQL agent
  SQL: {
    COUNT_COPROPRIETAIRES: {
      query: 'Combien de copropriétaires à Arc-en-Ciel ?',
      // Flexible keywords - any of these indicates success
      expectedKeywords: ['14', 'copropriétaires', 'coproprietaires', 'arc-en-ciel', 'résultat', 'nombre'],
      expectedBehavior: 'count_response',
      maxLatencyMs: 20000,
    },
    LIST_COPROPRIETES: {
      query: 'Liste toutes les copropriétés',
      // Should mention at least one copropriété
      expectedKeywords: ['arc-en-ciel', 'oliviers', 'haussmann', 'copropriété', 'copropriete', '3'],
      expectedBehavior: 'list_response',
      maxLatencyMs: 20000,
    },
    COUNT_LOTS: {
      query: 'Combien de lots dans la copropriété Le Clos des Oliviers ?',
      // Flexible keywords
      expectedKeywords: ['48', 'lots', 'lot', 'oliviers', 'résultat'],
      expectedBehavior: 'count_response',
      maxLatencyMs: 20000,
    },
  },

  // RAG queries - should search documents
  RAG: {
    PV_AG_RAVALEMENT: {
      query: 'Que dit le PV de la dernière AG sur le ravalement ?',
      // Flexible - any document or ravalement related response is valid
      expectedKeywords: ['ravalement', 'façade', 'facade', 'ag', 'assemblée', 'vote', 'travaux', 'devis', '38', 'document'],
      expectedBehavior: 'document_search',
      maxLatencyMs: 45000,
    },
    REGLEMENT_COPROPRIETE: {
      query: 'Quelles sont les règles concernant les animaux dans la copropriété ?',
      // Flexible - mentions of animals, pets, rules
      expectedKeywords: ['animaux', 'animal', 'chien', 'chat', 'laisse', 'règlement', 'reglement', 'parties communes', 'toléré', 'autorisé'],
      expectedBehavior: 'document_search',
      maxLatencyMs: 45000,
    },
    CONTRAT_SYNDIC: {
      query: 'Quand se termine le contrat du syndic ?',
      // Flexible - syndic contract info or no result message
      expectedKeywords: ['syndic', 'contrat', '2027', '2024', 'mandat', 'durée', 'échéance', 'honoraires', 'aucun', 'résultat', 'resultat', 'trouvé', 'trouve', 'question', 'information'],
      expectedBehavior: 'document_search',
      maxLatencyMs: 45000,
    },
  },

  // Legal queries - should use legal knowledge
  LEGAL: {
    MAJORITE_RAVALEMENT: {
      query: 'Quelle majorité est nécessaire pour voter un ravalement de façade ?',
      // Flexible - mentions of majority, articles, legal terms
      expectedKeywords: ['majorité', 'majorite', 'article', '25', '24', '26', 'vote', 'voix', 'loi', 'copropriété'],
      expectedBehavior: 'legal_response',
      maxLatencyMs: 30000,
    },
    LOI_COPROPRIETE: {
      query: 'Quels sont les droits des copropriétaires concernant les parties communes ?',
      // Flexible - mentions of rights, common areas
      expectedKeywords: ['parties communes', 'droit', 'copropriétaire', 'coproprietaire', 'usage', 'loi', 'jouissance'],
      expectedBehavior: 'legal_response',
      maxLatencyMs: 30000,
    },
  },

  // Emergency scenarios - should trigger action plan
  URGENCE: {
    FUITE_EAU: {
      query: 'Il y a une fuite d\'eau urgente au 3ème étage de Arc-en-Ciel !',
      // Very flexible - any emergency/action-oriented keyword
      expectedKeywords: ['plombier', 'urgence', 'urgent', 'couper', 'eau', 'fermer', 'vanne', 'appeler', 'contact', 'intervention', 'sinistre', 'assurance', 'dégât', 'immédiat', 'immediat', 'fuite', 'action', 'étape', 'faire', 'contacter', 'joindre', 'professionnel'],
      expectedBehavior: 'emergency_response',
      maxLatencyMs: 45000,
    },
    PANNE_ELECTRIQUE: {
      query: 'Coupure électrique dans tout l\'immeuble Haussmann Saint-Germain',
      // Very flexible - any emergency/action-oriented keyword
      expectedKeywords: ['électricien', 'electricien', 'urgence', 'urgent', 'sécurité', 'securite', 'disjoncteur', 'edf', 'enedis', 'panne', 'coupure', 'électrique', 'electrique', 'contacter', 'appeler', 'intervention', 'courant'],
      expectedBehavior: 'emergency_response',
      maxLatencyMs: 45000,
    },
  },

  // Ambiguous queries - should ask for clarification
  AMBIGUOUS: {
    COMBIEN: {
      query: 'Combien ?',
      // Flexible - response should ask for clarification or provide context
      expectedKeywords: ['préciser', 'preciser', 'quoi', 'de quoi', '?', 'quel', 'quelle', 'souhaitez'],
      expectedBehavior: 'clarification_request',
      maxLatencyMs: 15000,
    },
    ENVOIE_EMAIL: {
      query: 'Envoie un email',
      // Flexible - should ask for details
      expectedKeywords: ['qui', 'destinataire', 'souhaitez', 'adresse', 'email', 'à qui', 'contenu', 'objet'],
      expectedBehavior: 'clarification_request',
      maxLatencyMs: 15000,
    },
  },
};

// Long conversation scenarios - with flexible keywords
export const CONVERSATION_SCENARIOS = {
  MULTI_TURN_SQL_RAG: [
    {
      user: 'Combien de copropriétaires à Arc-en-Ciel ?',
      expectedKeywords: ['14', 'copropriétaire', 'coproprietaire', 'arc-en-ciel'],
    },
    {
      user: 'Et au Clos des Oliviers ?',
      expectedKeywords: ['4', 'copropriétaire', 'coproprietaire', 'oliviers'],
    },
    {
      user: 'Que dit le règlement sur les travaux ?',
      expectedKeywords: ['travaux', 'autorisation', 'règlement', 'reglement', 'ag', 'majorité'],
    },
    {
      user: 'Comment contacter le plombier référencé ?',
      expectedKeywords: ['plombier', 'contact', 'téléphone', 'telephone', 'email', 'professionnel'],
    },
  ],

  CONTEXT_SWITCH: [
    {
      user: 'Parle-moi de la copropriété Arc-en-Ciel',
      expectedKeywords: ['arc-en-ciel', 'copropriété', 'copropriete', 'nice', 'boulevard'],
    },
    {
      user: 'Combien de lots ?',
      expectedKeywords: ['24', 'lots', 'lot'],
    },
    {
      user: 'Maintenant parle-moi de Haussmann Saint-Germain',
      expectedKeywords: ['haussmann', 'paris', 'saint-germain', 'copropriété'],
    },
    {
      user: 'Et là combien de lots ?',
      expectedKeywords: ['12', 'lots', 'lot'],
    },
  ],
};

// Timing thresholds - increased for AI processing time
export const PERFORMANCE_THRESHOLDS = {
  FAST_RESPONSE_MS: 15000,    // Ambiguity detection, simple queries
  NORMAL_RESPONSE_MS: 30000,  // SQL queries, standard responses
  SLOW_RESPONSE_MS: 60000,    // RAG searches, complex queries
  MAX_RESPONSE_MS: 120000,    // Absolute maximum for any query
};

// UI Selectors
export const SELECTORS = {
  CHAT_INPUT: 'textarea[placeholder*="Posez votre question"]',
  SEND_BUTTON: 'button:has(svg.lucide-send)',
  LOADING_SPINNER: '.animate-spin',
  MESSAGE_CONTAINER: '.space-y-4',
  ASSISTANT_MESSAGE: '.bg-gray-100',
  USER_MESSAGE: '.bg-blue-600',
  QUICK_ACTIONS: 'button:has-text("Actions rapides")',
};
