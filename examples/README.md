# Tool Agent Demo Examples

这个目录包含了使用 tool_agent_demo 包的示例代码。这些示例展示了如何创建和使用工具代理(Agent)、定义工具(Tools)和工作流(Workflows)，以及处理错误和链式操作。

## 基础示例 (basic_example.py)

这个示例展示了工具代理的基本用法:

- 创建简单的计算器工具
- 使用 `@Agent.tool` 装饰器定义工具
- 使用 `@Agent.workflow` 装饰器定义工作流
- 基本的错误处理
- 工具的链式调用

运行示例:
```bash
python examples/basic_example.py
```

## 高级示例 (advanced_example.py)

这个示例展示了更高级的功能:

- 数据存储和检索
- 文本处理
- 数据验证
- 复杂的错误处理
- 多步骤工作流
- 链式操作

运行示例:
```bash
python examples/advanced_example.py
```

## 关键概念

### 1. 工具 (Tools)

工具是使用 `@Agent.tool` 装饰器定义的方法。每个工具都应该:
- 有清晰的文档字符串
- 返回一个具体的值
- 在出错时抛出异常

```python
@Agent.tool
def my_tool(self, param: str) -> str:
    """Tool description"""
    return processed_result
```

### 2. 工作流 (Workflows)

工作流使用 `@Agent.workflow` 装饰器定义，用于组合多个工具操作:
- 可以按顺序调用多个工具
- 使用 `unwrap()` 获取工具的返回值
- 可以包含错误处理逻辑

```python
@Agent.workflow
def my_workflow(self, input: str) -> str:
    result1 = self.tool1(input)
    result2 = self.tool2(result1.unwrap())
    return result2
```

### 3. 错误处理

使用 Result 类型进行错误处理:
- `is_ok()` - 检查是否成功
- `is_err()` - 检查是否有错误
- `unwrap()` - 获取结果值或抛出错误
- 使用 try/except 捕获特定异常

```python
result = agent.some_tool(input)
if result.is_ok():
    value = result.unwrap()
else:
    error = result.error
```

### 4. 链式操作

工具结果可以使用 `|` 操作符链式组合:
```python
result = (
    self.tool1(input)
    | self.tool2(param)
    | self.tool3()
)
```

## 最佳实践

1. 总是为工具和工作流提供清晰的文档字符串
2. 使用类型注解提高代码可读性
3. 实现适当的错误处理
4. 将复杂操作分解为多个工具
5. 使用工作流组合工具操作
6. 在需要时使用链式操作简化代码
