const { observation, canDeliver } = require('../web/model.js');

test('integer registers preserve exact values and skips omit values', () => {
  const visit = { action: 'read', value: '9999999999', observed_at: '2026-10-15T12:00:00-07:00' };
  expect(observation(visit).value).toBe(9999999999);
  for (const value of ['12.5', '-1', '1e3', '', ' 12']) expect(() => observation({ ...visit, value })).toThrow();
  expect(observation({ ...visit, action: 'skip' }).value).toBeNull();
  expect(() => observation({ ...visit, observed_at: '2026-10-15T12:00:00' })).toThrow();
});

test('delivery requires a prepared artifact and the enabled exact target', () => {
  const round = { channel: { delivery_target: 'water', gateway_profile: 'neptune' }, environment_id: 'pilot', fixture_only: true, artifact: { sha256: 'hash' } };
  const target = { id: 'water', enabled: true, gateway_profile: 'neptune', environment_id: 'pilot', fixture_only: true };
  expect(canDeliver(round, [])).toBe(false);
  expect(canDeliver(round, [{ id: 'gas', enabled: true }])).toBe(false);
  expect(canDeliver(round, [{ id: 'water', enabled: false }])).toBe(false);
  expect(canDeliver({ ...round, artifact: null }, [{ id: 'water', enabled: true }])).toBe(false);
  expect(canDeliver(round, [target])).toBe(true);
  expect(canDeliver(round, [{ ...target, environment_id: 'elsewhere' }])).toBe(false);
  expect(canDeliver(round, [{ ...target, gateway_profile: 'mvrs' }])).toBe(false);
  expect(canDeliver(round, [{ ...target, fixture_only: false }])).toBe(false);
});
