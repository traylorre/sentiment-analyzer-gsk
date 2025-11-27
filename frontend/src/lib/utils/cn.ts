import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/**
 * Merge class names with Tailwind CSS support
 * Combines clsx for conditional classes with tailwind-merge for deduplication
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
