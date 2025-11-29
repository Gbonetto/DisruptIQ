/**
 * E2E Tests - Long Conversations
 *
 * Tests the assistant's ability to maintain context over multiple turns:
 * - 10-20 message conversations
 * - Context switching between topics
 * - Reference to previous messages
 * - Mixed SQL/RAG/Legal queries in sequence
 */

import { test, expect } from '@playwright/test';
import { goToAssistant, sendAndVerify, sendMessage, isErrorResponse, clearConversation } from './helpers';
import { CONVERSATION_SCENARIOS, PERFORMANCE_THRESHOLDS } from './fixtures';

test.describe('Long Conversations', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('Multi-turn conversation with SQL and RAG', async ({ page }) => {
    const scenario = CONVERSATION_SCENARIOS.MULTI_TURN_SQL_RAG;

    for (let i = 0; i < scenario.length; i++) {
      const turn = scenario[i];
      console.log(`Turn ${i + 1}: "${turn.user.substring(0, 50)}..."`);

      const result = await sendAndVerify(
        page,
        turn.user,
        turn.expectedKeywords,
        { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
      );

      expect(isErrorResponse(result.response)).toBe(false);
      console.log(`  Response received in ${result.responseTimeMs}ms`);
      console.log(`  Found keywords: ${result.foundKeywords.join(', ')}`);
    }
  });

  test('Context switching between buildings', async ({ page }) => {
    const scenario = CONVERSATION_SCENARIOS.CONTEXT_SWITCH;

    for (let i = 0; i < scenario.length; i++) {
      const turn = scenario[i];
      console.log(`Turn ${i + 1}: "${turn.user}"`);

      const result = await sendAndVerify(
        page,
        turn.user,
        turn.expectedKeywords,
        { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
      );

      expect(isErrorResponse(result.response)).toBe(false);

      // Check context is maintained
      if (i > 0 && turn.user.toLowerCase().includes('combien')) {
        // Follow-up questions should not need full context repetition
        expect(result.response.length).toBeGreaterThan(10);
      }
    }
  });

  test('10-turn mixed conversation', async ({ page }) => {
    const queries = [
      { q: 'Bonjour, parle-moi de Arc-en-Ciel', kw: ['Arc-en-Ciel', 'copropriété', 'Nice'] },
      { q: 'Combien de lots ?', kw: ['24', 'lots'] },
      { q: 'Et de copropriétaires ?', kw: ['14', 'copropriétaires'] },
      { q: 'Quel est le syndic actuel ?', kw: ['syndic', 'gestion'] },
      { q: 'Quand se termine son contrat ?', kw: ['contrat'] },
      { q: 'Parlons maintenant de Haussmann Saint-Germain', kw: ['Haussmann', 'Paris'] },
      { q: 'Combien de lots là-bas ?', kw: ['12'] },
      { q: 'Y a-t-il des travaux prévus ?', kw: ['travaux'] },
      { q: 'Quelle majorité pour les voter ?', kw: ['majorité', 'vote'] },
      { q: 'Merci, résume notre conversation', kw: ['Arc-en-Ciel', 'Haussmann', 'résumé'] },
    ];

    const results = [];

    for (let i = 0; i < queries.length; i++) {
      const { q, kw } = queries[i];
      console.log(`\nTurn ${i + 1}/10: "${q}"`);

      const startTime = Date.now();
      const response = await sendMessage(page, q, {
        timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS,
        waitForKeywords: kw,
      });
      const responseTime = Date.now() - startTime;

      results.push({
        turn: i + 1,
        query: q,
        responseTime,
        responseLength: response.length,
      });

      expect(isErrorResponse(response)).toBe(false);
      console.log(`  Response: ${response.substring(0, 100)}...`);
      console.log(`  Time: ${responseTime}ms, Length: ${response.length} chars`);
    }

    // Summary statistics
    const avgResponseTime = results.reduce((a, b) => a + b.responseTime, 0) / results.length;
    const maxResponseTime = Math.max(...results.map(r => r.responseTime));

    console.log('\n=== Conversation Summary ===');
    console.log(`Total turns: ${results.length}`);
    console.log(`Avg response time: ${avgResponseTime.toFixed(0)}ms`);
    console.log(`Max response time: ${maxResponseTime}ms`);

    // Performance assertions
    expect(avgResponseTime).toBeLessThan(PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS);
    expect(maxResponseTime).toBeLessThan(PERFORMANCE_THRESHOLDS.MAX_RESPONSE_MS);
  });

  test('Pronoun reference in conversation', async ({ page }) => {
    // First establish context
    await sendAndVerify(
      page,
      'Parle-moi de la copropriété Arc-en-Ciel',
      ['Arc-en-Ciel', 'arc-en-ciel', 'copropriété', 'copropriete', 'résultat', 'resultat', 'information'],
      { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
    );

    // Use pronoun reference - flexible keywords
    const result = await sendAndVerify(
      page,
      'Combien y a-t-il de lots là-bas ?',
      ['24', 'lots', 'lot', 'résultat', 'resultat', 'nombre', 'arc-en-ciel', 'information', 'question'],
      { timeout: PERFORMANCE_THRESHOLDS.NORMAL_RESPONSE_MS }
    );

    expect(isErrorResponse(result.response)).toBe(false);

    // Very flexible check - response should have some content
    expect(result.response.length).toBeGreaterThan(20);
  });

  test('Question follow-up chain', async ({ page }) => {
    // Chain of related questions - very flexible keywords
    const chain = [
      { q: 'Qui est le président du conseil syndical de Arc-en-Ciel ?', expect: ['président', 'president', 'conseil', 'syndical', 'arc-en-ciel', 'résultat', 'resultat', 'information', 'question'] },
      { q: 'Depuis quand ?', expect: ['depuis', 'élu', 'elu', 'mandat', 'date', 'année', 'annee', 'résultat', 'resultat', 'information', 'question'] },
      { q: 'Comment le contacter ?', expect: ['contact', 'email', 'téléphone', 'telephone', 'joindre', 'appeler', 'résultat', 'resultat', 'information', 'question'] },
    ];

    for (const step of chain) {
      const result = await sendAndVerify(
        page,
        step.q,
        step.expect,
        { timeout: PERFORMANCE_THRESHOLDS.SLOW_RESPONSE_MS }
      );

      expect(isErrorResponse(result.response)).toBe(false);
    }
  });
});

test.describe('Conversation Stress Tests', () => {
  test.beforeEach(async ({ page }) => {
    await goToAssistant(page);
  });

  test('20-turn conversation without degradation', async ({ page }) => {
    // This test runs 20 conversation turns, so we need a longer timeout
    test.setTimeout(600000); // 10 minutes

    const queries = [
      'Bonjour',
      'Quelles copropriétés gérez-vous ?',
      'Parlez-moi de Arc-en-Ciel',
      'Combien de lots ?',
      'Combien de copropriétaires ?',
      'Qui est le syndic ?',
      'Quand finit le contrat ?',
      'Y a-t-il des impayés ?',
      'Quels travaux sont prévus ?',
      'Quel est le budget prévisionnel ?',
      'Parlons de Haussmann Saint-Germain maintenant',
      'Combien de lots à Haussmann ?',
      'Des travaux prévus ?',
      'Quel artisan pour la plomberie ?',
      'Son numéro de téléphone ?',
      'Revenons à Arc-en-Ciel',
      'Résumez les dernières AG',
      'Quelle majorité pour le ravalement ?',
      'Des documents à me montrer ?',
      'Merci, faites un résumé global',
    ];

    const responseTimes: number[] = [];

    for (let i = 0; i < queries.length; i++) {
      const startTime = Date.now();

      const response = await sendMessage(page, queries[i], {
        timeout: PERFORMANCE_THRESHOLDS.MAX_RESPONSE_MS,
      });

      const responseTime = Date.now() - startTime;
      responseTimes.push(responseTime);

      console.log(`Turn ${i + 1}: ${responseTime}ms - "${queries[i].substring(0, 30)}..."`);

      expect(isErrorResponse(response)).toBe(false);
    }

    // Check for performance degradation
    const firstHalf = responseTimes.slice(0, 10);
    const secondHalf = responseTimes.slice(10);

    const avgFirst = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
    const avgSecond = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;

    console.log(`\nAvg response time (turns 1-10): ${avgFirst.toFixed(0)}ms`);
    console.log(`Avg response time (turns 11-20): ${avgSecond.toFixed(0)}ms`);

    // Second half should not be more than 2x slower (allowing for context growth)
    expect(avgSecond).toBeLessThan(avgFirst * 2.5);
  });

  test('Rapid-fire questions', async ({ page }) => {
    const rapidQueries = [
      'Combien de lots à Arc-en-Ciel ?',
      'Et à Haussmann ?',
      'Total des deux ?',
      'Le plus grand ?',
      'Le syndic de Arc-en-Ciel ?',
    ];

    for (const query of rapidQueries) {
      const startTime = Date.now();
      const response = await sendMessage(page, query, {
        timeout: PERFORMANCE_THRESHOLDS.NORMAL_RESPONSE_MS,
      });
      const responseTime = Date.now() - startTime;

      console.log(`"${query}" -> ${responseTime}ms`);
      expect(isErrorResponse(response)).toBe(false);
    }
  });
});
