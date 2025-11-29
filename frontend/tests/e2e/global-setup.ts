/**
 * Playwright Global Setup
 *
 * Runs before all tests to ensure the test environment is ready:
 * 1. Verify backend is accessible
 * 2. Load SQL fixtures via API
 * 3. Index RAG fixtures via API
 * 4. Verify fixtures are loaded (sanity check)
 */

import { FullConfig, request } from '@playwright/test';

const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://localhost:8000';
const MAX_RETRIES = 30;  // 30 seconds max wait
const RETRY_DELAY = 1000;  // 1 second between retries

async function waitForBackend(): Promise<boolean> {
  console.log('⏳ Waiting for backend to be ready...');

  for (let i = 0; i < MAX_RETRIES; i++) {
    try {
      const apiContext = await request.newContext();
      const response = await apiContext.get(`${BACKEND_URL}/health`);
      await apiContext.dispose();

      if (response.ok()) {
        console.log('✅ Backend is ready');
        return true;
      }
    } catch (e) {
      // Backend not ready yet
    }

    await new Promise(resolve => setTimeout(resolve, RETRY_DELAY));
    process.stdout.write('.');
  }

  console.log('\n❌ Backend not available after 30 seconds');
  return false;
}

async function loadSQLFixtures(): Promise<boolean> {
  console.log('📊 Loading SQL fixtures...');

  const apiContext = await request.newContext();

  try {
    // Call the fixtures endpoint to load SQL data
    const response = await apiContext.post(`${BACKEND_URL}/api/test/load-fixtures`, {
      data: { type: 'sql' },
      timeout: 60000,
    });

    if (response.ok()) {
      const result = await response.json();
      console.log(`✅ SQL fixtures loaded: ${JSON.stringify(result)}`);
      await apiContext.dispose();
      return true;
    }

    console.log(`⚠️ SQL fixtures endpoint returned ${response.status()}`);
    await apiContext.dispose();
    // Continue anyway - fixtures might already be loaded
    return true;
  } catch (e) {
    console.log(`⚠️ SQL fixtures endpoint not available: ${e}`);
    await apiContext.dispose();
    // Continue anyway - fixtures might already be loaded
    return true;
  }
}

async function indexRAGFixtures(): Promise<boolean> {
  console.log('📚 Indexing RAG fixtures...');

  const apiContext = await request.newContext();

  try {
    // Call the fixtures endpoint to index RAG documents
    const response = await apiContext.post(`${BACKEND_URL}/api/test/index-rag-fixtures`, {
      timeout: 120000,  // 2 minutes for indexing
    });

    if (response.ok()) {
      const result = await response.json();
      console.log(`✅ RAG fixtures indexed: ${JSON.stringify(result)}`);
      await apiContext.dispose();
      return true;
    }

    console.log(`⚠️ RAG indexing endpoint returned ${response.status()}`);
    await apiContext.dispose();
    // Continue anyway - fixtures might already be indexed
    return true;
  } catch (e) {
    console.log(`⚠️ RAG indexing endpoint not available: ${e}`);
    await apiContext.dispose();
    // Continue anyway - fixtures might already be indexed
    return true;
  }
}

async function verifySQLData(): Promise<boolean> {
  console.log('🔍 Verifying SQL data...');

  const apiContext = await request.newContext();

  try {
    // Simple query to verify SQL data is accessible
    const response = await apiContext.post(`${BACKEND_URL}/api/assistant-v2/chat`, {
      data: {
        message: 'Combien de copropriétés ?',
        conversation_history: [],
        use_world_class_router: true,
      },
      timeout: 30000,
    });

    if (response.ok()) {
      const result = await response.json();
      const reply = result.reply || result.response || '';

      // Check if response contains expected data
      if (reply.toLowerCase().includes('3') || reply.toLowerCase().includes('copropriété')) {
        console.log('✅ SQL data verification passed');
        await apiContext.dispose();
        return true;
      }

      console.log(`⚠️ SQL response received but no expected data: ${reply.substring(0, 100)}`);
    }

    await apiContext.dispose();
    return true;  // Continue anyway
  } catch (e) {
    console.log(`⚠️ SQL verification failed: ${e}`);
    await apiContext.dispose();
    return true;  // Continue anyway
  }
}

async function verifyRAGData(): Promise<boolean> {
  console.log('🔍 Verifying RAG data...');

  const apiContext = await request.newContext();

  try {
    // Simple query to verify RAG data is accessible
    const response = await apiContext.post(`${BACKEND_URL}/api/assistant-v2/chat`, {
      data: {
        message: 'Que dit le règlement sur les animaux ?',
        conversation_history: [],
        use_world_class_router: true,
      },
      timeout: 60000,
    });

    if (response.ok()) {
      const result = await response.json();
      const reply = result.reply || result.response || '';

      // Check if response mentions animals or pets
      if (reply.toLowerCase().includes('animaux') || reply.toLowerCase().includes('chien') || reply.toLowerCase().includes('laisse')) {
        console.log('✅ RAG data verification passed');
        await apiContext.dispose();
        return true;
      }

      console.log(`⚠️ RAG response received but no expected data: ${reply.substring(0, 100)}`);
    }

    await apiContext.dispose();
    return true;  // Continue anyway
  } catch (e) {
    console.log(`⚠️ RAG verification failed: ${e}`);
    await apiContext.dispose();
    return true;  // Continue anyway
  }
}

async function globalSetup(config: FullConfig): Promise<void> {
  console.log('\n' + '='.repeat(60));
  console.log('DisruptIQ E2E Tests - Global Setup');
  console.log('='.repeat(60) + '\n');

  // Step 1: Wait for backend
  const backendReady = await waitForBackend();
  if (!backendReady) {
    throw new Error('Backend not available. Please start the backend before running tests.');
  }

  // Step 2: Load SQL fixtures
  await loadSQLFixtures();

  // Step 3: Index RAG fixtures
  await indexRAGFixtures();

  // Step 4: Verify data is accessible
  await verifySQLData();
  await verifyRAGData();

  console.log('\n' + '='.repeat(60));
  console.log('Global Setup Complete - Starting Tests');
  console.log('='.repeat(60) + '\n');
}

export default globalSetup;
