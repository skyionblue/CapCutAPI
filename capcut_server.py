from flask import Flask, request, jsonify
from pyJianYingDraft.metadata.capcut_animation_meta import CapCut_Intro_type, CapCut_Outro_type, CapCut_Group_animation_type
from pyJianYingDraft.metadata.capcut_transition_meta import CapCut_Transition_type
from pyJianYingDraft.metadata.capcut_mask_meta import CapCut_Mask_type
from pyJianYingDraft.metadata.capcut_audio_effect_meta import CapCut_Voice_filters_effect_type, CapCut_Voice_characters_effect_type, CapCut_Speech_to_song_effect_type
from pyJianYingDraft.metadata.font_meta import Font_type
from pyJianYingDraft.metadata.capcut_text_animation_meta import CapCut_Text_intro, CapCut_Text_outro, CapCut_Text_loop_anim
from pyJianYingDraft.metadata.capcut_effect_meta import CapCut_Video_scene_effect_type, CapCut_Video_character_effect_type
from save_draft_impl import save_draft_impl, query_task_status, query_script_impl
from export_impl import export_video, query_export_status, export_preflight
from export_subtitles_impl import export_subtitles_impl
from export_draft_impl import export_draft_impl
# The catalogue and dispatch the MCP gateway also uses; the routes below are
# adapters over it rather than re-implementing the wiring.
from tool_registry import TOOLS, execute_tool
from create_draft import create_draft
from util import generate_draft_url as utilgenerate_draft_url

from settings.local import PORT

app = Flask(__name__)


# --- shared dispatch -------------------------------------------------------------------
# These routes are thin adapters over tool_registry, the same catalogue and dispatch the MCP
# gateway uses. They previously re-declared every parameter with their own defaults, which is
# how the two surfaces drifted apart -- see enhancements-plan.md, Phase C2.

# Legacy request keys kept working after being renamed to match the catalogue.
PARAMETER_ALIASES = {
    "add_sticker": {"sticker_id": "resource_id"},
    # This route read "srt" while the catalogue and implementation call it "srt_path" --
    # the same mismatch add_sticker had. Both names keep working.
    "add_subtitle": {"srt": "srt_path"},
}


def _dispatch(tool_name):
    """Run a catalogue tool with the request body and shape the HTTP envelope.

    Only keys the caller actually sent are forwarded, so every default comes from the
    implementation rather than being restated here.
    """
    data = request.get_json(silent=True) or {}
    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    schema = next(t for t in TOOLS if t["name"] == tool_name)["inputSchema"]
    properties = schema.get("properties", {})

    arguments = {}
    for key, value in data.items():
        key = PARAMETER_ALIASES.get(tool_name, {}).get(key, key)
        if key in properties:
            arguments[key] = value

    # Validate required parameters
    for name in schema.get("required", []):
        if arguments.get(name) in (None, ""):
            result["error"] = (f"Hi, the required parameter '{name}' is missing. "
                               f"Please add it and try again.")
            return jsonify(result)

    try:
        outcome = execute_tool(tool_name, arguments)
    except Exception as e:
        result["error"] = f"Error occurred while running {tool_name}: {str(e)}."
        return jsonify(result)

    if not outcome.get("success"):
        result["error"] = outcome.get("error", f"{tool_name} failed")
        return jsonify(result)

    result["success"] = True
    result["output"] = outcome["result"]
    return jsonify(result)

@app.route('/add_video', methods=['POST'])
def add_video():
    return _dispatch('add_video')

@app.route('/add_audio', methods=['POST'])
def add_audio():
    return _dispatch('add_audio')

@app.route('/create_draft', methods=['POST'])
def create_draft_service():
    data = request.get_json()

    # Get parameters
    width = data.get('width', 1080)
    height = data.get('height', 1920)

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    try:
        # Create new draft
        script, draft_id = create_draft(width=width, height=height)

        result["success"] = True
        result["output"] = {
            "draft_id": draft_id,
            "draft_url": utilgenerate_draft_url(draft_id)
        }
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while creating draft: {str(e)}."
        result["error"] = error_message
        return jsonify(result)

