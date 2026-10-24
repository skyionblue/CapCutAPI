"""Text segments and their related types."""

import json
import uuid
from copy import deepcopy

from typing import Dict, Tuple, Any, List
from typing import Union, Optional, Literal

from pyJianYingDraft.metadata.capcut_text_animation_meta import CapCut_Text_intro, CapCut_Text_outro, CapCut_Text_loop_anim

from .time_util import Timerange, tim
from .segment import Clip_settings, Visual_segment
from .animation import Segment_animations, Text_animation

from .metadata import Font_type, Effect_meta

class Text_style:
    """Font style."""

    size: float
    """Font size."""

    bold: bool
    """Whether the text is bold."""
    italic: bool
    """Whether the text is italic."""
    underline: bool
    """Whether the text is underlined."""

    color: Tuple[float, float, float]
    """Font colour as an RGB triple, each 0-1."""
    alpha: float
    """Font opacity."""

    align: Literal[0, 1, 2]
    """Alignment."""
    vertical: bool
    """Whether the text is set vertically."""

    letter_spacing: int
    """Letter spacing."""
    line_spacing: int
    """Line spacing."""

    def __init__(self, *, size: float = 8.0, bold: bool = False, italic: bool = False, underline: bool = False,
                 color: Tuple[float, float, float] = (1.0, 1.0, 1.0), alpha: float = 1.0,
                 align: Literal[0, 1, 2] = 0, vertical: bool = False,
                 letter_spacing: int = 0, line_spacing: int = 0):
        """
        Args:
            size (`float`, optional): font size. Default 8.0
            bold (`bool`, optional): bold text. Default False
            italic (`bool`, optional): italic text. Default False
            underline (`bool`, optional): underlined text. Default False
            color (`Tuple[float, float, float]`, optional): font colour as an RGB triple, each 0-1. Default white
            alpha (`float`, optional): font opacity, 0-1. Fully opaque by default
            align (`int`, optional): 0 left, 1 centre, 2 right. Default left
            vertical (`bool`, optional): set the text vertically. Default False
            letter_spacing (`int`, optional): letter spacing, defined as in the editor. Default 0
            line_spacing (`int`, optional): line spacing, defined as in the editor. Default 0
        """
        self.size = size
        self.bold = bold
        self.italic = italic
        self.underline = underline

        self.color = color
        self.alpha = alpha

        self.align = align
        self.vertical = vertical

        self.letter_spacing = letter_spacing
        self.line_spacing = line_spacing

class Text_border:
    """Text stroke settings."""

    alpha: float
    """Stroke opacity."""
    color: Tuple[float, float, float]
    """Stroke colour as an RGB triple, each 0-1."""
    width: float
    """Stroke width."""

    def __init__(self, *, alpha: float = 1.0, color: Tuple[float, float, float] = (0.0, 0.0, 0.0), width: float = 40.0):
        """
        Args:
            alpha (`float`, optional): stroke opacity, 0-1. Default 1.0
            color (`Tuple[float, float, float]`, optional): stroke colour as an RGB triple, each 0-1. Default black
            width (`float`, optional): stroke width as in the editor, 0-100. Default 40.0
        """
        self.alpha = alpha
        self.color = color
        self.width = width / 100.0 * 0.2  # this mapping may not be exactly right

    def export_json(self) -> Dict[str, Any]:
        """Export the JSON, placed in the material content's `styles`."""
        return {
            "content": {
                "solid": {
                    "alpha": self.alpha,
                    "color": list(self.color),
                }
            },
            "width": self.width
        }

