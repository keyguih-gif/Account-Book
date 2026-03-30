from __future__ import annotations
import io
from pathlib import Path
import pandas as pd
from models.transaction import StandardTransaction, TransactionType
from decimal import Decimal

class ExpenseCleaner:
    ALIPAY_HEADER_KEYS = ["交易时间", "交易分类", "收/支", "金额"]
    WECHAT_HEADER_KEYS = ["交易时间", "交易类型", "收/支", "金额(元)"]
    MANUAL_HEADER_KEYS = ["时间", "金额", "收/支", "分类", "交易对手", "备注"]

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
    
    def _parse_manual(self, path: Path) -> pd.DataFrame:
        """解析手动输入的 CSV 文件"""
        # 手动文件建议使用 utf-8-sig 编码，这样 Excel 编辑后保存不会乱码
        df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
        
        # 映射关系
        mapping = {
            "时间": "transaction_time",
            "分类": "category_raw",
            "交易对手": "counterparty",
            "备注": "item",
            "收/支": "direction_raw",
            "金额": "amount"
        }
        
        out = df.rename(columns=mapping).copy()
        
        # 补齐标准字段（缺失的补空字符串）
        output_columns = [
            "transaction_time", "category_raw", "counterparty", 
            "counterparty_account", "item", "direction_raw", 
            "amount", "pay_method", "status", "transaction_id", 
            "merchant_order_id", "note"
        ]
        for col in output_columns:
            if col not in out.columns:
                out[col] = ""
        
        return out[output_columns]

    def process_all(self, input_dir: Path) -> pd.DataFrame:
        files = self.find_input_files(input_dir)
        frames = []
        for file in files:
            # 逻辑：如果文件名包含 'manual'，则按手动格式解析
            if "manual" in file.name.lower():
                print(f"[MANUAL] 正在载入手动账单: {file.name}")
                raw = self._parse_manual(file)
                platform = "manual"
            else:
                platform, raw = self.detect_and_parse(file)
            
            cleaned = self.normalize(platform, raw, file.name)
            frames.append(cleaned)
        
        if not frames: return pd.DataFrame()
        return pd.concat(frames, ignore_index=True).sort_values("transaction_time")

def convert_to_models(df) -> list[StandardTransaction]:
    ts_list = []
    for _, row in df.iterrows():
        # 强制去空格并转小写
        raw_dir = str(row['direction']).strip().lower()
        
        if raw_dir == 'expense':
            t_type = TransactionType.EXPENSE
        elif raw_dir == 'income':
            t_type = TransactionType.INCOME
        elif raw_dir == 'neutral':
            t_type = TransactionType.NEUTRAL
        else:
            t_type = TransactionType.UNKNOWN
            
        ts_list.append(StandardTransaction(
            timestamp=row['transaction_time'],
            amount=Decimal(str(row['amount'])),
            trans_type=t_type,
            category=row['category_raw'] or "未分类",
            merchant=row['counterparty'],
            item=row['item']
        ))
    return ts_list


    