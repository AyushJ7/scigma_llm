import json
import os
import re
import textwrap

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError

try:
    string_types = (basestring,)
except NameError:
    string_types = (str,)


DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "gemma4:31b-cloud"
DEFAULT_REFERENCE_CHARS = 30000
DEFAULT_MAX_COMMANDS = 30
DEFAULT_MAX_COMMAND_CHARS = 500
DEFAULT_ANSWER_WRAP_CHARS = 78

DENIED_COMMANDS = set([
    "!!",
    "load", "loa", "lo", "l",
    "equations", "equation", "equatio", "equati", "equat", "equa", "equ", "eq",
    "history", "session",
    "write", "writeln", "data", "dataln", "warn", "warnln", "error", "errorln",
    "quit", "qui", "qu", "q", "bye", "end",
    "reset", "rese", "res",
    "save", "sav",
])


class LLMError(Exception):
    pass


def handle(prompt, win):
    prompt = prompt.strip()
    if not prompt:
        raise LLMError("empty LLM request after '!!'")

    _write_note(win, "LLM: generating SCIGMA commands...\n")
    response = request_commands(prompt, win)
    if response["type"] == "clarification":
        message = _ascii(response["message"])
        _write_note(win, "LLM clarification: " + message + "\n")
        print("LLM clarification: " + message)
        _append_llm_history(win, "commands", prompt, "clarification: " + message)
        return []

    commands = validate_commands(response["commands"], win)
    if not commands:
        raise LLMError("LLM generated no executable commands")

    _write_note(win, "LLM generated commands:\n")
    print("LLM generated commands:")
    for command in commands:
        _write_data(win, "  " + command + "\n")
        print("  " + command)

    _append_llm_history(win, "commands", prompt, "\n".join(commands))
    win.queue = commands + win.queue
    return commands


def answer(prompt, win):
    prompt = prompt.strip()
    if not prompt:
        raise LLMError("empty LLM question after '?'")

    _write_note(win, "LLM: answering...\n")
    response = request_answer(prompt, win)
    response = _truncate_answer(_ascii(response).strip())
    if not response:
        raise LLMError("LLM returned an empty answer")
    display_response = _wrap_console_text(response)

    _write_note(win, "LLM answer:\n")
    _write_data(win, display_response + "\n")
    print("LLM answer:")
    print(display_response)
    _append_llm_history(win, "answer", prompt, response)
    return response


def request_commands(prompt, win):
    payload = {
        "model": _model(),
        "messages": [
            {
                "role": "system",
                "content": _system_prompt(),
            },
            {
                "role": "user",
                "content": _user_prompt(prompt, win),
            },
        ],
        "stream": False,
        "format": "json",
        "options": {
            "temperature": float(os.environ.get("SCIGMA_LLM_TEMPERATURE", "0.1")),
        },
    }

    raw = _post_json(_endpoint(), payload)
    try:
        content = raw["message"]["content"]
    except KeyError:
        raise LLMError("Ollama response did not contain message.content")
    return parse_response(content)


def request_answer(prompt, win):
    payload = {
        "model": _model(),
        "messages": [
            {
                "role": "system",
                "content": _answer_system_prompt(),
            },
            {
                "role": "user",
                "content": _answer_user_prompt(prompt, win),
            },
        ],
        "stream": False,
        "options": {
            "temperature": float(os.environ.get("SCIGMA_LLM_ANSWER_TEMPERATURE", "0.2")),
        },
    }

    raw = _post_json(_endpoint(), payload)
    try:
        return raw["message"]["content"]
    except KeyError:
        raise LLMError("Ollama response did not contain message.content")


def parse_response(content):
    data = _loads_json_object(content)

    if isinstance(data, list):
        data = {"type": "commands", "commands": data}

    if not isinstance(data, dict):
        raise LLMError("LLM response must be a JSON object")

    response_type = data.get("type")
    if response_type is None and "commands" in data:
        response_type = "commands"
    if response_type is None and "message" in data:
        response_type = "clarification"

    if response_type == "commands":
        commands = data.get("commands")
        if isinstance(commands, string_types):
            commands = commands.splitlines()
        if not isinstance(commands, list):
            raise LLMError("LLM commands response must contain a command list")
        return {"type": "commands", "commands": commands}

    if response_type == "clarification":
        message = data.get("message", "")
        if not isinstance(message, string_types):
            raise LLMError("LLM clarification message must be a string")
        return {"type": "clarification", "message": message}

    raise LLMError("LLM response type must be 'commands' or 'clarification'")


