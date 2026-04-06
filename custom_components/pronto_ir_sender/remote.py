"""Remote platform for Pronto IR Sender integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any, override

from infrared_protocols import Command, Timing

from homeassistant.components import infrared
from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_NUM_REPEATS,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_INFRARED_ENTITY_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

# Pronto time unit constant: each unit = freq_code * PRONTO_CLOCK_US microseconds
_PRONTO_CLOCK_US = 0.241246
_PRONTO_RAW_TYPE = 0x0000


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Pronto IR Sender remote from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    async_add_entities([ProntoIrRemote(entry, infrared_entity_id)])


class ProntoCommand(Command):
    """An infrared command built from a raw Pronto hex code string."""

    def __init__(self, pronto_hex: str) -> None:
        """Parse a raw Pronto hex code and prepare the command.

        Args:
            pronto_hex: Space-separated hex words, e.g. "0000 006C 0022 0002 ..."

        Raises:
            ServiceValidationError: If the code is not valid raw Pronto format.
        """
        try:
            words = [int(w, 16) for w in pronto_hex.strip().split()]
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_pronto_code",
                translation_placeholders={"code": pronto_hex},
            ) from err

        if len(words) < 4:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_pronto_code",
                translation_placeholders={"code": pronto_hex},
            )

        pronto_type = words[0]
        if pronto_type != _PRONTO_RAW_TYPE:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unsupported_pronto_type",
                translation_placeholders={
                    "code": pronto_hex,
                    "type": f"{pronto_type:04X}",
                },
            )

        freq_code = words[1]
        n1 = words[2]
        n2 = words[3]
        required_length = 4 + (n1 + n2) * 2
        if len(words) < required_length:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_pronto_code",
                translation_placeholders={"code": pronto_hex},
            )

        # Carrier frequency in Hz (0 means unmodulated / no carrier)
        if freq_code > 0:
            modulation = round(1_000_000 / (freq_code * _PRONTO_CLOCK_US))
        else:
            modulation = 0

        super().__init__(modulation=modulation)

        self._pronto_unit_us = round(freq_code * _PRONTO_CLOCK_US) if freq_code else 0
        self._words = words
        self._n1 = n1
        self._n2 = n2

    @override
    def get_raw_timings(self) -> list[Timing]:
        """Return raw mark/space timings derived from the Pronto code."""
        unit = self._pronto_unit_us
        timings: list[Timing] = []

        # Sequence 1 (played once)
        offset = 4
        for i in range(self._n1):
            mark_us = self._words[offset + i * 2] * unit
            space_us = self._words[offset + i * 2 + 1] * unit
            timings.append(Timing(high_us=mark_us, low_us=space_us))

        # Sequence 2 (repeat sequence), appended repeat_count times
        offset2 = 4 + self._n1 * 2
        for _ in range(self.repeat_count):
            for i in range(self._n2):
                mark_us = self._words[offset2 + i * 2] * unit
                space_us = self._words[offset2 + i * 2 + 1] * unit
                timings.append(Timing(high_us=mark_us, low_us=space_us))

        return timings


class ProntoIrRemote(RemoteEntity):
    """Remote entity that sends raw Pronto IR codes via an infrared emitter."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_assumed_state = True
    _attr_is_on = True

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the Pronto IR remote entity."""
        self._infrared_entity_id = infrared_entity_id
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Pronto IR Sender",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to infrared emitter state changes to track availability."""
        await super().async_added_to_hass()

        @callback
        def _async_ir_state_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            ir_available = (
                new_state is not None and new_state.state != STATE_UNAVAILABLE
            )
            if ir_available != self.available:
                _LOGGER.info(
                    "Infrared entity %s used by %s is %s",
                    self._infrared_entity_id,
                    self.entity_id,
                    "available" if ir_available else "unavailable",
                )
                self._attr_available = ir_available
                self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._infrared_entity_id], _async_ir_state_changed
            )
        )

        ir_state = self.hass.states.get(self._infrared_entity_id)
        self._attr_available = (
            ir_state is not None and ir_state.state != STATE_UNAVAILABLE
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """No-op: this remote has no power state feedback."""

    async def async_turn_off(self, **kwargs: Any) -> None:
        """No-op: this remote has no power state feedback."""

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more Pronto IR codes via the configured emitter.

        Args:
            command: Iterable of raw Pronto hex code strings.

        Raises:
            ServiceValidationError: If a code is not valid raw Pronto format.
            HomeAssistantError: If transmission fails.
        """
        num_repeats: int = kwargs.get(ATTR_NUM_REPEATS, DEFAULT_NUM_REPEATS)
        delay_secs: float = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)

        commands = [ProntoCommand(code) for code in command]

        for repeat in range(num_repeats):
            for cmd in commands:
                await infrared.async_send_command(
                    self.hass,
                    self._infrared_entity_id,
                    cmd,
                    context=self._context,
                )
            if repeat < num_repeats - 1:
                await asyncio.sleep(delay_secs)
