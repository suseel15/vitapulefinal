export const MovementQuality = Object.freeze({
  GOOD: "GOOD",
  MODERATE: "MODERATE",
  NEEDS_ATTENTION: "NEEDS_ATTENTION",
  INSUFFICIENT_DATA: "INSUFFICIENT_DATA",
});

export const FatigueSignal = Object.freeze({
  LOW: "LOW",
  MODERATE: "MODERATE",
  HIGH: "HIGH",
  INSUFFICIENT_DATA: "INSUFFICIENT_DATA",
});

export class MovementDataSource {
  async nextSample() {
    throw new Error("MovementDataSource.nextSample must be implemented.");
  }
}

export class SimulationMovementDataSource extends MovementDataSource {
  constructor({ scenario = "NORMAL", seed = 17 } = {}) {
    super();
    this.scenario = scenario;
    this.randomState = seed >>> 0;
    this.samplesSeen = 0;
  }

  nextSample(timestamp = Date.now()) {
    this.samplesSeen += 1;
    if (this.scenario === "CONNECTION_DROP" && this.samplesSeen % 60 >= 30 && this.samplesSeen % 60 < 45) {
      return null;
    }
    this.randomState = (1664525 * this.randomState + 1013904223) >>> 0;
    const random = (this.randomState / 0xffffffff - 0.5);
    const phase = (timestamp % 4000) / 4000 * Math.PI * 2;
    const noiseScale = this.scenario === "GOOD_FORM" ? 0.008
      : ["POOR_FORM", "ABNORMAL_MOVEMENT"].includes(this.scenario) ? 0.13 : 0.035;
    const fatigue = this.scenario === "FATIGUE" && this.samplesSeen > 100 ? 0.25 : 0;
    const spike = this.scenario === "ABNORMAL_MOVEMENT" && this.samplesSeen % 50 === 0 ? 2.7 : 0;
    const intensity = Math.sin(phase) * (0.5 + fatigue) + spike;
    const jitter = random * noiseScale;
    return Object.freeze({
      timestamp,
      ax: intensity + jitter,
      ay: Math.cos(phase / 2) * 0.04 + jitter,
      az: 1 + Math.cos(phase) * 0.12 + jitter,
      gx: intensity * 0.3 + jitter,
      gy: intensity * 0.1 + jitter,
      gz: jitter,
      source: "SIMULATION",
    });
  }
}

export class RepetitionDetector {
  constructor({ startThreshold = 0.28, stopThreshold = 0.16, minimumDurationMs = 400 } = {}) {
    this.startThreshold = startThreshold;
    this.stopThreshold = stopThreshold;
    this.minimumDurationMs = minimumDurationMs;
    this.moving = false;
    this.startedAt = null;
    this.repetitions = 0;
  }

  feed(sample) {
    if (![sample.ax, sample.ay, sample.az, sample.gx, sample.gy, sample.gz].every(Number.isFinite)) return null;
    const movementMagnitude = Math.abs(Math.hypot(sample.ax, sample.ay, sample.az) - 1);
    if (!this.moving && movementMagnitude >= this.startThreshold) {
      this.moving = true;
      this.startedAt = sample.timestamp;
      return null;
    }
    if (this.moving && movementMagnitude <= this.stopThreshold) {
      this.moving = false;
      const durationMs = sample.timestamp - this.startedAt;
      const startedAt = this.startedAt;
      this.startedAt = null;
      if (durationMs < this.minimumDurationMs) return null;
      this.repetitions += 1;
      return { rep_number: this.repetitions, started_at: new Date(startedAt).toISOString(), ended_at: new Date(sample.timestamp).toISOString(), duration_ms: durationMs };
    }
    return null;
  }

  reset() {
    this.moving = false;
    this.startedAt = null;
    this.repetitions = 0;
  }
}

export class SquatRepetitionDetector extends RepetitionDetector {
  constructor() {
    super({ startThreshold: 0.34, stopThreshold: 0.18, minimumDurationMs: 650 });
  }
}

export class RehabSafetyMonitor {
  evaluate(sample) {
    const values = [sample.ax, sample.ay, sample.az, sample.gx, sample.gy, sample.gz];
    if (!values.every(Number.isFinite)) return "REVIEW_REQUIRED";
    return Math.max(...values.map(Math.abs)) > 2.5 ? "CAUTION" : "NORMAL";
  }
}

export function summarizeMovementSamples(samples, repetitions = []) {
  const valid = samples.filter((sample) =>
    [sample.ax, sample.ay, sample.az, sample.gx, sample.gy, sample.gz].every(Number.isFinite));
  if (valid.length < 10) {
    return {
      sample_count: valid.length,
      movement_quality: MovementQuality.INSUFFICIENT_DATA,
      stability: MovementQuality.INSUFFICIENT_DATA,
      smoothness: MovementQuality.INSUFFICIENT_DATA,
      fatigue_signal: FatigueSignal.INSUFFICIENT_DATA,
      metrics: [],
    };
  }
  const acceleration = valid.map(({ ax, ay, az }) => Math.hypot(ax, ay, az));
  const mean = acceleration.reduce((total, value) => total + value, 0) / acceleration.length;
  const variability = Math.sqrt(acceleration.reduce((total, value) => total + (value - mean) ** 2, 0) / acceleration.length);
  const differences = acceleration.slice(1).map((value, index) => Math.abs(value - acceleration[index]));
  const jerkSignal = differences.reduce((total, value) => total + value, 0) / differences.length;
  const stability = qualityFromVariability(variability);
  const smoothness = qualityFromVariability(jerkSignal);
  const movementQuality = [stability, smoothness].includes(MovementQuality.NEEDS_ATTENTION)
    ? MovementQuality.NEEDS_ATTENTION
    : [stability, smoothness].includes(MovementQuality.MODERATE) ? MovementQuality.MODERATE : MovementQuality.GOOD;
  const durations = repetitions.map((rep) => rep.duration_ms);
  const fatigue = fatigueFromRepetitions(durations);
  return {
    sample_count: valid.length,
    movement_quality: movementQuality,
    stability,
    smoothness,
    fatigue_signal: fatigue,
    metrics: [
      { metric_name: "acceleration_variability", metric_value: round(variability), unit: "sensor_units", calculation_version: "1" },
      { metric_name: "movement_smoothness_signal", metric_value: round(jerkSignal), unit: "sensor_units_per_sample", calculation_version: "1" },
      { metric_name: "peak_acceleration_magnitude", metric_value: round(Math.max(...acceleration)), unit: "sensor_units", calculation_version: "1" },
    ],
  };
}

function qualityFromVariability(value) {
  if (!Number.isFinite(value)) return MovementQuality.INSUFFICIENT_DATA;
  if (value <= 0.18) return MovementQuality.GOOD;
  if (value <= 0.38) return MovementQuality.MODERATE;
  return MovementQuality.NEEDS_ATTENTION;
}

function fatigueFromRepetitions(durations) {
  if (durations.length < 3 || durations.some((value) => !Number.isFinite(value) || value <= 0)) {
    return FatigueSignal.INSUFFICIENT_DATA;
  }
  const split = Math.floor(durations.length / 2);
  const mean = (values) => values.reduce((sum, value) => sum + value, 0) / values.length;
  const firstHalf = mean(durations.slice(0, split));
  const lastHalf = mean(durations.slice(split));
  const change = (lastHalf - firstHalf) / firstHalf;
  return change >= 0.35 ? FatigueSignal.HIGH : change >= 0.15 ? FatigueSignal.MODERATE : FatigueSignal.LOW;
}

function round(value) {
  return Math.round(value * 1000) / 1000;
}
