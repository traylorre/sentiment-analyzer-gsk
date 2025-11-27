export type AlertType = 'sentiment_threshold' | 'volatility_threshold';
export type ThresholdDirection = 'above' | 'below';

export interface AlertRule {
  alertId: string;
  configId: string;
  ticker: string;
  alertType: AlertType;
  thresholdValue: number;
  thresholdDirection: ThresholdDirection;
  isEnabled: boolean;
  lastTriggeredAt: string | null;
  triggerCount: number;
  createdAt: string;
}

export interface AlertList {
  alerts: AlertRule[];
  total: number;
  dailyEmailQuota: {
    used: number;
    limit: number;
    resetsAt: string;
  };
}

export interface CreateAlertRequest {
  configId: string;
  ticker: string;
  alertType: AlertType;
  thresholdValue: number;
  thresholdDirection: ThresholdDirection;
}

export interface Notification {
  notificationId: string;
  alertId: string;
  ticker: string;
  alertType: AlertType;
  triggeredValue: number;
  thresholdValue: number;
  subject: string;
  sentAt: string;
  status: 'sent' | 'failed' | 'pending';
  deepLink: string;
}
