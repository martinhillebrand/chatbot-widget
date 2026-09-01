# Chatbot Widget

`ChatMCPController` works with any OpenAI-compatible chat-completions endpoint.
Pass the provider's model name unchanged and, for a non-OpenAI provider, its API
base URL. The selected model must support tool calling to use MCP tools.

```python
from chatbot_widget.controller.chat_mcp_controller import ChatMCPController

controller = ChatMCPController(
	mcp_server_manager,
	model="openai/gpt-4.1-mini",
	base_url="http://localhost:4000/v1",  # LiteLLM proxy
	api_key="your-proxy-api-key",
)
```

For OpenRouter, use its OpenAI-compatible endpoint and a provider-qualified model
name:

```python
controller = ChatMCPController(
	mcp_server_manager,
	model="anthropic/claude-sonnet-4",
	base_url="https://openrouter.ai/api/v1",
	api_key="your-openrouter-api-key",
)
```

`api_key` is optional. When omitted, LangChain reads `OPENAI_API_KEY` from the
environment. Omitting `base_url` uses the official OpenAI API.
