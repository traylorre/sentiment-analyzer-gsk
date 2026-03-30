import { useAuthStore } from '@/stores/auth-store';

export const useIsOperator = () =>
  useAuthStore((state) => state.user?.role === 'operator');

export const useIsOperatorLoading = () =>
  useAuthStore((state) => state.isLoading);
