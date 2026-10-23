"""Video and text animation types."""

import uuid

from typing import Union, Optional
from typing import Literal, Dict, List, Any

from .time_util import Timerange

from .metadata.animation_meta import Animation_meta
from .metadata import CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type
from .metadata import CapCut_Text_intro, CapCut_Text_loop_anim, CapCut_Text_outro

class Animation:
    """A single video or text animation."""

    name: str
    """Animation name; defaults to the effect's own name."""
    effect_id: str
    """An alternative animation id, supplied by the editor."""
    animation_type: str
    """Animation type, defined by the subclass."""
    resource_id: str
    """Resource id, supplied by the editor."""

    start: int
    """Offset from the start of the segment, in microseconds."""
    duration: int
    """Animation duration, in microseconds."""

    is_video_animation: bool
    """Whether this is a video animation; defined by the subclass."""

    def __init__(self, animation_meta: Animation_meta, start: int, duration: int):
        self.name = animation_meta.title
        self.effect_id = animation_meta.effect_id
        self.resource_id = animation_meta.resource_id

        self.start = start
        self.duration = duration

    def export_json(self) -> Dict[str, Any]:
        return {
            "anim_adjust_params": None,
            "platform": "all",
            "panel": "video" if self.is_video_animation else "",
            "material_type": "video" if self.is_video_animation else "sticker",

            "name": self.name,
            "id": self.effect_id,
            "type": self.animation_type,
            "resource_id": self.resource_id,

            "start": self.start,
            "duration": self.duration,
            # path and request_id are deliberately not exported
        }

class Video_animation(Animation):
    """A video animation."""

    animation_type: Literal["in", "out", "group"]

    def __init__(self, animation_type: Union[CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type],
                 start: int, duration: int):
        super().__init__(animation_type.value, start, duration)

        if isinstance(animation_type, CapCut_Intro_type):
            self.animation_type = "in"
        elif isinstance(animation_type, CapCut_Outro_type):
            self.animation_type = "out"
        elif isinstance(animation_type, CapCut_Group_animation_type):
            self.animation_type = "group"

        self.is_video_animation = True

class Text_animation(Animation):
    """A text animation."""

    animation_type: Literal["in", "out", "loop"]

    def __init__(self, animation_type: Union[CapCut_Text_intro, CapCut_Text_outro, CapCut_Text_loop_anim],
                 start: int, duration: int):
        super().__init__(animation_type.value, start, duration)

        if isinstance(animation_type, CapCut_Text_intro):
            self.animation_type = "in"
        elif isinstance(animation_type, CapCut_Text_outro):
            self.animation_type = "out"
        elif isinstance(animation_type, CapCut_Text_loop_anim):
            self.animation_type = "loop"

        self.is_video_animation = False

class Segment_animations:
    """The animations attached to one material.

    Video segments take intro, outro or combo animations; text segments take intro, outro or loop animations."""

    animation_id: str
    """Global id for the animation set, generated automatically."""

    animations: List[Animation]
    """The animations."""

    def __init__(self):
        self.animation_id = uuid.uuid4().hex
        self.animations = []

    def get_animation_trange(self, animation_type: Literal["in", "out", "group", "loop"]) -> Optional[Timerange]:
        """The time range of the animation of the given type."""
        for animation in self.animations:
            if animation.animation_type == animation_type:
                return Timerange(animation.start, animation.duration)
        return None

    def add_animation(self, animation: Union[Video_animation, Text_animation]) -> None:
        # At most one animation of each type (two intro animations, for instance, are rejected)
        if animation.animation_type in [ani.animation_type for ani in self.animations]:
            raise ValueError(f"This segment already has an animation of type '{animation.animation_type}'")

        if isinstance(animation, Video_animation):
            # A combo animation cannot coexist with intro/outro animations
            if any(ani.animation_type == "group" for ani in self.animations):
                raise ValueError("This segment already has a combo animation; no other animation can be added")
            if animation.animation_type == "group" and len(self.animations) > 0:
                raise ValueError("A combo animation cannot be added to a segment that already has an animation")
        elif isinstance(animation, Text_animation):
            if any(ani.animation_type == "loop" for ani in self.animations):
                raise ValueError("This segment already has a loop animation. To combine a loop animation with intro/outro animations, add the intro/outro ones first")

        self.animations.append(animation)

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.animation_id,
            "type": "sticker_animation",
            "multi_language_current": "none",
            "animations": [animation.export_json() for animation in self.animations]
        }
