from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

class TransactionType(Enum):
    INCOME = "income"
    EXPENSE = "expense"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"

@dataclass
class StandardTransaction:
    timestamp: datetime
    amount: Decimal
    trans_type: TransactionType
    category: str
    merchant: str
    item: str
    is_deleted: bool = False