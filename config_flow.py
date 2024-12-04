"""Config flow for EVduty integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from evduty import EVduty

from homeassistant import config_entries, core
from homeassistant.helpers import selector
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from . import InvalidAuth, EVdutyCoordinator
from .const import CONF_STATION, CONF_TERMINAL, DOMAIN

COMPONENT_DOMAIN = DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: core.HomeAssistant, data: dict[str, Any]
) -> dict[str, str]:
    """Validate the user input allows to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    evduty = EVduty(data["username"], data["password"])
    evduty_coordinator = EVdutyCoordinator(data["station"], data["terminal"], evduty, hass)

    await evduty_coordinator.async_validate_input()

    # Return info that you want to store in the config entry.
    return {"title": "EVduty Portal"}


def get_stations(username: str, password: str):
    evd = EVduty(username, password)
    evd.authenticate()
    return evd.get_station_ids()


def get_terminals(username: str, password: str, station: str):
    evd = EVduty(username, password)
    evd.authenticate()
    return evd.get_terminal_ids(station)


class ConfigFlow(config_entries.ConfigFlow, domain=COMPONENT_DOMAIN):
    """Handle a config flow for EVduty."""

    def __init__(self) -> None:
        """Start the EVduty config flow."""
        self._reauth_entry: config_entries.ConfigEntry | None = None
        self._temp_user = None
        self._temp_pass = None
        self._temp_station = None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors = {}

        try:
            if CONF_TERMINAL in user_input:
                info = await validate_input(self.hass, {CONF_USERNAME: self._temp_user,
                                                             CONF_PASSWORD: self._temp_pass,
                                                             CONF_STATION: self._temp_station,
                                                             CONF_TERMINAL: user_input[CONF_TERMINAL]})
                await self.async_set_unique_id(user_input["terminal"])
                if not self._reauth_entry:
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data={CONF_USERNAME: self._temp_user,
                                                                          CONF_PASSWORD: self._temp_pass,
                                                                          CONF_STATION: self._temp_station,
                                                                          CONF_TERMINAL: user_input["terminal"]
                                                                          })
            elif CONF_STATION in user_input:
                terminals = await self.hass.async_add_executor_job(get_terminals,
                                                                  self._temp_user,
                                                                  self._temp_pass,
                                                                  user_input[CONF_STATION])
                self._temp_station = user_input[CONF_STATION]
                tt = vol.Schema({vol.Required(CONF_TERMINAL): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=terminals, translation_key=CONF_TERMINAL))
                })
                return self.async_show_form(
                    step_id="user",
                    data_schema=tt,
                )
            elif CONF_PASSWORD in user_input and CONF_USERNAME in user_input:
                stations = await self.hass.async_add_executor_job(get_stations,
                                                       user_input[CONF_USERNAME],
                                                       user_input[CONF_PASSWORD])
                self._temp_user = user_input[CONF_USERNAME]
                self._temp_pass = user_input[CONF_PASSWORD]
                tt = vol.Schema({vol.Required(CONF_STATION): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=stations, translation_key=CONF_STATION))
                })
                return self.async_show_form(
                    step_id="user",
                    data_schema=tt,
                )

            await self.async_set_unique_id(user_input["terminal"])
            if not self._reauth_entry:
                self._abort_if_unique_id_configured()
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            if user_input["terminal"] == self._reauth_entry.data[CONF_TERMINAL]:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input, unique_id=user_input["terminal"]
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")
            errors["base"] = "reauth_invalid"
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )