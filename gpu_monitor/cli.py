#!/usr/bin/env python3
import subprocess
import time
import argparse
from collections import deque

from rich.live import Live
from rich.panel import Panel
from rich.console import Console
from rich.layout import Layout

# Default number of data points if no width is available (should normally be overridden)
DEFAULT_HISTORY_LENGTH = 120

console = Console()

def get_gpu_metrics():
    """
    Uses nvidia-smi to retrieve GPU utilisation, used memory (in MiB),
    power draw (in Watts) and temperature (in °C).
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,power.draw,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        # Expect a single line for the first GPU; split by comma and strip spaces.
        line = result.stdout.strip().splitlines()[0]
        values = [v.strip() for v in line.split(",")]
        utilisation = float(values[0])
        mem_used = float(values[1])
        power = float(values[2])
        temp = float(values[3])
        return utilisation, mem_used, power, temp
    except Exception as e:
        console.print(f"[red]Error retrieving GPU metrics: {e}[/red]")
        return None, None, None, None

def get_gpu_info():
    """
    Uses nvidia-smi to retrieve the total GPU memory (in MiB) and the power limit (in Watts).
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total,power.limit",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        line = result.stdout.strip().splitlines()[0]
        values = [v.strip() for v in line.split(",")]
        mem_total = float(values[0])
        power_limit = float(values[1])
        return mem_total, power_limit
    except Exception as e:
        console.print(f"[red]Error retrieving GPU info: {e}[/red]")
        return None, None

def generate_filled_chart(data, colour, min_val, max_val, chart_height):
    """
    Generates an ASCII chart with the area under the curve filled and y-axis labels.
    The y-axis labels and ticks appear on the right side of the chart.
    Each column represents one data point. The curve and fill are drawn with the
    same colour as the surrounding panel.
    """
    if not data:
        return "No data available"

    ncols = len(data)
    # Create a grid of spaces for the chart area.
    grid = [[" " for _ in range(ncols)] for _ in range(chart_height)]

    # Avoid division by zero.
    span = max_val - min_val if max_val - min_val != 0 else 1

    # For each data point, determine its row in the grid.
    for i, value in enumerate(data):
        # Normalise value to a row index; higher values appear at the top.
        relative = (value - min_val) / span
        relative = max(0, min(1, relative))
        row = chart_height - 1 - int(relative * (chart_height - 1))
        # Draw the curve.
        grid[row][i] = "▇"
        # Fill the area below the curve.
        for r in range(row + 1, chart_height):
            grid[r][i] = "█"

    # Build the string with y-axis labels on the right.
    lines = []
    for row_idx in range(chart_height):
        # Compute the corresponding y-axis value.
        if chart_height > 1:
            y_val = max_val - row_idx * (max_val - min_val) / (chart_height - 1)
        else:
            y_val = max_val
        chart_line = "".join(grid[row_idx])
        # Append the tick and label to the right.
        label = f" │ {y_val:6.1f}"
        # Wrap the entire line with the colour.
        lines.append(f"[{colour}]{chart_line}{label}[/{colour}]")
    return "\n".join(lines)

def generate_chart(title, data, colour, min_val, max_val, chart_height):
    """
    Returns a Panel containing an ASCII chart for the given data.
    The chart's height is set to 'chart_height' so it fills the panel.
    """
    chart = generate_filled_chart(data, colour, min_val, max_val, chart_height)
    return Panel(chart, title=title, border_style=colour)

def build_layout(util_panel, mem_panel, power_panel, temp_panel):
    """
    Builds and returns a vertical layout with the provided panels.
    """
    layout = Layout(name="root")
    layout.split_column(
        Layout(util_panel, name="utilisation"),
        Layout(mem_panel, name="memory"),
        Layout(power_panel, name="power"),
        Layout(temp_panel, name="temperature"),
    )
    return layout

def main():
    parser = argparse.ArgumentParser(
        description="GPU Monitoring Dashboard with dynamically resizing history length."
    )
    parser.add_argument(
        "-n",
        "--history-length",
        type=int,
        default=DEFAULT_HISTORY_LENGTH,
        help="Initial number of data points to display in each chart (default: 60). "
             "This value will be overridden by the terminal width.",
    )
    args = parser.parse_args()

    # Start with the initial history length from the command line.
    current_history_length = args.history_length

    # Set up historical data deques for each metric.
    util_history = deque([0] * current_history_length, maxlen=current_history_length)
    mem_history = deque([0] * current_history_length, maxlen=current_history_length)
    power_history = deque([0] * current_history_length, maxlen=current_history_length)
    temp_history = deque([0] * current_history_length, maxlen=current_history_length)

    # Retrieve full GPU specs for memory and power.
    mem_total, power_limit = get_gpu_info()
    if mem_total is None or power_limit is None:
        console.print("[red]Unable to retrieve GPU full specs. Exiting.[/red]")
        return

    with Live(console=console, refresh_per_second=4) as live:
        while True:
            # Determine available width for the chart.
            # Account for right-hand y-axis label and tick (approx 10 characters).
            tick_margin = 15
            term_width = console.size.width
            new_history_length = max(10, term_width - tick_margin)

            # If the terminal width has changed, update the deques.
            if new_history_length != current_history_length:
                current_history_length = new_history_length
                util_history = deque(list(util_history)[-current_history_length:], maxlen=current_history_length)
                mem_history = deque(list(mem_history)[-current_history_length:], maxlen=current_history_length)
                power_history = deque(list(power_history)[-current_history_length:], maxlen=current_history_length)
                temp_history = deque(list(temp_history)[-current_history_length:], maxlen=current_history_length)

            # Calculate the available height for each chart panel.
            term_height = console.size.height
            # Leave room for panel borders and titles.
            chart_height = max(4, (term_height - 8) // 4)

            util, mem, power, temp = get_gpu_metrics()
            if util is None:
                time.sleep(1)
                continue

            util_history.append(util)
            mem_history.append(mem)
            power_history.append(power)
            temp_history.append(temp)

            # Create charts for each metric.
            util_panel = generate_chart("GPU Utilisation (%)", util_history, "green", 0, 100, chart_height)
            mem_panel = generate_chart("Memory Used (MiB)", mem_history, "cyan", 0, mem_total, chart_height)
            power_panel = generate_chart("Power Draw (W)", power_history, "magenta", 0, power_limit, chart_height)
            # For temperature, allow a little extra headroom above current measurements.
            temp_max = max(max(temp_history), 100)
            temp_panel = generate_chart("Temperature (°C)", temp_history, "red", 0, temp_max, chart_height)

            # Build the layout with each metric's panel.
            layout = build_layout(util_panel, mem_panel, power_panel, temp_panel)
            live.update(layout)
            time.sleep(1)

if __name__ == "__main__":
    main()
