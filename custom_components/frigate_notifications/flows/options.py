"""Options flow handler for Notifications for Frigate."""

from typing import Any

from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)
import voluptuous as vol

from ..const import (
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_EMOJI,
    DEFAULT_EMOJI_MAP,
    DEFAULT_INITIAL_DELAY,
    DEFAULT_PHASE_EMOJI_MAP,
    DEFAULT_TITLE_GENAI_PREFIXES,
    DEFAULT_TITLE_TEMPLATE,
    DOMAIN,
    FRIGATE_DOMAIN,
    PRESENCE_ENTITY_DOMAINS,
    humanize_zone,
)
from ..enums import TimeFilterMode
from ..presets import async_ensure_preset_cache
from .helpers import (
    GUARD_ENTITY_SELECTOR,
    INITIAL_DELAY_SELECTOR,
    SILENCE_SELECTOR,
    build_base_url_options,
    build_frigate_url_options,
    discover_all_sub_labels,
    get_available_cameras,
    get_camera_zones,
    supports_genai,
    title_selector,
)


class OptionsFlowHandler(OptionsFlow):
    """Shared defaults for all notification profiles."""

    def __init__(self) -> None:
        """Initialize options flow state."""
        self._data: dict[str, Any] = {}
        self._reconfiguring = False
        self._frigate_entry_id = ""

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        """Start the options flow — menu if already configured, linear otherwise."""
        del user_input
        await async_ensure_preset_cache(self.hass)
        self._data = dict(self.config_entry.options)
        self._frigate_entry_id = self.config_entry.data["frigate_entry_id"]
        if self._data.get("base_url"):
            self._reconfiguring = True
            return await self.async_step_menu()
        return await self.async_step_delivery()

    async def async_step_menu(self, user_input=None) -> ConfigFlowResult:
        """Show section menu for reconfigure."""
        return self.async_show_menu(
            step_id="menu",
            menu_options=["delivery", "appearance", "zone_aliases", "save"],
        )

    async def async_step_save(self, user_input=None) -> ConfigFlowResult:
        """Finalize and save options."""
        return self.async_create_entry(data=self._data)

    async def async_step_delivery(self, user_input=None) -> ConfigFlowResult:
        """Delivery defaults and shared filter entities."""
        if user_input is not None:
            self._apply_delivery(user_input)
            if self._reconfiguring:
                return await self.async_step_menu()
            return await self.async_step_appearance()

        url_options, suggested_base_url = build_base_url_options(self.hass, self._data)
        frigate_url_options, suggested_frigate_url = build_frigate_url_options(
            self.hass, self._data, self._frigate_entry_id
        )
        schema = vol.Schema(
            {
                vol.Required("base_url"): SelectSelector(
                    SelectSelectorConfig(
                        options=url_options,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("frigate_url"): SelectSelector(
                    SelectSelectorConfig(
                        options=frigate_url_options,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("timers"): section(
                    vol.Schema(
                        {
                            vol.Required(
                                "initial_delay",
                                default=self._data.get("initial_delay", DEFAULT_INITIAL_DELAY),
                            ): INITIAL_DELAY_SELECTOR,
                            vol.Required(
                                "silence_duration",
                                default=self._data.get("silence_duration", 30),
                            ): SILENCE_SELECTOR,
                            vol.Required(
                                "cooldown_seconds",
                                default=self._data.get(
                                    "cooldown_seconds", DEFAULT_COOLDOWN_SECONDS
                                ),
                            ): NumberSelector(
                                NumberSelectorConfig(
                                    min=0, max=3600, step=1, unit_of_measurement="seconds"
                                )
                            ),
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
                vol.Optional("guard"): section(
                    vol.Schema({vol.Optional("shared_guard_entity"): GUARD_ENTITY_SELECTOR}),
                    SectionConfig(collapsed=True),
                ),
                vol.Optional("time_filter"): section(
                    vol.Schema(
                        {
                            vol.Optional("shared_time_filter_mode"): SelectSelector(
                                SelectSelectorConfig(
                                    options=[
                                        TimeFilterMode.DISABLED,
                                        TimeFilterMode.ONLY_DURING,
                                        TimeFilterMode.NOT_DURING,
                                    ],
                                    translation_key="time_filter_mode",
                                    mode=SelectSelectorMode.DROPDOWN,
                                )
                            ),
                            vol.Optional("shared_time_filter_start"): TimeSelector(),
                            vol.Optional("shared_time_filter_end"): TimeSelector(),
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
                vol.Optional("presence"): section(
                    vol.Schema(
                        {
                            vol.Optional("shared_presence_entities"): EntitySelector(
                                EntitySelectorConfig(
                                    domain=list(PRESENCE_ENTITY_DOMAINS), multiple=True
                                )
                            ),
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
                vol.Optional("state_filter"): section(
                    vol.Schema(
                        {
                            vol.Optional("shared_state_entity"): EntitySelector(
                                EntitySelectorConfig()
                            ),
                            vol.Optional("shared_state_filter_states"): SelectSelector(
                                SelectSelectorConfig(
                                    options=["on", "off", "home", "not_home", "open", "closed"],
                                    custom_value=True,
                                    multiple=True,
                                    mode=SelectSelectorMode.DROPDOWN,
                                )
                            ),
                        }
                    ),
                    SectionConfig(collapsed=True),
                ),
            }
        )
        suggested: dict[str, Any] = {
            "base_url": self._data.get("base_url", suggested_base_url),
            "frigate_url": self._data.get("frigate_url", suggested_frigate_url),
            "timers": {
                "initial_delay": self._data.get("initial_delay", DEFAULT_INITIAL_DELAY),
                "silence_duration": self._data.get("silence_duration", 30),
                "cooldown_seconds": self._data.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS),
            },
        }
        guard_suggested: dict[str, Any] = {}
        if "shared_guard_entity" in self._data:
            guard_suggested["shared_guard_entity"] = self._data["shared_guard_entity"]
        suggested["guard"] = guard_suggested
        tf_suggested: dict[str, Any] = {}
        for key in (
            "shared_time_filter_mode",
            "shared_time_filter_start",
            "shared_time_filter_end",
        ):
            if key in self._data:
                tf_suggested[key] = self._data[key]
        suggested["time_filter"] = tf_suggested
        pres_suggested: dict[str, Any] = {}
        if "shared_presence_entities" in self._data:
            pres_suggested["shared_presence_entities"] = self._data["shared_presence_entities"]
        suggested["presence"] = pres_suggested
        sf_suggested: dict[str, Any] = {}
        for key in ("shared_state_entity", "shared_state_filter_states"):
            if key in self._data:
                sf_suggested[key] = self._data[key]
        suggested["state_filter"] = sf_suggested
        return self.async_show_form(
            step_id="delivery",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders={"example_frigate_url": "https://frigate.local:5000"},
            last_step=False,
        )

    def _apply_delivery(self, user_input: dict[str, Any]) -> None:
        """Store delivery step fields into _data."""
        self._data["base_url"] = user_input["base_url"]
        self._data["frigate_url"] = user_input.get("frigate_url", "")
        timers = user_input.get("timers", {})
        self._data["initial_delay"] = timers.get("initial_delay", DEFAULT_INITIAL_DELAY)
        self._data["silence_duration"] = timers.get("silence_duration", 30)
        self._data["cooldown_seconds"] = int(
            timers.get("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS)
        )
        guard = user_input.get("guard", {})
        if guard.get("shared_guard_entity"):
            self._data["shared_guard_entity"] = guard["shared_guard_entity"]
        else:
            self._data.pop("shared_guard_entity", None)
        tf = user_input.get("time_filter", {})
        for key in (
            "shared_time_filter_mode",
            "shared_time_filter_start",
            "shared_time_filter_end",
        ):
            if tf.get(key):
                self._data[key] = tf[key]
            else:
                self._data.pop(key, None)
        pres = user_input.get("presence", {})
        if pres.get("shared_presence_entities"):
            self._data["shared_presence_entities"] = pres["shared_presence_entities"]
        else:
            self._data.pop("shared_presence_entities", None)
        sf = user_input.get("state_filter", {})
        if sf.get("shared_state_entity"):
            self._data["shared_state_entity"] = sf["shared_state_entity"]
        else:
            self._data.pop("shared_state_entity", None)
        if sf.get("shared_state_filter_states"):
            self._data["shared_state_filter_states"] = sf["shared_state_filter_states"]
        else:
            self._data.pop("shared_state_filter_states", None)

    async def async_step_appearance(self, user_input=None) -> ConfigFlowResult:
        """Title template, emoji style, custom emoji map, and sub-label overrides."""
        if user_input is not None:
            self._apply_appearance(user_input)
            if self._reconfiguring:
                return await self.async_step_menu()
            return await self.async_step_zone_aliases()

        typed_sub_labels = discover_all_sub_labels(self.hass, self._frigate_entry_id)
        faces = [(typ, name) for typ, name in typed_sub_labels if typ == "face"]
        plates = [(typ, name) for typ, name in typed_sub_labels if typ == "lpr"]
        existing_overrides = self._data.get("sub_label_overrides", {})

        schema_fields: dict[Any, Any] = {
            vol.Optional("title_template", default=DEFAULT_TITLE_TEMPLATE): title_selector(
                self.hass.data.get(DOMAIN, {}).get("template_presets", {})
            ),
            vol.Optional("emoji_config"): section(
                vol.Schema(
                    {
                        vol.Optional(
                            "enable_emojis",
                            default=self._data.get("enable_emojis", True),
                        ): BooleanSelector(),
                        vol.Optional("default_emoji", default=DEFAULT_EMOJI): TextSelector(),
                    }
                ),
                SectionConfig(collapsed=False),
            ),
            vol.Optional("custom_emoji_config"): section(
                vol.Schema({vol.Optional("emoji_map"): ObjectSelector()}),
                SectionConfig(collapsed=True),
            ),
            vol.Optional("phase_emoji_config"): section(
                vol.Schema(
                    {
                        vol.Optional("phase_initial"): TextSelector(),
                        vol.Optional("phase_update"): TextSelector(),
                        vol.Optional("phase_end"): TextSelector(),
                        vol.Optional("phase_genai"): TextSelector(),
                    }
                ),
                SectionConfig(collapsed=True),
            ),
        }

        if supports_genai(self.hass, self._frigate_entry_id):
            schema_fields[vol.Optional("genai_prefix_config")] = section(
                vol.Schema(
                    {
                        vol.Optional("title_genai_prefix_0"): TextSelector(),
                        vol.Optional("title_genai_prefix_1"): TextSelector(),
                        vol.Optional("title_genai_prefix_2"): TextSelector(),
                    }
                ),
                SectionConfig(collapsed=True),
            )

        if faces:
            face_fields: dict[Any, Any] = {}
            for _, name in faces:
                face_fields[vol.Optional(name, default=existing_overrides.get(name, ""))] = (
                    TextSelector()
                )
            schema_fields[vol.Optional("face_overrides")] = section(
                vol.Schema(face_fields),
                SectionConfig(collapsed=True),
            )

        if plates:
            plate_fields: dict[Any, Any] = {}
            for _, name in plates:
                plate_fields[vol.Optional(name, default=existing_overrides.get(name, ""))] = (
                    TextSelector()
                )
            schema_fields[vol.Optional("plate_overrides")] = section(
                vol.Schema(plate_fields),
                SectionConfig(collapsed=True),
            )

        schema = vol.Schema(schema_fields)

        base_emoji_map = dict(DEFAULT_EMOJI_MAP)
        if self._data.get("emoji_map"):
            base_emoji_map.update(self._data["emoji_map"])
        suggested: dict[str, Any] = {
            "title_template": self._data.get("title_template", DEFAULT_TITLE_TEMPLATE),
            "emoji_config": {
                "enable_emojis": self._data.get("enable_emojis", True),
                "default_emoji": self._data.get("default_emoji", DEFAULT_EMOJI),
            },
            "custom_emoji_config": {
                "emoji_map": base_emoji_map,
            },
        }
        existing_phase = self._data.get("phase_emoji_map", {})
        suggested["phase_emoji_config"] = {
            f"phase_{k}": existing_phase.get(k, v) for k, v in DEFAULT_PHASE_EMOJI_MAP.items()
        }

        if supports_genai(self.hass, self._frigate_entry_id):
            existing_prefixes = self._data.get("title_genai_prefixes", {})
            suggested["genai_prefix_config"] = {
                f"title_genai_prefix_{level}": existing_prefixes.get(
                    level, DEFAULT_TITLE_GENAI_PREFIXES.get(level, "")
                )
                for level in (0, 1, 2)
            }

        if faces:
            suggested["face_overrides"] = {
                name: existing_overrides.get(name, "") for _, name in faces
            }
        if plates:
            suggested["plate_overrides"] = {
                name: existing_overrides.get(name, "") for _, name in plates
            }

        return self.async_show_form(
            step_id="appearance",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            last_step=False,
        )

    def _apply_appearance(self, user_input: dict[str, Any]) -> None:
        """Store appearance step fields (including title template) into _data."""
        self._data["title_template"] = (
            user_input.get("title_template") or DEFAULT_TITLE_TEMPLATE
        ).strip()

        emoji_section = user_input.get("emoji_config", {})
        self._data["enable_emojis"] = emoji_section.get("enable_emojis", True)
        self._data["default_emoji"] = (emoji_section.get("default_emoji") or DEFAULT_EMOJI).strip()

        custom_emoji = user_input.get("custom_emoji_config", {})
        custom_map = custom_emoji.get("emoji_map")
        if custom_map and isinstance(custom_map, dict):
            deltas = {k: v for k, v in custom_map.items() if DEFAULT_EMOJI_MAP.get(k) != v}
            if deltas:
                self._data["emoji_map"] = deltas
            else:
                self._data.pop("emoji_map", None)
        else:
            self._data.pop("emoji_map", None)

        self._data.pop("emoji_style", None)

        overrides: dict[str, str] = {}
        for section_key in ("face_overrides", "plate_overrides"):
            section_data = user_input.get(section_key, {})
            for name, value in section_data.items():
                if value and str(value).strip():
                    overrides[name] = str(value).strip()
        if overrides:
            self._data["sub_label_overrides"] = overrides
        else:
            self._data.pop("sub_label_overrides", None)

        phase_section = user_input.get("phase_emoji_config", {})
        phase_overrides: dict[str, str] = {}
        for phase_key in ("initial", "update", "end", "genai"):
            val = (phase_section.get(f"phase_{phase_key}") or "").strip()
            if val != DEFAULT_PHASE_EMOJI_MAP.get(phase_key, ""):
                phase_overrides[phase_key] = val
        if phase_overrides:
            self._data["phase_emoji_map"] = phase_overrides
        else:
            self._data.pop("phase_emoji_map", None)

        genai_sec = user_input.get("genai_prefix_config", {})
        if genai_sec:
            prefixes: dict[int, str] = {}
            for level in (0, 1, 2):
                value = (genai_sec.get(f"title_genai_prefix_{level}") or "").strip()
                if value:
                    prefixes[level] = value
            if prefixes:
                self._data["title_genai_prefixes"] = prefixes
            else:
                self._data.pop("title_genai_prefixes", None)

    async def async_step_zone_aliases(self, user_input=None) -> ConfigFlowResult:
        """Zone aliases — one collapsed section per camera with zones."""
        if self._frigate_entry_id not in self.hass.data.get(FRIGATE_DOMAIN, {}):
            return await self._finish_or_menu()

        cameras_with_zones = self._cameras_with_zones()
        if not cameras_with_zones:
            return await self._finish_or_menu()

        # Build display-name → camera-id mapping for humanized section keys.
        display_to_camera = {humanize_zone(c): c for c in cameras_with_zones}

        if user_input is not None:
            self._apply_zone_aliases(user_input, cameras_with_zones, display_to_camera)
            return await self._finish_or_menu()

        existing_aliases = self._data.get("zone_aliases", {})
        schema_fields: dict[Any, Any] = {}
        suggested: dict[str, Any] = {}

        for display_name, camera in display_to_camera.items():
            zones = get_camera_zones(self.hass, self._frigate_entry_id, camera)
            zone_fields: dict[Any, Any] = {}
            cam_suggested: dict[str, str] = {}
            cam_aliases = existing_aliases.get(camera, {})
            for zone in zones:
                zone_fields[vol.Optional(zone)] = TextSelector()
                cam_suggested[zone] = cam_aliases.get(zone, humanize_zone(zone))
            schema_fields[vol.Optional(display_name)] = section(
                vol.Schema(zone_fields),
                SectionConfig(collapsed=True),
            )
            suggested[display_name] = cam_suggested

        return self.async_show_form(
            step_id="zone_aliases",
            data_schema=self.add_suggested_values_to_schema(vol.Schema(schema_fields), suggested),
            last_step=False,
        )

    def _apply_zone_aliases(
        self,
        user_input: dict[str, Any],
        cameras_with_zones: list[str],
        display_to_camera: dict[str, str],
    ) -> None:
        """Store zone aliases from the single-step form."""
        aliases: dict[str, dict[str, str]] = {}
        for display_name, camera in display_to_camera.items():
            cam_input = user_input.get(display_name, {})
            camera_aliases: dict[str, str] = {}
            for zone in get_camera_zones(self.hass, self._frigate_entry_id, camera):
                value = (cam_input.get(zone) or "").strip()
                if value:
                    camera_aliases[zone] = value
            if camera_aliases:
                aliases[camera] = camera_aliases
        if aliases:
            self._data["zone_aliases"] = aliases
        else:
            self._data.pop("zone_aliases", None)

    async def _finish_or_menu(self) -> ConfigFlowResult:
        """Return to menu in reconfigure mode, or save in linear mode."""
        if self._reconfiguring:
            return await self.async_step_menu()
        return self.async_create_entry(data=self._data)

    def _cameras_with_zones(self) -> list[str]:
        """Return camera names that have at least one zone."""
        return [
            c
            for c in get_available_cameras(self.hass, self._frigate_entry_id)
            if get_camera_zones(self.hass, self._frigate_entry_id, c)
        ]
