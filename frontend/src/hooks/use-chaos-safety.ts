import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { chaosApi } from '@/lib/api/chaos';
import type { GateState } from '@/types/chaos';

const SAFETY_KEYS = {
  gate: ['chaos', 'gate'] as const,
};

export function useHealthCheck() {
  return useMutation({
    mutationFn: () => chaosApi.getHealth(),
    onError: (error) => {
      toast.error(`Health check failed: ${error.message}`);
    },
  });
}

export function useGateState() {
  return useQuery({
    queryKey: SAFETY_KEYS.gate,
    queryFn: () => chaosApi.getGate(),
    refetchInterval: 30_000,
  });
}

export function useSetGateState() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (state: GateState) => chaosApi.setGate(state as 'armed' | 'disarmed'),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: SAFETY_KEYS.gate });
      toast.success(`Gate ${data.state === 'armed' ? 'armed' : 'disarmed'}`);
    },
    onError: (error) => {
      toast.error(`Failed to update gate: ${error.message}`);
    },
  });
}

export function useAndonCord() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => chaosApi.triggerAndonCord(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: SAFETY_KEYS.gate });
      queryClient.invalidateQueries({ queryKey: ['chaos', 'experiments'] });
      if (data.failed > 0) {
        toast.error(`Emergency stop: ${data.restored} restored, ${data.failed} failed`);
      } else {
        toast.success(`Emergency stop complete: ${data.restored} experiments restored`);
      }
    },
    onError: (error) => {
      toast.error(`Emergency stop failed: ${error.message}`);
    },
  });
}
