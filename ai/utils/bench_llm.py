"""Benchmark Ollama models on this machine (Pascal GPU / CPU).

Uses server-reported timings from the final /api/generate chunk so results are
independent of streaming text capture (thinking-mode models return no text until
reasoning completes). Metrics follow standard LLM inference practice:

  prefill t/s = prompt_eval_count / prompt_eval_duration   (context ingestion)
  decode  t/s = eval_count / eval_duration                 (token generation)
  TTFT        = load_duration + prompt_eval_duration       (time to first token)
  total       = total_duration                             (full request, warm)

Run from repo root: .venv/bin/python scripts/bench_llm.py [model ...] [--trials N]
"""

import argparse
import random
import subprocess
import time

import ollama

HOST = "http://localhost:11434"
MAX_TOKENS = 200


def build_long_prompt(seed: int = 0) -> str:
    """Synthetic assembled context (~15k chars) mimicking the AI context builder
    at Gate C's 16k-char limit: many device status lines plus an insight task.
    The seed varies the content so every trial prefills cold KV (llama.cpp
    prompt-cache would otherwise reuse the identical prompt and fake prefill t/s)."""
    rng = random.Random(seed)
    n_devices = 210 + seed % 60
    lines = [
        f"device pos-{i:03d}: cpu {rng.randint(20, 99)}% ram {rng.randint(30, 95)}% "
        f"temp {rng.randint(40, 95)}C net_latency {rng.randint(10, 400)}ms "
        f"heartbeat {rng.randint(1, 8)}min ago status online"
        for i in range(n_devices)
    ]
    context = "\n".join(lines)
    task = (
        "\n\nWrite a concise operator insight for the site: summarize any "
        "devices showing high CPU, temperature, or latency, and prioritize them."
    )
    return context + task


PROMPTS = {
    "short": "Say hi in one word.",
    "medium": (
        "A device pos-001 reported CPU 95%, temperature 88C, and net latency "
        "300ms for the last 10 minutes. Its heartbeat was 4 minutes ago. What "
        "might be wrong and what should an operator check?"
    ),
    "long": build_long_prompt,
}


def nvidia_vram_mib() -> int:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        ).stdout.strip().splitlines()
        return int(out[0]) if out else 0
    except Exception:
        return 0


def measure(client: ollama.Client, model: str, prompt: str, max_tokens: int = MAX_TOKENS):
    start = time.perf_counter()
    resp = client.generate(
        model=model, prompt=prompt,
        options={"num_predict": max_tokens, "temperature": 0.0},
        stream=False,
    )
    wall = time.perf_counter() - start
    prefill = resp.prompt_eval_count / (resp.prompt_eval_duration / 1e9) if resp.prompt_eval_duration else 0.0
    decode = resp.eval_count / (resp.eval_duration / 1e9) if resp.eval_duration else 0.0
    thinking_chars = len(resp.get("thinking") or "")
    return {
        "wall_s": wall,
        "load_ms": resp.load_duration / 1e6,
        "prefill_tok": resp.prompt_eval_count,
        "prefill_s": resp.prompt_eval_duration / 1e9,
        "prefill_tok_s": prefill,
        "eval_tok": resp.eval_count,
        "eval_s": resp.eval_duration / 1e9,
        "decode_tok_s": decode,
        "ttft_ms": (resp.load_duration + resp.prompt_eval_duration) / 1e6,
        "total_ms": resp.total_duration / 1e6,
        "out_chars": len(resp.response),
        "thinking_chars": thinking_chars,
        "vram_mib": nvidia_vram_mib(),
    }


def run_trials(client, model, prompts, trials):
    results = {}
    for name, prompt in prompts.items():
        trial_runs = []
        for i in range(trials):
            if i == 0:
                client.generate(model=model, prompt="hi", options={"num_predict": 4}, stream=False)
            p = prompt(i) if callable(prompt) else prompt
            trial_runs.append(measure(client, model, p))
        results[name] = trial_runs
    return results


def summarize(results):
    def med(key):
        return sorted(r[key] for r in results)[len(results) // 2]
    r = results[0]
    return {
        "prefill_tok_s": round(med("prefill_tok_s"), 1),
        "decode_tok_s": round(med("decode_tok_s"), 1),
        "ttft_ms": round(med("ttft_ms")),
        "total_ms": round(med("total_ms")),
        "wall_s": round(med("wall_s"), 2),
        "eval_tok": med("eval_tok"),
        "prefill_tok": med("prefill_tok"),
        "out_chars": med("out_chars"),
        "thinking_chars": med("thinking_chars"),
        "vram_mib": max(r["vram_mib"] for r in results),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+")
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    client = ollama.Client(host=HOST, timeout=600)
    for model in args.models:
        print(f"\n=== {model} ===")
        runs = run_trials(client, model, PROMPTS, args.trials)
        for name, trial_runs in runs.items():
            s = summarize(trial_runs)
            print(
                f"  {name:8s} | prefill {s['prefill_tok_s']:>7.1f} t/s ({s['prefill_tok']:>4d} tok) | "
                f"decode {s['decode_tok_s']:>6.1f} t/s ({s['eval_tok']:>4d} tok) | "
                f"TTFT {s['ttft_ms']:>6.0f} ms | total {s['total_ms']:>7.0f} ms | "
                f"wall {s['wall_s']:>6.2f} s | out {s['out_chars']:>4d}ch think {s['thinking_chars']:>4d}ch"
            )
        print(f"  VRAM sampled: {nvidia_vram_mib()} MiB")


if __name__ == "__main__":
    main()