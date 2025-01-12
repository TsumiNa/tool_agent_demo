from typing import Dict, List, Any, Optional, Set, Union
import ast
from pydantic import BaseModel, Field


class Port(BaseModel):
    id: str = Field(description="端口ID，格式：node_id:input/output:index")
    name: str = Field(description="变量名或字面量值")


class Node(BaseModel):
    id: str = Field(description="节点ID")
    type: str = Field(description="函数名")
    inputs: List[Port] = Field(description="输入端口列表")
    outputs: List[Port] = Field(description="输出端口列表")
    position: Dict[str, int] = Field(description="节点位置")


class Edge(BaseModel):
    id: str = Field(description="边ID")
    source: str = Field(description="源端口ID (node_id:output:index)")
    target: str = Field(description="目标端口ID (node_id:input:index)")


class WorkflowGraph(BaseModel):
    nodes: List[Node] = Field(description="工作流中的所有节点")
    edges: List[Edge] = Field(description="工作流中的所有边")


class WorkflowSerializer:
    """Serializes and deserializes workflows to/from React Flow compatible format"""

    @staticmethod
    def serialize_workflow(source_code: str) -> WorkflowGraph:
        """Convert workflow source code to nodes and edges"""
        # Parse the source into an AST
        tree = ast.parse(source_code)

        # 分析变量依赖关系
        analyzer = WorkflowSerializer.DependencyAnalyzer()
        analyzer.visit(tree)

        nodes: List[Node] = []
        edges: List[Edge] = []
        node_counter = 0
        edge_counter = 0

        # 创建函数调用节点
        for func_call in analyzer.function_calls:
            node_id = f"node_{node_counter}"
            node_counter += 1

            # 收集输入和输出端口
            inputs = []
            for i, arg in enumerate(func_call.args):
                port_id = f"{node_id}:input:{i}"
                if isinstance(arg, ast.Name):
                    inputs.append(Port(id=port_id, name=arg.id))
                elif isinstance(arg, ast.Constant):
                    inputs.append(Port(id=port_id, name=repr(arg.value)))

            outputs = []
            if func_call.target:
                port_id = f"{node_id}:output:0"
                outputs.append(Port(id=port_id, name=func_call.target))

            # 创建节点
            nodes.append(Node(
                id=node_id,
                type=func_call.func_name,
                inputs=inputs,
                outputs=outputs,
                position={"x": 100 + node_counter * 200, "y": 100}
            ))

            # 创建边
            for input_port in inputs:
                # 如果是字面量值，跳过创建边
                if input_port.name.startswith('"') or input_port.name.startswith("'"):
                    continue

                # 查找产生这个输入变量的节点
                for other_node in nodes[:-1]:  # 不包括当前节点
                    for output_port in other_node.outputs:
                        if output_port.name == input_port.name:
                            edges.append(Edge(
                                id=f"edge_{edge_counter}",
                                source=output_port.id,
                                target=input_port.id
                            ))
                            edge_counter += 1

        return WorkflowGraph(nodes=nodes, edges=edges)

    @staticmethod
    def to_json(graph: WorkflowGraph) -> str:
        """Convert workflow graph to JSON string

        Args:
            graph: The workflow graph to serialize

        Returns:
            JSON string representation of the workflow graph
        """
        return graph.model_dump_json(indent=2)

    @staticmethod
    def from_json(json_str: str) -> WorkflowGraph:
        """Create workflow graph from JSON string

        Args:
            json_str: JSON string representation of a workflow graph

        Returns:
            WorkflowGraph instance created from the JSON
        """
        return WorkflowGraph.model_validate_json(json_str)

    @staticmethod
    def deserialize_workflow(graph: WorkflowGraph) -> str:
        """Convert nodes and edges back to workflow code"""
        # 构建变量依赖图
        input_vars: Dict[str, str] = {}  # port_id -> var_name
        output_vars: Dict[str, str] = {}  # port_id -> var_name
        # node_id -> {dependent_node_ids}
        dependencies: Dict[str, Set[str]] = {}

        # 收集所有端口的变量名
        for node in graph.nodes:
            for port in node.inputs:
                input_vars[port.id] = port.name
            for port in node.outputs:
                output_vars[port.id] = port.name

        # 构建节点依赖关系
        for edge in graph.edges:
            source_node_id = edge.source.split(':')[0]
            target_node_id = edge.target.split(':')[0]
            if target_node_id not in dependencies:
                dependencies[target_node_id] = set()
            dependencies[target_node_id].add(source_node_id)

        # 按依赖顺序生成代码
        code_lines = []
        processed = set()

        def process_node(node_id: str) -> None:
            if node_id in processed:
                return

            node = next(n for n in graph.nodes if n.id == node_id)

            # 先处理依赖的节点
            if node_id in dependencies:
                for dep_id in dependencies[node_id]:
                    process_node(dep_id)

            # 生成函数调用代码
            args = []
            for input_port in node.inputs:
                # 如果是字面量值，直接使用，否则使用变量名
                if input_port.name.startswith('"') or input_port.name.startswith("'"):
                    args.append(input_port.name)
                else:
                    args.append(input_vars[input_port.id])

            if node.outputs:
                output_var = output_vars[node.outputs[0].id]
                code_lines.append(
                    f"{output_var} = self.{node.type}({', '.join(args)})")
            else:
                code_lines.append(f"self.{node.type}({', '.join(args)})")

            processed.add(node_id)

        # 处理所有节点
        for node in graph.nodes:
            process_node(node.id)

        return '\n'.join(code_lines)

    class DependencyAnalyzer(ast.NodeVisitor):
        """分析AST中的函数调用和变量依赖关系"""

        class FunctionCall(BaseModel):
            func_name: str = Field(description="函数名称")
            args: List[ast.expr] = Field(description="函数参数列表")
            target: Optional[str] = Field(default=None, description="赋值目标变量名")

            model_config = {
                "arbitrary_types_allowed": True
            }

        def __init__(self):
            self.function_calls: List[WorkflowSerializer.DependencyAnalyzer.FunctionCall] = [
            ]

        def visit_Assign(self, node: ast.Assign) -> None:
            if isinstance(node.value, ast.Call):
                # 获取目标变量名
                target = node.targets[0].id if isinstance(
                    node.targets[0], ast.Name) else None

                # 获取函数名
                if isinstance(node.value.func, ast.Attribute) and \
                   isinstance(node.value.func.value, ast.Name) and \
                   node.value.func.value.id == 'self':
                    func_name = node.value.func.attr
                    self.function_calls.append(
                        self.FunctionCall(
                            func_name=func_name,
                            args=node.value.args,
                            target=target
                        ))

            self.generic_visit(node)

        def visit_Expr(self, node: ast.Expr) -> None:
            if isinstance(node.value, ast.Call):
                # 获取函数名
                if isinstance(node.value.func, ast.Attribute) and \
                   isinstance(node.value.func.value, ast.Name) and \
                   node.value.func.value.id == 'self':
                    func_name = node.value.func.attr
                    self.function_calls.append(
                        self.FunctionCall(
                            func_name=func_name,
                            args=node.value.args
                        ))

            self.generic_visit(node)

        def visit_Return(self, node: ast.Return) -> None:
            if isinstance(node.value, ast.Call):
                # 获取函数名
                if isinstance(node.value.func, ast.Attribute) and \
                   isinstance(node.value.func.value, ast.Name) and \
                   node.value.func.value.id == 'self':
                    func_name = node.value.func.attr
                    self.function_calls.append(
                        self.FunctionCall(
                            func_name=func_name,
                            args=node.value.args
                        ))

            self.generic_visit(node)
