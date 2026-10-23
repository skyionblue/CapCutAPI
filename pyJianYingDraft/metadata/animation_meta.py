
class Animation_meta:
    title: str
    is_vip: bool
    duration: int
    """Default effect duration, in microseconds."""

    resource_id: str
    effect_id: str
    md5: str

    def __init__(self, title: str, is_vip: bool, duration: float, resource_id: str, effect_id: str, md5: str):
        self.title = title
        self.is_vip = is_vip
        self.duration = int(round(duration * 1e6))
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5
