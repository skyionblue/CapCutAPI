import os
import json
import math
from copy import deepcopy

from typing import Optional, Literal, Union, overload
from typing import Type, Dict, List, Any


from . import util
from . import exceptions
from .template_mode import EditableTrack, ImportedMediaTrack, ImportedTextTrack, Shrink_mode, Extend_mode, import_track
from .time_util import Timerange, tim, srt_tstamp
from .local_materials import Video_material, Audio_material
from .segment import Base_segment, Speed, Clip_settings
from .audio_segment import Audio_segment, Audio_fade, Audio_effect
from .video_segment import Video_segment, Sticker_segment, Segment_animations, Video_effect, Transition, Filter, BackgroundFilling
from .effect_segment import Effect_segment
from .text_segment import Text_segment, Text_style, TextBubble, Text_border, Text_background, TextEffect
from .track import Track_type, Base_track, Track

from .metadata import CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type, Font_type

class Script_material:
    """The materials section of a draft file."""

    audios: List[Audio_material]
    """Audio materials."""
    videos: List[Video_material]
    """Video materials."""
    stickers: List[Dict[str, Any]]
    """Sticker materials."""
    texts: List[Dict[str, Any]]
    """Text materials."""

    audio_effects: List[Audio_effect]
    """Audio effects."""
    audio_fades: List[Audio_fade]
    """Audio fades."""
    animations: List[Segment_animations]
    """Animation materials."""
    video_effects: List[Video_effect]
    """Video effects."""

    speeds: List[Speed]
    """Speed settings."""
    masks: List[Dict[str, Any]]
    """Masks."""
    transitions: List[Transition]
    """Transitions."""
    filters: List[Union[Filter, TextBubble]]
    """Filters, text effects and text bubbles; exported into `effects`."""
    canvases: List[BackgroundFilling]
    """Background fills."""

    def __init__(self):
        self.audios = []
        self.videos = []
        self.stickers = []
        self.texts = []

        self.audio_effects = []
        self.audio_fades = []
        self.animations = []
        self.video_effects = []

        self.speeds = []
        self.masks = []
        self.transitions = []
        self.filters = []
        self.canvases = []

    @overload
    def __contains__(self, item: Union[Video_material, Audio_material]) -> bool: ...
    @overload
    def __contains__(self, item: Union[Audio_fade, Audio_effect]) -> bool: ...
    @overload
    def __contains__(self, item: Union[Segment_animations, Video_effect, Transition, Filter]) -> bool: ...

    def __contains__(self, item) -> bool:
        if isinstance(item, Video_material):
            return item.material_id in [video.material_id for video in self.videos]
        elif isinstance(item, Audio_material):
            return item.material_id in [audio.material_id for audio in self.audios]
        elif isinstance(item, Audio_fade):
            return item.fade_id in [fade.fade_id for fade in self.audio_fades]
        elif isinstance(item, Audio_effect):
            return item.effect_id in [effect.effect_id for effect in self.audio_effects]
        elif isinstance(item, Segment_animations):
            return item.animation_id in [ani.animation_id for ani in self.animations]
        elif isinstance(item, Video_effect):
            return item.global_id in [effect.global_id for effect in self.video_effects]
        elif isinstance(item, Transition):
            return item.global_id in [transition.global_id for transition in self.transitions]
        elif isinstance(item, Filter):
            return item.global_id in [filter_.global_id for filter_ in self.filters]
        else:
            raise TypeError("Invalid argument type '%s'" % type(item))

    def export_json(self) -> Dict[str, List[Any]]:
        result = {
            "ai_translates": [],
            "audio_balances": [],
            "audio_effects": [effect.export_json() for effect in self.audio_effects],
            "audio_fades": [fade.export_json() for fade in self.audio_fades],
            "audio_track_indexes": [],
            "audios": [audio.export_json() for audio in self.audios],
            "beats": [],
            "canvases": [canvas.export_json() for canvas in self.canvases],
            "chromas": [],
            "color_curves": [],
            "digital_humans": [],
            "drafts": [],
            "effects": [_filter.export_json() for _filter in self.filters],
            "flowers": [],
            "green_screens": [],
            "handwrites": [],
            "hsl": [],
            "images": [],
            "log_color_wheels": [],
            "loudnesses": [],
            "manual_deformations": [],
            "material_animations": [ani.export_json() for ani in self.animations],
            "material_colors": [],
            "multi_language_refs": [],
            "placeholders": [],
            "plugin_effects": [],
            "primary_color_wheels": [],
            "realtime_denoises": [],
            "shapes": [],
            "smart_crops": [],
            "smart_relights": [],
            "sound_channel_mappings": [],
            "speeds": [spd.export_json() for spd in self.speeds],
            "stickers": self.stickers,
            "tail_leaders": [],
            "text_templates": [],
            "texts": self.texts,
            "time_marks": [],
            "transitions": [transition.export_json() for transition in self.transitions],
            "video_effects": [effect.export_json() for effect in self.video_effects],
            "video_trackings": [],
            "videos": [video.export_json() for video in self.videos],
            "vocal_beautifys": [],
            "vocal_separations": []
        }

        result["common_mask"] = self.masks

        return result