@app.route('/add_subtitle', methods=['POST'])
def add_subtitle():
    return _dispatch('add_subtitle')

@app.route('/add_text', methods=['POST'])
def add_text():
    return _dispatch('add_text')

@app.route('/add_image', methods=['POST'])
def add_image():
    return _dispatch('add_image')

@app.route('/add_video_keyframe', methods=['POST'])
def add_video_keyframe():
    return _dispatch('add_video_keyframe')

@app.route('/add_effect', methods=['POST'])
def add_effect():
    return _dispatch('add_effect')

@app.route('/query_script', methods=['POST'])
def query_script():
    data = request.get_json()

    # Get required parameters
    draft_id = data.get('draft_id')
    force_update = data.get('force_update', True)

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not draft_id:
        error_message = "Hi, the required parameter 'draft_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        # Call query_script_impl method
        script = query_script_impl(draft_id=draft_id, force_update=force_update)

        if script is None:
            error_message = f"Draft {draft_id} does not exist in cache."
            result["error"] = error_message
            return jsonify(result)

        # Convert script object to JSON serializable dictionary
        script_str = script.dumps()

        result["success"] = True
        result["output"] = script_str
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while querying script: {str(e)}. "
        result["error"] = error_message
        return jsonify(result)

@app.route('/save_draft', methods=['POST'])
def save_draft():
    data = request.get_json()

    # Get required parameters
    draft_id = data.get('draft_id')
    draft_folder = data.get('draft_folder')  # Draft folder parameter
    # Saving downloads every remote asset, so a large draft can outlast an HTTP client's
    # patience. wait=False returns a task_id to poll via /query_draft_status instead.
    wait = data.get('wait', True)

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not draft_id:
        error_message = "Hi, the required parameter 'draft_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        # Call save_draft_impl method, start background task
        draft_result = save_draft_impl(draft_id, draft_folder, wait=wait)

        result["success"] = True
        result["output"] = draft_result
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while saving draft: {str(e)}. "
        result["error"] = error_message
        return jsonify(result)

# Add new query status interface
@app.route('/query_draft_status', methods=['POST'])
def query_draft_status():
    data = request.get_json()

    # Get required parameters
    task_id = data.get('task_id')

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not task_id:
        error_message = "Hi, the required parameter 'task_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        # Get task status
        task_status = query_task_status(task_id)

        if task_status["status"] == "not_found":
            error_message = f"Task with ID {task_id} not found. Please check if the task ID is correct."
            result["error"] = error_message
            return jsonify(result)

        result["success"] = True
        result["output"] = task_status
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while querying task status: {str(e)}."
        result["error"] = error_message
        return jsonify(result)

@app.route('/generate_draft_url', methods=['POST'])
def generate_draft_url():
    data = request.get_json()

    # Get required parameters
    draft_id = data.get('draft_id')

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not draft_id:
        error_message = "Hi, the required parameter 'draft_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        # Use the shared helper rather than rebuilding the URL here: the hand-rolled version
        # emitted "?=<id>", a query string with no parameter name, while every other response
        # from this same server (and the MCP tool) returns "?draft_id=<id>".
        draft_result = {"draft_url": utilgenerate_draft_url(draft_id)}

        result["success"] = True
        result["output"] = draft_result
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while saving draft: {str(e)}."
        result["error"] = error_message
        return jsonify(result)

@app.route('/add_sticker', methods=['POST'])
def add_sticker():
    return _dispatch('add_sticker')

@app.route('/get_intro_animation_types', methods=['GET'])
def get_intro_animation_types():
    """Return supported entrance animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        animation_types = []

        for name, member in CapCut_Intro_type.__members__.items():
            animation_types.append({
                "name": name
            })

        result["output"] = animation_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting entrance animation types: {str(e)}"
        return jsonify(result)

@app.route('/get_outro_animation_types', methods=['GET'])
def get_outro_animation_types():
    """Return supported exit animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        animation_types = []

        for name, member in CapCut_Outro_type.__members__.items():
            animation_types.append({
                "name": name
            })

        result["output"] = animation_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting exit animation types: {str(e)}"
        return jsonify(result)


