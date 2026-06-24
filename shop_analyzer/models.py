"""数据模型 - 闲鱼店铺商品数据模型"""

from dataclasses import dataclass
from typing import List


@dataclass
class ShopItem:
    """代表闲鱼店铺中的一个商品"""
    商品ID: str = ""
    商品名称: str = ""
    价格_元: float = 0.0
    想要人数: int = 0
    浏览次数: int = 0
    转化率_想要_浏览: float = 0.0
    卖家昵称: str = ""
    商品链接: str = ""

    @property
    def is_zombie(self) -> bool:
        """僵尸品：想要数 <= 2 且 浏览低"""
        return self.想要人数 <= 2 and self.浏览次数 < 200

    @property
    def is_potential(self) -> bool:
        """潜力品：想要数 5-10 或 转化率 > 0.1 但曝光低（浏览 < 500）"""
        return (5 <= self.想要人数 <= 10) or (self.转化率_想要_浏览 > 0.1 and self.浏览次数 < 500)

    @property
    def is_hot(self) -> bool:
        """爆款候选：想要数 >= 200"""
        return self.想要人数 >= 200

    @classmethod
    def field_names(cls) -> List[str]:
        """CSV 表头字段名列表（对应 CSV 文件中的中文列名）"""
        return [
            "商品ID", "商品名称", "价格(元)", "想要人数",
            "浏览次数", "转化率(想要/浏览)", "卖家昵称", "商品链接",
        ]

    @classmethod
    def from_csv_row(cls, row: dict) -> "ShopItem":
        """从 CSV 字典行解析为 ShopItem"""
        return cls(
            商品ID=row.get("商品ID", ""),
            商品名称=row.get("商品名称", ""),
            价格_元=float(row.get("价格(元)", 0) or 0),
            想要人数=int(float(row.get("想要人数", 0) or 0)),
            浏览次数=int(float(row.get("浏览次数", 0) or 0)),
            转化率_想要_浏览=float(row.get("转化率(想要/浏览)", 0) or 0),
            卖家昵称=row.get("卖家昵称", ""),
            商品链接=row.get("商品链接", ""),
        )

    def to_csv_dict(self) -> dict:
        """转回 CSV 字典行"""
        return {
            "商品ID": self.商品ID,
            "商品名称": self.商品名称,
            "价格(元)": self.价格_元,
            "想要人数": self.想要人数,
            "浏览次数": self.浏览次数,
            "转化率(想要/浏览)": self.转化率_想要_浏览,
            "卖家昵称": self.卖家昵称,
            "商品链接": self.商品链接,
        }
