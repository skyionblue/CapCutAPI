"""Export backend implementations.

Each backend exposes:

    export(task_id: str, draft_id: str, options: dict) -> str

returning the path of the file it produced. export_impl relocates that file to the
caller's requested output_path, so a backend only has to produce the file somewhere and
report where. Progress and any fidelity warnings are reported through
export_task_cache.update_export_task / add_fidelity_warning.
"""
