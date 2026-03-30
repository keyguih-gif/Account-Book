import pandas as pd
from pathlib import Path
from expense_processor.cleaner import ExpenseCleaner
from analyzer.engine import StatisticsEngine
from importer.cleaner import convert_to_models

class TransactionReporter:
    """账单报表生成管理器"""

    def __init__(self, input_dir: str | Path, output_root: str | Path = "./analysis_reports"):
        self.input_dir = Path(input_dir)
        self.output_root = Path(output_root)
        self.cleaner = ExpenseCleaner()
        self.engine = None
        self.df_raw = None

    def run_pipeline(self):
        """执行完整流水线：清洗 -> 转换 -> 分析 -> 导出"""
        print(f"开始处理目录: {self.input_dir.resolve()}")
        
        # 1. 自动清洗
        self.df_raw = self.cleaner.process_all(self.input_dir)
        if self.df_raw.empty:
            print("警告: 未发现有效账单数据")
            return False

        # 保存汇总明细（可选）
        self.df_raw.to_csv(self.output_root.parent / "all_transactions_cleaned.csv", 
                           index=False, encoding="utf-8-sig")

        # 2. 转换模型
        transactions = convert_to_models(self.df_raw)

        # 3. 初始化分析引擎
        self.engine = StatisticsEngine(transactions)

        # 4. 导出报表
        self._export_all_csvs()
        
        print(f"成功！报表已保存至: {self.output_root.resolve()}")
        return True

    def _export_all_csvs(self):
        """内部方法：执行具体的导出逻辑"""
        self.output_root.mkdir(parents=True, exist_ok=True)
        
        # 提取引擎
        e = self.engine
        
        # --- 1. 概览表 ---
        desc = e.descriptive_statistics()
        pd.DataFrame([
            {"指标": "总收入", "数值": desc['total_income']},
            {"指标": "总支出", "数值": desc['total_expense']},
            {"指标": "净收益", "数值": desc['net_income']},
            {"指标": "交易笔数", "数值": desc['transaction_count']},
            {"指标": "均支", "数值": desc['average_expense']},
        ]).to_csv(self.output_root / "1_summary.csv", index=False, encoding="utf-8-sig")

        # --- 2. 分类统计 ---
        pd.DataFrame(e.summary_by_category()).to_csv(
            self.output_root / "2_categories.csv", index=False, encoding="utf-8-sig")

        # --- 3. 商户统计 ---
        if hasattr(e, 'merchant_analysis'):
            pd.DataFrame(e.merchant_analysis()).to_csv(
                self.output_root / "3_merchants.csv", index=False, encoding="utf-8-sig")

        # --- 4. 趋势与预测 ---
        trend = e.trend_analysis()
        df_trend = pd.DataFrame(trend['monthly_data'])
        pred = e.predictive_analysis()
        if pred['predicted_next_month_expense']:
            pred_row = pd.DataFrame([{
                "period": "下月预测",
                "expense": pred['predicted_next_month_expense'],
                "income": pred['predicted_next_month_income']
            }])
            df_trend = pd.concat([df_trend, pred_row], ignore_index=True)
        df_trend.to_csv(self.output_root / "4_trends.csv", index=False, encoding="utf-8-sig")

        # --- 5. 建议 ---
        pd.DataFrame({"建议": e.prescriptive_advice()['advice']}).to_csv(
            self.output_root / "5_advice.csv", index=False, encoding="utf-8-sig")