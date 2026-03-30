import { useQuery } from '@tanstack/react-query';
import { chaosApi } from '@/lib/api/chaos';

const REPORT_KEYS = {
  list: (filters: { scenario_type?: string; verdict?: string; cursor?: string }) =>
    ['chaos', 'reports', filters] as const,
  detail: (id: string) => ['chaos', 'report', id] as const,
  compare: (id: string, baselineId: string) =>
    ['chaos', 'report-compare', id, baselineId] as const,
  trends: (scenario: string, limit: number) =>
    ['chaos', 'trends', scenario, limit] as const,
};

export function useReports(filters: {
  scenario_type?: string;
  verdict?: string;
  cursor?: string;
  limit?: number;
}) {
  return useQuery({
    queryKey: REPORT_KEYS.list(filters),
    queryFn: () => chaosApi.listReports(filters),
    staleTime: 30_000,
  });
}

export function useReport(id: string | null) {
  return useQuery({
    queryKey: REPORT_KEYS.detail(id ?? ''),
    queryFn: () => chaosApi.getReport(id!),
    enabled: !!id,
    staleTime: 60_000,
  });
}

export function useCompareReports(currentId: string | null, baselineId: string | null) {
  return useQuery({
    queryKey: REPORT_KEYS.compare(currentId ?? '', baselineId ?? ''),
    queryFn: () => chaosApi.compareReports(currentId!, baselineId!),
    enabled: !!currentId && !!baselineId,
  });
}

export function useTrends(scenario: string | null, limit: number = 20) {
  return useQuery({
    queryKey: REPORT_KEYS.trends(scenario ?? '', limit),
    queryFn: () => chaosApi.getTrends(scenario!, limit),
    enabled: !!scenario,
    staleTime: 60_000,
  });
}
