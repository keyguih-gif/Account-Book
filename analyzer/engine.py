from __future__ import annotations
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal
from dataclasses import dataclass
from models.transaction import TransactionType, StandardTransaction

class StatisticsEngine:
    """统计计算引擎"""
    
    def __init__(self, transactions: List[StandardTransaction]):
        # 过滤掉不计收支和已删除的交易
        self.transactions = [t for t in transactions if not t.is_deleted]
        # 调试用：看看前5个交易的类型
        if self.transactions:
            sample = self.transactions[0]
            print(f"调试: 第一笔交易类型={sample.trans_type}, 目标类型={TransactionType.EXPENSE}, 匹配结果={sample.trans_type == TransactionType.EXPENSE}")


        self.expense_only = [t for t in self.transactions if t.trans_type == TransactionType.EXPENSE]
        self.income_only = [t for t in self.transactions if t.trans_type == TransactionType.INCOME]

    # --- 1. 描述性统计 ---
    def descriptive_statistics(self) -> Dict:
        amounts = [float(t.amount) for t in self.transactions]
        income = sum(float(t.amount) for t in self.income_only)
        expense = sum(float(t.amount) for t in self.expense_only)
        
        return {
            'total_income': round(income, 2),
            'total_expense': round(expense, 2),
            'net_income': round(income - expense, 2),
            'transaction_count': len(self.transactions),
            'average_expense': round(expense / len(self.expense_only), 2) if self.expense_only else 0,
            'max_expense': max([float(t.amount) for t in self.expense_only]) if self.expense_only else 0,
        }

    # --- 2. 诊断性分析 ---
    def diagnostic_analysis(self) -> Dict:
        cat_stat = self.summary_by_category(TransactionType.EXPENSE)
        main_expense_cat = cat_stat[0]['category'] if cat_stat else "无"
        main_expense_amt = cat_stat[0]['amount'] if cat_stat else 0
        
        trend = self.trend_analysis(months=6)
        max_mom = 0
        if trend['monthly_data']:
            mom_list = [m.get('mom', 0) for m in trend['monthly_data'] if 'mom' in m]
            max_mom = max(mom_list, key=abs) if mom_list else 0
            
        return {
            'main_expense_category': main_expense_cat,
            'main_expense_amount': main_expense_amt,
            'max_monthly_change_percent': max_mom,
            'max_expense_month': trend.get('max_expense_month', {}).get('period') if trend.get('max_expense_month') else None
        }

    # --- 3. 预测性分析 ---
    def predictive_analysis(self) -> Dict:
        """基于最近两个月的简单线性增长预测"""
        summary = self.summary_by_period('month')
        if len(summary) < 2:
            return {'predicted_next_month_expense': None, 'predicted_next_month_income': None}
        
        last = summary[-1]
        prev = summary[-2]
        
        def forecast(curr_val, prev_val):
            delta = curr_val - prev_val
            return max(0, round(curr_val + delta, 2))

        return {
            'predicted_next_month_expense': forecast(last['expense'], prev['expense']),
            'predicted_next_month_income': forecast(last['income'], prev['income'])
        }

    # --- 4. 规范性建议 ---
    def prescriptive_advice(self) -> Dict:
        desc = self.descriptive_statistics()
        diag = self.diagnostic_analysis()
        advice = []
        
        if desc['net_income'] < 0:
            advice.append(f"⚠️ 支出大于收入({desc['net_income']})，建议控制【{diag['main_expense_category']}】类别的支出。")
        
        if diag['max_monthly_change_percent'] > 30:
            advice.append(f"📈 上月支出波动较大({diag['max_monthly_change_percent']}%)，请检查是否有意外的大额开销。")
            
        if not advice:
            advice.append("✅ 财务状况稳定，继续保持！")
            
        return {'advice': advice}

    # --- 辅助聚合方法 ---
    def summary_by_period(self, period: str = 'month') -> List[Dict]:
        fmt = {'day': '%Y-%m-%d', 'month': '%Y-%m', 'year': '%Y'}.get(period, '%Y-%m')
        
        result = defaultdict(lambda: {'income': Decimal('0'), 'expense': Decimal('0'), 'count': 0})
        
        for t in self.transactions:
            key = t.timestamp.strftime(fmt)
            if t.trans_type == TransactionType.INCOME:
                result[key]['income'] += t.amount
            elif t.trans_type == TransactionType.EXPENSE:
                result[key]['expense'] += t.amount
            result[key]['count'] += 1
            
        summary = []
        for key in sorted(result.keys()):
            data = result[key]
            summary.append({
                'period': key,
                'income': float(data['income']),
                'expense': float(data['expense']),
                'net': float(data['income'] - data['expense']),
                'count': data['count']
            })
        return summary

    def summary_by_category(self, trans_type: TransactionType = TransactionType.EXPENSE) -> List[Dict]:
        category_map = defaultdict(lambda: {'amount': Decimal('0'), 'count': 0})
        target_list = self.expense_only if trans_type == TransactionType.EXPENSE else self.income_only
        
        for t in target_list:
            category_map[t.category]['amount'] += t.amount
            category_map[t.category]['count'] += 1
            
        total_amt = sum(v['amount'] for v in category_map.values())
        
        result = []
        for cat, data in category_map.items():
            amt = float(data['amount'])
            result.append({
                'category': cat,
                'amount': amt,
                'count': data['count'],
                'percentage': round(amt / float(total_amt) * 100, 2) if total_amt > 0 else 0
            })
        return sorted(result, key=lambda x: x['amount'], reverse=True)

    def trend_analysis(self, months: int = 6) -> Dict:
        summary = self.summary_by_period('month')
        recent_summary = summary[-months:]
        
        for i in range(1, len(recent_summary)):
            prev = recent_summary[i-1]['expense']
            curr = recent_summary[i]['expense']
            if prev > 0:
                recent_summary[i]['mom'] = round((curr - prev) / prev * 100, 2)
        
        return {
            'monthly_data': recent_summary,
            'avg_monthly_expense': sum(m['expense'] for m in recent_summary) / len(recent_summary) if recent_summary else 0,
            'max_expense_month': max(recent_summary, key=lambda x: x['expense']) if recent_summary else None
        }