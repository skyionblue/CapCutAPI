"""Audio segments and their related types.

Covers fades, audio effects and similar.
"""

import uuid
from copy import deepcopy

from typing import Optional, Literal, Union
from typing import Dict, List, Any

from pyJianYingDraft.metadata.capcut_audio_effect_meta import CapCut_Speech_to_song_effect_type, CapCut_Voice_characters_effect_type, CapCut_Voice_filters_effect_type

from .time_util import tim, Timerange
from .segment import Media_segment
from .local_materials import Audio_material
from .keyframe import Keyframe_property, Keyframe_list

from .metadata import Effect_param_instance

class Audio_fade:
    """An audio fade in/out."""

    fade_id: str
    """Global id for the fade, generated automatically."""

    in_duration: int
    """Fade-in duration, in microseconds."""
    out_duration: int
    """Fade-out duration, in microseconds."""

    def __init__(self, in_duration: int, out_duration: int):
        """Construct a fade from the given fade-in and fade-out durations."""

        self.fade_id = uuid.uuid4().hex
        self.in_duration = in_duration
        self.out_duration = out_duration

    def export_json(self) -> Dict[str, Any]:
        return {
            "id": self.fade_id,
            "fade_in_duration": self.in_duration,
            "fade_out_duration": self.out_duration,
            "fade_type": 0,
            "type": "audio_fade"
        }

class Audio_effect:
    """An audio effect."""

    name: str
    """Effect name."""
    effect_id: str
    """Global effect id, generated automatically."""
    resource_id: str
    """Resource id, supplied by the editor."""

    category_id: Literal["sound_effect", "tone", "speech_to_song"]
    category_name: Literal["Voice filters", "Voice characters", "Speech to song"]

    audio_adjust_params: List[Effect_param_instance]

    def __init__(self, effect_meta: Union[CapCut_Voice_filters_effect_type, CapCut_Voice_characters_effect_type, CapCut_Speech_to_song_effect_type],
                 params: Optional[List[Optional[float]]] = None):
        """Construct an audio effect from its metadata and parameter list; params range 0-100."""

        self.name = effect_meta.value.name
        self.effect_id = uuid.uuid4().hex
        self.resource_id = effect_meta.value.resource_id
        self.audio_adjust_params = []

        if isinstance(effect_meta, CapCut_Voice_filters_effect_type):
            self.category_id = "sound_effect"
            self.category_name = "Voice filters"
        elif isinstance(effect_meta, CapCut_Voice_characters_effect_type):
            self.category_id = "tone"
            self.category_name = "Voice characters"
        elif isinstance(effect_meta, CapCut_Speech_to_song_effect_type):
            self.category_id = "speech_to_song"
            self.category_name = "Speech to song"
        else:
            raise TypeError("Unsupported metadata type %s" % type(effect_meta))

        self.audio_adjust_params = effect_meta.value.parse_params(params)

    def export_json(self) -> Dict[str, Any]:
        return {
            "audio_adjust_params": [param.export_json() for param in self.audio_adjust_params],
            "category_id": self.category_id,
            "category_name": self.category_name,
            "id": self.effect_id,
            "is_ugc": False,
            "name": self.name,
            "production_path": "",
            "resource_id": self.resource_id,
            "speaker_id": "",
            "sub_type": 1,
            "time_range": {"duration": 0, "start": 0},  # appears to be unused
            "type": "audio_effect"
            # path and constant_material_id are deliberately not exported
        }

