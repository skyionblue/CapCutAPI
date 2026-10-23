from enum import Enum

from typing import List, Dict, Any
from typing import TypeVar, Optional

class Effect_param:
    """Effect parameter metadata."""

    name: str
    """Parameter name."""
    default_value: float
    """Default value."""
    min_value: float
    """Minimum value."""
    max_value: float
    """Maximum value."""

    def __init__(self, name: str, default_value: float, min_value: float, max_value: float):
        self.name = name
        self.default_value = default_value
        self.min_value = min_value
        self.max_value = max_value

class Effect_param_instance(Effect_param):
    """An effect parameter instance."""

    index: int
    """Parameter index."""
    value: float
    """Current value."""

    def __init__(self, meta: Effect_param, index: int, value: float):
        super().__init__(meta.name, meta.default_value, meta.min_value, meta.max_value)
        self.index = index
        self.value = value

    def export_json(self) -> Dict[str, Any]:
        return {
            "default_value": self.default_value,
            "max_value": self.max_value,
            "min_value": self.min_value,
            "name": self.name,
            "parameterIndex": self.index,
            "portIndex": 0,
            "value": self.value
        }

class Effect_meta:
    """Effect metadata."""

    name: str
    """effect name"""
    is_vip: bool
    """whether this is a VIP feature"""

    resource_id: str
    """resource ID"""
    effect_id: str
    """effect ID"""
    md5: str

    params: List[Effect_param]
    """The effect's parameter metadata."""

    def __init__(self, name: str, is_vip: bool, resource_id: str, effect_id: str, md5: str, params: List[Effect_param] = []):
        self.name = name
        self.is_vip = is_vip
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5
        self.params = params

    def parse_params(self, params: Optional[List[Optional[float]]]) -> List[Effect_param_instance]:
        """Parse a parameter list (values 0-100) into parameter instances."""
        ret: List[Effect_param_instance] = []

        if params is None: params = []
        for i, param in enumerate(self.params):
            val = param.default_value
            if i < len(params):
                input_v = params[i]
                if input_v is not None:
                    if input_v < 0 or input_v > 100:
                        raise ValueError("Invalid parameter value %f within %s" % (input_v, str(param)))
                    val = param.min_value + (param.max_value - param.min_value) * input_v / 100.0  # map 0-100 onto the real range
            ret.append(Effect_param_instance(param, i, val))
        return ret


Effect_enum_subclass = TypeVar("Effect_enum_subclass", bound="Effect_enum")

class Effect_enum(Enum):
    """Base class for effect enums, providing `from_name` to look metadata up by name."""

    @classmethod
    def from_name(cls: "type[Effect_enum_subclass]", name: str) -> Effect_enum_subclass:
        """Look up effect metadata by name, ignoring case, spaces and underscores.

        Args:
            name (str): effect name

        Raises:
            `ValueError`: no effect with that name
        """
        name = name.lower().replace(" ", "").replace("_", "")
        for effect in cls:
            if effect.name.lower().replace(" ", "").replace("_", "") == name:
                return effect
        raise ValueError(f"Effect named '{name}' not found")
