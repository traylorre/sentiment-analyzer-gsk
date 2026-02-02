/**
 * Cross-tab synchronization utility using BroadcastChannel API.
 *
 * Feature: 1191 - Mid-Session Tier Upgrade
 *
 * Enables real-time communication between browser tabs for auth state changes.
 * Falls back to localStorage events for browsers without BroadcastChannel support.
 */

import type { UserRole } from '@/types/auth';

// Message types for cross-tab communication
export type BroadcastAction = 'ROLE_UPGRADED' | 'SIGN_OUT' | 'REFRESH';

export interface BroadcastMessage {
  type: 'AUTH';
  version: 1;
  timestamp: number;
  sourceTabId: string;
  data: {
    action: BroadcastAction;
    userId?: string;
    newRole?: UserRole;
  };
}

// Generate unique tab ID
const TAB_ID = typeof crypto !== 'undefined' ? crypto.randomUUID() : Math.random().toString(36);

// Channel name for auth sync
const CHANNEL_NAME = 'sentiment-analyzer-auth';

// LocalStorage key for fallback
const STORAGE_KEY = 'broadcast:auth';

type MessageHandler = (data: BroadcastMessage['data']) => void;

/**
 * BroadcastChannel wrapper with localStorage fallback.
 *
 * Usage:
 * ```typescript
 * const sync = new AuthBroadcastSync();
 * sync.connect();
 * sync.on('ROLE_UPGRADED', (data) => {
 *   // Handle role upgrade from other tab
 *   refreshUserProfile();
 * });
 * sync.broadcast('ROLE_UPGRADED', { userId: 'xxx', newRole: 'paid' });
 * ```
 */
export class AuthBroadcastSync {
  private channel: BroadcastChannel | null = null;
  private listeners = new Map<BroadcastAction, MessageHandler[]>();
  private useNative: boolean;

  constructor() {
    this.useNative = typeof BroadcastChannel !== 'undefined';
  }

  /**
   * Connect to the broadcast channel.
   * Call this on app initialization.
   */
  connect(): void {
    if (typeof window === 'undefined') return; // SSR guard

    if (this.useNative) {
      this.channel = new BroadcastChannel(CHANNEL_NAME);
      this.channel.onmessage = (event: MessageEvent<BroadcastMessage>) => {
        this.handleMessage(event.data);
      };
    } else {
      // Fallback: localStorage events
      window.addEventListener('storage', this.handleStorageEvent);
    }
  }

  /**
   * Disconnect from the broadcast channel.
   * Call this on app unmount.
   */
  disconnect(): void {
    if (this.channel) {
      this.channel.close();
      this.channel = null;
    }
    if (!this.useNative && typeof window !== 'undefined') {
      window.removeEventListener('storage', this.handleStorageEvent);
    }
    this.listeners.clear();
  }

  /**
   * Register a handler for a specific action.
   */
  on(action: BroadcastAction, handler: MessageHandler): void {
    const handlers = this.listeners.get(action) || [];
    handlers.push(handler);
    this.listeners.set(action, handlers);
  }

  /**
   * Remove a handler for a specific action.
   */
  off(action: BroadcastAction, handler: MessageHandler): void {
    const handlers = this.listeners.get(action) || [];
    const index = handlers.indexOf(handler);
    if (index > -1) {
      handlers.splice(index, 1);
    }
  }

  /**
   * Broadcast a message to all other tabs.
   */
  broadcast(action: BroadcastAction, data: Partial<BroadcastMessage['data']> = {}): void {
    const message: BroadcastMessage = {
      type: 'AUTH',
      version: 1,
      timestamp: Date.now(),
      sourceTabId: TAB_ID,
      data: {
        action,
        ...data,
      },
    };

    if (this.useNative && this.channel) {
      this.channel.postMessage(message);
    } else if (typeof window !== 'undefined') {
      // Fallback: localStorage (triggers storage event in other tabs)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(message));
      // Clear immediately (we only need the event, not the data)
      localStorage.removeItem(STORAGE_KEY);
    }
  }

  /**
   * Handle incoming messages.
   */
  private handleMessage(message: BroadcastMessage): void {
    // Ignore messages from this tab
    if (message.sourceTabId === TAB_ID) return;

    // Ignore messages with wrong type/version
    if (message.type !== 'AUTH' || message.version !== 1) return;

    const handlers = this.listeners.get(message.data.action) || [];
    handlers.forEach((handler) => {
      try {
        handler(message.data);
      } catch (error) {
        console.error('[AuthBroadcastSync] Handler error:', error);
      }
    });
  }

  /**
   * Handle localStorage storage events (fallback).
   */
  private handleStorageEvent = (event: StorageEvent): void => {
    if (event.key !== STORAGE_KEY || !event.newValue) return;

    try {
      const message = JSON.parse(event.newValue) as BroadcastMessage;
      this.handleMessage(message);
    } catch (error) {
      // Log parse errors for debugging cross-tab sync issues
      console.warn('[AuthBroadcastSync] Failed to parse localStorage message:', error);
    }
  };
}

// Singleton instance
let instance: AuthBroadcastSync | null = null;

/**
 * Get the singleton AuthBroadcastSync instance.
 */
export function getAuthBroadcastSync(): AuthBroadcastSync {
  if (!instance) {
    instance = new AuthBroadcastSync();
  }
  return instance;
}
