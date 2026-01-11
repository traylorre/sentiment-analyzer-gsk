/**
 * Cross-Tab Broadcast Message Contract
 * Used by BroadcastChannel for auth state sync
 */

export type BroadcastAction =
  | 'ROLE_UPGRADED'  // User upgraded to paid
  | 'SIGN_OUT'       // User signed out
  | 'REFRESH';       // Token refresh triggered

export interface BroadcastMessage {
  /** Message category */
  type: 'AUTH';

  /** Schema version for forward compatibility */
  version: 1;

  /** Unix timestamp in milliseconds */
  timestamp: number;

  /** Source tab ID to prevent echo */
  sourceTabId: string;

  /** Message payload */
  data: {
    action: BroadcastAction;
    userId?: string;
    newRole?: 'anonymous' | 'free' | 'paid' | 'operator';
  };
}

/**
 * Example messages:
 *
 * Role upgrade broadcast:
 * {
 *   type: 'AUTH',
 *   version: 1,
 *   timestamp: 1704931200000,
 *   sourceTabId: 'abc123',
 *   data: {
 *     action: 'ROLE_UPGRADED',
 *     userId: 'user_123',
 *     newRole: 'paid'
 *   }
 * }
 *
 * Sign out broadcast:
 * {
 *   type: 'AUTH',
 *   version: 1,
 *   timestamp: 1704931200000,
 *   sourceTabId: 'abc123',
 *   data: {
 *     action: 'SIGN_OUT'
 *   }
 * }
 */
