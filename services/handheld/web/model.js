(function (root) {
  "use strict";
  function observation(fields) {
    if (fields.action === "read" && !/^[0-9]+$/.test(fields.value)) throw new Error("Enter an unsigned whole-unit register.");
    if (!/(Z|[+-][0-9]{2}:[0-9]{2})$/.test(fields.observed_at) || !Number.isFinite(Date.parse(fields.observed_at))) throw new Error("Include the observation date, time and UTC offset.");
    return { ...fields, value: fields.action === "skip" ? null : Number(fields.value) };
  }
  function canDeliver(round, targets) {
    return Boolean(round.artifact && targets.some(target => target.id === round.channel.delivery_target && target.enabled
      && target.environment_id === round.environment_id && target.gateway_profile === round.channel.gateway_profile
      && (!round.fixture_only || target.fixture_only)));
  }
  const api = { observation, canDeliver };
  if (typeof module !== "undefined") module.exports = api;
  else root.HandheldModel = api;
})(typeof window === "undefined" ? {} : window);
