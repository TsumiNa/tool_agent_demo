from typing import Any, Callable, Dict, TypeVar, cast, Generator
from functools import wraps
import ast
import inspect

from tool_agent_demo.result import Result

T = TypeVar('T', bound='Agent')
F = TypeVar('F', bound=Callable[..., Any])


class Agent:
    def __init__(self) -> None:
        """Initialize the Agent with empty tools and workflows collections."""
        self._tools: Dict[str, Callable] = {}
        self._workflows: Dict[str, Callable] = {}

        # Automatically collect decorated methods from the instance
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if hasattr(attr, '_is_tool'):
                self._tools[attr_name] = attr
            elif hasattr(attr, '_is_workflow'):
                self._workflows[attr_name] = attr

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

        def visit_Assign(self, node: ast.Assign) -> Any:
            # First visit any child nodes
            self.generic_visit(node)

            # If the value is a tool call or a BinOp (for |), wrap it in a yield
            if (isinstance(node.value, ast.Call) and self.is_tool_call(node.value)) or \
               (isinstance(node.value, ast.BinOp) and isinstance(node.value.op, ast.BitOr)):
                # Create a new assignment with the original value
                new_assign = ast.Assign(targets=node.targets, value=node.value)
                # Create a yield statement with the same value
                yield_stmt = ast.Expr(value=ast.Yield(
                    value=ast.Name(id=node.targets[0].id, ctx=ast.Load())))
                # Return both statements
                return [new_assign, yield_stmt]
            return node

        def visit_Return(self, node: ast.Return) -> Any:
            # First visit any child nodes
            self.generic_visit(node)

            # If returning a tool call, yield it first
            if isinstance(node.value, ast.Call) and self.is_tool_call(node.value):
                # Create a yield statement
                yield_stmt = ast.Expr(value=ast.Yield(value=node.value))
                # Return both statements
                return [yield_stmt, node]
            return node

        def is_tool_call(self, node: ast.Call) -> bool:
            """Check if a Call node represents a tool call."""
            return (isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and
                    node.func.value.id == 'self')

    @classmethod
    def workflow(cls, func: Callable) -> Callable:
        """
        Decorator to mark a method as a workflow and transform it into a generator
        that yields after each tool call.

        Args:
            func: The method to be marked as a workflow.

        Returns:
            The decorated method that yields after each tool call.
        """
        # Get the source code of the function
        source = inspect.getsource(func)

        # Remove common leading whitespace from every line
        source = inspect.cleandoc(source)

        # Remove the decorator line(s)
        source_lines = source.splitlines()
        while source_lines[0].lstrip().startswith('@'):
            source_lines.pop(0)
        source = '\n'.join(source_lines)

        # Parse the source into an AST
        tree = ast.parse(source)

        # Transform the AST
        transformer = cls.WorkflowTransformer()
        new_tree = transformer.visit(tree)

        # Fix line numbers
        ast.fix_missing_locations(new_tree)

        # Convert the modified AST back to source code
        new_source = ast.unparse(new_tree)

        # Create a new function from the modified source
        namespace = {}
        exec(new_source, func.__globals__, namespace)
        new_func = namespace[func.__name__]

        @wraps(new_func)
        def wrapper(self: T, *args: Any, **kwargs: Any) -> Generator[Any, None, Any]:
            return new_func(self, *args, **kwargs)

        # Mark the method as a workflow
        wrapper._is_workflow = True
        return wrapper
