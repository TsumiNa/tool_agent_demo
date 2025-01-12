import json
import os
import queue
import random
import string
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from fastapi import HTTPException
from jupyter_client import KernelManager

from tool_agent_demo.core.db import get_executor


class AsyncExecutor:
    """Async wrapper for executing agent methods using Jupyter kernel"""

    def __init__(self, executor_type: str, executor_path: str):
        self.executor_type = executor_type
        self.executor_path = executor_path
        self.km = None
        self.kc = None
        self.initialized = False
        # kernel_id -> (module_path, var_name, method_name, args, kwargs)
        self.active_kernels: Dict[str, Tuple[str,
                                             str, str, List[Any], Dict[str, Any]]] = {}
        self._kernel_counter = 0

    async def _init_kernel(self):
        """Initialize Jupyter kernel if not already running"""
        if self.initialized:
            return

        # Get Python interpreter path from executor_path
        python_path = str(Path(self.executor_path) / "bin" / "python")

        # Verify Python interpreter exists
        if not os.path.exists(python_path):
            raise HTTPException(
                status_code=500,
                detail=f"Python interpreter not found at {python_path}"
            )

        # Configure kernel command
        kernel_cmd = [python_path, "-m",
                      "ipykernel_launcher", "-f", "{connection_file}"]

        try:
            # Start kernel with custom Python interpreter
            self.km = KernelManager()
            self.km.kernel_cmd = kernel_cmd
            self.km.start_kernel()

            # Get client and start channels
            self.kc = self.km.client()
            self.kc.start_channels()

            # Wait for kernel to be ready
            self.kc.wait_for_ready(timeout=30)
            self.initialized = True
        except Exception as e:
            await self._cleanup()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize kernel: {str(e)}"
            )

    async def _cleanup(self):
        """Cleanup kernel"""
        if self.kc:
            self.kc.stop_channels()
        if self.km:
            self.km.shutdown_kernel()
            self.km = None
            self.kc = None
            self.initialized = False

    async def execute(self, module_path: str, var_name: str, method_type: str,
                      method_name: str, args: List[Any], kwargs: Dict[str, Any],
                      step_by_step: bool = False, kernel_id: Optional[str] = None) -> Any:
        """Execute a method asynchronously using Jupyter kernel"""
        if self.executor_type == "env":
            # Initialize kernel if needed
            await self._init_kernel()

            if not self.kc:
                raise HTTPException(
                    status_code=500,
                    detail="Kernel client not initialized"
                )

            # If kernel_id is provided, validate it exists
            if kernel_id and kernel_id not in self.active_kernels:
                raise HTTPException(
                    status_code=404,
                    detail=f"Kernel {kernel_id} not found"
                )

            # If continuing execution with existing kernel
            if kernel_id:
                stored_info = self.active_kernels[kernel_id]
                if (stored_info[0] != module_path or stored_info[1] != var_name or
                    stored_info[2] != method_name or stored_info[3] != args or
                        stored_info[4] != kwargs):
                    raise HTTPException(
                        status_code=400,
                        detail="Kernel parameters do not match original execution"
                    )

                # Execute next step
                script = """
result = next(workflow_iterator, None)
if result is None:
    print(json.dumps({'result': final_result.unwrap() if final_result else None, 'kernel_id': None}))
else:
    if isinstance(result, Result):
        if result.is_err():
            print(json.dumps({'error': str(result.error)}))
            sys.exit(0)
        final_result = result
        if final_result.is_ok():
            print(json.dumps({'result': final_result.unwrap(), 'kernel_id': None}))
        else:
            print(json.dumps({'result': result, 'kernel_id': current_kernel_id}))
    else:
        print(json.dumps({'result': result, 'kernel_id': current_kernel_id}))
"""
            else:
                # Prepare new execution code
                script = f"""
import json
import sys
import importlib.util
from pathlib import Path

# Import module
module_path = Path('{module_path}.py')
spec = importlib.util.spec_from_file_location(
    module_path.stem, str(module_path))
if not spec or not spec.loader:
    sys.exit(1)

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Get agent class and create instance
agent_class = getattr(module, '{var_name}')
agent = agent_class()

# Get method
method = getattr(agent, '_{method_type}')['{method_name}']

# Execute
try:
    # Import Result type
    from tool_agent_demo.core.result import Result

    # Parse arguments
    args = json.loads('''{json.dumps(args)}''')
    kwargs = json.loads('''{json.dumps(kwargs)}''')

    if '{method_type}' == 'workflows':
        # For workflows, handle step by step execution
        current_kernel_id = '{kernel_id if kernel_id else f"k{self._kernel_counter:02d}" + "".join(random.choices(string.ascii_lowercase, k=3))}'
        workflow_iterator = method(*args, **kwargs)
        final_result = None

        if {step_by_step}:
            # Get first result for step by step
            result = next(workflow_iterator)
            if isinstance(result, Result):
                if result.is_err():
                    print(json.dumps({{'error': str(result.error)}}))
                    sys.exit(0)
                final_result = result
                if final_result.is_ok():
                    print(json.dumps(
                        {{'result': final_result.unwrap(), 'kernel_id': None}}))
                else:
                    print(json.dumps(
                        {{'result': result, 'kernel_id': current_kernel_id}}))
            else:
                print(json.dumps(
                    {{'result': result, 'kernel_id': current_kernel_id}}))
        else:
            # Execute to completion
            results = []
            for result in workflow_iterator:
                if isinstance(result, Result):
                    if result.is_err():
                        print(json.dumps({{'error': str(result.error)}}))
                        sys.exit(0)
                    final_result = result
                else:
                    results.append(result)

            if final_result is not None:
                print(json.dumps({{'result': final_result.unwrap()}}))
            else:
                print(json.dumps({{'results': results}}))
    else:
        # For tools, get single result
        result = method(*args, **kwargs)
        if isinstance(result, Result):
            if result.is_err():
                print(json.dumps({{'error': str(result.error)}}))
                sys.exit(0)  # Use 0 to indicate expected error
            print(json.dumps({{'result': result.unwrap()}}))
        else:
            print(json.dumps({{'result': result}}))
except Exception as e:
    print(json.dumps({{'error': str(e)}}))
    sys.exit(1)  # Use 1 to indicate unexpected error
"""
            try:
                # Execute code
                msg_id = self.kc.execute(script)

                # Get output first
                output = None
                while True:
                    try:
                        msg = self.kc.get_iopub_msg(timeout=0.1)
                        if msg['msg_type'] == 'stream':
                            try:
                                output = json.loads(msg['content']['text'])
                                break
                            except json.JSONDecodeError:
                                continue
                        elif msg['msg_type'] == 'error':
                            await self._cleanup()
                            raise HTTPException(
                                status_code=500,
                                detail=f"Error in output: {
                                    msg['content']['evalue']}"
                            )
                    except queue.Empty:
                        if output is not None:
                            break
                        continue

                # Get execution result
                reply = self.kc.get_shell_msg(timeout=30)
                if reply['content']['status'] == 'error':
                    # If we have output, it might be an expected error
                    if output and 'error' in output:
                        return output

                    # Otherwise it's an unexpected error
                    await self._cleanup()
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error executing code: {
                            reply['content']['evalue']}"
                    )

                # Store kernel info if step by step execution
                if step_by_step and not kernel_id and 'kernel_id' in output:
                    self.active_kernels[output['kernel_id']] = (
                        module_path, var_name, method_name, args, kwargs
                    )
                    # Increment counter for next kernel
                    self._kernel_counter = (self._kernel_counter + 1) % 100

                # Clean up if execution is complete
                if kernel_id and (
                    'kernel_id' not in output or output['kernel_id'] is None
                ):
                    del self.active_kernels[kernel_id]

                return output
            except Exception as e:
                await self._cleanup()  # Cleanup on error
                raise HTTPException(
                    status_code=500,
                    detail=f"Execution failed: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported executor type: {self.executor_type}"
            )

    def __del__(self):
        """Cleanup when object is destroyed"""
        if self.km:
            self.km.shutdown_kernel(now=True)


# Store loaded executors
executors: Dict[str, AsyncExecutor] = {}


def get_executor_wrapper(executor_id: str) -> AsyncExecutor:
    """Get or create executor wrapper"""
    if executor_id in executors:
        return executors[executor_id]

    executor = get_executor(executor_id)
    if not executor:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {executor_id} not found"
        )

    wrapper = AsyncExecutor(executor.executor_type, executor.executor_path)
    executors[executor_id] = wrapper
    return wrapper
