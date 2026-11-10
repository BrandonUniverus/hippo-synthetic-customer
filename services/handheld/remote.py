"""Explicit HTTP delivery on the consumer host, using the shared receipt ledger."""
import json
import re
from pathlib import Path
from urllib.request import urlopen

from services.sources.delivery import deliver


def sync(url, key, targets, target, *, replay=False):
    if not re.fullmatch(r"[a-f0-9]{32}", key):
        raise ValueError("Select an exact finalized round ID")
    with urlopen(url.rstrip("/") + "/api/rounds/" + key, timeout=15) as response:
        doc = json.load(response)
    config = targets.get(target)
    if not config or config.get("enabled") is not True or target != doc["channel"]["delivery_target"]:
        raise ValueError("Enable the binding's exact delivery target explicitly")
    if config.get("environment_id") != doc["environment_id"] or config.get("gateway_profile") != doc["channel"]["gateway_profile"]:
        raise ValueError("Delivery environment/gateway differs from the selected round")
    if doc["fixture_only"] and config.get("fixture_only") is not True:
        raise ValueError("Demonstration IDs require a fixture-only target")
    if not doc["artifact"]:
        raise ValueError("Round is not finalized")
    return deliver([doc["artifact"]], Path(config["destination"]), url=url, input_layout=True, replay=replay)
