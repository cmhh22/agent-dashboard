"""
Code Interpreter tool — executes Python code in a sandboxed subprocess.
"""
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

# Dangerous modules / keywords that are blocked
_BLOCKED = {
    "os.system", "subprocess", "shutil.rmtree", "shutil.move",
    "__import__", "exec(", "eval(", "compile(",
    "open(", "pathlib", "glob",
    "socket", "http.server", "ftplib", "smtplib",
    "ctypes", "importlib",
}


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
        # Basic safety check
        for blocked in _BLOCKED:
            if blocked in code:
                return f"⚠️ Blocked: usage of '{blocked}' is not allowed for security reasons."

        tmp = None
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            )
            tmp.write(code)
            tmp.close()

            result = subprocess.run(
                [sys.executable, tmp.name],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                cwd=tempfile.gettempdir(),
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