class Text_background:
    """Text background settings."""

    style: Literal[0, 2]
    """Background style."""

    alpha: float
    """Background opacity."""
    color: str
    """Background colour, in '#RRGGBB' form."""
    round_radius: float
    """Background corner radius."""
    height: float
    """Background height."""
    width: float
    """Background width."""
    horizontal_offset: float
    """Background horizontal offset."""
    vertical_offset: float
    """Background vertical offset."""

    def __init__(self, *, color: str, style: Literal[1, 2] = 1, alpha: float = 1.0, round_radius: float = 0.0,
                 height: float = 0.14, width: float = 0.14,
                 horizontal_offset: float = 0.5, vertical_offset: float = 0.5):
        """
        Args:
            color (`str`): background colour, in '#RRGGBB' form
            style (`int`, optional): background style; 1 and 2 match the editor's two styles. Default 1
            alpha (`float`, optional): background opacity as in the editor, 0-1. Default 1.0
            round_radius (`float`, optional): background corner radius as in the editor, 0-1. Default 0.0
            height (`float`, optional): background height as in the editor, 0-1. Default 0.14
            width (`float`, optional): background width as in the editor, 0-1. Default 0.14
            horizontal_offset (`float`, optional): background horizontal offset as in the editor, 0-1. Default 0.5
            vertical_offset (`float`, optional): background vertical offset as in the editor, 0-1. Default 0.5
        """
        self.style = (0, 2)[style - 1]

        self.alpha = alpha
        self.color = color
        self.round_radius = round_radius
        self.height = height
        self.width = width
        self.horizontal_offset = horizontal_offset * 2 - 1
        self.vertical_offset = vertical_offset * 2 - 1

    def export_json(self) -> Dict[str, Any]:
        """Build the JSON fragment merged in when a Text_segment is exported."""
        return {
            "background_style": self.style,
            "background_color": self.color,
            "background_alpha": self.alpha,
            "background_round_radius": self.round_radius,
            "background_height": self.height,
            "background_width": self.width,
            "background_horizontal_offset": self.horizontal_offset,
            "background_vertical_offset": self.vertical_offset,
        }

class Text_shadow:
    """Text shadow settings."""

    has_shadow: bool
    """Whether the shadow is enabled."""
    alpha: float
    """Shadow opacity."""
    angle: float
    """Shadow angle."""
    color: str
    """Shadow colour, in '#RRGGBB' form."""
    distance: float
    """Shadow distance."""
    smoothing: float
    """Shadow smoothing."""

    def __init__(self, *, has_shadow: bool = False, alpha: float = 0.9, angle: float = -45.0,
                 color: str = "#000000", distance: float = 5.0, smoothing: float = 0.45):
        """
        Args:
            has_shadow (`bool`, optional): enable the shadow. Default False
            alpha (`float`, optional): shadow opacity, 0-1. Default 0.9
            angle (`float`, optional): shadow angle, -180 to 180. Default -45.0
            color (`str`, optional): shadow colour in '#RRGGBB' form. Default black
            distance (`float`, optional): shadow distance. Default 5.0
            smoothing (`float`, optional): shadow smoothing, 0-1. Default 0.15
        """
        self.has_shadow = has_shadow
        self.alpha = alpha
        self.angle = angle
        self.color = color
        self.distance = distance
        self.smoothing = smoothing

    def export_json(self) -> Dict[str, Any]:
        """Build the JSON fragment merged in when a Text_segment is exported."""
        return {
            "has_shadow": self.has_shadow,
            "shadow_alpha": self.alpha,
            "shadow_angle": self.angle,
            "shadow_color": self.color,
            "shadow_distance": self.distance,
            "shadow_smoothing": self.smoothing * 3
        }

class TextBubble:
    """A text bubble material, structurally the same as a filter material."""

    global_id: str
    """Global bubble id, generated automatically."""

    effect_id: str
    resource_id: str

    def __init__(self, effect_id: str, resource_id: str):
        self.global_id = uuid.uuid4().hex
        self.effect_id = effect_id
        self.resource_id = resource_id

    def export_json(self) -> Dict[str, Any]:
        return {
            "apply_target_type": 0,
            "effect_id": self.effect_id,
            "id": self.global_id,
            "resource_id": self.resource_id,
            "type": "text_shape",
            "value": 1.0,
            # path and request_id are deliberately not exported
        }

class TextEffect(TextBubble):
    """A text effect material, also structurally the same as a filter material."""

    def export_json(self) -> Dict[str, Any]:
        ret = super().export_json()
        ret["type"] = "text_effect"
        ret["source_platform"] = 1
        return ret

