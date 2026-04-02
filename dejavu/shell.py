import argparse
import logging
import shlex
import sys
from typing import Any, Dict, Optional

import pandas as pd
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from dejavu.config import settings
from dejavu.context import SessionContext
from dejavu.data.alpaca import AlpacaProvider
from dejavu.data.cache import CacheManager
from dejavu.data.features import add_indicators
from dejavu.data.yahoo import YahooProvider
from dejavu.models.ar import AutoReg
from dejavu.models.hmm import GaussianHMMModel
from dejavu.models.rnn import LSTMModel
from dejavu.strategy.builder import StrategyBuilder
from dejavu.strategy.engine import BacktestEngine
from dejavu.ui.charts import plot_price_and_states, render_annotated_hlc
from dejavu.ui.tables import display_metrics, display_summary

logger = logging.getLogger(__name__)
console = Console()


class DejavuShell:
    def __init__(self):
        self.ctx = SessionContext()
        self.alpaca_provider = AlpacaProvider()
        self.yahoo_provider = YahooProvider()
        self.cache = CacheManager()
        self.commands = [
            "use",
            "model",
            "show",
            "chart",
            "backtest",
            "status",
            "strategy",
            "quit",
            "exit",
            "help",
        ]
        self.completer = WordCompleter(self.commands, ignore_case=True)
        self.session = PromptSession(completer=self.completer)

    def print_welcome(self):
        console.print(f"[bold blue]Welcome to {settings.APP_NAME}[/bold blue]")
        console.print("Type 'help' to list commands.")

    def run(self):
        self.print_welcome()
        while True:
            try:
                with patch_stdout():
                    text = self.session.prompt("(dejavu) ")
            except KeyboardInterrupt:
                continue
            except EOFError:
                break
            if not text.strip():
                continue
            self.dispatch(text)

    def dispatch(self, text: str):
        args = shlex.split(text)
        if not args:
            return
        cmd = args[0].lower()
        if cmd in ["quit", "exit"]:
            sys.exit(0)
        if cmd == "help":
            return self.do_help()
        if cmd == "status":
            return self.do_status()
        if cmd == "use":
            return self.do_use(args[1:])
        if cmd == "model":
            return self.do_model(args[1:])
        if cmd == "show":
            return self.do_show(args[1:])
        if cmd == "chart":
            return self.do_chart(args[1:])
        if cmd == "strategy":
            return self.do_strategy(args[1:])
        if cmd == "backtest":
            return self.do_backtest(args[1:])
        console.print(f"Unknown command: {cmd}")

    def do_help(self):
        console.print("[bold]Available commands:[/bold]")
        console.print("  [cyan]use [TICKER] --range [days] --freq [interval][/cyan] - Load data")
        console.print("  [cyan]status[/cyan] - Show active context")
        console.print("  [cyan]model [hmm|ar|rnn] [--states N] [--lags N] [--hidden N][/cyan] - Train model")
        console.print("  [cyan]strategy new [name] --rule \"[condition]\" --action [long|exit][/cyan] - Create a state-agnostic strategy")
        console.print("  [cyan]strategy add [name] --rule \"[condition]\" --action [long|exit][/cyan] - Append another rule")
        console.print("  [cyan]strategy list|show [name][/cyan] - Inspect saved strategies")
        console.print("  [cyan]backtest --strategy [name] --model [hmm|ar|rnn] --state [state][/cyan] - Run state-gated backtest")
        console.print("  [cyan]show [states|summary|trades][/cyan] - Inspect model/trade state")
        console.print("  [cyan]chart hlc [--overlay vwap] [--no-states] [--no-trades][/cyan] - Render annotated terminal chart")
        console.print("  [cyan]quit/exit[/cyan] - Leave Dejavu")

    def do_status(self):
        console.print("\n[bold]=== Session Status ===[/bold]")
        for key, value in self.ctx.status().items():
            console.print(f"{key}: {value}")
        console.print("")

    def _prompt_if_missing(self, prompt: str, current_value: Optional[str] = None) -> str:
        if current_value:
            return current_value
        return self.session.prompt(prompt)

    def do_use(self, args):
        if not args:
            console.print("Usage: use [TICKER] [--range 5d] [--freq 5m]")
            return
        parser = argparse.ArgumentParser(prog="use", add_help=False)
        parser.add_argument("ticker", type=str)
        parser.add_argument("--range", type=str, default="5d")
        parser.add_argument("--freq", type=str, default="5m")
        try:
            parsed_args, _ = parser.parse_known_args(args)
        except SystemExit:
            console.print("Usage: use [TICKER] [--range 5d] [--freq 5m]")
            return

        symbol = parsed_args.ticker
        timeframe = parsed_args.freq
        days = int(parsed_args.range.replace("d", "")) if "d" in parsed_args.range else 5
        self.ctx.active_ticker = symbol
        self.ctx.active_timeframe = timeframe

        try:
            end = pd.Timestamp.now(tz="America/New_York")
            start = end - pd.Timedelta(days=days)
            try:
                df = self.alpaca_provider.fetch_bars(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), timeframe)
                console.print("[green]Data fetched via Alpaca primary.[/green]")
            except Exception as alpaca_err:
                logger.warning("Alpaca provider failed: %s. Falling back to YahooQuery.", alpaca_err)
                df = self.yahoo_provider.fetch_bars(symbol, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), timeframe)
                console.print("[yellow]Data fetched via YahooQuery fallback.[/yellow]")
            df = add_indicators(df)
            self.ctx.data = df
            self.cache.save_data(symbol, timeframe, df, {"range": parsed_args.range})
            console.print(f"[green]Loaded {symbol} data into context.[/green]")
        except Exception as exc:
            console.print(f"[red]Error fetching data: {exc}[/red]")

    def do_model(self, args):
        if not args:
            console.print("Usage: model [hmm|ar|rnn] [--states N] [--lags N] [--hidden N]")
            return
        if self.ctx.data is None:
            console.print("[red]Error: No data loaded. Run 'use' first.[/red]")
            return
        parser = argparse.ArgumentParser(prog="model", add_help=False)
        parser.add_argument("model_type", type=str)
        parser.add_argument("--states", type=int, default=3)
        parser.add_argument("--lags", type=int, default=5)
        parser.add_argument("--hidden", type=int, default=64)
        try:
            parsed_args, _ = parser.parse_known_args(args)
        except SystemExit:
            console.print("Usage: model [hmm|ar|rnn] [--states N]")
            return

        model_type = parsed_args.model_type.lower()
        if model_type == "hmm":
            model = GaussianHMMModel(states=parsed_args.states)
        elif model_type == "ar":
            model = AutoReg(lags=parsed_args.lags)
        elif model_type == "rnn":
            model = LSTMModel(hidden=parsed_args.hidden)
        else:
            console.print(f"[red]Unknown model: {model_type}[/red]")
            return

        model.fit(self.ctx.data)
        states = model.infer_states(self.ctx.data)
        self.ctx.active_model = model_type
        self.ctx.state_sequence = states
        self.ctx.data["state"] = states
        labels = getattr(model, "state_labels", {})
        if not labels:
            labels = {int(state_id): f"State {int(state_id)}" for state_id in sorted(pd.Series(states).dropna().unique())}
        self.ctx.model_params = {"labels": labels}
        self.ctx.fitted_models[model_type] = {
            "states": states.copy(),
            "labels": labels,
            "params": model.params,
        }
        console.print(f"[green]Model {model_type} trained and states inferred (Static).[/green]")

    def do_show(self, args):
        if not args:
            console.print("Usage: show [states|summary|trades]")
            return
        cmd = args[0].lower()
        if cmd == "states":
            if self.ctx.data is None or self.ctx.state_sequence is None:
                console.print("[red]No active model states available.[/red]")
                return
            render_annotated_hlc(self.ctx.data, self.ctx.state_sequence, self.ctx.model_params.get("labels", {}), None)
            return
        if cmd == "summary":
            if self.ctx.data is None or self.ctx.state_sequence is None:
                console.print("[red]No active model summary available.[/red]")
                return
            labels = self.ctx.model_params.get("labels", {})
            df_copy = self.ctx.data.copy()
            df_copy["returns"] = df_copy["close"].pct_change()
            stats = df_copy.groupby("state")["returns"].agg(["mean", "std"]).to_dict(orient="index")
            display_data = {}
            for state, values in stats.items():
                values["label"] = labels.get(state, f"State {state}")
                display_data[state] = values
            display_summary(display_data)
            return
        if cmd == "trades":
            if not self.ctx.backtest_results:
                console.print("[red]No backtest results available to show trades.[/red]")
                return
            trades = self.ctx.backtest_results.trades.records_readable
            if trades is None or trades.empty:
                console.print("[yellow]No trades were executed.[/yellow]")
                return
            cols = ["Entry Timestamp", "Avg Entry Price", "Exit Timestamp", "Avg Exit Price", "Return"]
            console.print("[cyan]Sample of Executed Trades (Entry/Exit verification):[/cyan]")
            console.print(trades[cols].head(10))
            return
        console.print(f"Unknown show target: {cmd}")

    def do_chart(self, args):
        if not args:
            console.print("Usage: chart hlc [--overlay vwap] [--no-states] [--no-trades]")
            return
        parser = argparse.ArgumentParser(prog="chart", add_help=False)
        parser.add_argument("chart_type", type=str)
        parser.add_argument("--overlay", type=str, default=None)
        parser.add_argument("--no-states", action="store_true")
        parser.add_argument("--no-trades", action="store_true")
        try:
            parsed_args, _ = parser.parse_known_args(args)
        except SystemExit:
            console.print("Usage: chart hlc [--overlay vwap] [--no-states] [--no-trades]")
            return
        if parsed_args.chart_type.lower() != "hlc":
            console.print(f"Unknown chart type: {parsed_args.chart_type}")
            return
        if self.ctx.data is None:
            console.print("[red]No data loaded.[/red]")
            return
        states = None
        labels = None
        trades = None
        if self.ctx.last_backtest and not parsed_args.no_states:
            model_name = self.ctx.last_backtest["model"]
            model_payload = self.ctx.fitted_models.get(model_name, {})
            states = model_payload.get("states")
            labels = model_payload.get("labels")
        elif self.ctx.state_sequence is not None and not parsed_args.no_states:
            states = self.ctx.state_sequence
            labels = self.ctx.model_params.get("labels", {})
        if self.ctx.backtest_results and not parsed_args.no_trades:
            trades = self.ctx.backtest_results.trades.records_readable
        render_annotated_hlc(
            self.ctx.data,
            states=states,
            labels=labels,
            trades=trades,
            overlay_vwap=(parsed_args.overlay == "vwap"),
            show_states=not parsed_args.no_states,
            show_trades=not parsed_args.no_trades,
        )

    def do_strategy(self, args):
        if not args:
            console.print("Usage: strategy new|add|list|show ...")
            return
        cmd = args[0].lower()
        if cmd == "list":
            if not self.ctx.strategies:
                console.print("[yellow]No strategies saved.[/yellow]")
                return
            for name, builder in self.ctx.strategies.items():
                console.print(f"- {name} ({len(builder.list_rules())} rules)")
            return
        if cmd == "show":
            if len(args) < 2:
                console.print("Usage: strategy show [name]")
                return
            name = args[1]
            builder = self.ctx.strategies.get(name)
            if not builder:
                console.print(f"[red]Strategy {name} not found.[/red]")
                return
            console.print(f"[bold]{name}[/bold]")
            for idx, rule in enumerate(builder.list_rules(), start=1):
                console.print(f"  {idx}. ({rule['action']}) {rule['condition']}")
            return
        if cmd == "new":
            if len(args) < 2:
                console.print("Provide a strategy name: strategy new alpha")
                return
            name = args[1]
            parser = argparse.ArgumentParser(prog="strategy new", add_help=False)
            parser.add_argument("name", type=str)
            parser.add_argument("--rule", type=str, nargs="+", default=[])
            parser.add_argument("--action", type=str, default="long")
            parsed_args, _ = parser.parse_known_args(args[1:])
            builder = StrategyBuilder()
            try:
                if parsed_args.rule:
                    builder.add_rule(" ".join(parsed_args.rule), parsed_args.action)
                else:
                    rule_input = self.session.prompt(f"Enter rule for {name}: ")
                    action_input = self.session.prompt("Action [long|exit]: ") or "long"
                    builder.add_rule(rule_input, action_input)
            except Exception as exc:
                console.print(f"[red]Failed to build strategy: {exc}[/red]")
                return
            self.ctx.strategies[name] = builder
            self.ctx.active_strategy = name
            console.print(f"[green]Strategy {name} built and saved as active.[/green]")
            return
        if cmd == "add":
            if len(args) < 2:
                console.print("Provide a strategy name: strategy add alpha --rule \"[condition]\" --action [long|exit]")
                return
            name = args[1]
            builder = self.ctx.strategies.get(name)
            if not builder:
                console.print(f"[red]Strategy {name} does not exist. Use 'strategy new' first.[/red]")
                return
            parser = argparse.ArgumentParser(prog="strategy add", add_help=False)
            parser.add_argument("name", type=str)
            parser.add_argument("--rule", type=str, nargs="+", default=[])
            parser.add_argument("--action", type=str, default="long")
            parsed_args, _ = parser.parse_known_args(args[1:])
            try:
                if parsed_args.rule:
                    builder.add_rule(" ".join(parsed_args.rule), parsed_args.action)
                else:
                    rule_input = self.session.prompt(f"Enter rule to add to {name}: ")
                    action_input = self.session.prompt("Action [long|exit]: ") or "long"
                    builder.add_rule(rule_input, action_input)
            except Exception as exc:
                console.print(f"[red]Failed to add rule: {exc}[/red]")
                return
            console.print(f"[green]Rule added to strategy {name}. Total rules: {len(builder.list_rules())}[/green]")
            return
        console.print(f"Unknown strategy command: {cmd}")

    def _resolve_state(self, state_input: str, labels: Dict[int, str]) -> Optional[int]:
        if state_input.isdigit():
            state_id = int(state_input)
            return state_id if state_id in labels else None
        matches = [state_id for state_id, label in labels.items() if state_input.lower() in label.lower()]
        if len(matches) == 1:
            return matches[0]
        return None

    def do_backtest(self, args):
        if self.ctx.data is None:
            console.print("[red]Error: Must load data first.[/red]")
            return
        parser = argparse.ArgumentParser(prog="backtest", add_help=False)
        parser.add_argument("strategy_name", type=str, nargs="?", default=None)
        parser.add_argument("--strategy", type=str, dest="strategy_flag", default=None)
        parser.add_argument("--model", type=str, default=None)
        parser.add_argument("--state", type=str, default=None)
        try:
            parsed_args, _ = parser.parse_known_args(args)
        except SystemExit:
            console.print("Usage: backtest --strategy [name] --model [name] --state [id|label]")
            return

        strategy_name = parsed_args.strategy_flag or parsed_args.strategy_name
        strategy_name = self._prompt_if_missing("Strategy: ", strategy_name)
        if strategy_name not in self.ctx.strategies:
            console.print(f"[red]Strategy {strategy_name} not found.[/red]")
            return

        model_name = self._prompt_if_missing("Model: ", parsed_args.model or self.ctx.active_model)
        if model_name not in self.ctx.fitted_models:
            console.print(f"[red]Model {model_name} not fitted in this session.[/red]")
            return
        model_payload = self.ctx.fitted_models[model_name]
        labels = model_payload.get("labels", {})

        state_prompt_value = parsed_args.state
        if state_prompt_value is None:
            console.print("Available states:")
            for state_id, label in labels.items():
                console.print(f"  [{state_id}] {label}")
            state_prompt_value = self.session.prompt("State (id or label): ")
        target_state = self._resolve_state(state_prompt_value, labels)
        if target_state is None:
            console.print(f"[red]Invalid or ambiguous state: {state_prompt_value}[/red]")
            return

        builder = self.ctx.strategies[strategy_name]
        engine = BacktestEngine(self.ctx.data, builder)
        console.print(
            f"[yellow]Running VectorBT Backtest on strategy={strategy_name}, model={model_name}, state={target_state} ({labels.get(target_state, f'State {target_state}')}).[/yellow]"
        )
        portfolio, signals = engine.run(model_payload["states"], target_state)
        stats = portfolio.stats()
        stats_dict = {
            "Strategy": strategy_name,
            "Model": model_name,
            "State": labels.get(target_state, f"State {target_state}"),
            "Total Return [%]": stats.get("Total Return [%]", 0.0),
            "Sharpe Ratio": stats.get("Sharpe Ratio", 0.0),
            "Max Drawdown [%]": stats.get("Max Drawdown [%]", 0.0),
            "Win Rate [%]": stats.get("Win Rate [%]", 0.0),
            "Total Trades": stats.get("Total Trades", 0),
        }
        self.ctx.active_strategy = strategy_name
        self.ctx.active_model = model_name
        self.ctx.backtest_results = portfolio
        self.ctx.last_backtest = {
            "strategy": strategy_name,
            "model": model_name,
            "state_id": target_state,
            "state_label": labels.get(target_state, f"State {target_state}"),
            "signals": signals,
        }
        display_metrics(stats_dict)


if __name__ == "__main__":
    app = DejavuShell()
    app.run()
