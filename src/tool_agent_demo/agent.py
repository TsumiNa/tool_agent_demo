from typing import Any, Callable, Dict, TypeVar, cast, Generator, Optional
from functools import wraps, partial
import ast
import inspect

from tool_agent_demo.result import Result
from tool_agent_demo.workflow_serializer import WorkflowSerializer, WorkflowGraph

T = TypeVar('T', bound='Agent')
F = TypeVar('F', bound=Callable[..., Any])


class DeserializationError(Exception):
    """Error raised when workflow deserialization fails"""
    pass


class Agent:
    def __init__(self) -> None:
        """Initialize the Agent with empty tools and workflows collections."""
        self._tools: Dict[str, Callable] = {}
        self._workflows: Dict[str, Callable] = {}
        # Store workflow source code
        self._workflow_sources: Dict[str, str] = {}

        # Automatically collect decorated methods from the instance
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_is_tool'):
                self._tools[attr_name] = attr
            elif hasattr(attr, '_is_workflow'):
                self._workflows[attr_name] = attr
                # Store source code for workflow methods
                if hasattr(attr, '__wrapped__'):
                    source = inspect.getsource(attr.__wrapped__)
                    source = inspect.cleandoc(source)
                    source_lines = source.splitlines()
                    while source_lines[0].lstrip().startswith('@'):
                        source_lines.pop(0)
                    self._workflow_sources[attr_name] = '\n'.join(source_lines)

    def __str__(self) -> str:
        """Custom string representation of the Agent showing tools and workflows."""
        output = []

        # Display tools
        output.append("Tools:")
        for tool_name in sorted(self._tools.keys()):
            tool = self._tools[tool_name]
            # Get the tool's docstring if available
            doc = inspect.getdoc(tool) or "No description available"
            # Get the first line of the docstring
            doc_first_line = doc.split('\n')[0]
            output.append(f"  - {tool_name}: {doc_first_line}")

        # Display workflows
        if self._workflows:
            output.append("\nWorkflows:")
            for workflow_name in sorted(self._workflows.keys()):
                output.append(f"\n  {workflow_name}:")
                # Get the workflow graph
                graph = self.get_workflow_graph(workflow_name)
                if graph:
                    # Display nodes
                    output.append("    Nodes:")
                    for node in graph.nodes:
                        inputs_str = " ".join(p.name for p in node.inputs)
                        # For the last node, show [return] as output
                        is_last_node = node == graph.nodes[-1]
                        outputs_str = "[return]" if is_last_node else " ".join(
                            p.name for p in node.outputs)
                        output.append(
                            f"      - {node.type} (inputs: {inputs_str} outputs: {outputs_str})")

                    # Display edges
                    output.append("    Edges:")
                    for edge in graph.edges:
                        source_parts = edge.source.split(':')
                        target_parts = edge.target.split(':')
                        source_node = next(
                            n for n in graph.nodes if n.id == source_parts[0])
                        target_node = next(
                            n for n in graph.nodes if n.id == target_parts[0])
                        output.append(
                            f"      - {source_node.type} -> {target_node.type}")
                else:
                    output.append("    (No graph available)")

        return "\n".join(output)

    @classmethod
    def tool(cls, func: Callable) -> Callable:
        """
        Decorator to mark a method as a tool.

        Args:
            func: The method to be marked as a tool.

        Returns:
            The decorated method.
        """
        @wraps(func)
        def wrapper(self: T, *args: Any, **kwargs: Any) -> Result[Any]:
            try:
                # 检查参数中是否有Result类型
                for arg in args:
                    if isinstance(arg, Result):
                        if arg.is_err():
                            return arg
                        args = (*args[:args.index(arg)],
                                arg.unwrap(), *args[args.index(arg) + 1:])

                for key, value in kwargs.items():
                    if isinstance(value, Result):
                        if value.is_err():
                            return value
                        kwargs[key] = value.unwrap()

                result = func(self, *args, **kwargs)
                return Result(value=result)
            except Exception as e:
                return Result(error=e)

        # Mark the method as a tool
        wrapper._is_tool = True
        return cast(F, wrapper)

    class WorkflowTransformer(ast.NodeTransformer):
        """AST transformer that adds yield statements after tool calls."""

        def __init__(self, tools: Dict[str, Callable]):
            self.tools = tools

        def visit_Call(self, node: ast.Call) -> Any:
            """Visit Call nodes to identify tool calls."""
            self.generic_visit(node)
            if self.is_tool_call(node):
                node._is_tool_call = True
            return node

        def visit_Assign(self, node: ast.Assign) -> Any:
            # First visit any child nodes (this will mark tool calls)
            self.generic_visit(node)

            # If the value is a BinOp (for |), wrap it in a yield
            if isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.BitOr):
                # Create a new assignment with the original value
                new_assign = ast.Assign(targets=node.targets, value=node.value)
                # Create a yield statement with the same value
                yield_stmt = ast.Expr(value=ast.Yield(
                    value=ast.Name(id=node.targets[0].id, ctx=ast.Load())))
                # Return both statements
                return [new_assign, yield_stmt]
            # If the value is a tool call (marked during visit_Call), wrap it in a yield
            elif isinstance(node.value, ast.Call) and hasattr(node.value, '_is_tool_call'):
                # Create a new assignment with the original value
                new_assign = ast.Assign(targets=node.targets, value=node.value)
                # Create a yield statement with the same value
                yield_stmt = ast.Expr(value=ast.Yield(
                    value=ast.Name(id=node.targets[0].id, ctx=ast.Load())))
                # Return both statements
                return [new_assign, yield_stmt]
            return node

        def visit_Return(self, node: ast.Return) -> Any:
            # First visit any child nodes (this will mark tool calls)
            self.generic_visit(node)

            # If returning a tool call (marked during visit_Call), yield it first
            if isinstance(node.value, ast.Call) and hasattr(node.value, '_is_tool_call'):
                # Create a yield statement
                yield_stmt = ast.Expr(value=ast.Yield(value=node.value))
                # Return both statements
                return [yield_stmt, node]
            return node

        def is_tool_call(self, node: ast.Call) -> bool:
            """Check if a Call node represents a tool call."""
            if not (isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'self'):
                return False

            # Get the method name
            method_name = node.func.attr

            # Check if it's a tool method
            return method_name in self.tools

    def get_workflow_graph(self, workflow_name: str) -> Optional[WorkflowGraph]:
        """Get the workflow graph for visualization"""
        if workflow_name not in self._workflow_sources:
            return None
        return WorkflowSerializer.serialize_workflow(self._workflow_sources[workflow_name])

    def update_workflow_from_graph(self, workflow_name: str, graph: WorkflowGraph) -> None:
        """Update a workflow from a modified graph"""
        if workflow_name not in self._workflows:
            raise ValueError(f"Workflow {workflow_name} not found")

        # 验证所有工具都存在
        missing_tools = []
        for node in graph.nodes:
            if node.type not in self._tools:
                missing_tools.append(node.type)

        if missing_tools:
            raise DeserializationError(
                f"The following tools are not available: {', '.join(missing_tools)}")

        # Generate new source code
        code_body = WorkflowSerializer.deserialize_workflow(graph)

        # Create function definition with proper indentation
        indented_body = "\n".join(
            f"    {line}" for line in code_body.splitlines())
        new_source = f"""def {workflow_name}(self):
{indented_body}"""

        # Parse into AST and transform
        tree = ast.parse(new_source)
        transformer = self.WorkflowTransformer(self._tools)
        new_tree = transformer.visit(tree)
        ast.fix_missing_locations(new_tree)

        # Convert back to source
        transformed_source = ast.unparse(new_tree)

        # Store the new source
        self._workflow_sources[workflow_name] = transformed_source

        # Print debug info
        print("Generated source code:")
        print(transformed_source)

        # Compile and execute
        code = compile(transformed_source,
                       f"<workflow {workflow_name}>", "exec")
        namespace = {}
        exec(code, self._workflows[workflow_name].__globals__, namespace)
        new_func = namespace[workflow_name]

        # Add workflow marker and bind to instance
        new_func._is_workflow = True
        bound_method = partial(new_func, self)
        bound_method._is_workflow = True
        self._workflows[workflow_name] = bound_method

    @staticmethod
    def workflow(func: Callable) -> Callable:
        """
        Decorator to mark a method as a workflow and transform it into a generator
        that yields after each tool call.

        Args:
            func: The method to be marked as a workflow.

        Returns:
            The decorated method that yields after each tool call.
        """
        @wraps(func)
        def wrapper(self: T, *args: Any, **kwargs: Any) -> Generator[Any, None, Any]:
            # Get the source code from the workflow sources if available
            if hasattr(func, '__name__') and func.__name__ in self._workflow_sources:
                source = self._workflow_sources[func.__name__]
            else:
                # Get from function object for initial decoration
                source = inspect.getsource(func)
                source = inspect.cleandoc(source)
                source_lines = source.splitlines()
                while source_lines[0].lstrip().startswith('@'):
                    source_lines.pop(0)
                source = '\n'.join(source_lines)

            # Parse the source into an AST
            tree = ast.parse(source)

            # Transform the AST with access to instance tools
            transformer = Agent.WorkflowTransformer(self._tools)
            new_tree = transformer.visit(tree)

            # Fix line numbers
            ast.fix_missing_locations(new_tree)

            # Convert the modified AST back to source code
            new_source = ast.unparse(new_tree)

            # Create a new function from the modified source
            namespace = {}
            exec(new_source, func.__globals__, namespace)
            new_func = namespace[func.__name__]

            # Call the transformed function
            return new_func(self, *args, **kwargs)

        # Mark the method as a workflow
        wrapper._is_workflow = True
        return wrapper

    def to_json(self, file_path: Optional[str] = None) -> str:
        """
        Convert Agent's tools and workflows information to JSON format.

        Args:
            file_path: Optional path to save the JSON output to a file.

        Returns:
            A JSON string containing the Agent's tools and workflows information.
        """
        import json

        data = {
            "tools": {},
            "workflows": {}
        }

        # Collect tools information
        for tool_name, tool in self._tools.items():
            doc = inspect.getdoc(tool) or "No description available"
            sig = inspect.signature(tool)
            data["tools"][tool_name] = {
                "description": doc,
                "parameters": {
                    name: param.annotation.__name__ if hasattr(param.annotation, '__name__') else str(param.annotation) for name, param in sig.parameters.items()
                    if name != 'self'
                }
            }

        # Collect workflows information
        for workflow_name in self._workflows:
            graph = self.get_workflow_graph(workflow_name)
            if graph:
                data["workflows"][workflow_name] = {
                    "source": self._workflow_sources[workflow_name],
                    "graph": {
                        "nodes": [
                            {
                                "id": node.id,
                                "type": node.type,
                                "inputs": [{"name": p.name, "type": p.type} for p in node.inputs],
                                "outputs": [{"name": p.name, "type": p.type} for p in node.outputs]
                            } for node in graph.nodes
                        ],
                        "edges": [
                            {
                                "source": edge.source,
                                "target": edge.target
                            } for edge in graph.edges
                        ]
                    }
                }

        json_str = json.dumps(data, indent=2)

        if file_path:
            with open(file_path, 'w') as f:
                f.write(json_str)

        return json_str
