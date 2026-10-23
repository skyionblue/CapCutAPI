import os
import uuid
import subprocess
import json
from typing import Optional, Literal
from typing import Dict, Any

class Crop_settings:
    """Crop settings. All values are 0-1; the material's origin is its top-left corner."""

    upper_left_x: float
    upper_left_y: float
    upper_right_x: float
    upper_right_y: float
    lower_left_x: float
    lower_left_y: float
    lower_right_x: float
    lower_right_y: float

    def __init__(self, *, upper_left_x: float = 0.0, upper_left_y: float = 0.0,
                 upper_right_x: float = 1.0, upper_right_y: float = 0.0,
                 lower_left_x: float = 0.0, lower_left_y: float = 1.0,
                 lower_right_x: float = 1.0, lower_right_y: float = 1.0):
        """Initialise the crop settings; the defaults crop nothing."""
        self.upper_left_x = upper_left_x
        self.upper_left_y = upper_left_y
        self.upper_right_x = upper_right_x
        self.upper_right_y = upper_right_y
        self.lower_left_x = lower_left_x
        self.lower_left_y = lower_left_y
        self.lower_right_x = lower_right_x
        self.lower_right_y = lower_right_y

    def export_json(self) -> Dict[str, Any]:
        return {
            "upper_left_x": self.upper_left_x,
            "upper_left_y": self.upper_left_y,
            "upper_right_x": self.upper_right_x,
            "upper_right_y": self.upper_right_y,
            "lower_left_x": self.lower_left_x,
            "lower_left_y": self.lower_left_y,
            "lower_right_x": self.lower_right_x,
            "lower_right_y": self.lower_right_y
        }

