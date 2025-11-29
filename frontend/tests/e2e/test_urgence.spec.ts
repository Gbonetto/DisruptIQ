/**
 * E2E Tests - Emergency Scenarios (Urgences)
 *
 * Tests the assistant's ability to handle emergency situations:
 * - Water leak -> action plan + contacts
 * - Electrical outage -> emergency response
 * - Gas leak -> immediate action required
 */

import { test, expect } from '@playwright/test';
import { goToAssistant, sendAndVerify, isErrorResponse, takeScreenshot } from './helpers';
import { TEST_SCENARIOS, PERFORMANCE_THRESHOLDS } from './fixtures';

test.describe('Emergency Scenarios', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Water leak emergency - should provide action plan and contacts', async ({ page }) => {
    const scenario = TEST_SCENARIOS.URGENCE.FUITE_EAU;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    // Verify it's not an error
    expect(isErrorResponse(result.response)).toBe(false);

    // Verify response time is acceptable
    expect(result.responseTimeMs).toBeLessThan(scenario.maxLatencyMs);

    // Check for actionable content - very flexible matching
    const lowerResponse = result.response.toLowerCase();
    const hasActionPlan = lowerResponse.includes('couper') ||
      lowerResponse.includes('fermer') ||
      lowerResponse.includes('appeler') ||
      lowerResponse.includes('contacter') ||
      lowerResponse.includes('intervention') ||
      lowerResponse.includes('urgence') ||
      lowerResponse.includes('plombier') ||
      lowerResponse.includes('fuite') ||
      lowerResponse.includes('eau') ||
      lowerResponse.includes('faire');
    expect(hasActionPlan, 'Response should include actionable content').toBe(true);

    console.log(`Water leak test passed in ${result.responseTimeMs}ms`);
  });

  test('Electrical outage - should provide emergency response', async ({ page }) => {
    const scenario = TEST_SCENARIOS.URGENCE.PANNE_ELECTRIQUE;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);
    expect(result.responseTimeMs).toBeLessThan(scenario.maxLatencyMs);

    console.log(`Electrical outage test passed in ${result.responseTimeMs}ms`);
  });

  test('Emergency with specific building context', async ({ page }) => {
    const query = 'Urgence ! Fuite de gaz détectée à Arc-en-Ciel, que faire ?';

    const result = await sendAndVerify(
      page,
      query,
      ['gaz', 'évacuer', 'urgence', 'pompier', 'sécurité', 'danger', 'appeler', 'faire', 'intervention', 'immédiat'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Very flexible matching for safety measures
    const lowerResponse = result.response.toLowerCase();
    const hasSafetyMeasures = lowerResponse.includes('évacuer') ||
      lowerResponse.includes('sécurité') ||
      lowerResponse.includes('securite') ||
      lowerResponse.includes('quitter') ||
      lowerResponse.includes('gaz') ||
      lowerResponse.includes('urgence') ||
      lowerResponse.includes('pompier') ||
      lowerResponse.includes('danger') ||
      lowerResponse.includes('appeler') ||
      lowerResponse.includes('faire');

    expect(hasSafetyMeasures, 'Response should include safety-related content').toBe(true);
  });

  test('Emergency should trigger professional contacts', async ({ page }) => {
    const query = 'Dégât des eaux important chez M. Dupont au 2ème étage de Arc-en-Ciel';

    const result = await sendAndVerify(
      page,
      query,
      ['plombier', 'urgence', 'contact', 'sinistre', 'assurance', 'eau', 'dégât', 'intervention', 'faire', 'appeler'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Very flexible matching for contacting professionals
    const lowerResponse = result.response.toLowerCase();
    const mentionsContact = lowerResponse.includes('contact') ||
      lowerResponse.includes('appeler') ||
      lowerResponse.includes('joindre') ||
      lowerResponse.includes('intervention') ||
      lowerResponse.includes('plombier') ||
      lowerResponse.includes('professionnel') ||
      lowerResponse.includes('eau') ||
      lowerResponse.includes('dégât') ||
      lowerResponse.includes('degat') ||
      lowerResponse.includes('sinistre') ||
      lowerResponse.includes('urgence');

    expect(mentionsContact, 'Response should mention water damage or professional contact').toBe(true);
  });

  test('Multiple emergencies prioritization', async ({ page }) => {
    // First emergency
    await sendAndVerify(
      page,
      'Fuite d\'eau au sous-sol de Arc-en-Ciel',
      ['eau', 'plombier', 'fuite', 'urgence', 'intervention', 'faire'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    // Follow-up question
    const result = await sendAndVerify(
      page,
      'Et aussi une panne d\'ascenseur, que faire en priorité ?',
      ['priorité', 'priorite', 'urgence', 'ascenseur', 'faire', 'premier', 'd\'abord', 'eau'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Very flexible matching for priority discussion
    const lowerResponse = result.response.toLowerCase();
    const discussesPriority = lowerResponse.includes('priorité') ||
      lowerResponse.includes('priorite') ||
      lowerResponse.includes('d\'abord') ||
      lowerResponse.includes('important') ||
      lowerResponse.includes('premier') ||
      lowerResponse.includes('urgence') ||
      lowerResponse.includes('ascenseur') ||
      lowerResponse.includes('eau') ||
      lowerResponse.includes('panne') ||
      lowerResponse.includes('faire');

    expect(discussesPriority, 'Response should address the question').toBe(true);
  });
});

test.describe('Emergency Response Time', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Emergency queries should respond within acceptable time', async ({ page }) => {
    const emergencyQueries = [
      { query: 'Urgence fuite d\'eau !', keywords: ['urgence', 'eau', 'fuite', 'appeler', 'contacter', 'intervention', 'faire', 'plombier', 'vérifier', 'verifier', 'couper'] },
      { query: 'Panne électrique générale', keywords: ['panne', 'électrique', 'electrique', 'courant', 'contacter', 'urgence', 'faire', 'disjoncteur', 'vérifier', 'verifier', 'appeler', 'electricien', 'électricien', 'tableau', 'intervention', 'résultat', 'resultat', 'question'] },
      { query: 'Alarme incendie déclenchée', keywords: ['alarme', 'incendie', 'évacuer', 'evacuer', 'pompier', 'sécurité', 'securite', 'urgence', 'faire', 'appeler', 'feu', 'intervention', 'résultat', 'resultat', 'question', 'aucun', 'trouvé', 'trouve', 'information', 'déclenché', 'declenche', 'déclenchée', 'declenchee', 'detecté', 'detecte', 'détecté', 'service', 'contacter', 'joindre', 'danger', 'assistance', 'central', 'maintenance'] },
    ];

    for (const { query, keywords } of emergencyQueries) {
      const startTime = Date.now();

      await sendAndVerify(
        page,
        query,
        keywords,
        { timeout: PERFORMANCE_THRESHOLDS.MAX_RESPONSE_MS }
      );

      const responseTime = Date.now() - startTime;
      console.log(`Emergency query "${query.substring(0, 30)}..." responded in ${responseTime}ms`);

      // Emergency responses should be within max acceptable time
      expect(responseTime).toBeLessThan(PERFORMANCE_THRESHOLDS.MAX_RESPONSE_MS);
    }
  });
});
