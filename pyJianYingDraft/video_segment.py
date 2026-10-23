"""Video segments and their related types.

Covers image adjustments, animations, effects and transitions.
"""

import uuid
from copy import deepcopy

from typing import Optional, Literal, Union
from typing import Dict, List, Tuple, Any, TYPE_CHECKING

if TYPE_CHECKING:  # import cycle at runtime; needed only so the annotation resolves
    from .script_file import Script_file

from pyJianYingDraft.metadata.capcut_effect_meta import CapCut_Video_character_effect_type, CapCut_Video_scene_effect_type
from pyJianYingDraft.metadata.capcut_mask_meta import CapCut_Mask_type

from .time_util import tim, Timerange
from .segment import Visual_segment, Clip_settings
from .local_materials import Video_material
from .animation import Segment_animations, Video_animation

from .metadata import Effect_meta, Effect_param_instance
from .metadata import Mask_meta, CapCut_Transition_type
from .metadata import CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type


class Mask:
    """A mask."""

    mask_meta: Mask_meta
    """Mask metadata."""
    global_id: str
    """Global mask id, generated automatically."""

    center_x: float
    """Mask centre x, in units of half the material width."""
    center_y: float
    """Mask centre y, in units of half the material height."""
    width: float
    height: float
    aspect_ratio: float

    rotation: float
    invert: bool
    feather: float
    """Feathering, 0-1."""
    round_corner: float
    """Corner radius for a rectangular mask, 0-1."""

    def __init__(self, mask_meta: Mask_meta,
                 cx: float, cy: float, w: float, h: float,
                 ratio: float, rot: float, inv: bool, feather: float, round_corner: float):
        self.mask_meta = mask_meta
        self.global_id = uuid.uuid4().hex

        self.center_x, self.center_y = cx, cy
        self.width, self.height = w, h
        self.aspect_ratio = ratio

        self.rotation = rot
        self.invert = inv
        self.feather = feather
        self.round_corner = round_corner

    def export_json(self) -> Dict[str, Any]:
        return {
            "config": {
                "aspectRatio": self.aspect_ratio,
                "centerX": self.center_x,
                "centerY": self.center_y,
                "feather": self.feather,
                "height": self.height,
                "invert": self.invert,
                "rotation": self.rotation,
                "roundCorner": self.round_corner,
                "width": self.width
            },
            "category": "video",
            "category_id": "",
            "category_name": "",
            "id": self.global_id,
            "name": self.mask_meta.name,
            "platform": "all",
            "position_info": "",
            "resource_type": self.mask_meta.resource_type,
            "resource_id": self.mask_meta.resource_id,
            "type": "mask"
            # path is deliberately not exported
        }

