"""Test-only process memory and actual warmed ONNX session configuration."""

from time import perf_counter_ns


def memory_snapshot():
    import win32api
    import win32process

    memory = win32process.GetProcessMemoryInfo(win32api.GetCurrentProcess())
    return {
        "ns": perf_counter_ns(),
        "private_bytes": memory["PagefileUsage"],
        "working_set_bytes": memory["WorkingSetSize"],
    }


def ocr_options(recognizer):
    result = {}
    for name in ("text_det", "text_rec"):
        session = getattr(recognizer._engine, name).session.session
        options = session.get_session_options()
        result[name] = {
            "providers": session.get_providers(),
            "cpu_arena": options.enable_cpu_mem_arena,
            "threads": options.intra_op_num_threads,
            "inter_threads": options.inter_op_num_threads,
            "intra_spinning": options.get_session_config_entry("session.intra_op.allow_spinning"),
            "inter_spinning": options.get_session_config_entry("session.inter_op.allow_spinning"),
        }
    return result
