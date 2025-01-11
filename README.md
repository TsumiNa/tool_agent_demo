# Tool Agent Demo

一个用于构建工具代理的Python框架，支持工具定义、工作流组合和错误处理。

## 特性

- 🛠 工具定义：使用装饰器轻松定义工具方法
- 🔄 工作流组合：将多个工具组合成复杂的工作流
- ⚡ 链式操作：支持使用 | 操作符组合工具调用
- 🎯 错误处理：使用类似Rust的Result类型进行错误处理
- 📊 可视化：支持工作流图形可视化

## 安装

使用uv安装包：

```bash
uv add tool_agent_demo
```

## 基本用法

1. 创建一个Agent子类：

```python
from tool_agent_demo.agent import Agent
from tool_agent_demo.result import Result

class MyAgent(Agent):
    @Agent.tool
    def my_tool(self, param: str) -> str:
        """Tool description"""
        return processed_result

    @Agent.workflow
    def my_workflow(self, input: str) -> Result:
        result1 = self.tool1(input)
        if result1.is_err():
            return result1
        return self.tool2(result1.unwrap())
```

2. 使用工具和工作流：

```python
# 创建agent实例
agent = MyAgent()

# 使用单个工具
result = agent.my_tool("input")
if result.is_ok():
    print(result.unwrap())
else:
    print(f"Error: {result.error}")

# 使用工作流
for result in agent.my_workflow("input"):
    if result.is_err():
        print(f"Error in workflow: {result.error}")
        break
    final_result = result

if final_result.is_ok():
    print(f"Success: {final_result.unwrap()}")
```

## 示例

查看 [examples](examples/) 目录获取更多示例：

- [basic_example.py](examples/basic_example.py) - 基本工具和工作流使用
- [advanced_example.py](examples/advanced_example.py) - 高级功能和错误处理

## 错误处理

该框架使用类似Rust的Result类型进行错误处理：

```python
# 检查结果
if result.is_ok():
    value = result.unwrap()
else:
    error = result.error

# 链式调用中的错误处理
try:
    result = (
        self.tool1(input)
        | self.tool2()
        | self.tool3()
    )
    if result.is_ok():
        print(result.unwrap())
except Exception as e:
    print(f"Error in chain: {e}")
```

## 工作流可视化

可以使用str()函数查看Agent的工具和工作流信息：

```python
agent = MyAgent()
print(agent)  # 显示所有工具和工作流的结构
```

## 最佳实践

1. 为工具和工作流提供清晰的文档字符串
2. 使用类型注解提高代码可读性
3. 实现适当的错误处理
4. 将复杂操作分解为多个工具
5. 使用工作流组合工具操作
6. 在需要时使用链式操作简化代码

## 许可证

Apache-2.0
