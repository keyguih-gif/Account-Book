from __future__ import annotations
import io
from pathlib import Path
import pandas as pd

class ExpenseCleaner:
    ALIPAY_HEADER_KEYS = ["交易时间", "交易分类", "收/支", "金额"]
    WECHAT_HEADER_KEYS = ["交易时间", "交易类型", "收/支", "金额(元)"]

    def __init__(self):
        self.output_columns = [
            "transaction_time", "category_raw", "counterparty", 
            "counterparty_account", "item", "direction_raw", 
            "amount", "pay_method", "status", "transaction_id", 
            "merchant_order_id", "note"
        ]

    def find_input_files(self, input_dir: Path, exclude_name: str = "") -> list[Path]:
        exts = {".csv", ".xlsx", ".xls"}
        files: list[Path] = []
        for p in Path(input_dir).iterdir():
            if p.is_file() and p.suffix.lower() in exts and p.name != exclude_name and not p.name.startswith("~$"):
                files.append(p)
        return sorted(files)

    def _parse_wechat(self, path: Path) -> pd.DataFrame:
        raw = pd.read_excel(path, header=None, dtype=object)
        header_idx = None
        for i in range(len(raw)):
            row_text = "|".join(str(v).strip() for v in raw.iloc[i].tolist() if str(v) != "nan")
            if all(k in row_text for k in self.WECHAT_HEADER_KEYS):
                header_idx = i
                break
        if header_idx is None:
            raise ValueError(f"未找到微信表头: {path.name}")
        df = pd.read_excel(path, header=header_idx, dtype=object)
        return df.dropna(axis=1, how="all")

    def _parse_alipay(self, path: Path) -> pd.DataFrame:
        last_error = None
        for enc in ("gb18030", "gbk", "utf-8-sig"):
            try:
                with open(path, "r", encoding=enc, newline="") as f:
                    lines = f.readlines()
                header_idx = next((i for i, line in enumerate(lines) if all(k in line for k in self.ALIPAY_HEADER_KEYS)), None)
                if header_idx is None: raise ValueError("未找到支付宝表头")
                
                csv_text = "".join(lines[header_idx:])
                df = pd.read_csv(io.StringIO(csv_text), header=0, dtype=str, engine="python", on_bad_lines="skip")
                return df.dropna(axis=1, how="all")
            except Exception as e:
                last_error = e
        raise ValueError(f"解析支付宝失败: {path.name}; {last_error}")

    def normalize(self, platform: str, df: pd.DataFrame, source_file: str) -> pd.DataFrame:
        mapping = {
            "wechat": {
                "交易时间": "transaction_time", "交易类型": "category_raw", "交易对方": "counterparty",
                "商品": "item", "收/支": "direction_raw", "金额(元)": "amount",
                "支付方式": "pay_method", "当前状态": "status", "交易单号": "transaction_id",
                "商户单号": "merchant_order_id", "备注": "note",
            },
            "alipay": {
                "交易时间": "transaction_time", "交易分类": "category_raw", "交易对方": "counterparty",
                "对方账号": "counterparty_account", "商品说明": "item", "收/支": "direction_raw",
                "金额": "amount", "收/付款方式": "pay_method", "交易状态": "status",
                "交易订单号": "transaction_id", "商家订单号": "merchant_order_id", "备注": "note",
            }
        }[platform]

        out = df.rename(columns=mapping).copy()
        for col in self.output_columns:
            if col not in out.columns:
                out[col] = ""
        
        out = out[self.output_columns].copy()
        out["platform"] = platform
        out["source_file"] = source_file
        out["transaction_time"] = pd.to_datetime(out["transaction_time"], errors="coerce")
        out["amount"] = pd.to_numeric(
            out["amount"].astype(str).str.replace(",", "", regex=False).str.replace("¥", "", regex=False),
            errors="coerce"
        )
        
        direction = out["direction_raw"].astype(str).str.strip()
        out["direction"] = direction.map({"支出": "expense", "收入": "income", "不计收支": "neutral"}).fillna("unknown")
        
        return out[out["transaction_time"].notna()].sort_values("transaction_time")

    def process_all(self, input_dir: Path) -> pd.DataFrame:
        """一键处理目录下所有账单并返回 DataFrame"""
        files = self.find_input_files(input_dir)
        frames = []
        for file in files:
            platform = "wechat" if file.suffix.lower() in {".xlsx", ".xls"} else "alipay"
            raw = self._parse_wechat(file) if platform == "wechat" else self._parse_alipay(file)
            cleaned = self.normalize(platform, raw, file.name)
            frames.append(cleaned)
        
        if not frames:
            return pd.DataFrame()
            
        result = pd.concat(frames, ignore_index=True)
        return result.sort_values("transaction_time")