class TextStyleRange:
    """A style applied to one range of the text."""

    start: int
    """Start position, inclusive."""
    end: int
    """End position, exclusive."""
    style: Text_style
    """Font style."""
    border: Optional[Text_border]
    """Stroke settings; None means no stroke."""
    font: Optional[Effect_meta]
    """Font; None means the global font is used."""

    def __init__(self, start: int, end: int, style: Text_style, border: Optional[Text_border] = None, font_str: str = None):
        """Create a styled text range.

        Args:
            start (`int`): start position, inclusive
            end (`int`): end position, exclusive
            style (`Text_style`): the font style
            border (`Text_border`, optional): stroke settings. Default None, meaning no stroke
            font (optional): the font. Default None, meaning the global font
        """
        self.start = start
        self.end = end
        self.style = style
        self.border = border
        if font_str:
            try:
                font_type = getattr(Font_type, font_str).value
            except AttributeError:
                available_fonts = [attr for attr in dir(Font_type) if not attr.startswith('_')]
                raise ValueError(f"Unsupported font: {font_str}. Use one of the fonts in Font_type: {available_fonts}")
            self.font = font_type

    def get_range(self) -> List[int]:
        """The range as a list.

        Returns:
            `List[int]`: the range as [start, end]
        """
        return [self.start, self.end]

