import { api } from './client';
import type {
  Configuration,
  ConfigurationList,
  CreateConfigRequest,
  TickerConfig,
  UpdateConfigRequest,
} from '@/types/config';

// M1 WI-5: the backend speaks snake_case (config_id, timeframe_days, ...), the
// frontend types are camelCase, and client.ts does a bare response.json() with
// no transform. Previously configsApi cast the raw response straight to the
// camelCase type, so `configId`/`updatedAt` were ALWAYS undefined — the delete
// dialog (gated on `!!configId`) never opened and dates rendered "Invalid Date".
// It stayed hidden because the only path that exercised delete lost its session
// on reload (broken local mock) and skipped it. Map explicitly, both directions.

/** Raw snake_case configuration as returned by the backend. */
interface RawConfiguration {
  config_id: string;
  name: string;
  tickers: TickerConfig[];
  timeframe_days: number;
  include_extended_hours: boolean;
  created_at: string;
  updated_at: string;
}

interface RawConfigurationList {
  configurations: RawConfiguration[];
  max_allowed: number;
}

function mapConfiguration(raw: RawConfiguration): Configuration {
  return {
    configId: raw.config_id,
    name: raw.name,
    tickers: raw.tickers ?? [],
    timeframeDays: raw.timeframe_days,
    includeExtendedHours: raw.include_extended_hours,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

function mapConfigurationList(raw: RawConfigurationList): ConfigurationList {
  return {
    configurations: (raw.configurations ?? []).map(mapConfiguration),
    maxAllowed: raw.max_allowed,
  };
}

/**
 * Map a camelCase create/update request to the snake_case body the backend
 * expects. Without this, `timeframe_days` / `include_extended_hours` were never
 * sent, so the backend silently fell back to defaults (7 days, no extended
 * hours) and the user's chosen settings were dropped.
 */
function toConfigBody(
  req: CreateConfigRequest | UpdateConfigRequest
): Record<string, unknown> {
  const body: Record<string, unknown> = {};
  if (req.name !== undefined) body.name = req.name;
  if (req.tickers !== undefined) body.tickers = req.tickers;
  if (req.timeframeDays !== undefined) body.timeframe_days = req.timeframeDays;
  if (req.includeExtendedHours !== undefined) {
    body.include_extended_hours = req.includeExtendedHours;
  }
  return body;
}

export const configsApi = {
  /**
   * List all configurations for the current user
   */
  list: async (): Promise<ConfigurationList> => {
    const raw = await api.get<RawConfigurationList>('/api/v2/configurations');
    return mapConfigurationList(raw);
  },

  /**
   * Get a single configuration by ID
   */
  get: async (configId: string): Promise<Configuration> => {
    const raw = await api.get<RawConfiguration>(
      `/api/v2/configurations/${configId}`
    );
    return mapConfiguration(raw);
  },

  /**
   * Create a new configuration
   */
  create: async (config: CreateConfigRequest): Promise<Configuration> => {
    const raw = await api.post<RawConfiguration>(
      '/api/v2/configurations',
      toConfigBody(config)
    );
    return mapConfiguration(raw);
  },

  /**
   * Update an existing configuration
   */
  update: async (
    configId: string,
    updates: UpdateConfigRequest
  ): Promise<Configuration> => {
    const raw = await api.patch<RawConfiguration>(
      `/api/v2/configurations/${configId}`,
      toConfigBody(updates)
    );
    return mapConfiguration(raw);
  },

  /**
   * Delete a configuration
   */
  delete: (configId: string) =>
    api.delete<void>(`/api/v2/configurations/${configId}`),
};
