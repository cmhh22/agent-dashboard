"""
Calculator tool for mathematical computations.
"""
from langchain.tools import BaseTool
from typing import Optional
from pydantic import Field
import ast
import operator


# Maximum allowed exponent to prevent DoS
_MAX_EXPONENT = 1000

# Allowed operators for safe evaluation (module-level to avoid Pydantic issues)
_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


class CalculatorTool(BaseTool):
    """Tool for performing mathematical calculations."""
    
    name: str = "calculator"
    description: str = """Useful for performing mathematical calculations. 
    Input should be a valid mathematical expression like '2 + 2' or '(10 * 5) / 2'.
    Supports +, -, *, /, **, (), and basic math operations."""
    
    def _run(self, expression: str) -> str:
        """Execute the calculator tool."""
        try:
            # Parse and evaluate the expression safely
            result = self._eval_expression(expression)
            return f"The result is: {result}"
        except Exception as e:
            return f"Error calculating: {str(e)}"
    
    async def _arun(self, expression: str) -> str:
        """Async version of the calculator tool."""
        return self._run(expression)
    
    def _eval_expression(self, expression: str) -> float:
        """Safely evaluate a mathematical expression."""
        try:
            node = ast.parse(expression, mode='eval').body
            return self._eval_node(node)
        except Exception as e:
            raise ValueError(f"Invalid expression: {str(e)}")
    
    def _eval_node(self, node):
        """Recursively evaluate AST nodes."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_func = _OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            # Guard against exponent DoS
            if isinstance(node.op, ast.Pow) and isinstance(right, (int, float)) and abs(right) > _MAX_EXPONENT:
                raise ValueError(f"Exponent too large (max {_MAX_EXPONENT})")
            return op_func(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_func = _OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_func(operand)
        else:
            raise ValueError(f"Unsupported operation: {type(node).__name__}")