class Text_segment(Visual_segment):
    """A text segment. Only basic font styling is supported so far."""

    text: str
    """The text."""
    font: Optional[Effect_meta]
    """Font type."""
    style: Text_style
    """Font style."""

    border: Optional[Text_border]
    """Stroke settings; None means no stroke."""
    background: Optional[Text_background]
    """Background settings; None means no background."""

    shadow: Optional[Text_shadow]
    """Shadow settings; None means no shadow."""

    bubble: Optional[TextBubble]
    """Text bubble; registered as a material when placed on a track."""
    effect: Optional[TextEffect]
    """Text effect; registered as a material when placed on a track. Only some effects are supported."""

    fixed_width: float
    """Fixed width; -1 means unconstrained."""
    fixed_height: float
    """Fixed height; -1 means unconstrained."""

    text_styles: List[TextStyleRange]
    """The per-range text styles."""

    wrap_lines: bool
    """Whether CapCut may break the text across lines to keep it inside the frame.

    Serialised as `force_apply_line_max_width`, which applies `line_max_width` (0.82 of the
    frame) when no `fixed_width` constrains the text.
    """

    def __init__(self, text: str, timerange: Timerange, *,
                 font: Optional[Font_type] = None,
                 style: Optional[Text_style] = None, clip_settings: Optional[Clip_settings] = None,
                 border: Optional[Text_border] = None, background: Optional[Text_background] = None,
                 shadow: Optional[Text_shadow] = None,
                 fixed_width: int = -1, fixed_height: int = -1,
                 wrap_lines: bool = True):
        """Create a text segment with its timing, font style and image adjustments.

        Once created, add it to a track with `Script_file.add_segment`.

        Args:
            text (`str`): the text
            timerange (`Timerange`): the segment's time range on the track
            font (`Font_type`, optional): the font. Defaults to the system font
            style (`Text_style`, optional): font style, covering size, colour, alignment, opacity and so on.
            clip_settings (`Clip_settings`, optional): image adjustments; nothing is transformed by default
            border (`Text_border`, optional): stroke settings; no stroke by default
            background (`Text_background`, optional): background settings; no background by default
            fixed_width (`int`, optional): fixed width in pixels. Default -1, unconstrained
            fixed_height (`int`, optional): fixed height in pixels. Default -1, unconstrained
            wrap_lines (`bool`, optional): let CapCut break the text across lines to keep it
                inside the frame instead of running off both edges. Defaults to True.

                Measured against CapCut: with `fixed_width` set this changes nothing -- the
                width already forces the break. With `fixed_width` unset, which is what
                `add_text` produces, turning it off clips the text at the frame edges. So the
                only case it affects is the one where it is needed. Pass False for text that
                is meant to overflow.
        """
        super().__init__(uuid.uuid4().hex, None, timerange, 1.0, 1.0, clip_settings=clip_settings)

        self.text = text
        self.font = font.value if font else None
        self.style = style or Text_style()
        self.border = border
        self.background = background
        self.shadow = shadow

        self.bubble = None
        self.effect = None

        self.fixed_width = fixed_width
        self.fixed_height = fixed_height
        self.wrap_lines = wrap_lines
        self.text_styles = []

    # Set the style for a particular range of the text
    def add_text_style(self, textStyleRange: TextStyleRange) -> "Text_segment":
        # Add the new style range
        self.text_styles.append(textStyleRange)
        return self


    @classmethod
    def create_from_template(cls, text: str, timerange: Timerange, template: "Text_segment") -> "Text_segment":
        """Create a text segment from a template, with the given text."""
        new_segment = cls(text, timerange, style=deepcopy(template.style), clip_settings=deepcopy(template.clip_settings),
                          border=deepcopy(template.border), background=deepcopy(template.background))
        new_segment.font = deepcopy(template.font)

        # Animations and so on
        if template.animations_instance:
            new_segment.animations_instance = deepcopy(template.animations_instance)
            new_segment.animations_instance.animation_id = uuid.uuid4().hex
            new_segment.extra_material_refs.append(new_segment.animations_instance.animation_id)
        if template.bubble:
            new_segment.add_bubble(template.bubble.effect_id, template.bubble.resource_id)
        if template.effect:
            new_segment.add_effect(template.effect.effect_id)

        return new_segment

    def add_animation(self, animation_type: Union[CapCut_Text_intro, CapCut_Text_outro, CapCut_Text_loop_anim],
                      duration: Union[str, float] = 500000) -> "Text_segment":
        """Add an intro, outro or loop animation. Intro and outro durations may be set; a loop animation fills whatever time is left.

        Note: to combine a loop animation with intro/outro animations, **add the intro and outro first**.

        Args:
            animation_type (`CapCut_Text_intro`, `CapCut_Text_outro` or `CapCut_Text_loop_anim`): the text animation type.
            duration (`str` or `float`, optional): animation duration in microseconds; intro and outro animations only.
                Strings are parsed with `tim()`. Default 0.5 seconds
        """
        duration = min(tim(duration), self.target_timerange.duration)

        if isinstance(animation_type, CapCut_Text_intro):
            start = 0
        elif isinstance(animation_type, CapCut_Text_outro):
            start = self.target_timerange.duration - duration
        elif isinstance(animation_type, CapCut_Text_loop_anim):
            intro_trange = self.animations_instance and self.animations_instance.get_animation_trange("in")
            outro_trange = self.animations_instance and self.animations_instance.get_animation_trange("out")
            start = intro_trange.start if intro_trange else 0
            duration = self.target_timerange.duration - start - (outro_trange.duration if outro_trange else 0)
        else:
            raise TypeError("Invalid animation type %s" % type(animation_type))

        if self.animations_instance is None:
            self.animations_instance = Segment_animations()
            self.extra_material_refs.append(self.animations_instance.animation_id)

        self.animations_instance.add_animation(Text_animation(animation_type, start, duration))

        return self

    def add_bubble(self, effect_id: str, resource_id: str) -> "Text_segment":
        """Add a text bubble. The material details come from `Script_file.inspect_material` on a template.

        Args:
            effect_id (`str`): the bubble's effect_id
            resource_id (`str`): the bubble's resource_id
        """
        self.bubble = TextBubble(effect_id, resource_id)
        self.extra_material_refs.append(self.bubble.global_id)
        return self

    def add_effect(self, effect_id: str) -> "Text_segment":
        """Add a text effect. The material details come from `Script_file.inspect_material` on a template.

        Args:
            effect_id (`str`): the text effect's effect_id, which doubles as its resource_id
        """
        self.effect = TextEffect(effect_id, effect_id)
        self.extra_material_refs.append(self.effect.global_id)
        return self

    def export_material(self) -> Dict[str, Any]:
        """The material for this text segment, avoiding a separate Text_material class."""
        # Accumulate the effect flags
        check_flag: int = 7
        if self.border:
            check_flag |= 8
        if self.background:
            check_flag |= 16
        if self.shadow and self.shadow.has_shadow:
            check_flag |= 32  # shadow flag

        # Build the styles array
        styles = []

        if self.text_styles:
            # Sort the style ranges
            sorted_styles = sorted(self.text_styles, key=lambda x: x.start)

            # A default style may be needed before the first range
            if sorted_styles[0].start > 0:
                # Default style from 0 to the first styled range
                default_style = {
                    "fill": {
                        "alpha": 1.0,
                        "content": {
                            "render_type": "solid",
                            "solid": {
                                "alpha": self.style.alpha,
                                "color": list(self.style.color)
                            }
                        }
                    },
                    "range": [0, sorted_styles[0].start],
                    "size": self.style.size,
                    "bold": self.style.bold,
                    "italic": self.style.italic,
                    "underline": self.style.underline,
                    "strokes": [self.border.export_json()] if self.border else []
                }

                # Add the shadow to the style
                if self.shadow and self.shadow.has_shadow:
                    default_style["shadows"] = [
                        {
                            "diffuse": self.shadow.smoothing / 6,  # diffuse = smoothing/6
                            "angle": self.shadow.angle,
                            "content": {
                                "solid": {
                                    "color": [int(self.shadow.color[1:3], 16) / 255,
                                              int(self.shadow.color[3:5], 16) / 255,
                                              int(self.shadow.color[5:7], 16) / 255]
                                }
                            },
                            "distance": self.shadow.distance,
                            "alpha": self.shadow.alpha
                        }
                    ]

                # Add the global font to the style
                if self.font:
                    default_style["font"] = {
                        "id": self.font.resource_id,
                        "path": "C:/%s.ttf" % self.font.name
                    }

                # Add the text effect to the style
                if self.effect:
                    default_style["effectStyle"] = {
                        "id": self.effect.effect_id,
                        "path": "C:"  # nothing is actually stored at this path
                    }

                styles.append(default_style)

            # Each style range
            for i, style_range in enumerate(sorted_styles):
                # Style for the current range
                style_item = {
                    "fill": {
                        "alpha": 1.0,
                        "content": {
                            "render_type": "solid",
                            "solid": {
                                "alpha": style_range.style.alpha,
                                "color": list(style_range.style.color)
                            }
                        }
                    },
                    "range": style_range.get_range(),
                    "size": style_range.style.size,
                    "bold": style_range.style.bold,
                    "italic": style_range.style.italic,
                    "underline": style_range.style.underline,
                    "strokes": [style_range.border.export_json()] if style_range.border else []
                }

                # A range-level font takes precedence
                if hasattr(style_range, 'font') and style_range.font:
                    style_item["font"] = {
                        "id": style_range.font.resource_id,
                        "path": "C:/%s.ttf" % style_range.font.name
                    }
                # Otherwise fall back to the global font
                elif self.font:
                    style_item["font"] = {
                        "id": self.font.resource_id,
                        "path": "C:/%s.ttf" % self.font.name
                    }

                # Add the text effect to the style
                if self.effect:
                    style_item["effectStyle"] = {
                        "id": self.effect.effect_id,
                        "path": "C:"  # nothing is actually stored at this path
                    }

                styles.append(style_item)

                # A default style may be needed between this range and the next
                if i < len(sorted_styles) - 1 and style_range.end < sorted_styles[i + 1].start:
                    # Default style between the two ranges
                    gap_style = {
                        "fill": {
                            "alpha": 1.0,
                            "content": {
                                "render_type": "solid",
                                "solid": {
                                    "alpha": self.style.alpha,
                                    "color": list(self.style.color)
                                }
                            }
                        },
                        "range": [style_range.end, sorted_styles[i + 1].start],
                        "size": self.style.size,
                        "bold": self.style.bold,
                        "italic": self.style.italic,
                        "underline": self.style.underline,
                        "strokes": [self.border.export_json()] if self.border else []
                    }

                    # Add the global font to the style
                    if self.font:
                        gap_style["font"] = {
                            "id": self.font.resource_id,
                            "path": "C:/%s.ttf" % self.font.name
                        }

                    # Add the text effect to the style
                    if self.effect:
                        gap_style["effectStyle"] = {
                            "id": self.effect.effect_id,
                            "path": "C:"  # nothing is actually stored at this path
                        }

                    styles.append(gap_style)

            # A default style may be needed after the last range
            if sorted_styles[-1].end < len(self.text):
                # Default style from the last range to the end of the text
                end_style = {
                    "fill": {
                        "alpha": 1.0,
                        "content": {
                            "render_type": "solid",
                            "solid": {
                                "alpha": self.style.alpha,
                                "color": list(self.style.color)
                            }
                        }
                    },
                    "range": [sorted_styles[-1].end, len(self.text)],
                    "size": self.style.size,
                    "bold": self.style.bold,
                    "italic": self.style.italic,
                    "underline": self.style.underline,
                    "strokes": [self.border.export_json()] if self.border else []
                }

                # Add the global font to the style
                if self.font:
                    end_style["font"] = {
                        "id": self.font.resource_id,
                        "path": "C:/%s.ttf" % self.font.name
                    }

                # Add the text effect to the style
                if self.effect:
                    end_style["effectStyle"] = {
                        "id": self.effect.effect_id,
                        "path": "C:"  # nothing is actually stored at this path
                    }

                styles.append(end_style)
        else:
            # With no per-range styles, build a single default style
            style_item = {
                "fill": {
                    "alpha": 1.0,
                    "content": {
                        "render_type": "solid",
                        "solid": {
                            "alpha": self.style.alpha,
                            "color": list(self.style.color)
                        }
                    }
                },
                "range": [0, len(self.text)],
                "size": self.style.size,
                "bold": self.style.bold,
                "italic": self.style.italic,
                "underline": self.style.underline,
                "strokes": [self.border.export_json()] if self.border else []
            }

            # Add the shadow to the style
            if self.shadow and self.shadow.has_shadow:
                style_item["shadows"] = [
                    {
                        "diffuse": self.shadow.smoothing / 6,  # diffuse = smoothing/6
                        "angle": self.shadow.angle,
                        "content": {
                            "solid": {
                                "color": [int(self.shadow.color[1:3], 16) / 255,
                                          int(self.shadow.color[3:5], 16) / 255,
                                          int(self.shadow.color[5:7], 16) / 255]
                            }
                        },
                        "distance": self.shadow.distance,
                        "alpha": self.shadow.alpha
                    }
                ]

            # Add the global font to the style
            if self.font:
                style_item["font"] = {
                    "id": self.font.resource_id,
                    "path": "C:/%s.ttf" % self.font.name  # nothing is actually stored at this path
                }

            # Add the text effect to the style
            if self.effect:
                style_item["effectStyle"] = {
                    "id": self.effect.effect_id,
                    "path": "C:"  # nothing is actually stored at this path
                }

            styles.append(style_item)

        content_json = {
            "styles": styles,
            "text": self.text
        }

        ret = {
            "id": self.material_id,
            "content": json.dumps(content_json, ensure_ascii=False),

            "typesetting": int(self.style.vertical),
            "alignment": self.style.align,
            "letter_spacing": self.style.letter_spacing * 0.05,
            "line_spacing": 0.02 + self.style.line_spacing * 0.05,

            "line_feed": 1,
            "line_max_width": 0.82,
            "force_apply_line_max_width": self.wrap_lines,

            "check_flag": check_flag,

            "type": "text",

            "fixed_width": self.fixed_width,
            "fixed_height": self.fixed_height,

            # blend (+4)
            # "global_alpha": 1.0,

            # glow (+64); its properties live in extra_material_refs

            # shadow (+32)
            # "has_shadow": False,
            # "shadow_alpha": 0.9,
            # "shadow_angle": -45.0,
            # "shadow_color": "",
            # "shadow_distance": 5.0,
            # "shadow_point": {
            #     "x": 0.6363961030678928,
            #     "y": -0.6363961030678928
            # },
            # "shadow_smoothing": 0.45,

            # Overall font settings
            "font_category_id": "",
            "font_category_name": "",
            "font_id": "",
            "font_name": "",
            "font_path": "",
            "font_resource_id": "",
            "font_size": 15.0,
            "font_source_platform": 0,
            "font_team_id": "",
            "font_title": "none",
            "font_url": "",
            # Build the fonts array from text_styles. The inner `for font in [...]` binds the
            # range's own font, falling back to the segment's, so the choice is made once
            # rather than repeated in every field.
            "fonts": [] if not self.text_styles else [
                {
                    "category_id": "preset",
                    "category_name": "Editor presets",
                    "effect_id": font.resource_id,
                    "file_uri": "",
                    "id": "BFBA9655-1FE5-41A0-A85D-577EFFF17BDD",
                    "path": "C:/%s.ttf" % font.name,
                    "request_id": "20250713102314DA3D8F267527925ADC9A",
                    "resource_id": font.resource_id,
                    "source_platform": 0,
                    "team_id": "",
                    "title": font.name,
                }
                for style_range in self.text_styles
                for font in [getattr(style_range, "font", None) or self.font]
                if font
            ],

            # appears to be overridden by `content`
            # "text_alpha": 1.0,
            # "text_color": "#FFFFFF",
            # "text_curve": None,
            # "text_preset_resource_id": "",
            # "text_size": 30,
            # "underline": False,
        }

        if self.background:
            ret.update(self.background.export_json())

        # Add the shadow settings
        if self.shadow and self.shadow.has_shadow:
            shadow_json = self.shadow.export_json()
            ret.update(shadow_json)  # merge the shadow settings into the result

        return ret
