"""转场效果元数据"""


class Transition_meta:
    """转场元数据"""

    name: str
    """转场名称"""
    is_vip: bool
    """是否为VIP特权"""

    resource_id: str
    """资源ID"""
    effect_id: str
    """效果ID"""
    md5: str

    default_duration: int
    """默认持续时间, 单位为微秒"""
    is_overlap: bool
    """是否允许重叠(?)"""

    def __init__(self, name: str, is_vip: bool, resource_id: str, effect_id: str, md5: str, default_duration: float, is_overlap: bool):
        self.name = name
        self.is_vip = is_vip
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

        self.default_duration = int(round(default_duration * 1e6))
        self.is_overlap = is_overlap
