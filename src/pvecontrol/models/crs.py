"""HA Cluster Resource Scheduler (CRS) settings, the crs property string of datacenter.cfg"""

from dataclasses import dataclass

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


class PVECrs:
    """HA Cluster Resource Scheduler settings.

    Holds the keys explicitly set in datacenter.cfg, the other ones take their Proxmox default. Unknown keys,
    from a newer Proxmox VE for instance, are kept as is so that writing the settings back doesn't drop them.
    """

    def __init__(self, values=None):
        self._values = {}
        for key, value in (values or {}).items():
            option = CRS_OPTIONS_BY_KEY.get(key)
            if option is None:
                self._values[key] = value
            elif option.kind == "bool":
                self._values[key] = _parse_bool(value)
            elif option.kind == "number":
                self._values[key] = _parse_number(value)
            else:
                self._values[key] = str(value)

    @classmethod
    def from_api(cls, value):
        """Build the settings from the crs value of cluster/options: absent, a dict or a property string"""
        if value is None or value == "":
            return cls()
        if isinstance(value, dict):
            return cls(value)
        if isinstance(value, str):
            return cls(cls.parse_property_string(value))
        raise ValueError(f"unexpected crs value: {value!r}")

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

    def __getattr__(self, name):
        option = CRS_OPTIONS_BY_ATTRIBUTE.get(name)
        if option is None:
            raise AttributeError(name)
        return self._values.get(option.key, option.default)

    def __eq__(self, other):
        return isinstance(other, PVECrs) and self.to_property_string() == other.to_property_string()

    def __hash__(self):
        return hash(self.to_property_string())

    def __str__(self):
        return self.to_property_string()

    @property
    def values(self):
        """Keys explicitly set, by Proxmox key"""
        return dict(self._values)

    def is_set(self, attribute):
        return CRS_OPTIONS_BY_ATTRIBUTE[attribute].key in self._values

    def update(self, **changes):
        """Return new settings with the given attributes changed, None values are left unchanged"""
        values = dict(self._values)
        for attribute, value in changes.items():
            if value is None:
                continue
            values[CRS_OPTIONS_BY_ATTRIBUTE[attribute].key] = value
        return PVECrs(values)

    def to_property_string(self):
        """Serialize the explicitly set keys, in schema order then unknown keys.

        Every ha-auto-rebalance-* key requires ha-auto-rebalance in the same string, it is written with its
        current value (its default when unset) whenever one of them is.
        """
        values = dict(self._values)
        if AUTO_REBALANCE_KEY not in values and any(k.startswith(AUTO_REBALANCE_KEY + "-") for k in values):
            values[AUTO_REBALANCE_KEY] = CRS_OPTIONS_BY_KEY[AUTO_REBALANCE_KEY].default
        keys = [option.key for option in CRS_OPTIONS if option.key in values]
        keys += sorted(key for key in values if key not in CRS_OPTIONS_BY_KEY)
        return ",".join(f"{key}={_format_value(values[key])}" for key in keys)

    def validate(self):
        """Return the list of errors of the settings, empty when they are valid"""
        errors = []
        for option in CRS_OPTIONS:
            if option.key not in self._values:
                continue
            value = self._values[option.key]
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
                "source": "configured" if option.key in self._values else "default",
            }
            for option in CRS_OPTIONS
        ] + [
            {"option": key, "value": value, "source": "configured"}
            for key, value in sorted(self._values.items())
            if key not in CRS_OPTIONS_BY_KEY
        ]
