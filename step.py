from openai import OpenAI
import sys

# 初始化客户端（建议将 API Key 和配置改为环境变量，这里为了演示直接写入）
client = OpenAI(
    api_key="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",
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "https://your-site.com",  # 替换为你的网址（可选）
        "X-Title": "My AI Chat",  # 替换为你的应用名（可选）
    }
)

# 系统提示词（可自定义）
system_prompt = "你是阶跃星辰（StepFun）提供的AI聊天助手。你擅长中文、英文等多种语言。"

# 存储对话历史
messages = [{"role": "system", "content": system_prompt}]

print("=" * 50)
print("🤖 StepFun AI 对话助手（输入 'exit'、'quit' 或 '退出' 结束对话）")
print("=" * 50)

while True:
    try:
        # 1. 获取用户输入
        user_input = input("\n👤 你：").strip()

        # 2. 检查退出命令
        if user_input.lower() in ["exit", "quit", "退出", "q"]:
            print("👋 再见！")
            break

        # 3. 如果输入为空，跳过
        if not user_input:
            continue

        # 4. 将用户输入添加到历史
        messages.append({"role": "user", "content": user_input})

        # 5. 调用模型（流式）
        print("🤖 助手：", end="", flush=True)

        stream = client.chat.completions.create(
            model="stepfun/step-3.5-flash:free",
            messages=messages,
            stream=True,
            max_tokens=1000,  # 根据需求调整
            timeout=60  # 设置超时，避免长时间等待
        )

        # 6. 逐块接收并打印内容
        full_response = ""
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content

        print()  # 换行

        # 7. 将助手回复添加到历史（保持上下文）
        messages.append({"role": "assistant", "content": full_response})

        # 可选：限制历史长度，避免 token 超限（例如保留最近 10 轮对话）
        if len(messages) > 20:  # system + 10轮对话（每轮2条）
            messages = [messages[0]] + messages[-20:]

    except KeyboardInterrupt:
        print("\n\n👋 检测到中断，退出对话。")
        sys.exit(0)
    except Exception as e:
        # 处理常见错误
        error_msg = str(e)
        if "quota_exceeded" in error_msg or "402" in error_msg:
            print("\n❌ 错误：API 配额已用尽，请检查 OpenRouter 账户余额或更换 API Key。")
        elif "invalid_api_key" in error_msg or "401" in error_msg:
            print("\n❌ 错误：API Key 无效，请检查配置。")
        elif "model" in error_msg.lower() and "not found" in error_msg.lower():
            print("\n❌ 错误：模型不存在或不可用，请检查模型名称。")
        else:
            print(f"\n❌ 发生错误：{e}")

        # 错误后是否继续？可以询问用户
        retry = input("是否继续？(y/n): ").strip().lower()
        if retry != "y":
            print("👋 再见！")
            break