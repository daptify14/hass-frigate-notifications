"""Config flow for Notifications for Frigate."""

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
import voluptuous as vol

from .const import DOMAIN, FRIGATE_DOMAIN
from .flows.options import OptionsFlowHandler
from .flows.profile import ProfileSubentryFlowHandler


class FrigateNotificationsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the main Notifications for Frigate entry."""

    VERSION = 1
    MINOR_VERSION = 1

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported subentry types."""
        del config_entry
        return {"profile": ProfileSubentryFlowHandler}

    @classmethod
    @callback
    def async_get_options_flow(cls, config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Return the options flow handler."""
        return OptionsFlowHandler()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Select the Frigate instance this integration should follow."""
        frigate_entries = self.hass.config_entries.async_entries(FRIGATE_DOMAIN)
        if not frigate_entries:
            return self.async_abort(reason="frigate_not_loaded")

        errors: dict[str, str] = {}
        if user_input is not None:
            if not self._frigate_entry_exists(user_input["frigate_entry_id"]):
                errors["frigate_entry_id"] = "frigate_not_found"
            else:
                await self.async_set_unique_id(user_input["frigate_entry_id"])
                self._abort_if_unique_id_configured()
                frigate_entry = self.hass.config_entries.async_get_entry(
                    user_input["frigate_entry_id"]
                )
                title = (
                    f"Notifications for Frigate ({frigate_entry.title})"
                    if frigate_entry
                    else "Notifications for Frigate"
                )
                return self.async_create_entry(
                    title=title,
                    data={"frigate_entry_id": user_input["frigate_entry_id"]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("frigate_entry_id"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=entry.entry_id, label=entry.title)
                                for entry in frigate_entries
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            errors=errors,
        )

    def _frigate_entry_exists(self, entry_id: str) -> bool:
        """Check that the given entry_id refers to a loaded Frigate config entry."""
        return any(
            entry.entry_id == entry_id and entry.domain == FRIGATE_DOMAIN
            for entry in self.hass.config_entries.async_entries(FRIGATE_DOMAIN)
        )
