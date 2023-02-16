"""Home Assistant component for accessing the EVduty Portal API.
The number component allows control of charging current.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import cast, Union

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InvalidAuth, EVdutyCoordinator, EVdutyEntity
from .const import (    
    CHARGER_MAX_TERMINAL_CURRENT_KEY,
    CHARGER_TERMINAL_ID_KEY,
    CHARGER_MAX_CURRENT_KEY,
    DOMAIN,
)


@dataclass
class EVdutyNumberEntityDescription(NumberEntityDescription):
    """Describes EVduty number entity."""

NUMBER_TYPES: dict[str, EVdutyNumberEntityDescription] = {
    CHARGER_MAX_TERMINAL_CURRENT_KEY: EVdutyNumberEntityDescription(
        key=CHARGER_MAX_TERMINAL_CURRENT_KEY,
        name="Maximum supported charging current",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create EVduty number entities in HASS."""
    coordinator: EVdutyCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Add number component:
    async_add_entities(
        [
            EVdutyNumber(coordinator, entry, description)
            for ent in coordinator.data
            if (description := NUMBER_TYPES.get(ent))
        ]
    )


class EVdutyNumber(EVdutyEntity, NumberEntity):
    """Representation of the EVduty portal."""

    entity_description: EVdutyNumberEntityDescription

    def __init__(
        self,
        coordinator: EVdutyCoordinator,
        entry: ConfigEntry,
        description: EVdutyNumberEntityDescription,
    ) -> None:
        """Initialize a EVduty number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._coordinator = coordinator
        self._attr_name = f"{entry.title} {description.name}"
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_TERMINAL_ID_KEY]}"        

    @property
    def native_max_value(self) -> float:
        """Return the maximum available current."""
        return cast(float, self._coordinator.data[CHARGER_MAX_TERMINAL_CURRENT_KEY])

    @property
    def native_min_value(self) -> float:        
        return 0

    @property
    def native_value(self) -> float | None:
        """Return the value of the entity."""
        return cast(
            Union [float,None], self._coordinator.data[CHARGER_MAX_CURRENT_KEY]
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set the value of the entity."""
        await self._coordinator.async_set_charging_current(value)