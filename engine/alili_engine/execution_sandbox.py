"""Bounded, import-free Python task runner for AC.

This is a best-effort restricted runner, not a hardened OS/container boundary.
Do not expose it to hostile multi-tenant workloads without external isolation.
"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import time

MAX_CODE_CHARS = 8_000
MAX_INPUT_CHARS = 8_000
MAX_OUTPUT_CHARS = 16_000
DEFAULT_TIMEOUT_SECONDS = 2
MAX_TIMEOUT_SECONDS = 5
MAX_RANGE_ITEMS = 10_000

_ALLOWED_NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.Name, ast.Load, ast.Store,
    ast.Constant, ast.List, ast.Tuple, ast.Set, ast.Dict, ast.BinOp, ast.UnaryOp,
    ast.BoolOp, ast.Compare, ast.IfExp, ast.Call, ast.keyword, ast.ListComp,
    ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension, ast.Subscript,
    ast.Slice, ast.Index, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
    ast.Mod, ast.Pow, ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or, ast.Eq,
    ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is,
    ast.IsNot, ast.If, ast.For, ast.While, ast.Break, ast.Continue, ast.Pass,
    ast.JoinedStr, ast.FormattedValue,
)
_SAFE_NAMES = {
    "print", "len", "range", "min", "max", "sum", "sorted", "enumerate",
    "zip", "abs", "round", "int", "float", "str", "bool", "list", "dict",
    "tuple", "set", "True", "False", "None",
}
_CHILD = r'''
import ast, json, sys, resource
resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
resource.setrlimit(resource.RLIMIT_NOFILE, (16, 16))
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
if hasattr(resource, "RLIMIT_NPROC"):
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
payload = json.loads(sys.stdin.read())
code = payload["code"]
tree = ast.parse(code, mode="exec")
allowed = tuple(getattr(ast, n) for n in payload["allowed_nodes"])
safe_names = set(payload["safe_names"])
for node in ast.walk(tree):
    if not isinstance(node, allowed):
        raise ValueError("syntax_not_allowed:" + type(node).__name__)
    if isinstance(node, ast.Name) and node.id.startswith("__"):
        raise ValueError("dunder_name_not_allowed")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in safe_names:
            raise ValueError("call_not_allowed")
    if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and len(node.value) > 8000:
        raise ValueError("literal_too_large")
output = []
used = [0]
def bounded_print(*values, sep=" ", end="\n"):
    text = sep.join(str(v) for v in values) + end
    remaining = 16000 - used[0]
    if remaining <= 0:
        raise ValueError("output_limit_exceeded")
    if len(text) > remaining:
        output.append(text[:remaining])
        used[0] += remaining
        raise ValueError("output_limit_exceeded")
    output.append(text)
    used[0] += len(text)
def bounded_range(*args):
    value = range(*args)
    if len(value) > 10000:
        raise ValueError("range_limit_exceeded")
    return value
builtins = {
    "print": bounded_print, "len": len, "range": bounded_range,
    "min": min, "max": max, "sum": sum, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "abs": abs, "round": round,
    "int": int, "float": float, "str": str, "bool": bool,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
}
scope = {"__builtins__": builtins}
try:
    exec(compile(tree, "<ac-task>", "exec"), scope, scope)
    print(json.dumps({"ok": True, "stdout": "".join(output)}, ensure_ascii=False))
except BaseException as exc:
    print(json.dumps({"ok": False, "stdout": "".join(output),
                      "error": str(exc)[:300], "error_type": type(exc).__name__},
                     ensure_ascii=False))
'''


class ExecutionRejected(ValueError):
    """Raised when a task violates the AC execution policy."""



class ACExecutionSandbox:
    """Run small import-free Python snippets with strict input/time/output bounds."""

    def __init__(self, *, timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("invalid_timeout")
        if not 0.1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
            raise ValueError("timeout_out_of_range")
        self.timeout_seconds = float(timeout_seconds)

    def status(self):
        return {
            "enabled": os.name == "posix",
            "mode": "restricted_python_subprocess",
            "isolation": "best_effort_not_a_hardened_os_boundary",
            "network": "imports_and_attribute_access_blocked",
            "filesystem": "no_file_builtins_and_zero_file_size_limit",
            "paid_fallback": "prohibited",
        }

    def run(self, code, *, input_text=""):
        if not isinstance(code, str) or not code.strip() or len(code) > MAX_CODE_CHARS:
            raise ExecutionRejected("invalid_or_oversized_code")
        if not isinstance(input_text, str) or len(input_text) > MAX_INPUT_CHARS:
            raise ExecutionRejected("invalid_or_oversized_input")
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise ExecutionRejected("syntax_error") from exc
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ExecutionRejected("syntax_not_allowed:" + type(node).__name__)
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ExecutionRejected("dunder_name_not_allowed")
            if isinstance(node, ast.Call) and (
                not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_NAMES
            ):
                raise ExecutionRejected("call_not_allowed")
            if isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes)) and len(node.value) > MAX_INPUT_CHARS:
                raise ExecutionRejected("literal_too_large")
        if os.name != "posix":
            return {"ok": False, "status": "unavailable", "error": "posix_limits_required"}
        payload = {
            "code": code,
            "allowed_nodes": [item.__name__ for item in _ALLOWED_NODES],
            "safe_names": sorted(_SAFE_NAMES),
        }
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="ac-task-") as workspace:
            env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8"}
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", "-S", "-c", _CHILD],
                    input=json.dumps(payload), text=True, encoding="utf-8",
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    cwd=workspace, env=env, timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return {"ok": False, "status": "timeout", "error": "execution_timeout",
                        "duration_ms": int((time.monotonic() - started) * 1000)}
        if len(completed.stdout) > MAX_OUTPUT_CHARS + 1000:
            return {"ok": False, "status": "rejected", "error": "output_limit_exceeded"}
        try:
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"ok": False, "status": "failed", "error": "runner_failed",
                    "stderr": completed.stderr[:1000]}
        result.update({
            "status": "completed" if result.get("ok") else "rejected",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "network_access": "not_provided_by_policy",
            "workspace": "temporary_and_deleted",
        })
        return result
