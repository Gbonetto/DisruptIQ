/**
 * useUIContext Hook
 *
 * Détecte automatiquement le contexte UI pour optimiser la classification d'intent.
 * Permet au backend de bypasser la classification LLM quand l'intent est évident.
 *
 * Part of Sprint 1 - Level 0 Optimization (UI Context Bypass)
 */

import { useState, useEffect } from 'react';
import { useActiveDocuments } from '@/contexts/ActiveDocumentsContext';

export interface UIContext {
  ui_mode?: string;
  action_button?: string;
  selected_document_id?: number;
  active_document_ids?: number[];
}

export type UIMode =
  | 'chat'              // Default chat mode
  | 'sql_query_builder' // SQL/Database queries
  | 'document_viewer'   // Document analysis
  | 'email_composer'    // Email generation
  | 'legal_analyzer'    // Legal analysis
  | 'web_search'        // Web search
  | null;

export const useUIContext = () => {
  const [currentMode, setCurrentMode] = useState<UIMode>('chat');
  const [lastAction, setLastAction] = useState<string | null>(null);
  const { activeDocumentIds } = useActiveDocuments();

  /**
   * Build UI context object for backend
   * This context helps the backend bypass classification when intent is obvious
   */
  const buildContext = (): UIContext => {
    const context: UIContext = {};

    // Add UI mode if not default chat
    if (currentMode && currentMode !== 'chat') {
      context.ui_mode = currentMode;
    }

    // Add last action button if present
    if (lastAction) {
      context.action_button = lastAction;
    }

    // Add active documents
    if (activeDocumentIds && activeDocumentIds.length > 0) {
      context.active_document_ids = activeDocumentIds;

      // If only one document, also set selected_document_id
      if (activeDocumentIds.length === 1) {
        context.selected_document_id = activeDocumentIds[0];
      }
    }

    return context;
  };

  /**
   * Trigger an action button (for UI bypass)
   * Example: triggerAction('generate_email')
   */
  const triggerAction = (action: string) => {
    setLastAction(action);

    // Clear after 5 seconds (action is one-time)
    setTimeout(() => {
      setLastAction(null);
    }, 5000);
  };

  /**
   * Change UI mode
   * Example: setMode('sql_query_builder')
   */
  const setMode = (mode: UIMode) => {
    setCurrentMode(mode);
  };

  /**
   * Reset to default chat mode
   */
  const resetMode = () => {
    setCurrentMode('chat');
    setLastAction(null);
  };

  // Log context changes in dev mode
  useEffect(() => {
    if (import.meta.env.DEV) {
      const context = buildContext();
      if (Object.keys(context).length > 0) {
        console.log('[useUIContext] Context updated:', context);
      }
    }
  }, [currentMode, lastAction, activeDocumentIds]);

  return {
    currentMode,
    lastAction,
    buildContext,
    triggerAction,
    setMode,
    resetMode,
  };
};
