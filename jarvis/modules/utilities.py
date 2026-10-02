import ast
import math
import operator
import random
import re
from datetime import datetime

_CALC_WORDS = [
    (r"\bsquare root of\b", "sqrt("), (r"\bcube root of\b", "cbrt("),
    (r"\bsquare root\b", "sqrt"), (r"\bcubed\b", "**3"), (r"\bsquared\b", "**2"),
    (r"\bfactorial of\b", "factorial("), (r"\bfactorial\b", "factorial"),
    (r"\bnatural log of\b", "ln("), (r"\bnatural log\b", "ln"),
    (r"\bcommon log of\b", "log("), (r"\bsine of\b", "sin("), (r"\bsine\b", "sin"),
    (r"\bcosine of\b", "cos("), (r"\bcosine\b", "cos"),
    (r"\btangent of\b", "tan("), (r"\btangent\b", "tan"),
    (r"\bmultiplied by\b", "*"), (r"\bdivided by\b", "/"), (r"\bto the power of\b", "**"),
    (r"\bpower\b", "**"), (r"\bplus\b", "+"), (r"\bminus\b", "-"),
    (r"\btimes\b", "*"), (r"\bmultiply\b", "*"), (r"\bdivide\b", "/"),
    (r"\bover\b", "/"), (r"\bx\b", "*"), (r"\bpercent of\b", "%of%"),
]

def _deg_wrapper(func):
    return lambda x: func(math.radians(x))


def _safe_pow(a, b):
    if isinstance(b, (int, float)) and abs(b) > 1000:
        raise ValueError("Exponent too large")
    return operator.pow(a, b)


def _safe_factorial(x):
    n = int(x)
    if not 0 <= n <= 500:
        raise ValueError("Factorial out of range (0-500)")
    return math.factorial(n)


_ALLOWED_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: _safe_pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


_ALLOWED_FUNCS = {
    "sqrt": math.sqrt, "cbrt": lambda x: x ** (1 / 3),
    "sin": _deg_wrapper(math.sin), "cos": _deg_wrapper(math.cos), "tan": _deg_wrapper(math.tan),
    "asin": lambda x: math.degrees(math.asin(x)), "acos": lambda x: math.degrees(math.acos(x)),
    "atan": lambda x: math.degrees(math.atan(x)),
    "log": math.log10, "ln": math.log, "log10": math.log10,
    "factorial": _safe_factorial,
    "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "exp": math.exp,
}

_ALLOWED_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}

HELP_TEXT = (
    "Here's what I can do. Say: 'what time is it', 'calculate 12 times 8', "
    "'who is Albert Einstein', 'note that buy milk', 'read my notes', "
    "'set a timer for 5 minutes', 'remind me in 10 minutes to stretch', "
    "'list my reminders', 'take a screenshot', 'lock my computer', "
    "'open notepad', 'close notepad', 'search cats on youtube', "
    "'battery level', 'set volume to 50', 'tell me a joke'. Say 'exit' to quit."
)

class UtilityEngine:
    def get_time(self) -> str:
        return f"The time is currently {datetime.now().strftime('%I:%M %p')}."

    def get_date(self) -> str:
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    def get_joke(self) -> str:
        jokes = ["Why do programmers prefer dark mode? Because light attracts bugs!", "Why did the computer go to the doctor? It had a virus!"]
        return random.choice(jokes)

    def get_personal_opening(self) -> str:
        hour = datetime.now().hour
        greeting = "Good morning!" if hour < 12 else "Good afternoon!" if hour < 18 else "Good evening!"
        return f"{greeting} Welcome back. Systems are operational."

    def get_help(self) -> str:
        return HELP_TEXT

    def calculate(self, expression: str) -> str:
        """Safe math eval — no raw eval(), AST whitelist (ops + named funcs) only."""
        expr = expression.strip().lower().rstrip("?.!")
        for pattern, symbol in _CALC_WORDS:
            expr = re.sub(pattern, symbol, expr)
        # Bare function application from speech: 'sin 30' -> 'sin(30)',
        # 'log 100' -> 'log(100)'. Already-parenthesized calls untouched.
        expr = re.sub(
            r"\b(sin|cos|tan|asin|acos|atan|log10|log|ln|sqrt|cbrt|factorial|abs|round|floor|ceil|exp)\s+(?!\()(-?\d+(?:\.\d+)?)",
            r"\1(\2)", expr)
        # Handle '15 %of% 200' -> '15/100*200'
        expr = re.sub(r"(\d+(?:\.\d+)?)\s*%of%\s*(\d+(?:\.\d+)?)", r"(\1/100*\2)", expr)
        expr = expr.replace("%", "/100")
        # Auto-close parens opened by word forms: 'sqrt( 144' -> 'sqrt( 144)'
        _open, _close = expr.count("("), expr.count(")")
        if _open > _close:
            expr += ")" * (_open - _close)
        if not re.fullmatch(r"[\d\s+\-*/().,%a-z]+", expr):
            return f"I couldn't calculate '{expression}'. Try something like 'calculate 12 times 8'."
        try:
            node = ast.parse(expr, mode="eval")
            result = self._eval_node(node.body)
        except ZeroDivisionError:
            return "Division by zero is not allowed."
        except Exception:
            return f"I couldn't calculate '{expression}'."
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        if isinstance(result, float):
            result = round(result, 4)
        return f"The answer is {result}."

    def _eval_node(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name) and node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id in _ALLOWED_FUNCS and node.args
                and all(isinstance(a, (ast.Constant, ast.BinOp, ast.UnaryOp, ast.Call, ast.Name)) for a in node.args)):
            return _ALLOWED_FUNCS[node.func.id](*[self._eval_node(a) for a in node.args])
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(node.op)](self._eval_node(node.operand))
        raise ValueError("Unsupported expression")