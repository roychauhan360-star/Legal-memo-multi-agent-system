"""Run the pipeline without the UI (handy for debugging).

Example:
  python run_cli.py "ABC Industries Pvt Ltd" "Check pending litigation" "Gujarat High Court" "Supreme Court of India"
"""
import sys

from dotenv import load_dotenv

load_dotenv()

from memo_writer import config as cfg  # noqa: E402
from memo_writer.graph import build_graph  # noqa: E402
from memo_writer.pdf_export import build_pdf_bytes  # noqa: E402
from memo_writer.tracing import build_run_config  # noqa: E402

if len(sys.argv) < 3:
    sys.exit(__doc__)

subject, matter, *jurisdictions = sys.argv[1:]
models = cfg.list_chat_models()
fast = cfg.pick_default(models, cfg.FAST_MODEL_PREFERENCE)
strong = cfg.pick_default(models, cfg.STRONG_MODEL_PREFERENCE)
print(f"Models: fast={fast} strong={strong}")

run_config, trace_status = build_run_config(fast, strong)
print(trace_status)
inputs = {"subject": subject, "matter": matter, "jurisdictions": jurisdictions,
          "sources": [], "iteration": 0, "feedback": [], "log": []}

final = None
for mode, chunk in build_graph().stream(inputs, config=run_config, stream_mode=["updates", "values"]):
    if mode == "updates":
        for _node, update in chunk.items():
            for line in (update or {}).get("log", []):
                print("•", line)
    else:
        final = chunk

open("memo.pdf", "wb").write(build_pdf_bytes(final))
print("Status:", final["status"], "-> saved memo.pdf")
