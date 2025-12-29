/**
 * Gap Shader Primitive for lightweight-charts.
 *
 * Renders red-shaded rectangles for market closure periods (weekends, holidays).
 * Uses the Series Primitives API for custom canvas drawing.
 */

import type {
  ISeriesPrimitive,
  IPrimitivePaneView,
  IPrimitivePaneRenderer,
  SeriesAttachedParameter,
  PrimitiveHoveredItem,
  Time,
} from 'lightweight-charts';

import type { GapMarker } from '@/types/chart';

/**
 * Gap information with logical index for rendering.
 */
interface GapInfo {
  /** Logical index in the data array */
  index: number;
  /** Gap marker data */
  marker: GapMarker;
}

/**
 * Rendering context passed to the renderer.
 */
interface GapRenderContext {
  gaps: GapInfo[];
  getTimeToCoordinate: (time: Time) => number | null;
  getBarSpacing: () => number;
}

/**
 * Renderer for drawing red rectangles on the chart canvas.
 */
class GapShaderRenderer implements IPrimitivePaneRenderer {
  private context: GapRenderContext;
  private chartHeight: number;

  constructor(context: GapRenderContext, chartHeight: number) {
    this.context = context;
    this.chartHeight = chartHeight;
  }

  // The draw method receives a target with useBitmapCoordinateSpace
  draw(target: {
    useBitmapCoordinateSpace: (callback: (scope: {
      context: CanvasRenderingContext2D;
      horizontalPixelRatio: number;
      verticalPixelRatio: number;
      bitmapSize: { width: number; height: number };
    }) => void) => void;
  }): void {
    const { gaps, getTimeToCoordinate, getBarSpacing } = this.context;

    if (gaps.length === 0) return;

    target.useBitmapCoordinateSpace(({ context: ctx, horizontalPixelRatio, bitmapSize }) => {
      const barSpacing = getBarSpacing();
      const halfBar = barSpacing / 2;

      // Save context state
      ctx.save();

      // Light red with transparency for gap shading
      ctx.fillStyle = 'rgba(255, 100, 100, 0.12)';

      for (const gap of gaps) {
        const x = getTimeToCoordinate(gap.marker.time as Time);
        if (x === null) continue;

        // Draw rectangle spanning full height at the gap position
        // Convert from media coordinates to bitmap coordinates
        const rectX = Math.round((x - halfBar) * horizontalPixelRatio);
        const rectWidth = Math.round(barSpacing * horizontalPixelRatio);

        ctx.fillRect(rectX, 0, rectWidth, bitmapSize.height);
      }

      // Restore context state
      ctx.restore();
    });
  }
}

/**
 * Pane view that provides the renderer for the gap shading.
 */
class GapShaderPaneView implements IPrimitivePaneView {
  private primitive: GapShaderPrimitive;

  constructor(primitive: GapShaderPrimitive) {
    this.primitive = primitive;
  }

  zOrder(): 'bottom' | 'normal' | 'top' {
    // Draw behind the candlesticks
    return 'bottom';
  }

  renderer(): IPrimitivePaneRenderer {
    const context: GapRenderContext = {
      gaps: this.primitive.getGaps(),
      getTimeToCoordinate: this.primitive.getTimeToCoordinate.bind(this.primitive),
      getBarSpacing: this.primitive.getBarSpacing.bind(this.primitive),
    };
    return new GapShaderRenderer(context, this.primitive.getChartHeight());
  }
}

/**
 * Series Primitive that renders red-shaded rectangles for market gaps.
 *
 * Usage:
 * ```typescript
 * const gapShader = new GapShaderPrimitive();
 * candleSeries.attachPrimitive(gapShader);
 *
 * // When data changes:
 * gapShader.updateGaps(gapMarkers);
 * ```
 */
export class GapShaderPrimitive implements ISeriesPrimitive<Time> {
  private gaps: GapInfo[] = [];
  private attachedParams: SeriesAttachedParameter<Time> | null = null;
  private paneView: GapShaderPaneView;
  private chartHeight: number = 400;

  constructor() {
    this.paneView = new GapShaderPaneView(this);
  }

  /**
   * Update the gap markers to render.
   *
   * @param markers - Array of gap markers with their logical indices
   */
  updateGaps(markers: Array<{ index: number; marker: GapMarker }>): void {
    this.gaps = markers;
    this.requestUpdate();
  }

  /**
   * Set the chart height for rendering.
   */
  setChartHeight(height: number): void {
    this.chartHeight = height;
    this.requestUpdate();
  }

  /**
   * Get the current gaps.
   */
  getGaps(): GapInfo[] {
    return this.gaps;
  }

  /**
   * Get the chart height.
   */
  getChartHeight(): number {
    return this.chartHeight;
  }

  /**
   * Convert a time value to x-coordinate.
   */
  getTimeToCoordinate(time: Time): number | null {
    if (!this.attachedParams?.chart) return null;
    return this.attachedParams.chart.timeScale().timeToCoordinate(time);
  }

  /**
   * Get the current bar spacing.
   */
  getBarSpacing(): number {
    if (!this.attachedParams?.chart) return 10;
    // Use the time scale's bar spacing directly
    const barSpacing = this.attachedParams.chart.timeScale().options().barSpacing;
    return barSpacing;
  }

  // --- ISeriesPrimitive interface ---

  attached(params: SeriesAttachedParameter<Time>): void {
    this.attachedParams = params;
  }

  detached(): void {
    this.attachedParams = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return [this.paneView];
  }

  updateAllViews(): void {
    // Views update automatically via renderer
  }

  hitTest(): PrimitiveHoveredItem | null {
    // No hit testing for gap shading
    return null;
  }

  private requestUpdate(): void {
    if (this.attachedParams?.requestUpdate) {
      this.attachedParams.requestUpdate();
    }
  }
}
