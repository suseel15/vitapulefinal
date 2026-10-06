import test from "node:test";
import assert from "node:assert/strict";

import {
  MovementQuality,
  RehabSafetyMonitor,
  RepetitionDetector,
  SimulationMovementDataSource,
  SquatRepetitionDetector,
  summarizeMovementSamples,
} from "../src/rehab-movement.js";

test("simulation samples have an explicit deterministic source", () => {
  const first = new SimulationMovementDataSource({ seed: 5 });
  const second = new SimulationMovementDataSource({ seed: 5 });
  const samplesA = Array.from({ length: 12 }, (_, index) => first.nextSample(index * 100));
  const samplesB = Array.from({ length: 12 }, (_, index) => second.nextSample(index * 100));

  assert.deepEqual(samplesA, samplesB);
  assert.ok(samplesA.every((sample) => sample.source === "SIMULATION"));
});

test("exercise-specific repetition detector ignores malformed and short movement", () => {
  const detector = new RepetitionDetector({ minimumDurationMs: 500 });
  assert.equal(detector.feed({ timestamp: 0, ax: Number.NaN, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 }), null);
  assert.equal(detector.feed({ timestamp: 0, ax: 0, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 }), null);
  detector.feed({ timestamp: 100, ax: 2, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 });
  assert.equal(detector.feed({ timestamp: 300, ax: 0, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 }), null);
  assert.equal(detector.repetitions, 0);
  assert.ok(new SquatRepetitionDetector().minimumDurationMs > new RepetitionDetector().minimumDurationMs);
});

test("movement engine labels insufficient samples instead of returning a fabricated score", () => {
  const result = summarizeMovementSamples([
    { timestamp: 0, ax: 0, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 },
  ]);
  assert.equal(result.sample_count, 1);
  assert.equal(result.movement_quality, MovementQuality.INSUFFICIENT_DATA);
  assert.deepEqual(result.metrics, []);
});

test("movement engine only returns categorical quality and source-unit metrics", () => {
  const source = new SimulationMovementDataSource({ seed: 1, scenario: "GOOD_FORM" });
  const samples = Array.from({ length: 20 }, (_, index) => source.nextSample(index * 100));
  const result = summarizeMovementSamples(samples);

  assert.ok(Object.values(MovementQuality).includes(result.movement_quality));
  assert.ok(result.metrics.every((metric) => metric.unit.startsWith("sensor_units")));
  assert.equal("score" in result, false);
});

test("safety monitor flags invalid and unusually high movement signals", () => {
  const monitor = new RehabSafetyMonitor();
  assert.equal(monitor.evaluate({ ax: 0, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 }), "NORMAL");
  assert.equal(monitor.evaluate({ ax: 3, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 }), "CAUTION");
  assert.equal(monitor.evaluate({ ax: Number.NaN, ay: 0, az: 1, gx: 0, gy: 0, gz: 0 }), "REVIEW_REQUIRED");
});

test("connection-drop simulation has bounded deterministic gaps", () => {
  const source = new SimulationMovementDataSource({ scenario: "CONNECTION_DROP" });
  const samples = Array.from({ length: 60 }, (_, index) => source.nextSample(index * 250));

  assert.equal(samples.slice(29, 44).filter((sample) => sample === null).length, 15);
  assert.equal(samples[0].source, "SIMULATION");
  assert.equal(samples[44].source, "SIMULATION");
});
