import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { chaosApi } from '@/lib/api/chaos';
import type { CreateExperimentRequest } from '@/types/chaos';

const CHAOS_KEYS = {
  experiments: ['chaos', 'experiments'] as const,
  experimentReport: (id: string) => ['chaos', 'experiment-report', id] as const,
};

export function useExperiments() {
  const query = useQuery({
    queryKey: CHAOS_KEYS.experiments,
    queryFn: () => chaosApi.listExperiments({ limit: 50 }),
  });

  const hasActive = query.data?.some(
    (e) => e.status === 'running' || e.status === 'pending'
  );

  return {
    ...query,
    hasActive,
    activeExperiments: query.data?.filter(
      (e) => e.status === 'running' || e.status === 'pending'
    ) ?? [],
    historyExperiments: query.data?.filter(
      (e) => e.status === 'completed' || e.status === 'failed' || e.status === 'stopped'
    ) ?? [],
    // Enable 10s polling when active experiments exist
    refetchInterval: hasActive ? 10_000 : false,
  };
}

export function useCreateExperiment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateExperimentRequest) => chaosApi.createExperiment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAOS_KEYS.experiments });
      toast.success('Experiment created');
    },
    onError: (error) => {
      toast.error(`Failed to create experiment: ${error.message}`);
    },
  });
}

export function useStartExperiment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => chaosApi.startExperiment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAOS_KEYS.experiments });
      toast.success('Experiment started');
    },
    onError: (error) => {
      toast.error(`Failed to start experiment: ${error.message}`);
    },
  });
}

export function useStopExperiment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => chaosApi.stopExperiment(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CHAOS_KEYS.experiments });
      toast.success('Experiment stopped');
    },
    onError: (error) => {
      toast.error(`Failed to stop experiment: ${error.message}`);
    },
  });
}

export function useExperimentReport(id: string | null) {
  return useQuery({
    queryKey: CHAOS_KEYS.experimentReport(id ?? ''),
    queryFn: () => chaosApi.getExperimentReport(id!),
    enabled: !!id,
  });
}
