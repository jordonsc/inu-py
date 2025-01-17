"""
Inu Framework custom component.

## Configuration
To use this component you will need to add a hub using the HA UI. When prompted, enter your Inu network's NATS server:

    nats://<ipaddress>:4222

"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from inu import const

from . import hub

import logging

# HA domain & platforms
DOMAIN = "inu"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.TEXT, Platform.BUTTON, Platform.BINARY_SENSOR]


async def async_setup(hass: HomeAssistant, _: ConfigType) -> bool:
    hass.states.async_set('inu.build', const.INU_BUILD)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    logging.warning("inu: begin setup on host {}".format(entry.data["host"]))
    inu_hub = hub.Hub(hass, entry.data["host"])
    await inu_hub.inu.init()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = inu_hub
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    hass.services.async_register(DOMAIN, "nats_publish", inu_hub.nats_service)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    logging.warning("inu: unload component")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