class Video_effect:
    """A video effect material."""

    name: str
    """Effect name."""
    global_id: str
    """Global effect id, generated automatically."""
    effect_id: str
    """An effect id supplied by the editor."""
    resource_id: str
    """Resource id, supplied by the editor."""

    effect_type: Literal["video_effect", "face_effect"]
    apply_target_type: Literal[0, 2]
    """Apply target: 0 for the segment, 2 for global."""

    adjust_params: List[Effect_param_instance]

    def __init__(self, effect_meta: Union[CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type],
                 params: Optional[List[Optional[float]]] = None, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Build a video effect from its metadata and parameter list; params range 0-100."""

        self.name = effect_meta.value.name
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_meta.value.effect_id
        self.resource_id = effect_meta.value.resource_id
        self.adjust_params = []

        if isinstance(effect_meta, CapCut_Video_scene_effect_type):
            self.effect_type = "video_effect"
        elif isinstance(effect_meta, CapCut_Video_character_effect_type):
            self.effect_type = "face_effect"
        else:
            raise TypeError("Invalid effect meta type %s" % type(effect_meta))

        self.apply_target_type = apply_target_type

        self.adjust_params = effect_meta.value.parse_params(params)

    def export_json(self) -> Dict[str, Any]:
        return {
            "adjust_params": [param.export_json() for param in self.adjust_params],
            "apply_target_type": self.apply_target_type,
            "apply_time_range": None,
            "category_id": "",  # always empty
            "category_name": "",  # always empty
            "common_keyframes": [],
            "disable_effect_faces": [],
            "effect_id": self.effect_id,
            "formula_id": "",
            "id": self.global_id,
            "name": self.name,
            "platform": "all",
            "render_index": 11000,
            "resource_id": self.resource_id,
            "source_platform": 0,
            "time_range": None,
            "track_render_index": 0,
            "type": self.effect_type,
            "value": 1.0,
            "version": ""
            # path, request_id and algorithm_artifact_path are deliberately not exported
        }

class Filter:
    """A filter material."""

    global_id: str
    """Global filter id, generated automatically."""

    effect_meta: Effect_meta
    """Filter metadata."""
    intensity: float
    """Filter intensity, its only parameter."""

    apply_target_type: Literal[0, 2]
    """Apply target: 0 for the segment, 2 for global."""

    def __init__(self, meta: Effect_meta, intensity: float, *,
                 apply_target_type: Literal[0, 2] = 0):
        """Build a filter material from its metadata and intensity."""

        self.global_id = uuid.uuid4().hex
        self.effect_meta = meta
        self.intensity = intensity
        self.apply_target_type = apply_target_type

    def export_json(self) -> Dict[str, Any]:
        return {
            "adjust_params": [],
            "algorithm_artifact_path": "",
            "apply_target_type": self.apply_target_type,
            "bloom_params": None,
            "category_id": "",  # always empty
            "category_name": "",  # always empty
            "color_match_info": {
                "source_feature_path": "",
                "target_feature_path": "",
                "target_image_path": ""
            },
            "effect_id": self.effect_meta.effect_id,
            "enable_skin_tone_correction": False,
            "exclusion_group": [],
            "face_adjust_params": [],
            "formula_id": "",
            "id": self.global_id,
            "intensity_key": "",
            "multi_language_current": "",
            "name": self.effect_meta.name,
            "panel_id": "",
            "platform": "all",
            "resource_id": self.effect_meta.resource_id,
            "source_platform": 1,
            "sub_type": "none",
            "time_range": None,
            "type": "filter",
            "value": self.intensity,
            "version": ""
            # path and request_id are deliberately not exported
        }

class Transition:
    """A transition."""

    name: str
    """Transition name."""
    global_id: str
    """Global transition id, generated automatically."""
    effect_id: str
    """Transition effect id, supplied by the editor."""
    resource_id: str
    """Resource id, supplied by the editor."""

    duration: int
    """Transition duration, in microseconds."""
    is_overlap: bool
    """Whether it overlaps the previous segment (uncertain)."""

    def __init__(self, effect_meta: CapCut_Transition_type, duration: Optional[int] = None):
        """Build a transition from its metadata and duration."""
        self.name = effect_meta.value.name
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_meta.value.effect_id
        self.resource_id = effect_meta.value.resource_id

        self.duration = duration if duration is not None else effect_meta.value.default_duration
        self.is_overlap = effect_meta.value.is_overlap

    def export_json(self) -> Dict[str, Any]:
        return {
            "category_id": "",  # always empty
            "category_name": "",  # always empty
            "duration": self.duration,
            "effect_id": self.effect_id,
            "id": self.global_id,
            "is_overlap": self.is_overlap,
            "name": self.name,
            "platform": "all",
            "resource_id": self.resource_id,
            "type": "transition"
            # path and request_id are deliberately not exported
        }

class BackgroundFilling:
    """A background fill."""

    global_id: str
    """Global background-fill id, generated automatically."""
    fill_type: Literal["canvas_blur", "canvas_color"]
    """Background fill type."""
    blur: float
    """Blur amount, 0-1."""
    color: str
    """Background colour, in '#RRGGBBAA' form."""

    def __init__(self, fill_type: Literal["canvas_blur", "canvas_color"], blur: float, color: str):
        self.global_id = uuid.uuid4().hex
        self.fill_type = fill_type
        self.blur = blur
        self.color = color

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.global_id,
            "type": self.fill_type,
            "blur": self.blur,
            "color": self.color,
            "source_platform": 0,
        }

class Video_segment(Visual_segment):
    """A video or image segment placed on a track."""

    material_instance: Video_material
    """The material instance."""
    material_size: Tuple[int, int]
    """Material dimensions."""

    effects: List[Video_effect]
    """The effects.

    Added to the material list automatically when placed on a track.
    """
    filters: List[Filter]
    """The filters.

    Added to the material list automatically when placed on a track.
    """
    mask: Optional[Mask]
    """The mask, if any.

    Added to the material list automatically when placed on a track.
    """
    transition: Optional[Transition]
    """The transition, if any.

    Added to the material list automatically when placed on a track.
    """
    background_filling: Optional[BackgroundFilling]
    """The background fill, if any.

    Added to the material list automatically when placed on a track.
    """

    visible: Optional[bool]
    """Whether the segment is visible.
    Defaults to True.
    """

    # TODO: let the material argument accept a path for convenience
    def __init__(self, material: Video_material, target_timerange: Timerange, *,
                 source_timerange: Optional[Timerange] = None, speed: Optional[float] = None, volume: float = 1.0,
                 clip_settings: Optional[Clip_settings] = None):
        """Build a track segment from a video or image material, with its timing and image adjustments.

        Args:
            material (`Video_material`): the material instance
            target_timerange (`Timerange`): where the segment sits on the track
            source_timerange (`Timerange`, optional): the portion of the material to use. Defaults to a span from the start, scaled by `speed`, matching `target_timerange`
            speed (`float`, optional): playback speed, default 1.0. Given together with `source_timerange`, it overrides the duration in `target_timerange`
            volume (`float`, optional): volume, default 1.0
            clip_settings (`Clip_settings`, optional): image adjustments; by default nothing is transformed

        Raises:
            `ValueError`: the given or computed `source_timerange` runs past the end of the material
        """
        # if source_timerange is not None and speed is not None:
        #     target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))
        # elif source_timerange is not None and speed is None:
        #     speed = source_timerange.duration / target_timerange.duration
        # else:  # source_timerange is None
        #     speed = speed if speed is not None else 1.0
        #     source_timerange = Timerange(0, round(target_timerange.duration * speed))

        # if source_timerange.end > material.duration:
        #     source_timerange = Timerange(source_timerange.start, material.duration - source_timerange.start)
        #     # recompute the target time range
        #     target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))

        super().__init__(material.material_id, source_timerange, target_timerange, speed, volume, clip_settings=clip_settings)

        self.material_instance = deepcopy(material)
        self.material_size = (material.width, material.height)
        self.effects = []
        self.filters = []
        self.transition = None
        self.mask = None
        self.background_filling = None

    def add_animation(self, animation_type: Union[CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type],
                      duration: Optional[Union[int, str]] = None) -> "Video_segment":
        """Add an intro, outro or combo animation to this segment.

        Args:
            animation_type (`CapCut_Intro_type`, `CapCut_Outro_type`, or `CapCut_Group_animation_type`): the animation type
            duration (`int` or `str`, optional): animation duration in microseconds; strings are parsed with `tim()`.
                Omitted, the animation type's own default is used. In principle this applies only to intro and outro animations.
        """
        if duration is not None:
            duration = tim(duration)
        if isinstance(animation_type, CapCut_Intro_type):
            start = 0
            duration = duration or animation_type.value.duration
        elif isinstance(animation_type, CapCut_Outro_type):
            duration = duration or animation_type.value.duration
            start = self.target_timerange.duration - duration
        elif isinstance(animation_type, CapCut_Group_animation_type):
            start = 0
            duration = duration or self.target_timerange.duration
        else:
            raise TypeError("Invalid animation type %s" % type(animation_type))

        if self.animations_instance is None:
            self.animations_instance = Segment_animations()
            self.extra_material_refs.append(self.animations_instance.animation_id)

        self.animations_instance.add_animation(Video_animation(animation_type, start, duration))

        return self

    def add_effect(self, effect_type: Union[CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type],
                   params: Optional[List[Optional[float]]] = None) -> "Video_segment":
        """Add an effect covering the whole segment.

        Args:
            effect_type (`CapCut_Video_scene_effect_type` or `CapCut_Video_character_effect_type`): the effect type
            params (`List[Optional[float]]`, optional): effect parameters; omitted or None entries use the default.
                Values run 0-100, as in the editor. Which parameters an effect takes, and in what order, is given by the enum member's annotation.

        Raises:
            `ValueError`: too many parameters were given, or a value is out of range.
        """
        if params is not None and len(params) > len(effect_type.value.params):
            raise ValueError("Too many parameters given for effect %s" % effect_type.value.name)

        effect_inst = Video_effect(effect_type, params)
        self.effects.append(effect_inst)
        self.extra_material_refs.append(effect_inst.global_id)

        return self

    def add_mask(self, draft: "Script_file", mask_type: CapCut_Mask_type, *, center_x: float = 0.0, center_y: float = 0.0, size: float = 0.5,
                 rotation: float = 0.0, feather: float = 0.0, invert: bool = False,
                 rect_width: Optional[float] = None, round_corner: Optional[float] = None) -> "Video_segment":
        """Add a mask to the video segment.

        Args:
            mask_type (`CapCut_Mask_type`): the mask type
            center_x (`float`, optional): mask centre x in material pixels; defaults to the material centre
            center_y (`float`, optional): mask centre y in material pixels; defaults to the material centre
            size (`float`, optional): the mask's principal dimension (mirror height, circle diameter, heart height and so on) as a fraction of the material height. Default 0.5
            rotation (`float`, optional): clockwise mask rotation in **degrees**; no rotation by default
            feather (`float`, optional): mask feathering, 0-100; none by default
            invert (`bool`, optional): invert the mask; not inverted by default
            rect_width (`float`, optional): width of a rectangular mask, as a fraction of the material width. Rectangular masks only; defaults to `size`
            round_corner (`float`, optional): corner radius of a rectangular mask, 0-100. Rectangular masks only; default 0

        Raises:
            `ValueError`: a second mask was added, or `rect_width`/`round_corner` were set incorrectly
        """

        if self.mask is not None:
            raise ValueError("This segment already has a mask")
        if (rect_width is not None or round_corner is not None) and mask_type != CapCut_Mask_type.Rectangle:
            raise ValueError("`rect_width` and `round_corner` may only be set on a rectangular mask")
        if rect_width is None and mask_type == CapCut_Mask_type.Rectangle:
            rect_width = size
        if round_corner is None:
            round_corner = 0

        # Use the draft dimensions rather than the material's
        draft_width = draft.width
        draft_height = draft.height

        width = rect_width or size * draft_height * mask_type.value.default_aspect_ratio / draft_width
        self.mask = Mask(mask_type.value, center_x / (draft_width / 2), center_y / (draft_height / 2),
                         w=width, h=size, ratio=mask_type.value.default_aspect_ratio,
                         rot=rotation, inv=invert, feather=feather / 100, round_corner=round_corner / 100)
        self.extra_material_refs.append(self.mask.global_id)
        return self

    def add_transition(self, transition_type: CapCut_Transition_type, *, duration: Optional[Union[int, str]] = None) -> "Video_segment":
        """Add a transition. Note that it belongs on the **earlier** of the two segments.

        Args:
            transition_type (`CapCut_Transition_type`): the transition type
            duration (`int` or `str`, optional): transition duration in microseconds; strings are parsed with `tim()`. Omitted, the transition type's own default is used.

        Raises:
            `ValueError`: a second transition was added.
        """
        if self.transition is not None:
            raise ValueError("This segment already has a transition")
        if isinstance(duration, str): duration = tim(duration)

        self.transition = Transition(transition_type, duration)
        self.extra_material_refs.append(self.transition.global_id)
        return self

    def add_background_filling(self, fill_type: Literal["blur", "color"], blur: float = 0.0625, color: str = "#00000000") -> "Video_segment":
        """Add a background fill to the video segment.

        Note: background fills only take effect on segments in the bottom video track.

        Args:
            fill_type (`blur` or `color`): the fill type.
            blur (`float`, optional): blur amount, 0.0-1.0. Only meaningful when `fill_type` is `blur`. The editor's four blur levels are 0.0625, 0.375, 0.75 and 1.0; default 0.0625.
            color (`str`, optional): fill colour in '#RRGGBBAA' form. Only meaningful when `fill_type` is `color`.

        Raises:
            `ValueError`: the segment already has a background fill, or `fill_type` is invalid.
        """
        if self.background_filling is not None:
            raise ValueError("This segment already has a background fill")

        if fill_type == "blur":
            self.background_filling = BackgroundFilling("canvas_blur", blur, color)
        elif fill_type == "color":
            self.background_filling = BackgroundFilling("canvas_color", blur, color)
        else:
            raise ValueError(f"Invalid background fill type {fill_type}")

        self.extra_material_refs.append(self.background_filling.global_id)
        return self

    def export_json(self) -> Dict[str, Any]:
        json_dict = super().export_json()
        json_dict.update({
            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
        })
        return json_dict

class Sticker_segment(Visual_segment):
    """A sticker segment placed on a track."""

    resource_id: str
    """Sticker resource id."""

    def __init__(self, resource_id: str, target_timerange: Timerange, *, clip_settings: Optional[Clip_settings] = None):
        """Build a sticker segment from a resource id, with its timing and image adjustments.

        Once built, add it to a track with `Script_file.add_segment`.

        Args:
            resource_id (`str`): the sticker resource id, obtainable from a template with `Script_file.inspect_material`
            target_timerange (`Timerange`): where the segment sits on the track
            clip_settings (`Clip_settings`, optional): image adjustments; by default nothing is transformed
        """
        super().__init__(uuid.uuid4().hex, None, target_timerange, 1.0, 1.0, clip_settings=clip_settings)
        self.resource_id = resource_id

    def export_material(self) -> Dict[str, Any]:
        """Build a minimal sticker material, avoiding a dedicated sticker material class."""
        return {
            "id": self.material_id,
            "resource_id": self.resource_id,
            "sticker_id": self.resource_id,
            "source_platform": 1,
            "type": "sticker",
        }