def validate_commands(commands, win):
    max_commands = int(os.environ.get("SCIGMA_LLM_MAX_COMMANDS", DEFAULT_MAX_COMMANDS))
    max_chars = int(os.environ.get("SCIGMA_LLM_MAX_COMMAND_CHARS", DEFAULT_MAX_COMMAND_CHARS))
    command_roots = _command_roots(win)

    accepted = []
    for raw in commands:
        if not isinstance(raw, string_types):
            raise LLMError("LLM command entries must be strings")
        command = _require_ascii_command(raw).strip()
        if not command:
            continue
        if "\n" in command or "\r" in command:
            raise LLMError("LLM generated a multiline command")
        if len(command) > max_chars:
            raise LLMError("LLM command is too long: " + command[:80])
        if command.startswith("#"):
            continue
        if command.startswith("!!"):
            raise LLMError("LLM may not generate recursive '!!' commands")

        root = _command_root(command)
        if root in DENIED_COMMANDS:
            raise LLMError("LLM generated a denied command: " + root)

        if root in command_roots:
            accepted.append(command)
        elif _looks_like_equation_parser_command(command):
            accepted.append(command)
        elif _looks_like_option_command(root, win):
            accepted.append(command)
        else:
            raise LLMError("LLM generated an unknown SCIGMA command: " + command)

        if len(accepted) > max_commands:
            raise LLMError("LLM generated too many commands")

    return accepted


def build_session_context(win):
    lines = []
    lines.append("SCIGMA session context")
    lines.append("script: " + _safe_attr(win, "script", "unknown"))
    lines.append("equation source: " + _safe_attr(win, "source", "unknown"))
    lines.append("mode: " + _safe_panel_get(win, "equationPanel", "mode", "unknown"))

    eqsys = getattr(win, "eqsys", None)
    if eqsys is not None:
        lines.extend(_eqsys_context("current equation system", eqsys))

    invsys = getattr(win, "invsys", None)
    if invsys is not None:
        inv_defs = _safe_call(invsys, "var_defs", [])
        if inv_defs:
            lines.append("inverse definitions: " + ", ".join(inv_defs))

    selection = getattr(win, "selection", None)
    if isinstance(selection, dict) and "identifier" in selection:
        lines.append("selected object: " + str(selection["identifier"]))
    else:
        lines.append("selected object: none")

    graph_names = _graph_names(getattr(win, "graphs", None))
    if graph_names:
        lines.append("known graph/object names: " + ", ".join(graph_names[:30]))
    else:
        lines.append("known graph/object names: none")

    history = _context_history(win)
    if history:
        lines.append("recent commands:")
        for command in history:
            lines.append("- " + _ascii(command))
    else:
        lines.append("recent commands: none")

    llm_history = _recent_llm_history(win)
    if llm_history:
        lines.append("recent LLM interactions:")
        for item in llm_history:
            lines.append("- trigger: " + item["trigger"])
            lines.append("  user: " + item["prompt"])
            lines.append("  assistant: " + item["response"])
    else:
        lines.append("recent LLM interactions: none")

    return "\n".join(lines)


def _context_history(win):
    history = getattr(win, "history", [])
    try:
        start = int(getattr(win, "llm_context_start_index", 0))
    except Exception:
        start = 0
    if start < 0:
        start = 0
    if start > len(history):
        start = len(history)

    limit = int(os.environ.get("SCIGMA_LLM_HISTORY_LINES", "20"))
    scoped = history[start:]
    if limit <= 0:
        return []
    return scoped[-limit:]


def _append_llm_history(win, trigger, prompt, response):
    try:
        history = win.llm_history
    except AttributeError:
        history = []
        win.llm_history = history

    history.append({
        "trigger": _ascii(trigger),
        "prompt": _compact_context_text(prompt),
        "response": _compact_context_text(response),
    })

    limit = int(os.environ.get("SCIGMA_LLM_INTERACTION_HISTORY", "12"))
    if limit <= 0:
        del history[:]
    elif len(history) > limit:
        del history[:-limit]


def _recent_llm_history(win):
    try:
        history = list(win.llm_history)
    except AttributeError:
        return []

    limit = int(os.environ.get("SCIGMA_LLM_INTERACTION_HISTORY", "12"))
    if limit <= 0:
        return []
    return history[-limit:]


