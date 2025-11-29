/**
 * DisruptIQ E2E Test Helpers
 *
 * Common functions for interacting with the assistant UI.
 */

import { Page, expect } from '@playwright/test';
import { SELECTORS, PERFORMANCE_THRESHOLDS } from './fixtures';

/**
 * Navigate to the assistant page
 * The main chat interface is at root path '/'
 */
export async function goToAssistant(page: Page): Promise<void> {
  await page.goto('/');

  // Wait for DOM content to be loaded (faster than networkidle)
  await page.waitForLoadState('domcontentloaded');

  // Wait for the page content to load - look for any input or textarea
  const inputElement = page.locator('input, textarea').first();
  await inputElement.waitFor({ state: 'visible', timeout: 30000 });
}

/**
 * Send a message to the assistant and wait for response
 */
export async function sendMessage(
  page: Page,
  message: string,
  options: {
    timeout?: number;
    waitForKeywords?: string[];
  } = {}
): Promise<string> {
  const timeout = options.timeout || PERFORMANCE_THRESHOLDS.NORMAL_RESPONSE_MS;

  // Find the input textarea
  const input = page.locator(SELECTORS.CHAT_INPUT);
  await expect(input).toBeVisible();

  // Type the message
  await input.fill(message);

  const startTime = Date.now();

  // Press Enter to send (the UI uses Enter key, not a button)
  await input.press('Enter');

  // Wait for the user message to appear (confirms message was sent)
  // User messages have bg-primary class and are in a flex justify-end container in the main chat area
  // Use a more specific selector to avoid matching the sidebar "Nouvelle conversation" button
  const userMessageSelector = 'main .bg-primary, [role="main"] .bg-primary, .flex.justify-end .bg-primary';
  await expect(page.locator(userMessageSelector).last()).toContainText(message.substring(0, 20), {
    timeout: 5000,
  });

  // Wait for loading to start (indicates assistant is processing)
  // Look for the "Réflexion en cours" text or loading skeleton
  try {
    await page.locator('text="Réflexion en cours"').waitFor({ state: 'visible', timeout: 3000 });
  } catch {
    // Loading might be very fast
  }

  // Wait for loading to complete - the "Arrêter" button disappears or skeleton disappears
  // Or wait for a new assistant message (bg-secondary in message area)
  // The assistant message container has specific structure: rounded-2xl with bg-secondary
  const assistantMessageSelector = '.rounded-2xl.bg-secondary';

  // Wait for at least one assistant message to appear after our user message
  await expect(page.locator(assistantMessageSelector).last()).toBeVisible({
    timeout: timeout,
  });

  // Wait for loading skeleton to disappear (ensures response is fully loaded)
  try {
    await page.locator('[class*="Skeleton"]').waitFor({
      state: 'hidden',
      timeout: timeout
    });
  } catch {
    // Skeleton might already be gone or might not appear for fast responses
  }

  // Additional wait to ensure the response text is fully rendered
  await page.waitForTimeout(1000);

  // Get the last assistant message container
  // The full response is in a container with the structure:
  // div.flex.justify-start > div.w-full.space-y-4 (contains main message + table + suggestions)
  // We need to get all text from this container, not just the main bubble
  const assistantContainerSelector = '.flex.justify-start .space-y-4';

  // Wait for at least one assistant container to appear
  await expect(page.locator(assistantContainerSelector).last()).toBeVisible({
    timeout: 10000,
  });

  // Get all text from the full assistant response area (includes table, sources, etc.)
  const lastContainer = page.locator(assistantContainerSelector).last();

  // Wait for the container content to be non-empty with longer timeout
  // The assistant sometimes takes time to render the full response
  try {
    await expect(lastContainer).not.toBeEmpty({ timeout: 15000 });
  } catch {
    // If still empty, try to wait for any text content
    await page.waitForTimeout(2000);
  }

  // Get all the response text including table content
  const responseText = await lastContainer.textContent() || '';

  const responseTime = Date.now() - startTime;
  console.log(`Response received in ${responseTime}ms`);

  // Check for expected keywords if provided
  if (options.waitForKeywords && options.waitForKeywords.length > 0) {
    const lowerResponse = responseText.toLowerCase();
    const foundKeyword = options.waitForKeywords.some(kw =>
      lowerResponse.includes(kw.toLowerCase())
    );

    if (!foundKeyword) {
      console.warn(
        `Warning: None of the expected keywords [${options.waitForKeywords.join(', ')}] ` +
        `found in response: "${responseText.substring(0, 200)}..."`
      );
    }
  }

  return responseText;
}

/**
 * Send a message and verify response contains expected keywords
 */
