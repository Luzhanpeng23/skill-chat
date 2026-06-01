import threading


class TokenTracker:
    def __init__(self):
        self.lock = threading.Lock()
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.successful_calls = 0

    def add_usage(self, response):
        """从 LangChain 的响应对象中提取 token 使用情况，并记录成功调用次数"""
        input_t = 0
        output_t = 0
        total_t = 0

        # 处理不同版本和提供商的元数据格式
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_t = response.usage_metadata.get("input_tokens", 0)
            output_t = response.usage_metadata.get("output_tokens", 0)
            total_t = response.usage_metadata.get("total_tokens", 0)
        elif (
            hasattr(response, "response_metadata")
            and "token_usage" in response.response_metadata
        ):
            usage = response.response_metadata["token_usage"]
            input_t = usage.get("prompt_tokens", 0)
            output_t = usage.get("completion_tokens", 0)
            total_t = usage.get("total_tokens", 0)

        with self.lock:
            self.input_tokens += input_t
            self.output_tokens += output_t
            self.total_tokens += total_t
            self.successful_calls += 1

    def get_stats(self):
        with self.lock:
            return {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.total_tokens,
                "successful_calls": self.successful_calls,
            }

    def print_summary(self):
        stats = self.get_stats()
        print("\n" + "=" * 50)
        print("API 消耗统计 (Token Tracker)")
        # print("=" * 50)
        print(f"成功调用次数 (Calls):     {stats['successful_calls']:,}")
        print(f"输入 Tokens (Prompt):     {stats['input_tokens']:,}")
        print(f"输出 Tokens (Completion): {stats['output_tokens']:,}")
        print(f"总计 Tokens (Total):      {stats['total_tokens']:,}")
        print("=" * 50 + "\n")


# 全局单例
token_tracker = TokenTracker()
