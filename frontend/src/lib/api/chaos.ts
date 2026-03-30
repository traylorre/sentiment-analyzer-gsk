import { api } from './client';
import type {
  Experiment,
  CreateExperimentRequest,
  ExperimentReport,
  Report,
  ReportListResponse,
  ComparisonResult,
  TrendDataPoint,
  HealthCheck,
  GateResponse,
  AndonResult,
  MetricsResponse,
} from '@/types/chaos';

export const chaosApi = {
  // --- Experiment Management ---

  createExperiment: (data: CreateExperimentRequest) =>
    api.post<Experiment>('/chaos/experiments', data),

  listExperiments: (params?: { limit?: number; status?: string }) =>
    api.get<Experiment[]>('/chaos/experiments', { params }),

  getExperiment: (id: string) =>
    api.get<Experiment>(`/chaos/experiments/${id}`),

  startExperiment: (id: string) =>
    api.post<Experiment>(`/chaos/experiments/${id}/start`),

  stopExperiment: (id: string) =>
    api.post<Experiment>(`/chaos/experiments/${id}/stop`),

  getExperimentReport: (id: string) =>
    api.get<ExperimentReport>(`/chaos/experiments/${id}/report`),

  deleteExperiment: (id: string) =>
    api.delete<{ message: string }>(`/chaos/experiments/${id}`),

  // --- Report Management ---

  listReports: (params?: {
    scenario_type?: string;
    verdict?: string;
    limit?: number;
    cursor?: string;
  }) => api.get<ReportListResponse>('/chaos/reports', { params }),

  getReport: (id: string) =>
    api.get<Report>(`/chaos/reports/${id}`),

  compareReports: (id: string, baselineId: string) =>
    api.get<ComparisonResult>(`/chaos/reports/${id}/compare`, {
      params: { baseline_id: baselineId },
    }),

  getTrends: (scenarioType: string, limit?: number) =>
    api.get<TrendDataPoint[]>(`/chaos/reports/trends/${scenarioType}`, {
      params: { limit },
    }),

  // --- Safety Controls ---

  getHealth: () =>
    api.get<HealthCheck>('/chaos/health'),

  getGate: () =>
    api.get<GateResponse>('/chaos/gate'),

  setGate: (state: 'armed' | 'disarmed') =>
    api.put<GateResponse>('/chaos/gate', { state }),

  triggerAndonCord: () =>
    api.post<AndonResult>('/chaos/andon-cord'),

  // --- Metrics ---

  getMetrics: (params?: {
    start_time?: string;
    end_time?: string;
    period?: number;
  }) => api.get<MetricsResponse>('/chaos/metrics', { params }),
};