class Video_material:
    """A local video or image material. One material may be used by several segments."""

    material_id: str
    """Global material id, generated automatically."""
    local_material_id: str
    """Local material id; its purpose is unclear."""
    material_name: str
    """Material name."""
    path: str
    """Path to the material file."""
    remote_url: Optional[str] = None
    """Remote URL."""
    duration: int
    """Material duration, in microseconds."""
    height: int
    """Material height."""
    width: int
    """Material width."""
    crop_settings: Crop_settings
    """Crop settings for the material."""
    material_type: Literal["video", "photo"]
    """Material type: video or photo."""
    replace_path: Optional[str] = None
    """Replacement path. When set, it is written in place of `path` on export."""

    def __init__(self, material_type: Literal["video", "photo"],
                 path: Optional[str] = None,
                 replace_path: Optional[str] = None,
                 material_name: Optional[str] = None,
                 crop_settings: Crop_settings = Crop_settings(),
                 remote_url: Optional[str] = None,
                 duration: Optional[float] = None,
                 width: Optional[int] = None,
                 height: Optional[int] = None):
        """Load a video or image material from the given location.

        Args:
            path (`str`, optional): path to the file; common video formats (mp4, mov, avi) and images (jpg, jpeg, png) are supported.
            replace_path (`str`, optional): written in place of `path` when exporting JSON.
            material_type (`Literal["video", "photo"]`, optional): the material type; takes precedence when given.
            material_name (`str`, optional): the material name; defaults to the file name.
            crop_settings (`Crop_settings`, optional): crop settings; nothing is cropped by default.
            remote_url (`str`, optional): remote URL.
            duration (`float`, optional): duration in seconds; given, the ffprobe check is skipped.
            width (`int`, optional): material width; probed with ffprobe when omitted.
            height (`int`, optional): material height; probed with ffprobe when omitted.

        Raises:
            `ValueError`: unsupported file type, or a required argument is missing.
            `FileNotFoundError`: the file does not exist.
        """
        # At least one of path or remote_url must be given
        if not path and not remote_url:
            raise ValueError("At least one of `path` or `remote_url` must be given")

        # Remote URL
        if remote_url:
            if not material_name:
                raise ValueError("material_name is required when remote_url is used")
            self.remote_url = remote_url
            self.path = ""  # a remote resource has no local path
        else:
            # Local file
            path = os.path.abspath(path)
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path} not found")
            self.path = path
            self.remote_url = None

        # Material name
        self.material_name = material_name if material_name else os.path.basename(path)
        self.material_id = uuid.uuid3(uuid.NAMESPACE_DNS, self.material_name).hex
        self.replace_path = replace_path
        self.crop_settings = crop_settings
        self.local_material_id = ""
        self.material_type = material_type

        # Photos skip the ffprobe media probe
        if material_type == "photo":
            self.material_type = "photo"
            self.duration = 10800000000  # a still image defaults to 3 hours
            # Read the image dimensions with imageio
            try:
                # img = imageio.imread(self.remote_url)
                # self.height, self.width = img.shape[:2]
                # Use placeholder dimensions; the real ones are read at download time
                self.width = 0
                self.height = 0
            except Exception as e:
                # Fall back to defaults if that fails
                self.width = 1920
                self.height = 1080
            return


        # A caller-supplied duration skips the ffprobe check
        if duration is not None and width is not None and height is not None:
            self.duration = int(float(duration) * 1e6)  # to microseconds
            self.width = width
            self.height = height
            return  # nothing further to probe

        # Otherwise probe the duration with ffprobe
        try:
            # Probe the media with ffprobe
            media_path = self.path if self.path else self.remote_url
            command = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',  # the first video stream
                '-show_entries', 'stream=width,height,duration,codec_type',
                '-show_entries', 'format=duration,format_name',
                '-of', 'json',
                media_path
            ]
            result = subprocess.check_output(command, stderr=subprocess.STDOUT)
            result_str = result.decode('utf-8')
            # Find where the JSON starts (the first '{')
            json_start = result_str.find('{')
            if json_start != -1:
                json_str = result_str[json_start:]
                info = json.loads(json_str)
            else:
                raise ValueError(f"No JSON found in the output: {result_str}")

            if 'streams' in info and len(info['streams']) > 0:
                stream = info['streams'][0]
                self.width = int(stream.get('width', 0))
                self.height = int(stream.get('height', 0))

                # An explicit material_type wins
                if material_type is not None:
                    self.material_type = material_type
                else:
                    # Decide from format_name and codec_type whether this is moving video
                    format_name = info.get('format', {}).get('format_name', '').lower()
                    codec_type = stream.get('codec_type', '').lower()

                    # GIFs and other animated formats count as video
                    if 'gif' in format_name or (codec_type == 'video' and stream.get('duration') is not None):
                        self.material_type = "video"
                    else:
                        self.material_type = "photo"

                # Duration
                if self.material_type == "video":
                    # Prefer the stream duration, falling back to the container duration
                    duration = stream.get('duration') or info['format'].get('duration', '0')
                    self.duration = int(float(duration) * 1e6)  # to microseconds
                else:
                    self.duration = 10800000000  # a still image defaults to 3 hours
            else:
                raise ValueError(f"Could not read stream information for {media_path}")

        except subprocess.CalledProcessError as e:
            raise ValueError(f"Error processing {media_path}: {e.output.decode('utf-8')}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing the media information: {e}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Video_material":
        """Create a video material object from a dictionary.

        Args:
            data (Dict[str, Any]): dictionary holding the material's information

        Returns:
            Video_material: the newly created video material object
        """
        # Create the instance without calling __init__
        instance = cls.__new__(cls)

        # Basic attributes
        instance.material_id = data["id"]
        instance.local_material_id = data.get("local_material_id", "")
        instance.material_name = data["material_name"]
        instance.path = data["path"]
        instance.duration = data["duration"]
        instance.height = data["height"]
        instance.width = data["width"]
        instance.material_type = data["type"]
        instance.replace_path = None  # no replacement path by default
        # export_json writes remote_url, so restoring it keeps the round trip complete.
        # Without it a restored material has no source to fetch from.
        instance.remote_url = data.get("remote_url")

        # Crop settings
        crop_data = data.get("crop", {})
        instance.crop_settings = Crop_settings(
            upper_left_x=crop_data.get("upper_left_x", 0.0),
            upper_left_y=crop_data.get("upper_left_y", 0.0),
            upper_right_x=crop_data.get("upper_right_x", 1.0),
            upper_right_y=crop_data.get("upper_right_y", 0.0),
            lower_left_x=crop_data.get("lower_left_x", 0.0),
            lower_left_y=crop_data.get("lower_left_y", 1.0),
            lower_right_x=crop_data.get("lower_right_x", 1.0),
            lower_right_y=crop_data.get("lower_right_y", 1.0)
        )

        return instance

    def export_json(self) -> Dict[str, Any]:
        video_material_json = {
            "audio_fade": None,
            "category_id": "",
            "category_name": "local",
            "check_flag": 63487,
            "crop": self.crop_settings.export_json(),
            "crop_ratio": "free",
            "crop_scale": 1.0,
            "duration": self.duration,
            "height": self.height,
            "id": self.material_id,
            "local_material_id": self.local_material_id,
            "material_id": self.material_id,
            "material_name": self.material_name,
            "media_path": "",
            "path": self.replace_path if self.replace_path is not None else self.path,
            "remote_url": self.remote_url,
            "type": self.material_type,
            "width": self.width
        }
        return video_material_json

class Audio_material:
    """A local audio material."""

    material_id: str
    """Global material id, generated automatically."""
    material_name: str
    """Material name."""
    path: str
    """Path to the material file."""
    remote_url: Optional[str] = None
    """Remote URL."""
    replace_path: Optional[str] = None
    """Replacement path. When set, it is written in place of `path` on export."""

    has_audio_effect: bool = False
    """Whether an audio effect is applied."""

    duration: int
    """Material duration, in microseconds."""

    def __init__(self, path: Optional[str] = None, replace_path=None, material_name: Optional[str] = None,
                 remote_url: Optional[str] = None, duration: Optional[float] = None):
        """Load an audio material from the given location. Video files must not be used as audio materials.

        Args:
            path (`str`, optional): path to the file; common audio formats such as mp3 and wav are supported.
            material_name (`str`, optional): the material name; defaults to the file name from the URL.
            remote_url (`str`, optional): remote URL.
            duration (`float`, optional): duration in seconds; given, the ffprobe check is skipped.

        Raises:
            `ValueError`: unsupported file type, or a required argument is missing.
        """
        if not path and not remote_url:
            raise ValueError("At least one of `path` or `remote_url` must be given")

        if path:
            path = os.path.abspath(path)
            if not os.path.exists(path):
                raise FileNotFoundError(f"{path} not found")

        # Derive material_name from the URL
        if not material_name and remote_url:
            original_filename = os.path.basename(remote_url.split('?')[0])
            name_without_ext = os.path.splitext(original_filename)[0]  # strip the extension
            material_name = f"{name_without_ext}.mp3"  # original name with a fixed .mp3 extension

        self.material_name = material_name if material_name else (os.path.basename(path) if path else "unknown")
        self.material_id = uuid.uuid3(uuid.NAMESPACE_DNS, self.material_name).hex
        self.path = path if path else ""
        self.replace_path = replace_path
        self.remote_url = remote_url

        # A caller-supplied duration skips the ffprobe check
        if duration is not None:
            self.duration = int(float(duration) * 1e6)  # to microseconds
            return  # nothing further to probe

        # Otherwise probe the duration with ffprobe
        self.duration = 0  # updated below when a path is available

        try:
            # Probe the audio with ffprobe
            command = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'a:0',  # the first audio stream
                '-show_entries', 'stream=duration',
                '-show_entries', 'format=duration',
                '-of', 'json',
                path if path else remote_url
            ]
            result = subprocess.check_output(command, stderr=subprocess.STDOUT)
            result_str = result.decode('utf-8')
            # Find where the JSON starts (the first '{')
            json_start = result_str.find('{')
            if json_start != -1:
                json_str = result_str[json_start:]
                info = json.loads(json_str)
            else:
                raise ValueError(f"No JSON found in the output: {result_str}")

            # Check for a video stream
            video_command = [
                'ffprobe',
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=codec_type',
                '-of', 'json',
                path if path else remote_url
            ]
            video_result = subprocess.check_output(video_command, stderr=subprocess.STDOUT)
            video_result_str = video_result.decode('utf-8')
            # Find where the JSON starts (the first '{')
            video_json_start = video_result_str.find('{')
            if video_json_start != -1:
                video_json_str = video_result_str[video_json_start:]
                video_info = json.loads(video_json_str)
            else:
                print(f"No JSON found in the output: {video_result_str}")

            if 'streams' in video_info and len(video_info['streams']) > 0:
                raise ValueError("An audio material must not contain a video track")

            # Check the audio stream
            if 'streams' in info and len(info['streams']) > 0:
                stream = info['streams'][0]
                # Prefer the stream duration, falling back to the container duration
                duration_value = stream.get('duration') or info['format'].get('duration', '0')
                self.duration = int(float(duration_value) * 1e6)  # to microseconds
            else:
                raise ValueError(f"{path} has no audio track")

        except subprocess.CalledProcessError as e:
            raise ValueError(f"Error processing {path}: {e.output.decode('utf-8')}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing the media information: {e}")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Audio_material":
        """Create an audio material object from a dictionary.

        Args:
            data (Dict[str, Any]): dictionary holding the material's information

        Returns:
            Audio_material: the newly created audio material object
        """
        # Create the instance without calling __init__
        instance = cls.__new__(cls)

        # Basic attributes
        instance.material_id = data["id"]
        instance.material_name = data["name"]  # the key is "name", not "material_name"
        instance.path = data["path"]
        instance.duration = data["duration"]
        instance.replace_path = None  # no replacement path by default
        # export_json writes remote_url, so restoring it keeps the round trip complete.
        # Without it a restored material has no source to fetch from.
        instance.remote_url = data.get("remote_url")
        instance.remote_url = data.get("remote_url")

        return instance

    def export_json(self) -> Dict[str, Any]:
        return {
            "app_id": 0,
            "category_id": "",
            "category_name": "local",
            "check_flag": 3 if hasattr(self, 'has_audio_effect') and self.has_audio_effect else 1,
            "copyright_limit_type": "none",
            "duration": self.duration,
            "effect_id": "",
            "formula_id": "",
            "id": self.material_id,
            "intensifies_path": "",
            "is_ai_clone_tone": False,
            "is_text_edit_overdub": False,
            "is_ugc": False,
            "local_material_id": self.material_id,
            "music_id": self.material_id,
            "name": self.material_name,
            "path": self.replace_path if self.replace_path is not None else self.path,
            "remote_url": self.remote_url,
            "query": "",
            "request_id": "",
            "resource_id": "",
            "search_id": "",
            "source_from": "",
            "source_platform": 0,
            "team_id": "",
            "text_id": "",
            "tone_category_id": "",
            "tone_category_name": "",
            "tone_effect_id": "",
            "tone_effect_name": "",
            "tone_platform": "",
            "tone_second_category_id": "",
            "tone_second_category_name": "",
            "tone_speaker": "",
            "tone_type": "",
            "type": "extract_music",
            "video_id": "",
            "wave_points": []
        }
