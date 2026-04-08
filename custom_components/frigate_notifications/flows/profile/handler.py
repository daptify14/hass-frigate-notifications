"""Profile subentry flow handler for Notifications for Frigate."""

import copy
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentryFlow, SubentryFlowResult

from ...const import FRIGATE_DOMAIN, SUBENTRY_TYPE_PROFILE
from ...presets import async_ensure_preset_cache
from ..helpers import profile_placeholders, profile_title
from .context import FlowContext, build_flow_context
from .normalize import normalize_profile_data
from .steps.basics import (
    apply_basics_input,
    build_basics_schema,
    build_basics_suggested,
    validate_basics_input,
)
from .steps.content import apply_content_input, build_content_schema, validate_content_input
from .steps.delivery import (
    apply_delivery_input,
    build_delivery_schema,
    build_delivery_suggested,
)
from .steps.filtering import (
    apply_filtering_input,
    build_filtering_schema,
    build_filtering_suggested,
    validate_filtering_input,
)
from .steps.media_actions import (
    apply_media_actions_input,
    build_media_actions_schema,
    build_media_actions_suggested,
)
from .steps.preset import (
    apply_preset_input,
    build_preset_schema,
    preset_description_placeholders,
)


class ProfileSubentryFlowHandler(ConfigSubentryFlow):
    """Profile wizard: preset -> basics -> customize menu -> save."""

    def __init__(self) -> None:
        """Initialize profile subentry flow state."""
        self._data: dict[str, Any] = {}
        self._reconfiguring = False
        self._ctx: FlowContext | None = None

    async def async_step_user(self, user_input=None) -> SubentryFlowResult:
        """Start a new profile subentry flow."""
        return await self.async_step_preset()

    async def async_step_reconfigure(self, _user_input=None) -> SubentryFlowResult:
        """Pre-fill from existing subentry data and show section menu."""
        self._reconfiguring = True
        self._data.update(copy.deepcopy(dict(self._get_reconfigure_subentry().data)))
        self._invalidate_context()
        return await self.async_step_menu()

    async def async_step_menu(self, user_input=None) -> SubentryFlowResult:
        """Show section menu for reconfigure."""
        return self.async_show_menu(
            step_id="menu",
            menu_options=[
                "basics",
                "filtering",
                "content",
                "media_actions",
                "delivery",
                "save",
            ],
            description_placeholders=self._placeholders(),
        )

    async def async_step_customize(self, user_input=None) -> SubentryFlowResult:
        """Show customization menu after basics during initial profile creation."""
        return self.async_show_menu(
            step_id="customize",
            menu_options=["filtering", "content", "media_actions", "delivery", "save"],
            description_placeholders=self._placeholders(),
        )

    async def async_step_preset(self, user_input=None) -> SubentryFlowResult:
        """Step 1: choose a notification preset and GenAI toggle."""
        await async_ensure_preset_cache(self.hass)
        ctx = self._build_context()

        if user_input is not None:
            apply_preset_input(self._data, user_input, ctx)
            self._invalidate_context()
            return await self.async_step_basics()

        schema = build_preset_schema(self._data, ctx)
        placeholders = preset_description_placeholders(ctx)
        return self.async_show_form(
            step_id="preset",
            data_schema=schema,
            description_placeholders=placeholders,
        )

    async def async_step_basics(self, user_input=None) -> SubentryFlowResult:
        """Step 2: profile identity, camera binding, and notify target (two-pass)."""
        entry = self._get_entry()
        if not self._frigate_loaded(entry):
            return self.async_abort(reason="frigate_not_loaded")

        ctx = self._build_context()
        if not ctx.available_cameras:
            return self.async_abort(reason="no_cameras_available")

        pass_number = 2 if "provider" in self._data else 1
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = validate_basics_input(
                self._data,
                user_input,
                ctx,
                pass_number=pass_number,
                has_duplicate_title=self._has_duplicate_title,
            )
            if not errors:
                apply_basics_input(self._data, user_input, ctx, pass_number=pass_number)
                self._invalidate_context()
                if pass_number == 1:
                    return self._show_basics_form()
                return await self._go_to_menu()
            if pass_number == 1:
                self._data.pop("provider", None)

        return self._show_basics_form(errors=errors)

    def _show_basics_form(
        self,
        *,
        errors: dict[str, str] | None = None,
    ) -> SubentryFlowResult:
        """Show the basics form — schema adapts based on whether provider is set."""
        ctx = self._build_context()
        pass_number = 2 if "provider" in self._data else 1
        schema = build_basics_schema(self._data, ctx, pass_number=pass_number)
        suggested = build_basics_suggested(self._data)

        if pass_number == 1:
            existing_cameras = suggested.get("cameras", [])
            if not all(c in ctx.available_cameras for c in existing_cameras):
                suggested.pop("cameras", None)

        return self.async_show_form(
            step_id="basics",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors or {},
            last_step=False,
        )

    def _has_duplicate_title(self, candidate_title: str) -> bool:
        """Check whether another profile subentry already uses this title."""
        entry = self._get_entry()
        reconfigure_id = (
            self._get_reconfigure_subentry().subentry_id if self._reconfiguring else None
        )
        return any(
            se.title == candidate_title
            for se in entry.subentries.values()
            if se.subentry_type == SUBENTRY_TYPE_PROFILE and se.subentry_id != reconfigure_id
        )

    async def async_step_filtering(self, user_input=None) -> SubentryFlowResult:
        """Step 3: object filters, severity, zones, and gate behavior."""
        ctx = self._build_context()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = validate_filtering_input(self._data, user_input, ctx)
            if not errors:
                apply_filtering_input(self._data, user_input, ctx)
                self._invalidate_context()
                return await self._go_to_menu()

        schema = build_filtering_schema(self._data, ctx)
        suggested = build_filtering_suggested(self._data, ctx)
        return self.async_show_form(
            step_id="filtering",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders=self._placeholders(),
            last_step=False,
        )

    async def async_step_content(self, user_input=None) -> SubentryFlowResult:
        """Step 4: message templates, subtitles, and emoji across all 4 phases."""
        await async_ensure_preset_cache(self.hass)
        ctx = self._build_context()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = validate_content_input(self._data, user_input, ctx)
            if not errors:
                apply_content_input(self._data, user_input, ctx)
                self._invalidate_context()
                return await self._go_to_menu()

        schema = build_content_schema(self._data, ctx)
        return self.async_show_form(
            step_id="content",
            data_schema=schema,
            errors=errors,
            description_placeholders=self._placeholders(),
            last_step=False,
        )

    async def async_step_media_actions(self, user_input=None) -> SubentryFlowResult:
        """Step 5: attachments, video, and action presets across all 4 phases."""
        ctx = self._build_context()

        if user_input is not None:
            apply_media_actions_input(self._data, user_input, ctx)
            self._invalidate_context()
            return await self._go_to_menu()

        schema = build_media_actions_schema(self._data, ctx)
        suggested = build_media_actions_suggested(self._data, ctx)
        return self.async_show_form(
            step_id="media_actions",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders=self._placeholders(),
            last_step=False,
        )

    async def async_step_delivery(self, user_input=None) -> SubentryFlowResult:
        """Step 6: sound, volume, timing, and advanced delivery across all 4 phases."""
        ctx = self._build_context()

        if user_input is not None:
            apply_delivery_input(self._data, user_input, ctx)
            self._invalidate_context()
            return await self._go_to_menu()

        schema = build_delivery_schema(self._data, ctx)
        suggested = build_delivery_suggested(self._data, ctx)
        return self.async_show_form(
            step_id="delivery",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders=self._placeholders(),
            last_step=False,
        )

    async def async_step_save(self, user_input=None) -> SubentryFlowResult:
        """Finalize and save the profile (create or update)."""
        normalized = normalize_profile_data(self._data)
        title = profile_title(normalized["cameras"], normalized["name"])
        if self._reconfiguring:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                data=normalized,
                title=title,
            )
        return self.async_create_entry(title=title, data=normalized)

    def _frigate_loaded(self, entry: ConfigEntry) -> bool:
        """Check that the linked Frigate entry is loaded."""
        return entry.data["frigate_entry_id"] in self.hass.data.get(FRIGATE_DOMAIN, {})

    def _build_context(self) -> FlowContext:
        """Construct a FlowContext from current handler state, caching until data changes."""
        if self._ctx is None:
            entry = self._get_entry()
            self._ctx = build_flow_context(
                self.hass,
                entry,
                self._data,
                is_reconfiguring=self._reconfiguring,
            )
        return self._ctx

    def _invalidate_context(self) -> None:
        """Clear cached FlowContext after data changes."""
        self._ctx = None

    async def _go_to_menu(self) -> SubentryFlowResult:
        """Route to the appropriate menu (reconfigure vs initial creation)."""
        if self._reconfiguring:
            return await self.async_step_menu()
        return await self.async_step_customize()

    def _placeholders(self) -> dict[str, str]:
        """Build description placeholders for profile steps."""
        return profile_placeholders(self._data)
