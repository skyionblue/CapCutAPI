"""Custom exception types."""

class TrackNotFound(NameError):
    """No track matched the given criteria."""
class AmbiguousTrack(ValueError):
    """More than one track matched the given criteria."""
class SegmentOverlap(ValueError):
    """The new segment overlaps an existing one on the track."""

class MaterialNotFound(NameError):
    """No material matched the given criteria."""
class AmbiguousMaterial(ValueError):
    """More than one material matched the given criteria."""

class ExtensionFailed(ValueError):
    """Could not extend the segment while replacing its material."""

class DraftNotFound(NameError):
    """Draft not found."""
class AutomationError(Exception):
    """An automation step failed."""
class ExportTimeout(Exception):
    """The export timed out."""