@app.route('/get_combo_animation_types', methods=['GET'])
def get_combo_animation_types():
    """Return supported combo animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        animation_types = []

        for name, member in CapCut_Group_animation_type.__members__.items():
            animation_types.append({
                "name": name
            })

        result["output"] = animation_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting combo animation types: {str(e)}"
        return jsonify(result)


@app.route('/get_transition_types', methods=['GET'])
def get_transition_types():
    """Return supported transition animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        transition_types = []

        for name, member in CapCut_Transition_type.__members__.items():
            transition_types.append({
                "name": name
            })

        result["output"] = transition_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting transition animation types: {str(e)}"
        return jsonify(result)


@app.route('/get_mask_types', methods=['GET'])
def get_mask_types():
    """Return supported mask type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        mask_types = []

        for name, member in CapCut_Mask_type.__members__.items():
            mask_types.append({
                "name": name
            })

        result["output"] = mask_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting mask types: {str(e)}"
        return jsonify(result)


@app.route('/get_audio_effect_types', methods=['GET'])
def get_audio_effect_types():
    """Return supported audio effect type list

    The returned structure includes name, type and Effect_param information
    """
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        audio_effect_types = []

        # 1. Voice filters effect types
        for name, member in CapCut_Voice_filters_effect_type.__members__.items():
            params_info = []
            for param in member.value.params:
                params_info.append({
                    "name": param.name,
                    "default_value": param.default_value * 100,
                    "min_value": param.min_value * 100,
                    "max_value": param.max_value * 100
                })

            audio_effect_types.append({
                "name": name,
                "type": "Voice_filters",
                "params": params_info
            })

        # 2. Voice characters effect types
        for name, member in CapCut_Voice_characters_effect_type.__members__.items():
            params_info = []
            for param in member.value.params:
                params_info.append({
                    "name": param.name,
                    "default_value": param.default_value * 100,
                    "min_value": param.min_value * 100,
                    "max_value": param.max_value * 100
                })

            audio_effect_types.append({
                "name": name,
                "type": "Voice_characters",
                "params": params_info
            })

        # 3. Speech to song effect types
        for name, member in CapCut_Speech_to_song_effect_type.__members__.items():
            params_info = []
            for param in member.value.params:
                params_info.append({
                    "name": param.name,
                    "default_value": param.default_value * 100,
                    "min_value": param.min_value * 100,
                    "max_value": param.max_value * 100
                })

            audio_effect_types.append({
                "name": name,
                "type": "Speech_to_song",
                "params": params_info
            })

        result["output"] = audio_effect_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting audio effect types: {str(e)}"
        return jsonify(result)


@app.route('/get_font_types', methods=['GET'])
def get_font_types():
    """Return supported font type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        font_types = []

        for name, member in Font_type.__members__.items():
            font_types.append({
                "name": name
            })

        result["output"] = font_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting font types: {str(e)}"
        return jsonify(result)


@app.route('/get_text_intro_types', methods=['GET'])
def get_text_intro_types():
    """Return supported text entrance animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        text_intro_types = []

        for name, member in CapCut_Text_intro.__members__.items():
            text_intro_types.append({
                "name": name
            })

        result["output"] = text_intro_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting text entrance animation types: {str(e)}"
        return jsonify(result)

@app.route('/get_text_outro_types', methods=['GET'])
def get_text_outro_types():
    """Return supported text exit animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        text_outro_types = []

        for name, member in CapCut_Text_outro.__members__.items():
            text_outro_types.append({
                "name": name
            })

        result["output"] = text_outro_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting text exit animation types: {str(e)}"
        return jsonify(result)

@app.route('/get_text_loop_anim_types', methods=['GET'])
def get_text_loop_anim_types():
    """Return supported text loop animation type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        text_loop_anim_types = []

        for name, member in CapCut_Text_loop_anim.__members__.items():
            text_loop_anim_types.append({
                "name": name
            })

        result["output"] = text_loop_anim_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting text loop animation types: {str(e)}"
        return jsonify(result)


@app.route('/get_video_scene_effect_types', methods=['GET'])
def get_video_scene_effect_types():
    """Return supported scene effect type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        effect_types = []

        for name, member in CapCut_Video_scene_effect_type.__members__.items():
            effect_types.append({
                "name": name
            })

        result["output"] = effect_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting scene effect types: {str(e)}"
        return jsonify(result)


