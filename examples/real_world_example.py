import asyncio
import time
import random
import json
from pathlib import Path
from typing import List, Dict, Optional
from tool_agent_demo import Agent, Result


class DataAnalysisAgent(Agent):
    def __init__(self):
        super().__init__()
        self.cache = {}
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)

    @Agent.tool
    def fetch_data(self, source_id: str, delay: float = 1.0) -> Dict:
        """Simulate fetching data from an external API with delay"""
        time.sleep(delay)  # Simulate network delay
        # Simulate different data sources
        if source_id == "sales":
            return {
                "daily_sales": [random.randint(100, 1000) for _ in range(7)],
                "total_revenue": random.randint(10000, 50000),
                "top_products": ["Product A", "Product B", "Product C"]
            }
        elif source_id == "inventory":
            return {
                "stock_levels": {f"Product {chr(65+i)}": random.randint(0, 100)
                                 for i in range(5)},
                "low_stock_alerts": [f"Product {chr(65+i)}"
                                     for i in range(5) if random.random() < 0.3]
            }
        else:
            raise ValueError(f"Unknown data source: {source_id}")

    @Agent.tool
    def process_data(self, data: Dict, operation: str) -> Dict:
        """Process data with specified operation (CPU-intensive)"""
        time.sleep(0.5)  # Simulate processing time

        if operation == "analyze_sales":
            # Simulate complex calculations
            daily_sales = data.get("daily_sales", [])
            return {
                "average_sales": sum(daily_sales) / len(daily_sales),
                "peak_day": max(range(len(daily_sales)), key=lambda i: daily_sales[i]),
                "trend": "up" if daily_sales[-1] > daily_sales[0] else "down"
            }
        elif operation == "inventory_alerts":
            stock = data.get("stock_levels", {})
            return {
                "low_stock": [prod for prod, level in stock.items() if level < 20],
                "out_of_stock": [prod for prod, level in stock.items() if level == 0],
                "reorder_suggestions": [
                    {"product": prod, "amount": 100 - level}
                    for prod, level in stock.items() if level < 50
                ]
            }
        else:
            raise ValueError(f"Unknown operation: {operation}")

    @Agent.tool
    def save_to_file(self, data: Dict, filename: str) -> str:
        """Save processed data to a file (I/O operation)"""
        time.sleep(0.3)  # Simulate I/O delay
        filepath = self.data_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return str(filepath)

    @Agent.tool
    def load_from_file(self, filename: str) -> Dict:
        """Load data from a file (I/O operation)"""
        time.sleep(0.3)  # Simulate I/O delay
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filename}")
        with open(filepath) as f:
            return json.load(f)

    @Agent.tool
    def generate_report(self, sales_data: Dict, inventory_data: Dict) -> str:
        """Generate a combined report from multiple data sources"""
        time.sleep(1.0)  # Simulate report generation time

        # Simulate complex report generation
        report_lines = [
            "=== Business Intelligence Report ===\n",
            "Sales Performance:",
            f"- Average Daily Sales: ${sales_data['average_sales']:.2f}",
            f"- Sales Trend: {sales_data['trend']}",
            f"- Peak Sales Day: Day {sales_data['peak_day'] + 1}",
            "\nInventory Status:",
            f"- Low Stock Items: {', '.join(inventory_data['low_stock'])}",
            f"- Out of Stock Items: {
                ', '.join(inventory_data['out_of_stock'])}",
            "\nRecommended Actions:"
        ]

        for item in inventory_data['reorder_suggestions']:
            report_lines.append(
                f"- Order {item['amount']} units of {item['product']}")

        return "\n".join(report_lines)

    @Agent.workflow
    def analyze_sales_data(self) -> Result:
        """Workflow to analyze sales data"""
        # Fetch raw sales data
        sales_data = self.fetch_data("sales")
        if sales_data.is_err():
            return sales_data

        # Process the sales data
        analysis = self.process_data(sales_data.unwrap(), "analyze_sales")
        if analysis.is_err():
            return analysis

        # Save the results
        return self.save_to_file(analysis.unwrap(), "sales_analysis.json")

    @Agent.workflow
    def analyze_inventory_data(self) -> Result:
        """Workflow to analyze inventory data"""
        # Fetch raw inventory data
        inventory_data = self.fetch_data("inventory")
        if inventory_data.is_err():
            return inventory_data

        # Process the inventory data
        analysis = self.process_data(
            inventory_data.unwrap(), "inventory_alerts")
        if analysis.is_err():
            return analysis

        # Save the results
        return self.save_to_file(analysis.unwrap(), "inventory_analysis.json")

    @Agent.workflow
    def generate_business_report(self) -> Result:
        """Complex workflow combining multiple data sources and operations"""
        # Run both analysis workflows
        for result in self.analyze_sales_data():
            if result.is_err():
                return result
        sales_file = result.unwrap()

        for result in self.analyze_inventory_data():
            if result.is_err():
                return result
        inventory_file = result.unwrap()

        # Load the analyzed data
        sales_analysis = self.load_from_file("sales_analysis.json")
        if sales_analysis.is_err():
            return sales_analysis

        inventory_analysis = self.load_from_file("inventory_analysis.json")
        if inventory_analysis.is_err():
            return inventory_analysis

        # Generate the final report
        report = self.generate_report(
            sales_analysis.unwrap(),
            inventory_analysis.unwrap()
        )
        if report.is_err():
            return report

        # Save the report
        return self.save_to_file(
            {"report": report.unwrap()},
            "business_report.json"
        )


def main():
    # Create the agent
    agent = DataAnalysisAgent()

    print("=== Testing Individual Tools ===")

    # Test data fetching
    print("\nFetching sales data...")
    sales_result = agent.fetch_data("sales")
    if sales_result.is_ok():
        print(f"Sales data: {sales_result.unwrap()}")

    print("\nFetching inventory data...")
    inventory_result = agent.fetch_data("inventory")
    if inventory_result.is_ok():
        print(f"Inventory data: {inventory_result.unwrap()}")

    print("\n=== Running Complex Workflow ===")
    print("Generating business report (this will take some time)...")

    # Track workflow progress
    start_time = time.time()
    for result in agent.generate_business_report():
        if result.is_err():
            print(f"Error in workflow: {result.error}")
            break
        final_result = result

    if 'final_result' in locals() and final_result.is_ok():
        print(f"\nWorkflow completed in {
              time.time() - start_time:.2f} seconds")
        # Load and display the report
        report_data = agent.load_from_file("business_report.json")
        if report_data.is_ok():
            print("\nFinal Report:")
            print(report_data.unwrap()["report"])
    else:
        print("Workflow failed")

    # Print agent information
    print("\n=== Agent Information ===")
    print(agent)


if __name__ == "__main__":
    main()
