from pydantic_ai import Agent, RunContext



def register_demo_tools(agent: Agent) -> None:
    """注册演示用途的简单工具。"""

    @agent.tool_plain
    def calculate(expression: str) -> str:
        """计算简单数学表达式，例如 1+2*3。"""
        allowed_chars = set('0123456789+-*/(). ')
        if not set(expression) <= allowed_chars:
            return '表达式包含不允许的字符，只支持数字和 + - * / ( )'

        try:
            result = eval(expression, {'__builtins__': {}}, {})
        except Exception as exc:
            return f'计算失败: {exc}'

        return f'{expression} = {result}'

    @agent.tool
    def show_context(ctx: RunContext[None]) -> str:
        """演示带上下文的工具，会读取 RunContext 中的 deps。"""
        return f'这是一个带上下文的工具示例，当前 deps = {ctx.deps!r}'