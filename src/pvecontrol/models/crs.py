"""HA Cluster Resource Scheduler (CRS) settings, the crs property string of datacenter.cfg"""

from dataclasses import dataclass, fields
from typing import Optional, Union

from pvecontrol.models import api_kwargs

CRS_MODES = ["basic", "static", "dynamic"]
CRS_REBALANCE_METHODS = ["bruteforce", "topsis"]

# Key that every ha-auto-rebalance-* key requires in the same property string, or the API rejects it
AUTO_REBALANCE_KEY = "ha-auto-rebalance"


@dataclass(frozen=True)
class CrsOption:
    """One key of the crs property string"""

    key: str  # Proxmox key, kebab-case
    attribute: str  # snake_case name, used for the model attribute and the set command
    kind: str  # "enum", "bool" or "number"
    default: object
    choices: tuple = ()
    minimum: float = None
    maximum: float = None

    @property
    def field(self):
        """Name of the PVECrsData field holding the key"""
        return self.key.replace("-", "_")


CRS_OPTIONS = [
    CrsOption("ha", "mode", "enum", "basic", choices=tuple(CRS_MODES)),
    CrsOption("ha-rebalance-on-start", "rebalance_on_start", "bool", False),
    CrsOption(AUTO_REBALANCE_KEY, "auto_rebalance", "bool", False),
    CrsOption("ha-auto-rebalance-threshold", "threshold", "number", 30, minimum=0, maximum=100),
    CrsOption("ha-auto-rebalance-hold-duration", "hold_duration", "number", 3, minimum=0),
    CrsOption("ha-auto-rebalance-margin", "margin", "number", 10, minimum=0, maximum=100),
    CrsOption("ha-auto-rebalance-method", "method", "enum", "bruteforce", choices=tuple(CRS_REBALANCE_METHODS)),
]
CRS_OPTIONS_BY_KEY = {option.key: option for option in CRS_OPTIONS}
CRS_OPTIONS_BY_ATTRIBUTE = {option.attribute: option for option in CRS_OPTIONS}

# The key a property string token without "=" sets (crs: static means crs: ha=static)
CRS_DEFAULT_KEY = "ha"


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ValueError(f"invalid boolean value: '{value}'")


def _parse_number(value):
    number = float(value)
    return int(number) if number.is_integer() else number


def _format_value(value):
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


@dataclass(eq=False)
class PVECrsData:
    """Keys of the crs property string, None when datacenter.cfg doesn't set them"""

    ha: Optional[str] = None
    ha_rebalance_on_start: Optional[bool] = None
    ha_auto_rebalance: Optional[bool] = None
    ha_auto_rebalance_threshold: Optional[Union[int, float]] = None
    ha_auto_rebalance_hold_duration: Optional[Union[int, float]] = None
    ha_auto_rebalance_margin: Optional[Union[int, float]] = None
    ha_auto_rebalance_method: Optional[str] = None


def _effective(attribute):
    """Property returning the value of an option, its Proxmox default when it is not set"""
    option = CRS_OPTIONS_BY_ATTRIBUTE[attribute]

    def getter(self):
        value = getattr(self, option.field)
        return option.default if value is None else value

    return property(getter, doc=f"{option.key}, {option.default!r} when not set")