@app.route('/get_video_character_effect_types', methods=['GET'])
def get_video_character_effect_types():
    """Return supported character effect type list"""
    result = {
        "success": True,
        "output": "",
        "error": ""
    }

    try:
        effect_types = []

        for name, member in CapCut_Video_character_effect_type.__members__.items():
            effect_types.append({
                "name": name
            })

        result["output"] = effect_types
        return jsonify(result)

    except Exception as e:
        result["success"] = False
        result["error"] = f"Error occurred while getting character effect types: {str(e)}"
        return jsonify(result)


@app.route('/export_video', methods=['POST'])
def export_video_service():
    data = request.get_json()

    draft_id = data.get('draft_id')

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not draft_id:
        error_message = "Hi, the required parameter 'draft_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        export_result = export_video(
            draft_id=draft_id,
            backend=data.get('backend', 'auto'),
            output_path=data.get('output_path'),
            resolution=data.get('resolution'),
            framerate=data.get('framerate'),
            bitrate=data.get('bitrate'),
            draft_folder=data.get('draft_folder')
        )

        if not export_result.get("success"):
            result["error"] = export_result.get("error", "Export could not be started")
            return jsonify(result)

        result["success"] = True
        result["output"] = export_result
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while starting video export: {str(e)}."
        result["error"] = error_message
        return jsonify(result)


@app.route('/query_export_status', methods=['POST'])
def query_export_status_service():
    data = request.get_json()

    task_id = data.get('task_id')

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not task_id:
        error_message = "Hi, the required parameter 'task_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        task_status = query_export_status(task_id)

        if task_status["status"] == "not_found":
            error_message = f"Export task with ID {task_id} not found. Please check if the task ID is correct."
            result["error"] = error_message
            return jsonify(result)

        result["success"] = True
        result["output"] = task_status
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while querying export status: {str(e)}."
        result["error"] = error_message
        return jsonify(result)


@app.route('/export_preflight', methods=['GET'])
def export_preflight_service():
    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    try:
        result["success"] = True
        result["output"] = export_preflight()
        return jsonify(result)

    except Exception as e:
        result["error"] = f"Error occurred while checking export backends: {str(e)}."
        return jsonify(result)


@app.route('/export_subtitles', methods=['POST'])
def export_subtitles_service():
    data = request.get_json()

    draft_id = data.get('draft_id')

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not draft_id:
        error_message = "Hi, the required parameter 'draft_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        subtitles = export_subtitles_impl(
            draft_id=draft_id,
            output_path=data.get('output_path'),
            track_name=data.get('track_name'),
            time_offset=data.get('time_offset', 0.0)
        )

        if not subtitles.get("success"):
            result["error"] = subtitles.get("error", "Subtitle export failed")
            return jsonify(result)

        result["success"] = True
        result["output"] = subtitles
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while exporting subtitles: {str(e)}."
        result["error"] = error_message
        return jsonify(result)


@app.route('/export_draft', methods=['POST'])
def export_draft_service():
    data = request.get_json()

    draft_id = data.get('draft_id')

    result = {
        "success": False,
        "output": "",
        "error": ""
    }

    # Validate required parameters
    if not draft_id:
        error_message = "Hi, the required parameter 'draft_id' is missing. Please add it and try again."
        result["error"] = error_message
        return jsonify(result)

    try:
        bundle = export_draft_impl(
            draft_id=draft_id,
            output_path=data.get('output_path'),
            draft_folder=data.get('draft_folder')
        )

        if not bundle.get("success"):
            result["error"] = bundle.get("error", "Draft bundling failed")
            return jsonify(result)

        result["success"] = True
        result["output"] = bundle
        return jsonify(result)

    except Exception as e:
        error_message = f"Error occurred while bundling draft: {str(e)}."
        result["error"] = error_message
        return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
