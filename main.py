from analyzer import TransactionReporter

def main():
    reporter = TransactionReporter(input_dir="./data", output_root="./analysis_reports")
    reporter.run_pipeline()

if __name__ == "__main__":
    main()