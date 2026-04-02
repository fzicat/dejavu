from rich.console import Console
from rich.table import Table
import logging

logger = logging.getLogger(__name__)
console = Console()

def display_metrics(stats_dict):
    table = Table(
        title="Backtest Metrics", 
        show_header=True, 
        header_style="bold magenta",
        caption="⚠️ All results explicitly assume ZERO slippage and ZERO commission.",
        caption_style="yellow"
    )
    table.add_column("Metric", style="dim", width=20)
    table.add_column("Value")
    
    for k, v in stats_dict.items():
        table.add_row(str(k), f"{v:.2f}" if isinstance(v, float) else str(v))
        
    console.print(table)
    
def display_summary(state_data):
    """
    Expects state_data in format:
    { state_id: {'mean': X, 'std': Y, 'label': Z} }
    """
    table = Table(title="State Summaries", show_header=True, header_style="bold cyan")
    table.add_column("State", justify="right")
    table.add_column("Label")
    table.add_column("Mean Return")
    table.add_column("Volatility")
    
    for state, data in state_data.items():
        m = data.get('mean', 0.0)
        s = data.get('std', 0.0)
        l = data.get('label', 'Unknown')
        table.add_row(str(state), str(l), f"{m*100:.4f}%", f"{s*100:.4f}%")
        
    console.print(table)
