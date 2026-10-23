"""视频蒙版元数据"""


class Mask_meta:
    """蒙版元数据"""

    name: str
    """转场名称"""

    resource_type: str
    """资源类型, 与蒙版形状相关"""

    resource_id: str
    """资源ID"""
    effect_id: str
    """效果ID"""
    md5: str

    default_aspect_ratio: float
    """默认宽高比(宽高都是相对素材的比例)"""

    def __init__(self, name: str, resource_type: str, resource_id: str, effect_id: str, md5: str, default_aspect_ratio: float):
        self.name = name
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.effect_id = effect_id
        self.md5 = md5

        self.default_aspect_ratio = default_aspect_ratio
