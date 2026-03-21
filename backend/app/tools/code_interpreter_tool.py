"""
Code Interpreter tool — executes Python code in a sandboxed subprocess.
"""
import ast
import subprocess
import sys
import tempfile
import os
import asyncio
import logging
from langchain.tools import BaseTool

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10
_MAX_OUTPUT_CHARS = 4000

# Dangerous imports and calls that are blocked
_BLOCKED_MODULES = {
    "os", "subprocess", "shutil", "pathlib", "glob",
    "socket", "http", "ftplib", "smtplib",
    "ctypes", "importlib", "sys",
}

_BLOCKED_CALLS = {
    "eval", "exec", "compile", "open", "input", "__import__",
    "getattr", "setattr", "delattr", "globals", "locals", "vars",
}


def _attr_to_str(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _attr_to_str(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _validate_python_safety(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"❌ Python syntax error: {exc.msg} (line {exc.lineno})"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _BLOCKED_MODULES:
                    return f"⚠️ Blocked import: '{alias.name}' is not allowed."

        if isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if module in _BLOCKED_MODULES:
                return f"⚠️ Blocked import: 'from {node.module} import ...' is not allowed."

        if isinstance(node, ast.Call):
            call_name = _attr_to_str(node.func)
            call_root = call_name.split(".")[0] if call_name else ""
            if call_name in _BLOCKED_CALLS or call_root in _BLOCKED_CALLS:
                return f"⚠️ Blocked call: '{call_name}' is not allowed."
            if call_root in _BLOCKED_MODULES:
                return f"⚠️ Blocked module call: '{call_name}' is not allowed."

    return None


class CodeInterpreterTool(BaseTool):
    """Execute Python code safely and return stdout/stderr."""

    name: str = "code_interpreter"
    description: str = (
        "Execute Python code and return the printed output. "
        "Use this for calculations, data manipulation, generating lists, "
        "algorithm demos, date/time operations, string processing, etc. "
        "Input must be valid Python code. Always use print() to show results."
    )

    def _run(self, code: str) -> str:
        """Run Python code in a subprocess with timeout."""
        safety_error = _validate_python_safety(code)
        if safety_error:
            return safety_error

        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            )
            tmp.write(code)
            tmp.close()

            safe_env = os.environ.copy()
            safe_env["PYTHONDONTWRITEBYTECODE"] = "1"
            safe_env["PYTHONNOUSERSITE"] = "1"
            safe_env.pop("PYTHONPATH", None)

            result = subprocess.run(
                [sys.executable, "-I", tmp.name],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                cwd=tempfile.gettempdir(),
                env=safe_env,
            )

            stdout = result.stdout.strip()
            stderr = result.stderr.strip()

            if result.returncode != 0:
                output = f"❌ Error (exit {result.returncode}):\n{stderr[:_MAX_OUTPUT_CHARS]}"
            elif stdout:
                output = stdout[:_MAX_OUTPUT_CHARS]
            else:
                output = "(Code executed successfully with no output)"

            return output

        except subprocess.TimeoutExpired:
            return f"⏱️ Execution timed out after {_TIMEOUT_SECONDS}s."
        except Exception as e:
            logger.error(f"Code interpreter error: {e}")
            return f"Error running code: {str(e)}"
        finally:
            if tmp and os.path.exists(tmp.name):
                os.unlink(tmp.name)

    async def _arun(self, code: str) -> str:
        return await asyncio.to_thread(self._run, code)