class PVECrs(PVECrsData):
    """HA Cluster Resource Scheduler settings.

    The dataclass fields hold the keys explicitly set in datacenter.cfg, the properties below give the effective
    values, with the Proxmox default for the keys not set. Unknown keys, from a newer Proxmox VE for instance,
    are kept in extra so that writing the settings back doesn't drop them.
    """

    mode = _effective("mode")
    rebalance_on_start = _effective("rebalance_on_start")
    auto_rebalance = _effective("auto_rebalance")
    threshold = _effective("threshold")
    hold_duration = _effective("hold_duration")
    margin = _effective("margin")
    method = _effective("method")

    def __init__(self, extra=None, **kwargs):
        super().__init__(**kwargs)
        self.extra = dict(extra or {})

        for option in CRS_OPTIONS:
            value = getattr(self, option.field)
            if value is None:
                continue
            if option.kind == "bool":
                value = _parse_bool(value)
            elif option.kind == "number":
                value = _parse_number(value)
            else:
                value = str(value)
            setattr(self, option.field, value)

    @classmethod
    def from_api(cls, payload):
        """Build the settings from the crs value of cluster/options: absent, a dict or a property string"""
        if payload is None or payload == "":
            return cls()
        if isinstance(payload, str):
            payload = cls.parse_property_string(payload)
        if not isinstance(payload, dict):
            raise ValueError(f"unexpected crs value: {payload!r}")
        names = {f.name for f in fields(PVECrsData)}
        extra = {key: value for key, value in payload.items() if key.replace("-", "_") not in names}
        return cls(extra=extra, **api_kwargs(PVECrsData, payload))

    @staticmethod
    def parse_property_string(text):
        values = {}
        for token in text.split(","):
            token = token.strip()
            if not token:
                continue
            key, sep, value = token.partition("=")
            if not sep:
                key, value = CRS_DEFAULT_KEY, key
            values[key.strip()] = value.strip()
        return values

    def __str__(self):
        return self.to_property_string()

    def _set_values(self):
        """Keys explicitly set, by Proxmox key, in schema order then unknown keys"""
        values = {
            option.key: getattr(self, option.field) for option in CRS_OPTIONS if getattr(self, option.field) is not None
        }
        values.update(sorted(self.extra.items()))
        return values

    def is_set(self, attribute):
        return getattr(self, CRS_OPTIONS_BY_ATTRIBUTE[attribute].field) is not None

    def update(self, **changes):
        """Return new settings with the given attributes changed, None values are left unchanged"""
        values = {f.name: getattr(self, f.name) for f in fields(PVECrsData)}
        for attribute, value in changes.items():
            if value is not None:
                values[CRS_OPTIONS_BY_ATTRIBUTE[attribute].field] = value
        return PVECrs(extra=self.extra, **values)

    def to_property_string(self):
        """Serialize the explicitly set keys, in schema order then unknown keys.

        Every ha-auto-rebalance-* key requires ha-auto-rebalance in the same string, it is written with its
        current value (its default when unset) whenever one of them is.
        """
        values = self._set_values()
        if AUTO_REBALANCE_KEY not in values and any(k.startswith(AUTO_REBALANCE_KEY + "-") for k in values):
            values[AUTO_REBALANCE_KEY] = CRS_OPTIONS_BY_KEY[AUTO_REBALANCE_KEY].default
        keys = [option.key for option in CRS_OPTIONS if option.key in values]
        keys += [key for key in values if key not in CRS_OPTIONS_BY_KEY]
        return ",".join(f"{key}={_format_value(values[key])}" for key in keys)

    def validate(self):
        """Return the list of errors of the settings, empty when they are valid"""
        errors = []
        for option in CRS_OPTIONS:
            value = getattr(self, option.field)
            if value is None:
                continue
            if option.kind == "enum" and value not in option.choices:
                errors.append(f"{option.key}: '{value}' is not one of {', '.join(option.choices)}")
            if option.kind == "number":
                if option.minimum is not None and value < option.minimum:
                    errors.append(f"{option.key}: {value} is lower than {option.minimum}")
                if option.maximum is not None and value > option.maximum:
                    errors.append(f"{option.key}: {value} is greater than {option.maximum}")
        # Proxmox accepts it, but the HA manager silently ignores auto-rebalance in basic mode
        if self.auto_rebalance and self.mode == "basic":
            errors.append("ha-auto-rebalance requires the static or dynamic mode, the basic mode ignores it")
        return errors

    def to_rows(self):
        """One row per option, with its effective value and whether it is set or a default"""
        return [
            {
                "option": option.key,
                "value": getattr(self, option.attribute),
                "source": "configured" if self.is_set(option.attribute) else "default",
            }
            for option in CRS_OPTIONS
        ] + [{"option": key, "value": value, "source": "configured"} for key, value in sorted(self.extra.items())]
