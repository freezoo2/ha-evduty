"""The EVduty integration."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

import requests
from importlib import import_module
EVduty = import_module("custom_components.evduty.evduty").EVduty

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    CONF_STATION,
    CONF_TERMINAL,

    CHARGER_CHARGING_POWER_KEY,
    CHARGER_MAX_TERMINAL_CURRENT_KEY,
    CHARGER_MAX_CURRENT_KEY,
    CHARGER_NAME_KEY,
    CHARGER_STATUS,
    CHARGER_CHARGING_PROFILE_KEY,
    CHARGER_CHARGING_PROFILE_CURRENT_KEY,
    CHARGER_STATION_ID_KEY,
    CHARGER_TERMINAL_ID_KEY,
    CHARGER_VERISON_KEY,
    CHARGER_PART_NUMBER_KEY

)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.NUMBER, Platform.SWITCH]
UPDATE_INTERVAL = 30


class EVdutyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """EVduty Coordinator class."""

    def __init__(self, station: str, terminal: str, evduty: EVduty, hass: HomeAssistant) -> None:
        """Initialize."""
        self._station = station
        self._terminal = terminal
        self._evduty = evduty

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    def _authenticate(self) -> None:
        """Authenticate using EvDuty API."""
        try:
            self._evduty.authenticate()

        except requests.exceptions.HTTPError as evduty_connection_error:
            if evduty_connection_error.response.status_code == HTTPStatus.FORBIDDEN:
                raise ConfigEntryAuthFailed from evduty_connection_error
            raise ConnectionError from evduty_connection_error

    def _validate(self) -> None:
        """Authenticate using EvDuty API."""
        try:
            self._evduty.authenticate()
        except requests.exceptions.HTTPError as evduty_connection_error:
            if evduty_connection_error.response.status_code == 403:
                raise InvalidAuth from evduty_connection_error
            raise ConnectionError from evduty_connection_error

    async def async_validate_input(self) -> None:
        """Get new sensor data for EVduty component."""
        await self.hass.async_add_executor_job(self._validate)

    def _get_data(self) -> dict[str, Any]:
        """Get new sensor data for EVduty component."""
        try:
            self._authenticate()
            data: dict[str, Any] = self._evduty.get_terminal_info(self._station, self._terminal)

            data[CHARGER_MAX_CURRENT_KEY] = data[CHARGER_CHARGING_PROFILE_KEY][
                CHARGER_CHARGING_PROFILE_CURRENT_KEY
            ]

            return data
        except (
                ConnectionError,
                requests.exceptions.HTTPError,
        ) as evduty_connection_error:
            raise UpdateFailed from evduty_connection_error

    async def _async_update_data(self) -> dict[str, Any]:
        """Get new sensor data for EVduty component."""
        return await self.hass.async_add_executor_job(self._get_data)

    def _set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for EVduty terminal."""
        try:
            self._authenticate()
            self._evduty.set_max_charging_current(self._station, self._terminal, charging_current)
        except requests.exceptions.HTTPError as evduty_connection_error:
            if evduty_connection_error.response.status_code == 403:
                raise InvalidAuth from evduty_connection_error
            raise ConnectionError from evduty_connection_error

    async def async_set_charging_current(self, charging_current: float) -> None:
        """Set maximum charging current for EVduty terminal."""
        await self.hass.async_add_executor_job(
            self._set_charging_current, charging_current
        )
        await self.async_request_refresh()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EVduty from a config entry."""
    evduty = EVduty(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        jwt_token_drift=UPDATE_INTERVAL,
    )
    evduty_coordinator = EVdutyCoordinator(
        entry.data[CONF_STATION],
        entry.data[CONF_TERMINAL],
        evduty,
        hass,
    )

    try:
        await evduty_coordinator.async_validate_input()

    except InvalidAuth as ex:
        raise ConfigEntryAuthFailed from ex

    await evduty_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = evduty_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class EVdutyEntity(CoordinatorEntity[EVdutyCoordinator]):
    """Defines a base EVduty entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this EVduty device."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self.coordinator.data[CHARGER_STATION_ID_KEY],
                    self.coordinator.data[CHARGER_TERMINAL_ID_KEY]
                )
            },
            name=f"EVduty - {self.coordinator.data[CHARGER_NAME_KEY]}",
            manufacturer="EVduty",
            model=self.coordinator.data[CHARGER_PART_NUMBER_KEY],
            sw_version=self.coordinator.data[CHARGER_VERISON_KEY],
        )