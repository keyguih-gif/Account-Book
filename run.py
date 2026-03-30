from pathlib import Path
from expense_processor import ExpenseCleaner

def main():
    # 1. 初始化类
    cleaner = ExpenseCleaner()
    
    # 2. 执行处理逻辑
    input_path = Path("./my_bills")
    try:
        df = cleaner.process_all(input_path)
        
        if df.empty:
            print("没有找到有效账单")
            return

        # 3. 你可以对返回的 DataFrame 做进一步处理
        print(f"处理完成，共 {len(df)} 条记录")
        print(df.groupby("platform")["amount"].sum()) # 按平台统计总额
        
        # 4. 保存结果
        df.to_csv("cleaned_data.csv", index=False, encoding="utf-8-sig")
        
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == "__main__":
    main()