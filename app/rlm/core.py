"""Core RLM implementation."""

import asyncio
import re
from typing import Optional, Dict, Any, List

import litellm

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
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        max_depth: int = 5,
        max_iterations: int = 30,
        _current_depth: int = 0,
        **llm_kwargs: Any
    ):
        """
        Initialize RLM.

        Args:
            model: Model name (e.g., "gpt-4o", "claude-sonnet-4", "ollama/llama3.2")
            recursive_model: Optional cheaper model for recursive calls
            api_base: Optional API base URL
            api_key: Optional API key
            max_depth: Maximum recursion depth
            max_iterations: Maximum REPL iterations per call
            _current_depth: Internal current depth tracker
            **llm_kwargs: Additional LiteLLM parameters (temperature, timeout, etc.)
        """
        self.model = model
        self.recursive_model = recursive_model or model
        self.api_base = api_base
        self.api_key = api_key
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
            **kwargs: Additional LiteLLM parameters

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
            **kwargs: Additional LiteLLM parameters

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
        Call LLM API via LiteLLM.

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

        # Merge kwargs
        call_kwargs = {**self.llm_kwargs, **kwargs}
        if self.api_base:
            call_kwargs['api_base'] = self.api_base
        if self.api_key:
            call_kwargs['api_key'] = self.api_key

        # Call LiteLLM
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            **call_kwargs
        )

        # Extract text
        return response.choices[0].message.content

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
                api_base=self.api_base,
                api_key=self.api_key,
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