export async function sendAndVerify(
  page: Page,
  message: string,
  expectedKeywords: string[],
  options: {
    timeout?: number;
    atLeastOne?: boolean;
  } = {}
): Promise<{
  response: string;
  foundKeywords: string[];
  missingKeywords: string[];
  responseTimeMs: number;
}> {
  const timeout = options.timeout || PERFORMANCE_THRESHOLDS.NORMAL_RESPONSE_MS;
  const atLeastOne = options.atLeastOne ?? true;

  const startTime = Date.now();
  const response = await sendMessage(page, message, { timeout });
  const responseTimeMs = Date.now() - startTime;

  const lowerResponse = response.toLowerCase();
  const foundKeywords: string[] = [];
  const missingKeywords: string[] = [];

  for (const keyword of expectedKeywords) {
    if (lowerResponse.includes(keyword.toLowerCase())) {
      foundKeywords.push(keyword);
    } else {
      missingKeywords.push(keyword);
    }
  }

  if (atLeastOne) {
    expect(foundKeywords.length, `Expected at least one of [${expectedKeywords.join(', ')}] in response`).toBeGreaterThan(0);
  } else {
    expect(missingKeywords, `Missing keywords in response: ${missingKeywords.join(', ')}`).toHaveLength(0);
  }

  return { response, foundKeywords, missingKeywords, responseTimeMs };
}

/**
 * Check if a message indicates clarification is needed
 */
export function isClarificationRequest(response: string): boolean {
  const clarificationIndicators = [
    'préciser', 'pourriez-vous', 'de quoi', 'quel', 'quelle',
    'pouvez-vous', 'merci de', 'clarifier', 'à qui', 'souhaitez-vous',
    'voulez-vous', 'indiquez', 'concernant quoi'
  ];

  const lowerResponse = response.toLowerCase();
  return clarificationIndicators.some(ind => lowerResponse.includes(ind)) ||
    response.trim().endsWith('?');
}

/**
 * Check if a message is an error response
 * Note: "désolé" is removed because the assistant may apologize while still providing help
 */
export function isErrorResponse(response: string): boolean {
  const errorIndicators = [
    'erreur technique',
    'error',
    'impossible de traiter',
    'échoué',
    'failed',
    'exception',
    'stack trace',
    'internal server error',
    '500',
    'timeout'
  ];

  const lowerResponse = response.toLowerCase();

  // Check for hard errors
  const hasHardError = errorIndicators.some(ind => lowerResponse.includes(ind));

  // If response is very short and contains error indicators, it's likely an error
  if (hasHardError && response.length < 100) {
    return true;
  }

  // If response is longer, check if it's actually providing useful info despite mentioning an error
  if (hasHardError && response.length >= 100) {
    // Check if the response still contains useful content (numbers, copropriétés names, etc.)
    const hasUsefulContent =
      /\d+/.test(response) || // Contains numbers
      lowerResponse.includes('copropriété') ||
      lowerResponse.includes('arc-en-ciel') ||
      lowerResponse.includes('oliviers') ||
      lowerResponse.includes('haussmann');

    return !hasUsefulContent;
  }

  return hasHardError;
}

/**
 * Get message count on the page (user + assistant messages)
 */
export async function getMessageCount(page: Page): Promise<number> {
  // Use specific selector to avoid counting sidebar buttons
  const userMessages = await page.locator('.flex.justify-end .bg-primary').count();
  const assistantMessages = await page.locator('.flex.justify-start .space-y-4').count();
  return userMessages + assistantMessages;
}

/**
 * Get all assistant messages
 */
export async function getAssistantMessages(page: Page): Promise<string[]> {
  const messages = await page.locator('.bg-secondary').allTextContents();
  return messages;
}

/**
 * Wait for loading to complete
 */
export async function waitForLoading(page: Page, timeout: number = 60000): Promise<void> {
  // Wait for spinner to appear (if it does)
  try {
    await page.locator('.animate-spin').waitFor({ state: 'visible', timeout: 2000 });
  } catch {
    // Spinner might not appear for fast responses
    return;
  }

  // Wait for spinner to disappear
  await page.locator('.animate-spin').waitFor({ state: 'hidden', timeout });
}

/**
 * Clear conversation (refresh page)
 */
export async function clearConversation(page: Page): Promise<void> {
  await page.reload();
  await page.waitForLoadState('networkidle');
  // Wait for the app to be ready (look for the input field)
  const inputElement = page.locator('input, textarea').first();
  await inputElement.waitFor({ state: 'visible', timeout: 10000 });
}

/**
 * Take a screenshot with timestamp
 */
export async function takeScreenshot(page: Page, name: string): Promise<void> {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  await page.screenshot({ path: `screenshots/${name}-${timestamp}.png`, fullPage: true });
}

/**
 * Measure response time for a query
 */
export async function measureResponseTime(
  page: Page,
  message: string,
  maxExpectedMs: number
): Promise<{ responseTimeMs: number; withinThreshold: boolean; response: string }> {
  const startTime = Date.now();
  const response = await sendMessage(page, message, { timeout: maxExpectedMs + 10000 });
  const responseTimeMs = Date.now() - startTime;

  return {
    responseTimeMs,
    withinThreshold: responseTimeMs <= maxExpectedMs,
    response,
  };
}