def _eqsys_context(title, eqsys):
    lines = [title + ":"]
    lines.append("  variables: " + _join_or_none(_safe_call(eqsys, "var_names", [])))
    lines.append("  variable values: " + _join_or_none(_safe_call(eqsys, "var_vals", [])))
    lines.append("  parameters: " + _join_or_none(_safe_call(eqsys, "par_names", [])))
    lines.append("  parameter values: " + _join_or_none(_safe_call(eqsys, "par_vals", [])))
    lines.append("  functions: " + _join_or_none(_safe_call(eqsys, "func_names", [])))
    lines.append("  constants: " + _join_or_none(_safe_call(eqsys, "const_names", [])))
    lines.append("  variable definitions: " + _join_or_none(_safe_call(eqsys, "var_defs", [])))
    lines.append("  function definitions: " + _join_or_none(_safe_call(eqsys, "func_defs", [])))
    lines.append("  constant definitions: " + _join_or_none(_safe_call(eqsys, "const_defs", [])))
    return lines


def _system_prompt():
    return (
        "You translate natural language requests into SCIGMA console commands. "
        "Use only commands supported by the provided SCIGMA Markdown reference and current session context. "
        "Return JSON only. Return either "
        "{\"type\":\"commands\",\"commands\":[\"command 1\",\"command 2\"]} "
        "or {\"type\":\"clarification\",\"message\":\"question\"}. "
        "Do not include markdown fences, prose, shell commands, Python code, or recursive !! commands. "
        "Ask for clarification when required state is missing."
    )


def _answer_system_prompt():
    return (
        "You are a concise SCIGMA assistant. "
        "Answer the user's question in natural language using the SCIGMA reference and current session context. "
        "Keep the reply short: at most five concise sentences. "
        "You may suggest useful parameter values, analysis steps, or command names, but do not claim to have run commands. "
        "If the user asks you to change the session, explain that executable changes should use the !! trigger."
    )


def _user_prompt(prompt, win):
    return (
        "SCIGMA reference markdown:\n"
        "```markdown\n"
        + _reference_markdown()
        + "\n```\n\n"
        "Current session context:\n"
        "```text\n"
        + build_session_context(win)
        + "\n```\n\n"
        "User request:\n"
        + prompt
    )


def _answer_user_prompt(prompt, win):
    return (
        "SCIGMA reference markdown:\n"
        "```markdown\n"
        + _reference_markdown()
        + "\n```\n\n"
        "Current session context:\n"
        "```text\n"
        + build_session_context(win)
        + "\n```\n\n"
        "User question:\n"
        + prompt
    )


def _reference_markdown():
    configured_path = os.environ.get("SCIGMA_LLM_REFERENCE_FILE")
    paths = [configured_path] if configured_path else _default_reference_paths()
    limit = int(os.environ.get("SCIGMA_LLM_REFERENCE_CHARS", DEFAULT_REFERENCE_CHARS))
    text = None
    for path in paths:
        try:
            with open(path, "r") as f:
                text = f.read()
            break
        except IOError:
            pass
    if text is None:
        text = _fallback_reference()
    if len(text) > limit:
        text = text[:limit] + "\n\n[reference truncated]"
    return text


def _default_reference_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, os.pardir))
    return [
        os.path.join(root, "manual", "manual.md"),
        os.path.join(root, "scratch", "manual.md"),
    ]


def _fallback_reference():
    return """# SCIGMA command reference

Use one command per line.
Equation syntax:
x' = expression defines an ODE variable or map update.
x = value sets a variable/parameter value.
x = expression defines a dependent function.
$expression evaluates expression.
!x deletes symbol x.

Modes:
mode ode
mode map
mode strobe
mode Poincare

Common commands:
plot [n] [name]
guess [name]
evals [name]
evecs [name]
mstable [n] [origin] [name]
munstable [n] [origin] [name]
cont <n> <parameter>
cycle <n> <parameter>
select <name>
hide <name>
show <name>
clear
2d
3d
xrange <min> <max>
yrange <min> <max>
zrange <min> <max>
crange <min> <max>
fit

Settings:
dt, period, nperiod, secvar, secval, secdir, maxtime, ds, arc, alpha,
evec1, color, delay, marker.style, marker.size, point.style, point.size.
"""


