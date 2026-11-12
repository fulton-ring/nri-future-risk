import { release } from '../data/releases';

/** Product events sent to PEDP's PostHog project. Never include search text or other free-form input. */
export type AnalyticsEvent =
  | 'map_setting_changed'
  | 'map_layer_changed'
  | 'data_version_changed'
  | 'area_selected'
  | 'location_searched'
  | 'result_view_changed'
  | 'share_link_copied'
  | 'area_data_downloaded'
  | 'welcome_guide_opened'
  | 'panel_toggled'
  | 'legend_toggled'
  | 'map_reset';

type PostHog = { capture: (event: string, properties?: Record<string, unknown>, options?: Record<string, unknown>) => void };

/**
 * Capture an event with the selected release attached. Pass `beforeNavigation` for events
 * fired right before a page load so the browser still delivers them.
 */
export function track(event: AnalyticsEvent, properties: Record<string, unknown> = {}, { beforeNavigation = false } = {}) {
  try {
    const posthog = (window as unknown as { posthog?: PostHog }).posthog;
    posthog?.capture(event, { release: release.id, ...properties }, beforeNavigation ? { transport: 'sendBeacon' } : undefined);
  } catch {
    // Analytics must never break the explorer (blocked scripts, privacy extensions).
  }
}