class Script_file:
    """A draft file. Most of the API lives here."""

    save_path: Optional[str]
    """Where the draft is saved; template mode only."""
    content: Dict[str, Any]
    """The draft contents."""

    width: int
    """Video width, in pixels."""
    height: int
    """Video height, in pixels."""
    fps: int
    """Frame rate."""
    duration: int
    """Total duration, in microseconds."""

    materials: Script_material
    """The materials section of a draft file."""
    tracks: Dict[str, Track]
    """Tracks."""

    imported_materials: Dict[str, List[Dict[str, Any]]]
    """Imported materials."""
    imported_tracks: List[Track]
    """Imported tracks."""

    TEMPLATE_FILE = "draft_content_template.json"

    def __init__(self, width: int, height: int, fps: int = 30):
        """Create a draft.

        Args:
            width (int): video width, in pixels
            height (int): video height, in pixels
            fps (int, optional): frame rate. Defaults to 30.
        """
        self.save_path = None

        self.width = width
        self.height = height
        self.fps = fps
        self.duration = 0

        self.materials = Script_material()
        self.tracks = {}

        self.imported_materials = {}
        self.imported_tracks = []

        with open(os.path.join(os.path.dirname(__file__), self.TEMPLATE_FILE), "r", encoding="utf-8") as f:
            self.content = json.load(f)

    @staticmethod
    def load_template(json_path: str) -> "Script_file":
        """Load a draft template from a JSON file.

        Args:
            json_path (str): path to the JSON file

        Raises:
            `FileNotFoundError`: the JSON file does not exist
        """
        obj = Script_file(**util.provide_ctor_defaults(Script_file))
        obj.save_path = json_path
        if not os.path.exists(json_path):
            raise FileNotFoundError("JSON file '%s' does not exist" % json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            obj.content = json.load(f)

        util.assign_attr_with_json(obj, ["fps", "duration"], obj.content)
        util.assign_attr_with_json(obj, ["width", "height"], obj.content["canvas_config"])

        obj.imported_materials = deepcopy(obj.content["materials"])
        obj.imported_tracks = [import_track(track_data, obj.imported_materials) for track_data in obj.content["tracks"]]

        return obj

    def add_material(self, material: Union[Video_material, Audio_material]) -> "Script_file":
        """Add a material to the draft."""
        if material in self.materials:  # already present
            return self
        if isinstance(material, Video_material):
            self.materials.videos.append(material)
        elif isinstance(material, Audio_material):
            self.materials.audios.append(material)
        else:
            raise TypeError("Unsupported material type: '%s'" % type(material))
        return self

    def add_track(self, track_type: Track_type, track_name: Optional[str] = None, *,
                  mute: bool = False,
                  relative_index: int = 0, absolute_index: Optional[int] = None) -> "Script_file":
        """Add a track of the given type and name, optionally at a specific layer.

        Note: segments on the main (bottom) video track must start at 0s, or the editor forces them to 0s.

        To avoid ambiguity, the name may only be omitted for the first track of a given type.

        Args:
            track_type (Track_type): the track type
            track_name (str, optional): the track name. May only be omitted for the first track of a type.
            mute (bool, optional): whether the track is muted. Not muted by default.
            relative_index (int, optional): layer position relative to tracks of the same type; higher is nearer the foreground. Default 0.
            absolute_index (int, optional): absolute layer position; higher is nearer the foreground. Overwrites each segment's `render_index` directly -- for experienced users.
                Cannot be combined with `relative_index`.

        Raises:
            `NameError`: a track of this type exists and no name was given, or that name is already taken
        """

        if track_name is None:
            if track_type in [track.track_type for track in self.tracks.values()]:
                raise NameError("A '%s' track already exists; give the new track a name to avoid ambiguity" % track_type)
            track_name = track_type.name
        if track_name in [track.name for track in self.tracks.values()]:
            print("A track named '%s' already exists" % track_name)
            return self

        render_index = track_type.value.render_index + relative_index
        if absolute_index is not None:
            render_index = absolute_index

        self.tracks[track_name] = Track(track_type, track_name, render_index, mute)
        return self

    def get_track(self, segment_type: Type[Base_segment], track_name: Optional[str]) -> Track:
        # A track name was given
        if track_name is not None:
            if track_name not in self.tracks:
                raise NameError("No track named '%s'" % track_name)
            return self.tracks[track_name]
        # Find the single track of this type
        count = sum([1 for track in self.tracks.values() if track.track_type == segment_type])
        if count == 0: raise exceptions.TrackNotFound(f"No track accepts '{segment_type}'")
        if count > 1: raise NameError(f"Several tracks accept '{segment_type}'; specify a track name")

        return next(track for track in self.tracks.values() if track.accept_segment_type == segment_type)

    def _get_track_and_imported_track(self, segment_type: Type[Base_segment], track_name: Optional[str]) -> List[Track]:
        """Every track of the given type, both ordinary and imported.

        Args:
            segment_type (Type[Base_segment]): the segment type
            track_name (Optional[str]): restrict the result to a track of this name

        Returns:
            List[Track]: the matching tracks

        Raises:
            NameError: a track name was given but no such track exists
        """
        result_tracks = []

        # A track name was given
        if track_name is not None:
            # Search the ordinary tracks
            if track_name in self.tracks:
                result_tracks.append(self.tracks[track_name])
            # Search the imported tracks
            for track in self.imported_tracks:
                if track.name == track_name:
                    result_tracks.append(track)
            if not result_tracks:
                raise NameError("No track named '%s'" % track_name)
        else:
            # Search the ordinary tracks for one accepting this segment type
            for track in self.tracks.values():
                if track.accept_segment_type == segment_type:
                    result_tracks.append(track)
            # Search the imported tracks for one accepting this segment type
            for track in self.imported_tracks:
                if track.accept_segment_type == segment_type:
                    result_tracks.append(track)
            if not result_tracks:
                raise NameError("No track accepts '%s'" % segment_type)
            if len(result_tracks) > 1:
                raise NameError("Several tracks accept '%s'; specify a track name" % segment_type)

        return result_tracks

    def add_segment(self, segment: Union[Video_segment, Sticker_segment, Audio_segment, Text_segment],
                    track_name: Optional[str] = None) -> "Script_file":
        """Add a segment to a track.

        Args:
            segment (`Video_segment`, `Sticker_segment`, `Audio_segment`, or `Text_segment`): the segment to add
            track_name (`str`, optional): the target track. May be omitted when only one track of this type exists.

        Raises:
            `NameError`: no track of that name, or `track_name` was required but omitted
            `TypeError`: the segment type does not match the track type
            `SegmentOverlap`: the new segment overlaps an existing one
        """
        tracks = self._get_track_and_imported_track(type(segment), track_name)
        target = tracks[0]

        # Add to the track and update the duration
        target.add_segment(segment)
        self.duration = max(self.duration, segment.end)

        # Register the associated materials
        if isinstance(segment, Video_segment):
            # Intro/outro animations
            if (segment.animations_instance is not None) and (segment.animations_instance not in self.materials):
                self.materials.animations.append(segment.animations_instance)
            # Effects
            for effect in segment.effects:
                if effect not in self.materials:
                    self.materials.video_effects.append(effect)
            # Filters
            for filter_ in segment.filters:
                if filter_ not in self.materials:
                    self.materials.filters.append(filter_)
            # Mask
            if segment.mask is not None:
                self.materials.masks.append(segment.mask.export_json())
            # Transition
            if (segment.transition is not None) and (segment.transition not in self.materials):
                self.materials.transitions.append(segment.transition)
            # Background fill
            if segment.background_filling is not None:
                self.materials.canvases.append(segment.background_filling)

            self.materials.speeds.append(segment.speed)
        elif isinstance(segment, Sticker_segment):
            self.materials.stickers.append(segment.export_material())
        elif isinstance(segment, Audio_segment):
            # Fade
            if (segment.fade is not None) and (segment.fade not in self.materials):
                self.materials.audio_fades.append(segment.fade)
            # Effects
            for effect in segment.effects:
                if effect not in self.materials:
                    self.materials.audio_effects.append(effect)
            self.materials.speeds.append(segment.speed)
        elif isinstance(segment, Text_segment):
            # Intro/outro animations
            if (segment.animations_instance is not None) and (segment.animations_instance not in self.materials):
                self.materials.animations.append(segment.animations_instance)
            # Text bubble
            if segment.bubble is not None:
                self.materials.filters.append(segment.bubble)
            # Text effect
            if segment.effect is not None:
                self.materials.filters.append(segment.effect)
            # Font style
            self.materials.texts.append(segment.export_material())

        # Register the segment material
        if isinstance(segment, (Video_segment, Audio_segment)):
            self.add_material(segment.material_instance)

        return self

    def add_effect(self, effect: Union[CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type],
                   t_range: Timerange, track_name: Optional[str] = None, *,
                   params: Optional[List[Optional[float]]] = None) -> "Script_file":
        """Add an effect segment to an effect track.

        Args:
            effect (`CapCut_Video_scene_effect_type` or `CapCut_Video_character_effect_type`): the effect type
            t_range (`Timerange`): the effect segment's time range
            track_name (`str`, optional): the target track. May be omitted when only one effect track exists.
            params (`List[Optional[float]]`, optional): effect parameters; omitted or None entries use the default.
                Values run 0-100, as in the editor. Which parameters an effect takes, and in what order, is given by the enum member's annotation.

        Raises:
            `NameError`: no track of that name, or `track_name` was required but omitted
            `TypeError`: the named track is not an effect track
            `ValueError`: the segment overlaps an existing one, too many parameters were given, or a value is out of range.
        """
        target = self.get_track(Effect_segment, track_name)

        # Add to the track and update the duration
        segment = Effect_segment(effect, t_range, params)
        target.add_segment(segment)
        self.duration = max(self.duration, t_range.start + t_range.duration)

        # Register the associated materials
        if segment.effect_inst not in self.materials:
            self.materials.video_effects.append(segment.effect_inst)
        return self

    def import_srt(self, srt_content: str, track_name: str, *,
                   time_offset: Union[str, float] = 0.0,
                   style_reference: Optional[Text_segment] = None,
                   font: Optional[str] = None,
                   text_style: Text_style = Text_style(size=5, align=1),
                   clip_settings: Optional[Clip_settings] = Clip_settings(transform_y=-0.8),
                   border: Optional[Text_border] = None,
                   background: Optional[Text_background] = None,
                   bubble: Optional[TextBubble] = None,
                   effect: Optional[TextEffect] = None) -> "Script_file":
        """Import subtitles from an SRT file, optionally taking a `Text_segment` as a style reference.

        Note: the reference segment's `clip_settings` are not used by default; pass `clip_settings=None` explicitly to adopt them.

        Args:
            srt_content (`str`): the SRT content, or a path to a local file
            track_name (`str`): the text track to import into; created if absent
            style_reference (`Text_segment`, optional): a text segment whose style is copied.
            font (`Optional[str]`, optional): the font. Defaults to None.
            time_offset (`Union[str, float]`, optional): shift every subtitle by this many microseconds. Default 0.
            text_style (`Text_style`, optional): subtitle style; defaults to the editor's own imported-subtitle style, and is overridden by `style_reference`.
            clip_settings (`Clip_settings`, optional): image adjustments; defaults to the editor's own imported-subtitle settings and overrides `style_reference` unless set to `None`.
            border (`Text_border`, optional): stroke settings; the reference's stroke is kept by default
            background (`Text_background`, optional): background settings; the reference's background is kept by default
            bubble (`TextBubble`, optional): a text bubble; none is added by default
            effect (`TextEffect`, optional): a text effect; none is added by default

        Raises:
            `NameError`: a track of that name already exists
            `TypeError`: the track type does not match
        """
        if style_reference is None and clip_settings is None:
            raise ValueError("Provide `clip_settings` when no style reference is given")

        # Must exist even when no font was requested: the nested __add_text_segment below
        # references it unconditionally, so leaving it unbound made import_srt raise
        # NameError for the default font=None.
        font_type = None
        if font:
            try:
                font_type = getattr(Font_type, font)
            except AttributeError:
                available_fonts = [attr for attr in dir(Font_type) if not attr.startswith('_')]
                raise ValueError(f"Unsupported font: {font}, please use one of the fonts in Font_type: {available_fonts}")

        time_offset = tim(time_offset)
        # Is track_name already in self.tracks or self.imported_tracks?
        track_exists = (track_name in self.tracks) or any(track.name == track_name for track in self.imported_tracks)
        if not track_exists:
            self.add_track(Track_type.text, track_name, relative_index=999)  # above every other text track

        # A local file path rather than inline content
        if os.path.exists(srt_content):
            with open(srt_content, "r", encoding="utf-8-sig") as srt_file:
                lines = srt_file.readlines()
        else:
            # Split the content into lines
            lines = srt_content.splitlines()

        def __add_text_segment(text: str, t_range: Timerange) -> None:
            fixed_width = -1
            if self.width < self.height:  # portrait
                fixed_width = int(1080 * 0.6)
            else:  # landscape
                fixed_width = int(1920 * 0.7)

            if style_reference:
                seg = Text_segment.create_from_template(text, t_range, style_reference)
                if clip_settings is not None:
                    seg.clip_settings = deepcopy(clip_settings)
                # Copy the other optional attributes
                if border:
                    seg.border = deepcopy(border)
                if background:
                    seg.background = deepcopy(background)
                if bubble:
                    seg.bubble = deepcopy(bubble)
                if effect:
                    seg.effect = deepcopy(effect)
                # Fixed width
                seg.fixed_width = fixed_width
                # Font
                if font_type:
                    seg.font = font_type.value
            else:
                seg = Text_segment(text, t_range, style=text_style, clip_settings=clip_settings,
                                   border=border, background=background,
                                   font=font_type,
                                   fixed_width=fixed_width)
                # Add the bubble and text effect
                if bubble:
                    seg.bubble = deepcopy(bubble)
                if effect:
                    seg.effect = deepcopy(effect)
            # A bubble or text effect must also be registered as a material
            if bubble:
                self.materials.filters.append(bubble)
            if effect:
                self.materials.filters.append(effect)
            self.add_segment(seg, track_name)

        index = 0
        text: str = ""
        text_trange: Timerange
        read_state: Literal["index", "timestamp", "content"] = "index"
        while index < len(lines):
            line = lines[index].strip()
            if read_state == "index":
                if len(line) == 0:
                    index += 1
                    continue
                if not line.isdigit():
                    raise ValueError("Expected a number at line %d, got '%s'" % (index + 1, line))
                index += 1
                read_state = "timestamp"
            elif read_state == "timestamp":
                # Read the timestamp
                start_str, end_str = line.split(" --> ")
                start, end = srt_tstamp(start_str), srt_tstamp(end_str)
                text_trange = Timerange(start + time_offset, end - start)

                index += 1
                read_state = "content"
            elif read_state == "content":
                # End of the cue; build the segment
                if len(line) == 0:
                    __add_text_segment(text.strip(), text_trange)

                    text = ""
                    read_state = "index"
                else:
                    text += line + "\n"
                index += 1

        # Add the final segment
        if len(text) > 0:
            __add_text_segment(text.strip(), text_trange)

        return self

    def get_imported_track(self, track_type: Literal[Track_type.video, Track_type.audio, Track_type.text],
                           name: Optional[str] = None, index: Optional[int] = None) -> Track:
        """Get an imported track of the given type, so material on it can be replaced.

        Filtering by track name is preferred where the name is known.

        Args:
            track_type (`Track_type.video`, `Track_type.audio` or `Track_type.text`): the track type; only audio, video and text are supported
            name (`str`, optional): filter by track name; omitted, no name filter is applied.
            index (`int`, optional): index among **imported tracks of the same type**, 0 being the bottom. Omitted, no index filter is applied.

        Raises:
            `TrackNotFound`: no track matched
            `AmbiguousTrack`: more than one track matched
        """
        tracks_of_same_type: List[Track] = []
        for track in self.imported_tracks:
            if track.track_type == track_type:
                assert isinstance(track, Track)
                tracks_of_same_type.append(track)

        ret: List[Track] = []
        for ind, track in enumerate(tracks_of_same_type):
            if (name is not None) and (track.name != name): continue
            if (index is not None) and (ind != index): continue
            ret.append(track)

        if len(ret) == 0:
            raise exceptions.TrackNotFound(
                "No track matched: track_type=%s, name=%s, index=%s" % (track_type, name, index))
        if len(ret) > 1:
            raise exceptions.AmbiguousTrack(
                "More than one track matched: track_type=%s, name=%s, index=%s" % (track_type, name, index))

        return ret[0]

    def import_track(self, source_file: "Script_file", track: EditableTrack, *,
                     offset: Union[str, int] = 0,
                     new_name: Optional[str] = None, relative_index: Optional[int] = None) -> "Script_file":
        """Import an `Editable_track` into this `Script_file`, for instance pulling a text or video track out of a template draft.

        Note: segment and material ids are preserved, so the same track cannot be imported twice into one draft.

        Args:
            source_file (`Script_file`): the file holding the track to import
            track (`EditableTrack`): the track to import, obtained from `get_imported_track`.
            offset (`str | int`, optional): time offset in microseconds, as an integer or a time string such as "1s". No offset by default.
            new_name (`str`, optional): the new track name; the source name is used by default.
            relative_index (`int`, optional): adjusts the imported track's render layer. The original layer is kept by default.
        """
        # Copy the original track structure, adjusting the render layer if asked
        imported_track = deepcopy(track)
        if relative_index is not None:
            imported_track.render_index = track.track_type.value.render_index + relative_index
        if new_name is not None:
            imported_track.name = new_name

        # Apply the offset
        offset_us = tim(offset)
        if offset_us != 0:
            for seg in imported_track.segments:
                seg.target_timerange.start = max(0, seg.target_timerange.start + offset_us)
        self.imported_tracks.append(imported_track)

        # Collect every material id that must be copied
        material_ids = set()
        segments: List[Dict[str, Any]] = track.raw_data.get("segments", [])
        for segment in segments:
            # Primary material id
            material_id = segment.get("material_id")
            if material_id:
                material_ids.add(material_id)

            # Material ids from extra_material_refs
            extra_refs: List[str] = segment.get("extra_material_refs", [])
            material_ids.update(extra_refs)

        # Copy the materials
        for material_type, material_list in source_file.imported_materials.items():
            for material in material_list:
                if material.get("id") in material_ids:
                    self.imported_materials[material_type].append(deepcopy(material))
                    material_ids.remove(material.get("id"))

        assert len(material_ids) == 0, "Materials not found: %s" % material_ids

        # Update the total duration
        self.duration = max(self.duration, track.end_time)

        return self

    def replace_material_by_name(self, material_name: str, material: Union[Video_material, Audio_material],
                                 replace_crop: bool = False) -> "Script_file":
        """Replace the named material everywhere it is referenced.

        Segment durations and `source_timerange` are left unchanged, which suits image materials particularly well.

        Args:
            material_name (`str`): the material to replace
            material (`Video_material` or `Audio_material`): the replacement; only video and audio are supported
            replace_crop (`bool`, optional): replace the original crop settings. Default False; video materials only.

        Raises:
            `MaterialNotFound`: no material of the same type has that name
            `AmbiguousMaterial`: several materials of the same type share that name
        """
        video_mode = isinstance(material, Video_material)
        # Find the material
        target_json_obj: Optional[Dict[str, Any]] = None
        target_material_list = self.imported_materials["videos" if video_mode else "audios"]
        name_key = "material_name" if video_mode else "name"
        for mat in target_material_list:
            if mat[name_key] == material_name:
                if target_json_obj is not None:
                    raise exceptions.AmbiguousMaterial(
                        "Several materials named '%s' of type '%s'" % (material_name, type(material)))
                target_json_obj = mat
        if target_json_obj is None:
            raise exceptions.MaterialNotFound("No material named '%s' of type '%s'" % (material_name, type(material)))

        # Update the material
        target_json_obj.update({name_key: material.material_name, "path": material.path, "duration": material.duration})
        if video_mode:
            target_json_obj.update({"width": material.width, "height": material.height, "material_type": material.material_type})
            if replace_crop:
                target_json_obj.update({"crop": material.crop_settings.export_json()})

        return self

    def replace_material_by_seg(self, track: EditableTrack, segment_index: int, material: Union[Video_material, Audio_material],
                                source_timerange: Optional[Timerange] = None, *,
                                handle_shrink: Shrink_mode = Shrink_mode.cut_tail,
                                handle_extend: Union[Extend_mode, List[Extend_mode]] = Extend_mode.cut_material_tail) -> "Script_file":
        """Replace the material of one segment on an audio or video track. Segments with a speed change are not yet supported.

        Args:
            track (`Editable_track`): the track, obtained from `get_imported_track`
            segment_index (`int`): index of the segment, starting at 0
            material (`Video_material` or `Audio_material`): the replacement, which must match the original type
            source_timerange (`Timerange`, optional): the portion of the new material to use. Defaults to the whole of it, or to the original segment length for images.
            handle_shrink (`Shrink_mode`, optional): what to do when the replacement is shorter. Defaults to trimming the tail so the segment matches the material.
            handle_extend (`Extend_mode` or `List[Extend_mode]`, optional): what to do when the replacement is longer; each is tried in turn until one succeeds or all fail.
                Defaults to trimming the material's tail so the segment keeps its length.

        Raises:
            `IndexError`: `segment_index` is out of range
            `TypeError`: the track or material type is wrong
            `ExtensionFailed`: the longer replacement could not be accommodated
        """
        if not isinstance(track, ImportedMediaTrack):
            raise TypeError("Material replacement is not supported on a %s track" % track.track_type)
        if not 0 <= segment_index < len(track):
            raise IndexError("Segment index %d is outside [0, %d)" % (segment_index, len(track)))
        if not track.check_material_type(material):
            raise TypeError("Material type %s does not match track type %s", (type(material), track.track_type))
        seg = track.segments[segment_index]

        if isinstance(handle_extend, Extend_mode):
            handle_extend = [handle_extend]
        if source_timerange is None:
            if isinstance(material, Video_material) and (material.material_type == "photo"):
                source_timerange = Timerange(0, seg.duration)
            else:
                source_timerange = Timerange(0, material.duration)

        # Apply the duration change
        track.process_timerange(segment_index, source_timerange, handle_shrink, handle_extend)

        # Finally, relink the material
        track.segments[segment_index].material_id = material.material_id
        self.add_material(material)

        # TODO: update the total duration
        return self

    def replace_text(self, track: EditableTrack, segment_index: int, text: Union[str, List[str]],
                     recalc_style: bool = True) -> "Script_file":
        """Replace the text of one segment on a text track. Plain text segments and text templates are both supported.

        Args:
            track (`Editable_track`): the text track, obtained from `get_imported_track`
            segment_index (`int`): index of the segment, starting at 0
            text (`str` or `List[str]`): the new text; a list of strings for text templates.
            recalc_style (`bool`): recompute how the font styles are distributed, keeping each style's share of the text roughly as it was. Enabled by default.

        Raises:
            `IndexError`: `segment_index` is out of range
            `TypeError`: the track type is wrong
            `ValueError`: the number of strings does not match the text template
        """
        if not isinstance(track, ImportedTextTrack):
            raise TypeError("Text replacement is not supported on a %s track" % track.track_type)
        if not 0 <= segment_index < len(track):
            raise IndexError("Segment index %d is outside [0, %d)" % (segment_index, len(track)))

        def __recalc_style_range(old_len: int, new_len: int, styles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Redistribute the font styles."""
            new_styles: List[Dict[str, Any]] = []
            for style in styles:
                start = math.ceil(style["range"][0] / old_len * new_len)
                end = math.ceil(style["range"][1] / old_len * new_len)
                style["range"] = [start, end]
                if start != end:
                    new_styles.append(style)
            return new_styles

        replaced: bool = False
        material_id: str = track.segments[segment_index].material_id
        # Try replacing in the text materials
        for mat in self.imported_materials["texts"]:
            if mat["id"] != material_id:
                continue

            if isinstance(text, list):
                if len(text) != 1:
                    raise ValueError(f"A plain text segment holds a single string, but the replacement was {text}")
                text = text[0]

            content = json.loads(mat["content"])
            if recalc_style:
                content["styles"] = __recalc_style_range(len(content["text"]), len(text), content["styles"])
            content["text"] = text
            mat["content"] = json.dumps(content, ensure_ascii=False)
            replaced = True
            break
        if replaced:
            return self

        # Try replacing in the text templates
        for template in self.imported_materials["text_templates"]:
            if template["id"] != material_id:
                continue

            resources = template["text_info_resources"]
            if isinstance(text, str):
                text = [text]
            if len(text) > len(resources):
                raise ValueError(
                    f"Text template '{template['name']}' has {len(resources)} text slots, but {len(text)} replacements were given")

            for sub_material_id, new_text in zip(map(lambda x: x["text_material_id"], resources), text):
                for mat in self.imported_materials["texts"]:
                    if mat["id"] != sub_material_id:
                        continue

                    if isinstance(mat["content"], str):
                        mat["content"] = new_text
                    else:
                        content = json.loads(mat["content"])
                        if recalc_style:
                            content["styles"] = __recalc_style_range(len(content["text"]), len(new_text), content["styles"])
                        content["text"] = new_text
                        mat["content"] = json.dumps(content, ensure_ascii=False)
                    break
            replaced = True
            break

        assert replaced, f"No material found for the segment: {material_id}"

        return self

    def inspect_material(self) -> None:
        """Print the metadata of the imported sticker, text bubble and text effect materials."""
        print("Sticker materials:")
        for sticker in self.imported_materials["stickers"]:
            print("\tResource id: %s '%s'" % (sticker["resource_id"], sticker.get("name", "")))

        print("Text bubbles:")
        for effect in self.imported_materials["effects"]:
            if effect["type"] == "text_shape":
                print("\tEffect id: %s ,Resource id: %s '%s'" %
                      (effect["effect_id"], effect["resource_id"], effect.get("name", "")))

        print("Text effects:")
        for effect in self.imported_materials["effects"]:
            if effect["type"] == "text_effect":
                print("\tResource id: %s '%s'" % (effect["resource_id"], effect.get("name", "")))

    def dumps(self) -> str:
        """Export the draft contents as a JSON string."""
        self.content["fps"] = self.fps
        self.content["duration"] = self.duration
        self.content["canvas_config"] = {"width": self.width, "height": self.height, "ratio": "original"}
        self.content["materials"] = self.materials.export_json()

        self.content["last_modified_platform"] = {
            "app_id": 359289,
            "app_source": "cc",
            "app_version": "6.5.0",
            "device_id": "c4ca4238a0b923820dcc509a6f75849b",
            "hard_disk_id": "307563e0192a94465c0e927fbc482942",
            "mac_address": "c3371f2d4fb02791c067ce44d8fb4ed5",
            "os": "mac",
            "os_version": "15.5"
        }

        self.content["platform"] = {
            "app_id": 359289,
            "app_source": "cc",
            "app_version": "6.5.0",
            "device_id": "c4ca4238a0b923820dcc509a6f75849b",
            "hard_disk_id": "307563e0192a94465c0e927fbc482942",
            "mac_address": "c3371f2d4fb02791c067ce44d8fb4ed5",
            "os": "mac",
            "os_version": "15.5"
        }

        # Merge the imported materials
        for material_type, material_list in self.imported_materials.items():
            if material_type not in self.content["materials"]:
                self.content["materials"][material_type] = material_list
            else:
                self.content["materials"][material_type].extend(material_list)

        # Sort the tracks and export
        track_list: List[Base_track] = list(self.tracks.values())
        track_list.extend(self.imported_tracks)
        track_list.sort(key=lambda track: track.render_index)
        self.content["tracks"] = [track.export_json() for track in track_list]

        return json.dumps(self.content, ensure_ascii=False, indent=4)

    def dump(self, file_path: str) -> None:
        """Write the draft contents to a file."""
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.dumps())

    def save(self) -> None:
        """Save the draft back to the path it was opened from. Template mode only.

        Raises:
            `ValueError`: not in template mode
        """
        if self.save_path is None:
            raise ValueError("No save path is set; this draft is probably not in template mode")
        self.dump(self.save_path)