def _post_json(url, payload):
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    api_key = os.environ.get("SCIGMA_LLM_API_KEY") or os.environ.get("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    request = Request(url, data=body, headers=headers)
    timeout = float(os.environ.get("SCIGMA_LLM_TIMEOUT", "60"))
    try:
        response = urlopen(request, timeout=timeout)
        raw = response.read().decode("utf-8")
    except HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")
        except Exception:
            pass
        raise LLMError("Ollama API HTTP error " + str(e.code) + (": " + detail if detail else ""))
    except URLError as e:
        raise LLMError("could not reach Ollama API: " + str(e.reason))
    except Exception as e:
        raise LLMError("Ollama API request failed: " + str(e))

    try:
        return json.loads(raw)
    except ValueError:
        raise LLMError("Ollama API returned invalid JSON")


def _endpoint():
    explicit = os.environ.get("SCIGMA_LLM_ENDPOINT")
    if explicit:
        return explicit

    host = (
        os.environ.get("SCIGMA_LLM_OLLAMA_HOST")
        or os.environ.get("OLLAMA_HOST")
        or DEFAULT_HOST
    ).rstrip("/")
    if host.endswith("/api"):
        return host + "/chat"
    return host + "/api/chat"


def _model():
    return os.environ.get("SCIGMA_LLM_MODEL") or os.environ.get("OLLAMA_MODEL") or DEFAULT_MODEL


def _loads_json_object(content):
    if not isinstance(content, string_types):
        raise LLMError("LLM response content must be a string")
    text = content.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass

    extracted = _extract_json_object(text)
    if extracted is None:
        raise LLMError("LLM response was not valid JSON")
    try:
        return json.loads(extracted)
    except ValueError:
        raise LLMError("LLM response contained malformed JSON")


def _extract_json_object(text):
    start = text.find("{")
    if start < 0:
        start = text.find("[")
    if start < 0:
        return None

    opening = text[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "\"":
                in_string = False
        else:
            if ch == "\"":
                in_string = True
            elif ch == opening:
                depth += 1
            elif ch == closing:
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return None


def _command_roots(win):
    roots = set()

    def visit(entry):
        if isinstance(entry, dict):
            for key, value in entry.items():
                if isinstance(value, dict):
                    visit(value)
                else:
                    roots.add(str(key))

    visit(getattr(win, "commands", {}))
    return roots


def _command_root(command):
    return command.split()[0].strip().lower()


def _looks_like_equation_parser_command(command):
    stripped = command.strip()
    if stripped.startswith("$") or stripped.startswith("!"):
        return True
    if "=" in stripped:
        return True
    return False


def _looks_like_option_command(root, win):
    options = getattr(win, "options", None)
    if not isinstance(options, dict):
        return False
    return root.lower() in _option_roots(options)


def _option_roots(options):
    roots = set()

    def visit(entry, path=""):
        if isinstance(entry, dict):
            for key, value in entry.items():
                key = str(key)
                child_path = (path + "." + key).strip(".")
                if not isinstance(value, dict):
                    roots.add(key.lower())
                    roots.add(child_path.lower())
                visit(value, child_path)

    for panel, data in options.items():
        visit(data)
    return roots


def _graph_names(entry):
    names = []

    def visit(node):
        if isinstance(node, dict):
            if "identifier" in node:
                names.append(str(node["identifier"]))
            else:
                for value in node.values():
                    visit(value)

    visit(entry)
    return names


def _safe_call(obj, name, default):
    try:
        return getattr(obj, name)()
    except Exception:
        return default


def _safe_attr(obj, name, default):
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    return _ascii(value)


def _safe_panel_get(win, panel_name, key, default):
    try:
        panel = getattr(win, panel_name)
        return _ascii(panel.get(key))
    except Exception:
        return default


def _join_or_none(values):
    if values is None:
        return "none"
    try:
        values = list(values)
    except TypeError:
        return _ascii(values)
    if not values:
        return "none"
    return ", ".join([_ascii(value) for value in values])


def _compact_context_text(text):
    text = _ascii(text).replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = " | ".join(lines)
    limit = int(os.environ.get("SCIGMA_LLM_INTERACTION_CHARS", "1200"))
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " [truncated]"


def _write_note(win, text):
    try:
        win.console.write_note(_ascii(text))
    except Exception:
        pass


def _write_data(win, text):
    try:
        win.console.write_data(_ascii(text))
    except Exception:
        pass


def _ascii(value):
    text = str(value)
    try:
        text.encode("ascii")
        return text
    except UnicodeEncodeError:
        return text.encode("ascii", "replace").decode("ascii")


def _require_ascii_command(value):
    text = str(value)
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        raise LLMError("LLM generated a non-ASCII command")
    return text


def _truncate_answer(text):
    limit = int(os.environ.get("SCIGMA_LLM_ANSWER_MAX_CHARS", "1200"))
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[answer truncated]"


def _wrap_console_text(text):
    width = int(os.environ.get("SCIGMA_LLM_ANSWER_WRAP_CHARS", DEFAULT_ANSWER_WRAP_CHARS))
    if width <= 0:
        return text

    wrapped = []
    for line in text.splitlines():
        if not line.strip():
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line,
                                     width=width,
                                     break_long_words=True,
                                     break_on_hyphens=False))
    return "\n".join(wrapped)
