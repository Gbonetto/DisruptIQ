/**
 * E2E Tests - SQL, Legal, and RAG Queries
 *
 * Tests the assistant's ability to:
 * - Execute SQL queries (count, list, aggregate)
 * - Answer legal questions (majority rules, regulations)
 * - Search RAG documents (PV AG, contracts, regulations)
 */

import { test, expect } from '@playwright/test';
import { goToAssistant, sendAndVerify, isErrorResponse, isClarificationRequest } from './helpers';
import { TEST_SCENARIOS, PERFORMANCE_THRESHOLDS, COPROPRIETES } from './fixtures';

test.describe('SQL Queries', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Count query - Copropriétaires à Arc-en-Ciel', async ({ page }) => {
    const scenario = TEST_SCENARIOS.SQL.COUNT_COPROPRIETAIRES;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);
    expect(isClarificationRequest(result.response)).toBe(false);

    // Should contain a number (the count)
    const hasNumber = /\d+/.test(result.response);
    expect(hasNumber, 'Response should contain a count number').toBe(true);

    console.log(`SQL COUNT test passed in ${result.responseTimeMs}ms`);
    console.log(`Found keywords: ${result.foundKeywords.join(', ')}`);
  });

  test('List query - All coproprietes', async ({ page }) => {
    const scenario = TEST_SCENARIOS.SQL.LIST_COPROPRIETES;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should mention actual coproprietes from database
    const mentionsArcEnCiel = result.response.toLowerCase().includes('arc-en-ciel');
    const mentionsOliviers = result.response.toLowerCase().includes('oliviers');
    const mentionsHaussmann = result.response.toLowerCase().includes('haussmann');

    expect(mentionsArcEnCiel || mentionsOliviers || mentionsHaussmann, 'Should mention at least one copropriete').toBe(true);
  });

  test('Count lots in specific copropriete', async ({ page }) => {
    const scenario = TEST_SCENARIOS.SQL.COUNT_LOTS;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should contain the expected count (48 for Le Clos des Oliviers)
    const has48 = result.response.includes('48');
    expect(has48, 'Response should contain "48" for Le Clos des Oliviers lots').toBe(true);
  });

  test('SQL query with filtering', async ({ page }) => {
    const query = 'Quels copropriétaires ont des impayés à Arc-en-Ciel ?';

    const result = await sendAndVerify(
      page,
      query,
      ['impayé', 'impaye', 'copropriétaire', 'coproprietaire', 'Arc-en-Ciel', 'arc-en-ciel', 'résultat', 'resultat', 'solde', 'dette', 'montant', 'charge', 'information', 'question', 'aucun'],
      { timeout: PERFORMANCE_THRESHOLDS.NORMAL_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);
  });
});

test.describe('Legal Queries', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Majority rules for ravalement', async ({ page }) => {
    const scenario = TEST_SCENARIOS.LEGAL.MAJORITE_RAVALEMENT;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should mention legal articles or majority types
    const hasLegalReference = result.response.toLowerCase().includes('article') ||
      result.response.toLowerCase().includes('majorité') ||
      result.response.toLowerCase().includes('loi');

    expect(hasLegalReference, 'Response should include legal reference').toBe(true);
  });

  test('Copropriete rights and obligations', async ({ page }) => {
    const scenario = TEST_SCENARIOS.LEGAL.LOI_COPROPRIETE;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);
  });

  test('Legal question about AGE convocation', async ({ page }) => {
    const query = 'Dans quel délai doit-on convoquer une AG extraordinaire ?';

    const result = await sendAndVerify(
      page,
      query,
      ['délai', 'jour', 'convocation', 'AG'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should mention a timeframe
    const hasTimeframe = /\d+\s*(jour|semaine)/i.test(result.response);
    expect(hasTimeframe, 'Response should mention a timeframe').toBe(true);
  });
});

test.describe('RAG Document Queries', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('PV AG about ravalement', async ({ page }) => {
    const scenario = TEST_SCENARIOS.RAG.PV_AG_RAVALEMENT;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should reference the AG or vote
    const hasAGReference = result.response.toLowerCase().includes('ag') ||
      result.response.toLowerCase().includes('assemblée') ||
      result.response.toLowerCase().includes('vote');

    expect(hasAGReference, 'Response should reference AG or voting').toBe(true);
  });

  test('Reglement copropriete query', async ({ page }) => {
    const scenario = TEST_SCENARIOS.RAG.REGLEMENT_COPROPRIETE;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);
  });

  test('Contrat syndic expiration', async ({ page }) => {
    const scenario = TEST_SCENARIOS.RAG.CONTRAT_SYNDIC;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should mention a date or year
    const hasDate = /\d{4}|202\d/.test(result.response);
    expect(hasDate, 'Response should mention a year').toBe(true);
  });

  test('Document search with specific building', async ({ page }) => {
    const query = 'Montre-moi le dernier devis pour les travaux à Arc-en-Ciel';

    const result = await sendAndVerify(
      page,
      query,
      ['devis', 'travaux', 'Arc-en-Ciel', 'ravalement'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);
  });
});

test.describe('Mixed Source Queries', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Query requiring both SQL and RAG', async ({ page }) => {
    const query = 'Combien de copropriétaires à Arc-en-Ciel et que dit le PV sur leurs charges ?';

    const result = await sendAndVerify(
      page,
      query,
      ['copropriétaires', 'Arc-en-Ciel', 'charge'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Should include count and document reference
    const hasCount = /\d+/.test(result.response);
    expect(hasCount, 'Response should contain a count').toBe(true);
  });

  test('Query with legal + RAG context', async ({ page }) => {
    const query = 'Le ravalement voté en AG respecte-t-il la loi sur les majorités ?';

    const result = await sendAndVerify(
      page,
      query,
      ['majorité', 'ravalement', 'AG', 'vote'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);
  });
});

test.describe('Ambiguity Detection', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Ambiguous count query should ask for clarification', async ({ page }) => {
    const scenario = TEST_SCENARIOS.AMBIGUOUS.COMBIEN;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    // Should ask for clarification, not return an error
    expect(isErrorResponse(result.response)).toBe(false);
    expect(isClarificationRequest(result.response), 'Should ask for clarification').toBe(true);
  });

  test('Incomplete action should ask for details', async ({ page }) => {
    const scenario = TEST_SCENARIOS.AMBIGUOUS.ENVOIE_EMAIL;

    const result = await sendAndVerify(
      page,
      scenario.query,
      scenario.expectedKeywords,
      { timeout: scenario.maxLatencyMs }
    );

    expect(isErrorResponse(result.response)).toBe(false);
    expect(isClarificationRequest(result.response), 'Should ask for clarification').toBe(true);
  });
});
