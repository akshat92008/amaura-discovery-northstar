"""
Amaura Discovery Engine: Command-Line Interface
===============================================
CLI for running discovery loops, evaluating custom heuristics, and serving the cockpit.
"""

import argparse
import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from rich.syntax import Syntax

from amaura.config import DiscoveryConfig
from amaura.engine.candidate import Candidate
from amaura.engine.discovery import DiscoveryEngine
from amaura.analysis.reporter import DiscoveryReporter


console = Console()


def print_banner():
    banner = (
        "[bold cyan]    ___   __  ______  __  ______  ___ \n"
        "   /   | /  |/  /   |/ / / / __ \\/   |\n"
        "  / /| |/ /|_/ / /| / / / / /_/ / /| |\n"
        " / ___ / /  / / ___ / /_/ / _, _/ ___ |\n"
        "/_/  |_/_/  /_/_/  |_\\____/_/ |_/_/  |_|[/bold cyan]\n"
        "[bold white]Autonomous AI Algorithmic Discovery Engine[/bold white] [dim]| Amaura Labs[/dim]"
    )
    console.print(Panel(banner, border_style="cyan", padding=(1, 2)))


def cmd_run(args):
    """Run an automated discovery loop."""
    print_banner()
    config = DiscoveryConfig(
        problem=args.problem,
        generations=args.generations,
        num_islands=args.islands,
        population_size=args.population,
        llm_provider=args.provider,
        llm_model=args.model,
        llm_base_url=args.base_url,
        seed=args.seed,
        output_dir=args.output
    )

    console.print(f"[bold green]Starting discovery run:[/bold green] Problem=[cyan]{config.problem}[/cyan], "
                  f"Generations=[cyan]{config.generations}[/cyan], Islands=[cyan]{config.num_islands}[/cyan], "
                  f"Provider=[cyan]{config.llm_provider}[/cyan]")

    engine = DiscoveryEngine(config)

    # Rich table to track evolutionary milestones
    table = Table(title="Evolutionary Generation Milestones", border_style="dim")
    table.add_column("Gen", justify="right", style="cyan")
    table.add_column("Best Fitness", justify="right", style="bold green")
    table.add_column("Baseline", justify="right", style="yellow")
    table.add_column("Δ vs Baseline", justify="right")
    table.add_column("Mutation Operator", style="magenta")
    table.add_column("Evaluated", justify="right", style="dim")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Evolving algorithmic candidates...", total=config.generations)

        def on_step(event):
            if event["type"] == "generation_step":
                s = event["summary"]
                progress.advance(task, 1)

                imp = s["improvement_pct"]
                imp_style = "[bold green]+" if imp > 0 else "[red]"
                imp_text = f"{imp_style}{imp:.2f}%[/]"

                if s["generation"] % max(1, config.generations // 10) == 0 or s["generation"] == config.generations or imp > 0:
                    table.add_row(
                        str(s["generation"]),
                        f"{s['best_fitness']:.4f}",
                        f"{s['baseline_fitness']:.4f}",
                        imp_text,
                        str(s["best_mutation"]),
                        str(s["total_candidates"])
                    )

        engine.add_telemetry_callback(on_step)
        best_candidate = engine.run()

    console.print(table)

    # Render discovery result
    if best_candidate and engine.human_baseline:
        base_fit = engine.human_baseline.fitness
        disc_fit = best_candidate.fitness
        imp_pct = ((base_fit - disc_fit) / max(1e-6, abs(base_fit))) * 100.0

        if imp_pct > 0:
            console.print(Panel(
                f"[bold green]✓ SUCCESS: Discovered algorithm outperforms human baseline by +{imp_pct:.2f}%![/bold green]\n"
                f"Discovered Fitness: [bold cyan]{disc_fit:.4f}[/bold cyan] (Human Baseline: {base_fit:.4f})\n"
                f"Candidate ID: {best_candidate.id} | Generation: {best_candidate.generation} | Operator: {best_candidate.mutation_type}",
                title="[bold green]DISCOVERY BREAKTHROUGH[/bold green]",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[yellow]Discovery run completed. Best candidate matched human baseline ({base_fit:.4f}).[/yellow]",
                title="[yellow]RUN CONCLUDED[/yellow]",
                border_style="yellow"
            ))

        console.print("\n[bold]Discovered Code Snippet:[/bold]")
        console.print(Syntax(best_candidate.code, "python", theme="monokai", line_numbers=True))

        # Generate markdown report
        report = DiscoveryReporter.generate_markdown_report(
            problem=config.problem,
            human_baseline=engine.human_baseline,
            discovered_champ=best_candidate,
            history=engine.history
        )
        report_path = os.path.join(config.output_dir, "discovery_report.md")
        with open(report_path, "w") as f:
            f.write(report)
        console.print(f"\n[dim]Full validation report saved to: [underline]{report_path}[/underline][/dim]")


def cmd_evaluate(args):
    """Evaluate a specific candidate file against the benchmark suite."""
    print_banner()
    if not os.path.exists(args.file):
        console.print(f"[bold red]File not found: {args.file}[/bold red]")
        sys.exit(1)

    with open(args.file, "r") as f:
        code = f.read()

    func_name = "priority" if args.problem == "bin_packing" else "evict_score"
    candidate = Candidate(code=code, function_name=func_name)

    config = DiscoveryConfig(problem=args.problem)
    engine = DiscoveryEngine(config)

    console.print(f"[bold cyan]Evaluating candidate from {args.file} on {args.problem}...[/bold cyan]")
    res = engine.evaluator.evaluate_candidate(candidate)

    if not res.is_valid:
        console.print(f"[bold red]Evaluation FAILED: {res.error_message}[/bold red]")
        sys.exit(1)

    table = Table(title="Evaluation Results", border_style="cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Score", justify="right", style="green")
    table.add_row("Fitness (Lower is better)", f"{res.fitness:.4f}")
    table.add_row("Train Score", f"{res.train_score:.4f}")
    table.add_row("Test Score", f"{res.test_score:.4f}")
    table.add_row("Generalization Score (Unseen)", f"{res.generalization_score:.4f}")
    table.add_row("Tests Passed", f"{res.passed_tests} / {res.total_tests}")
    table.add_row("Execution Latency", f"{res.runtime_ms:.2f} ms")
    console.print(table)


def cmd_serve(args):
    """Launch the Web Cockpit server."""
    print_banner()
    import uvicorn
    console.print(f"[bold green]Launching Amaura Discovery Cockpit on http://{args.host}:{args.port}[/bold green]")
    uvicorn.run("amaura.web.app:app", host=args.host, port=args.port, reload=False)


def main():
    parser = argparse.ArgumentParser(description="Amaura Discovery Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: run
    p_run = subparsers.add_parser("run", help="Run automated algorithmic discovery loop")
    p_run.add_argument("--problem", choices=["bin_packing", "cache_policy"], default="bin_packing", help="Target problem")
    p_run.add_argument("--generations", type=int, default=30, help="Number of evolutionary generations")
    p_run.add_argument("--islands", type=int, default=3, help="Number of evolutionary islands")
    p_run.add_argument("--population", type=int, default=12, help="Total population size")
    p_run.add_argument("--provider", choices=["auto", "openai", "anthropic", "gemini", "ollama", "ast"], default="auto", help="LLM / Mutator provider")
    p_run.add_argument("--model", type=str, default="gpt-4o-mini", help="LLM model name")
    p_run.add_argument("--base-url", type=str, default=None, help="Custom LLM API base URL")
    p_run.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    p_run.add_argument("--output", type=str, default="amaura_runs", help="Output directory")

    # Subcommand: evaluate
    p_eval = subparsers.add_parser("evaluate", help="Evaluate a candidate algorithm file")
    p_eval.add_argument("file", help="Python file containing the function")
    p_eval.add_argument("--problem", choices=["bin_packing", "cache_policy"], default="bin_packing")

    # Subcommand: serve
    p_serve = subparsers.add_parser("serve", help="Launch real-time web discovery cockpit")
    p_serve.add_argument("--host", type=str, default="127.0.0.1", help="Host address")
    p_serve.add_argument("--port", type=int, default=8000, help="Port number")

    args = parser.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "serve":
        cmd_serve(args)


if __name__ == "__main__":
    main()
