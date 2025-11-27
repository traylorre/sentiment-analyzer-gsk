export type ConnectionStatus = 'connected' | 'reconnecting' | 'offline' | 'error';

export interface RefreshState {
  lastRefresh: string;
  nextScheduledRefresh: string;
  refreshIntervalSeconds: number;
  countdownSeconds: number;
  isRefreshing: boolean;
}

export interface ConnectionState {
  status: ConnectionStatus;
  lastConnectedAt: string | null;
  reconnectAttempts: number;
  error: string | null;
}
