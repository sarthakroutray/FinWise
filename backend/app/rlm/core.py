"""Core RLM implementation."""

import asyncio
import re
from typing import Optional, Dict, Any, List

import requests
from google import genai

from .types import Message
from .repl import REPLExecutor, REPLError
from .prompts import build_system_prompt
from .parser import parse_response, is_final


class RLMError(Exception):
    """Base error for RLM."""
    pass


class MaxIterationsError(RLMError):
    """Max iterations exceeded."""
    pass


class MaxDepthError(RLMError):
    """Max recursion depth exceeded."""
    pass


class RLM:
    """
    Recursive Language Model.

    Enables LLMs to process unbounded context by storing it as a variable
    and allowing the model to recursively explore it via a Python REPL.

    Examples:
        # Basic usage
        rlm = RLM(model="gpt-4o-mini")
        result = rlm.complete(
            query="Summarize the key findings",
            context=long_document
        )

        # Two models for cost optimization
        rlm = RLM(
            model="gpt-4o",
            recursive_model="gpt-4o-mini"
        )

        # Async usage
        result = await rlm.acomplete(query, context)
    """

    def __init__(
        self,
        model: str,
        recursive_model: Optional[str] = None,
        provider: str = "gemini",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openrouter_base_url: str = "https://openrouter.ai/api/v1/chat/completions",
        openrouter_free_models: Optional[List[str]] = None,
        max_depth: int = 5,
        max_iterations: int = 30,
        _current_depth: int = 0,
        **llm_kwargs: Any
    ):
        """
        Initialize RLM.

        Args:
            model: Model name (e.g., "gemini-1.5-flash", "gemini-1.5-pro")
            recursive_model: Optional cheaper model for recursive calls
            api_base: Unused for Gemini SDK (kept for compatibility)
            api_key: Gemini API key (AI Studio)
            max_depth: Maximum recursion depth
            max_iterations: Maximum REPL iterations per call
            _current_depth: Internal current depth tracker
            **llm_kwargs: Additional generation parameters (temperature, max_tokens, etc.)
        """
        self.model = model
        self.recursive_model = recursive_model or model
        self.provider = (provider or "gemini").strip().lower()
        self.api_base = api_base
        self.api_key = api_key
        self.openrouter_api_key = openrouter_api_key
        self.openrouter_base_url = openrouter_base_url
        self.openrouter_free_models = openrouter_free_models or []
        self.max_depth = max_depth
        self.max_iterations = max_iterations
        self._current_depth = _current_depth
        self.llm_kwargs = llm_kwargs

        self.repl = REPLExecutor()

        # Stats
        self._llm_calls = 0
        self._iterations = 0

    def complete(
        self,
        query: str = "",
        context: str = "",
        **kwargs: Any
    ) -> str:
        """
        Synchronous completion — processes context recursively via REPL.

        Args:
            query: User query (optional if query is in context)
            context: Context to process (optional, can pass query here)
            **kwargs: Additional generation parameters

        Returns:
            Final answer string

        Examples:
            # Standard usage
            rlm.complete(query="Summarize this", context=document)

            # Query in context (RLM will extract task)
            rlm.complete(context="Summarize this document: ...")

            # Single string (treated as context)
            rlm.complete("Process this text and extract dates")
        """
        # If only one argument provided, treat it as context
        if query and not context:
            context = query
            query = ""

        return asyncio.run(self.acomplete(query, context, **kwargs))

    async def acomplete(
        self,
        query: str = "",
        context: str = "",
        **kwargs: Any
    ) -> str:
        """
        Async completion — main entry point for recursive context processing.

        The LLM iteratively writes Python code to explore the context,
        and returns its final answer via FINAL("answer").

        Args:
            query: User query (optional if query is in context)
            context: Context to process (optional, can pass query here)
            **kwargs: Additional generation parameters

        Returns:
            Final answer string

        Raises:
            MaxIterationsError: If max iterations exceeded
            MaxDepthError: If max recursion depth exceeded
        """
        # If only query provided, treat it as context
        if query and not context:
            context = query
            query = ""

        if self._current_depth >= self.max_depth:
            raise MaxDepthError(f"Max recursion depth ({self.max_depth}) exceeded")

        # Initialize REPL environment
        repl_env = self._build_repl_env(query, context)

        # Auto-Schema Discovery (Peek)
        peek_result = self._auto_peek(context, repl_env)

        # Build initial messages
        system_prompt = build_system_prompt(len(context), self._current_depth)
        messages: List[Message] = [
            {"role": "system", "content": system_prompt},
        ]
        
        if peek_result:
            messages.append({"role": "system", "content": f"Initial context scan results:\n{peek_result}"})
            
        messages.append({"role": "user", "content": query})

        # Main REPL loop
        for iteration in range(self.max_iterations):
            self._iterations = iteration + 1

            # Call LLM
            response = await self._call_llm(messages, **kwargs)

            # Check for FINAL
            if is_final(response):
                answer = parse_response(response, repl_env)
                if answer is not None:
                    return answer

            # Execute code in REPL with Self-Healing Logic
            try:
                exec_result = self.repl.execute(response, repl_env)
                # Add successful execution to conversation
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": exec_result})
            except REPLError as e:
                # SELF-HEALING: Feed the error back to the LLM
                error_msg = f"Error: Your Python code failed.\nTraceback:\n{str(e)}\n\nPlease fix the error and try again."
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": error_msg})
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content": error_msg})

        raise MaxIterationsError(
            f"Max iterations ({self.max_iterations}) exceeded without FINAL()"
        )

    async def _call_llm(
        self,
        messages: List[Message],
        **kwargs: Any
    ) -> str:
        """
        Call configured LLM provider API.

        Args:
            messages: Conversation messages
            **kwargs: Additional parameters (can override model here)

        Returns:
            LLM response text
        """
        self._llm_calls += 1

        # Choose model based on depth (root uses main model, recursions use cheaper model)
        default_model = self.model if self._current_depth == 0 else self.recursive_model

        # Allow override via kwargs
        model = kwargs.pop('model', default_model)
        provider = (kwargs.pop('provider', self.provider) or self.provider).strip().lower()

        # Merge kwargs
        call_kwargs = {**self.llm_kwargs, **kwargs}
        if provider == "gemini":
            return await self._call_gemini(model=model, messages=messages, call_kwargs=call_kwargs)
        if provider == "openrouter":
            return await self._call_openrouter(model=model, messages=messages, call_kwargs=call_kwargs)

        raise RLMError(f"Unsupported RLM provider: {provider}")

    async def _call_gemini(self, model: str, messages: List[Message], call_kwargs: Dict[str, Any]) -> str:
        """Execute a Gemini completion call."""
        if not self.api_key:
            raise RLMError("GEMINI_API_KEY is missing. Set it in your .env to use Gemini RLM.")

        prompt = self._messages_to_prompt(messages)
        generation_config = self._build_generation_config(call_kwargs, provider="gemini")

        def _invoke() -> str:
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=generation_config or None,
            )
            return self._extract_response_text(response)

        return await asyncio.to_thread(_invoke)

    async def _call_openrouter(self, model: str, messages: List[Message], call_kwargs: Dict[str, Any]) -> str:
        """Execute an OpenRouter chat completions call."""
        api_key = self.openrouter_api_key or self.api_key
        if not api_key:
            raise RLMError("OPENROUTER_API_KEY is missing. Set it in your .env to use OpenRouter RLM.")

        payload: Dict[str, Any] = {
            "model": model,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        payload.update(self._build_generation_config(call_kwargs, provider="openrouter"))

        free_models = call_kwargs.get("free_models") or self.openrouter_free_models
        if free_models:
            payload["models"] = [m for m in free_models if m]
            payload["route"] = "fallback"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        def _invoke() -> str:
            response = requests.post(self.openrouter_base_url, headers=headers, json=payload, timeout=60)
            if response.status_code >= 400:
                raise RLMError(f"OpenRouter error {response.status_code}: {response.text[:400]}")
            data = response.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RLMError("OpenRouter returned an unexpected response format.") from exc

            if isinstance(content, str):
                return content
            if isinstance(content, list):
                chunks = [part.get("text", "") for part in content if isinstance(part, dict)]
                text = "\n".join([c for c in chunks if c])
                if text:
                    return text
            raise RLMError("OpenRouter returned empty content.")

        return await asyncio.to_thread(_invoke)

    def _messages_to_prompt(self, messages: List[Message]) -> str:
        """Flatten chat history into a Gemini-friendly text prompt."""
        lines: List[str] = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            lines.append(f"{role}: {content}")
        lines.append("ASSISTANT:")
        return "\n\n".join(lines)

    def _build_generation_config(self, kwargs: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """Map generic kwargs to provider-specific generation config keys."""
        generation_config: Dict[str, Any] = {}
        if "temperature" in kwargs:
            generation_config["temperature"] = kwargs["temperature"]

        if provider == "gemini":
            if "max_tokens" in kwargs:
                generation_config["max_output_tokens"] = kwargs["max_tokens"]
            elif "max_output_tokens" in kwargs:
                generation_config["max_output_tokens"] = kwargs["max_output_tokens"]
        else:
            if "max_tokens" in kwargs:
                generation_config["max_tokens"] = kwargs["max_tokens"]
            elif "max_output_tokens" in kwargs:
                generation_config["max_tokens"] = kwargs["max_output_tokens"]

        if "top_p" in kwargs:
            generation_config["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            generation_config["top_k"] = kwargs["top_k"]
        return generation_config

    def _extract_response_text(self, response: Any) -> str:
        """Extract plain text from Gemini response object."""
        text = getattr(response, "text", None)
        if text:
            return text

        candidates = getattr(response, "candidates", None) or []
        chunks: List[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)

        if chunks:
            return "\n".join(chunks)
        raise RLMError("Gemini returned no text content.")

    def _auto_peek(self, context: str, env: Dict[str, Any]) -> Optional[str]:
        """
        Automatically 'peek' at the context to understand its schema.
        This helps the AI understand the columns and data types before it starts.
        """
        if not context or len(context) < 10:
            return None
            
        # Quick script to summarize context if it looks like a CSV/Table
        peek_script = """
# Auto-generated peek script
lines = context.strip().split('\\n')
if len(lines) > 0:
    header = lines[0]
    print(f"Header/Columns: {header}")
    if len(lines) > 1:
        print(f"Sample Row: {lines[1]}")
    print(f"Total Rows: {len(lines)}")
"""
        try:
            return self.repl.execute(f"```python\\n{peek_script}\\n```", env)
        except:
            return "Failed to auto-scan context. Proceed with manual exploration."

    def _build_repl_env(self, query: str, context: str) -> Dict[str, Any]:
        """
        Build REPL environment with context, query, and recursive_llm.

        Args:
            query: User query
            context: Context string

        Returns:
            Environment dict
        """
        env: Dict[str, Any] = {
            'context': context,
            'query': query,
            'recursive_llm': self._make_recursive_fn(),
            're': re,  # Whitelist re module
        }
        return env

    def _make_recursive_fn(self) -> Any:
        """
        Create recursive LLM function for use inside the REPL.

        Returns a synchronous function that spawns a child RLM at depth+1,
        allowing the model to recursively process sub-sections of the context.

        Returns:
            Sync function callable from REPL
        """
        async def recursive_llm(sub_query: str, sub_context: str) -> str:
            """
            Recursively process sub-context.

            Args:
                sub_query: Query for sub-context
                sub_context: Sub-context to process

            Returns:
                Answer from recursive call
            """
            if self._current_depth + 1 >= self.max_depth:
                return f"Max recursion depth ({self.max_depth}) reached"

            # Create sub-RLM with increased depth
            sub_rlm = RLM(
                model=self.recursive_model,
                recursive_model=self.recursive_model,
                provider=self.provider,
                api_base=self.api_base,
                api_key=self.api_key,
                openrouter_api_key=self.openrouter_api_key,
                openrouter_base_url=self.openrouter_base_url,
                openrouter_free_models=self.openrouter_free_models,
                max_depth=self.max_depth,
                max_iterations=self.max_iterations,
                _current_depth=self._current_depth + 1,
                **self.llm_kwargs
            )

            return await sub_rlm.acomplete(sub_query, sub_context)

        # Wrap in sync function for REPL compatibility
        def sync_recursive_llm(sub_query: str, sub_context: str) -> str:
            """Sync wrapper for recursive_llm."""
            # Check if we're in an async context
            try:
                loop = asyncio.get_running_loop()
                # We're in async context, but REPL is sync
                # Create a new thread to run async code
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        recursive_llm(sub_query, sub_context)
                    )
                    return future.result()
            except RuntimeError:
                # No running loop, safe to use asyncio.run
                return asyncio.run(recursive_llm(sub_query, sub_context))

        return sync_recursive_llm

    @property
    def stats(self) -> Dict[str, int]:
        """Get execution statistics."""
        return {
            'llm_calls': self._llm_calls,
            'iterations': self._iterations,
            'depth': self._current_depth,
        }
