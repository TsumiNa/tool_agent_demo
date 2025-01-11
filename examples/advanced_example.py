from tool_agent_demo.agent import Agent
from tool_agent_demo.result import Result
from typing import Optional
import time


class DataProcessingAgent(Agent):
    def __init__(self):
        super().__init__()
        self.data_store = {}

    @Agent.tool
    def store_data(self, key: str, value: any) -> str:
        """Store data with a given key"""
        self.data_store[key] = value
        return f"Data stored with key: {key}"

    @Agent.tool
    def get_data(self, key: str) -> any:
        """Retrieve data for a given key"""
        if key not in self.data_store:
            raise KeyError(f"No data found for key: {key}")
        return self.data_store[key]

    @Agent.tool
    def process_text(self, text: str) -> str:
        """Convert text to uppercase and add timestamp"""
        return f"{text.upper()} (Processed at {time.time()})"

    @Agent.tool
    def validate_number(self, value: float, min_val: Optional[float] = None, max_val: Optional[float] = None) -> float:
        """Validate a number is within given range"""
        if min_val is not None and value < min_val:
            raise ValueError(f"Value {value} is below minimum {min_val}")
        if max_val is not None and value > max_val:
            raise ValueError(f"Value {value} is above maximum {max_val}")
        return value

    @Agent.workflow
    def process_and_store(self, key: str, text: str) -> Result:
        """Process text and store the result"""
        # Process the text first
        processed = self.process_text(text)
        if processed.is_err():
            return processed
        # Store the processed result
        return self.store_data(key, processed.unwrap())

    @Agent.workflow
    def validate_and_store(self, key: str, value: float, min_val: float, max_val: float) -> Result:
        """Validate a number and store if valid"""
        # First validate the number
        validated = self.validate_number(value, min_val, max_val)
        if validated.is_err():
            return validated
        # Store if validation succeeds
        return self.store_data(key, validated.unwrap())

    @Agent.workflow
    def chain_operations(self, text: str) -> Result:
        """Demonstrate chaining multiple operations with error handling"""
        # Process text and store with key 'latest'
        for result in self.process_and_store("latest", text):
            if result.is_err():
                return result

        # Try to retrieve it back
        retrieved = self.get_data("latest")
        if retrieved.is_err():
            return retrieved

        # Process it again
        final_result = self.process_text(retrieved.unwrap())
        return final_result


def main():
    # Create data processing agent
    agent = DataProcessingAgent()

    # Basic tool usage
    print("\n=== Basic Tool Usage ===")
    store_result = agent.store_data("test", "hello world")
    print(store_result.unwrap())

    get_result = agent.get_data("test")
    print(f"Retrieved: {get_result.unwrap()}")

    process_result = agent.process_text("sample text")
    print(f"Processed: {process_result.unwrap()}")

    # Error handling
    print("\n=== Error Handling ===")
    try:
        invalid_get = agent.get_data("nonexistent")
        print(invalid_get.unwrap())
    except KeyError as e:
        print(f"Expected error caught: {e}")

    validate_result = agent.validate_number(15, min_val=0, max_val=10)
    if validate_result.is_err():
        print(f"Validation error caught: {validate_result.error}")

    # Workflow usage
    print("\n=== Workflow Usage ===")
    for result in agent.process_and_store("workflow_test", "workflow input"):
        if result.is_err():
            print(f"Error in workflow: {result.error}")
            break
        workflow_result = result

    if 'workflow_result' in locals() and workflow_result.is_ok():
        print(f"Workflow result: {workflow_result.unwrap()}")

    # Chain operations
    print("\n=== Chained Operations ===")
    for result in agent.chain_operations("chain test"):
        if result.is_err():
            print(f"Error in workflow: {result.error}")
            break
        chain_result = result

    if 'chain_result' in locals() and chain_result.is_ok():
        print(f"Chain success: {chain_result.unwrap()}")
    else:
        print(f"Chain error: {chain_result.error}")

    # Print agent information
    print("\n=== Agent Information ===")
    print(agent)


if __name__ == "__main__":
    main()