class Audio_segment(Media_segment):
    """An audio segment placed on a track."""

    material_instance: Audio_material
    """The audio material instance."""

    fade: Optional[Audio_fade]
    """The audio fade, if any.

    Added to the material list automatically when placed on a track.
    """

    effects: List[Audio_effect]
    """The audio effects.

    Added to the material list automatically when placed on a track.
    """

    def __init__(self, material: Audio_material, target_timerange: Timerange, *,
                 source_timerange: Optional[Timerange] = None, speed: Optional[float] = None, volume: float = 1.0):
        """Build a track segment from an audio material, with its timing, speed and volume.

        Args:
            material (`Audio_material`): the material instance
            target_timerange (`Timerange`): where the segment sits on the track
            source_timerange (`Timerange`, optional): the portion of the material to use. Defaults to a span from the start, scaled by `speed`, matching `target_timerange`
            speed (`float`, optional): playback speed, default 1.0. Given together with `source_timerange`, it overrides the duration in `target_timerange`
            volume (`float`, optional): volume, default 1.0

        Raises:
            `ValueError`: the given or computed `source_timerange` runs past the end of the material
        """
        if source_timerange is not None and speed is not None:
            target_timerange = Timerange(target_timerange.start, round(source_timerange.duration / speed))
        elif source_timerange is not None and speed is None:
            speed = source_timerange.duration / target_timerange.duration
        else:  # source_timerange is None
            speed = speed if speed is not None else 1.0
            source_timerange = Timerange(0, round(target_timerange.duration * speed))

        # if source_timerange.end > material.duration:
        #     raise ValueError(f"source range {source_timerange} runs past the material duration ({material.duration})")

        super().__init__(material.material_id, source_timerange, target_timerange, speed, volume)

        self.material_instance = deepcopy(material)
        self.fade = None
        self.effects = []

    def add_effect(self, effect_type: Union[CapCut_Voice_filters_effect_type, CapCut_Voice_characters_effect_type, CapCut_Speech_to_song_effect_type],
                   params: Optional[List[Optional[float]]] = None,
                   effect_id: Optional[str] = None) -> "Audio_segment":
        """Add an audio effect covering the whole segment. Speech-to-song effects are not picked up automatically by the editor.

        Args:
            effect_type (`CapCut_Voice_filters_effect_type` | `CapCut_Voice_characters_effect_type` | `CapCut_Speech_to_song_effect_type`): the effect type; only one of each category may be added.
            params (`List[Optional[float]]`, optional): effect parameters; omitted or None entries use the default.
                Values run 0-100, as in the editor. Which parameters an effect takes, and in what order, is given by the enum member's annotation.
            effect_id (`str`, optional): the effect id; generated automatically when omitted.

        Raises:
            `ValueError`: the effect type is already present, too many parameters were given, or a value is out of range.
        """
        if params is not None and len(params) > len(effect_type.value.params):
            raise ValueError("Too many parameters given for audio effect %s" % effect_type.value.name)
        self.material_instance.has_audio_effect = True
        effect_inst = Audio_effect(effect_type, params)
        if effect_id is not None:
            effect_inst.effect_id = effect_id
        if effect_inst.category_id in [eff.category_id for eff in self.effects]:
            raise ValueError("This audio segment already has an effect of category %s" % effect_inst.category_name)
        self.effects.append(effect_inst)
        self.extra_material_refs.append(effect_inst.effect_id)

        return self

    def add_fade(self, in_duration: Union[str, int], out_duration: Union[str, int]) -> "Audio_segment":
        """Add a fade in/out to the audio segment.

        Args:
            in_duration (`int` or `str`): fade-in duration in microseconds; strings are parsed with `tim()`
            out_duration (`int` or `str`): fade-out duration in microseconds; strings are parsed with `tim()`

        Raises:
            `ValueError`: the segment already has a fade
        """
        if self.fade is not None:
            raise ValueError("This segment already has a fade")

        if isinstance(in_duration, str): in_duration = tim(in_duration)
        if isinstance(out_duration, str): out_duration = tim(out_duration)

        self.fade = Audio_fade(in_duration, out_duration)
        self.extra_material_refs.append(self.fade.fade_id)

        return self

    def add_keyframe(self, time_offset: int, volume: float) -> "Audio_segment":
        """Add a *volume* keyframe to the audio segment, appending it to the keyframe list.

        Args:
            time_offset (`int`): the keyframe's time offset, in microseconds
            volume (`float`): the volume at `time_offset`
        """
        _property = Keyframe_property.volume
        for kf_list in self.common_keyframes:
            if kf_list.keyframe_property == _property:
                kf_list.add_keyframe(time_offset, volume)
                return self
        kf_list = Keyframe_list(_property)
        kf_list.add_keyframe(time_offset, volume)
        self.common_keyframes.append(kf_list)
        return self

    def export_json(self) -> Dict[str, Any]:
        json_dict = super().export_json()
        json_dict.update({
            "clip": None,
            "hdr_settings": None
        })
        return json_dict
