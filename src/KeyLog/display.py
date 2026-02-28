import os

from rich.panel import Panel
from rich.table import Table
from rich.box import ROUNDED

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Static, Header, Footer, Rule
from textual.reactive import reactive

from time import monotonic

from .constants import BASE_DIR, Theme

FLASH_DURATION = 0.5
REFRESH_INTERVAL = 0.1
TOP_N_OPTIONS = [5, 10, 25, None]  # None -> show all


def get_flash_style(key: str, current_count: int, prev_counts: dict,
                    flash_dict: dict, now: float) -> str:
    prev = prev_counts.get(key, 0)
    if current_count != prev:
        flash_dict[key] = now
        prev_counts[key] = current_count

    age = now - flash_dict.get(key, 999)
    return Theme.highlight if age < FLASH_DURATION else ""


def styled(text: str, style: str) -> str:
    return f"[{style}]{text}[/]" if style else text



class TablePanel(Static):
    """Panel with a Rich Table and optional footer text."""

    table: reactive[Table | None] = reactive(None)

    def __init__(self, title: str, id: str):
        super().__init__(id=id)
        self.title = title

    def update_table(self, table: Table):
        """Update the table and optionally footer text."""
        self.table = table
        self.refresh()

    def render(self):
        if self.table is None:
            return Panel("Loading...", title=self.title, box=ROUNDED, border_style="bright_white")

        return Panel(
            self.table,
            title=self.title,
            box=ROUNDED,
            border_style=Theme.border,
        )


class SummaryPanel(Static):
    def __init__(self, id: str):
        super().__init__(id=id)
        self.table = Table.grid(expand=True)

    def update_totals(self, keyboard_total: int, mouse_total: int,
                      prev_totals: dict, totals_flash: dict):
        from time import monotonic
        now = monotonic()

        table = Table.grid(expand=True)
        table.add_column(justify="center")
        table.add_column(justify="center")
        table.add_column(justify="center")

        # Use helper to determine style per total
        keyboard_style = get_flash_style("keyboard", keyboard_total,
                                         prev_totals, totals_flash,
                                         now)
        mouse_style = get_flash_style("mouse", mouse_total,
                                      prev_totals, totals_flash, now)
        total_style = get_flash_style("total", keyboard_total + mouse_total,
                                      prev_totals, totals_flash, now)

        table.add_row(
            f"[bold]Keyboard[/]: {styled(str(keyboard_total), keyboard_style)}",
            f"[bold]Clicks[/]: {styled(str(mouse_total), mouse_style)}",
            f"[bold]Total[/]: {styled(str(keyboard_total + mouse_total), total_style)}",
        )

        self.table = table
        self.refresh()

    def render(self):
        return Panel(
            self.table,
            title="[bold]Totals[/bold]",
            title_align="center",
            box=ROUNDED,
            border_style=Theme.border,
        )


class StatsApp(App):
    """Textual app showing keyboard and mouse stats in a separate window."""

    top_n_index = 1  # start at 10

    top_n = reactive(TOP_N_OPTIONS[top_n_index])
    stats_ref = reactive(dict)

    DEBUG = False

    CSS_PATH = os.path.join(BASE_DIR, "styles.css")
    BINDINGS = [
        Binding(key="n", action="toggle_top_n", description="Toggle Count"),
        Binding(key="d", action="toggle_debug", description="Debug"),
        Binding(key="up", action="scroll_up", description="Up"),
        Binding(key="down", action="scroll_down", description="Down"),
        Binding(key="pageup", action="page_up", description="Pg Up"),
        Binding(key="pagedown", action="page_down", description="Pg Down"),
        Binding(key="s", action="sort", description="Sort Order"),
    ]

    kb_offset = 0
    kb_page_size = 10  # number of rows visible
    _prev_size = None
    size_increased = False

    reversed_sort = True

    def __init__(self, stats_ref, lock):
        super().__init__()
        self.stats_ref = stats_ref
        self.lock = lock

        # Rich tables for keyboard and mouse
        self.kb_table = Table(expand=True)
        self.kb_table.add_column("Key")
        self.kb_table.add_column("Count")

        self.ms_table = Table(expand=True)
        self.ms_table.add_column("Button")
        self.ms_table.add_column("Count")

        # Animation data
        self.prev_kb_counts = {}
        self.prev_ms_counts = {}

        self.prev_totals = {
            "keyboard": 0,
            "mouse": 0,
            "total": 0
        }

        self.kb_row_flash = {}
        self.ms_row_flash = {}

        self.totals_flash = {
            "keyboard": 0,
            "mouse": 0,
            "total": 0
        }

        self.debug_widget = Static(self.get_debug_message(), id="debug_message",
                                   expand=False)
        self.status_row = None

    def get_debug_message(self) -> str:
        return "[b]DEBUG:[/] " + f"{self.kb_offset=}, {self.kb_page_size=}"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        yield SummaryPanel(id="summary")

        with Vertical():
            with Horizontal():
                # Scrollable panels
                yield TablePanel("Keyboard", id="kb_panel")
                yield TablePanel("Mouse", id="ms_panel")

            self.status_row = Container(
                Static(
                    f"Currently Displaying: {styled(str(self.top_n if self.top_n else 'All'), Theme.highlight)}",
                    id="top_n_display",
                    expand=True,
                ),
                id="status_row",
            )

            if self.DEBUG:
                self.status_row.mount(self.debug_widget)

            yield Rule()
            yield self.status_row
            yield Footer()  # custom footer/status bar

    def on_mount(self):
        self.theme = "textual-dark"
        self.set_interval(REFRESH_INTERVAL, self.refresh_tables)
        self.set_interval(REFRESH_INTERVAL,
                          lambda: self.debug_widget.update(self.get_debug_message()))

    def on_ready(self):
        self.compute_kb_page_size()
        self.refresh_tables()

    def on_resize(self, event):
        new_size = event.size
        prev_size = new_size if self._prev_size is None else self._prev_size

        self.size_increased = new_size.height > prev_size.height

        # Update previous size for next event
        self._prev_size = new_size
        self.compute_kb_page_size()
        self.refresh_tables()

    def refresh_tables(self):
        """Update keyboard and mouse Rich Tables incrementally by rebuilding them."""
        with self.lock:
            keyboard_stats = dict(self.stats_ref.get("keyboard", {}))
            mouse_stats = dict(self.stats_ref.get("mouse", {}))

        # --- Update header totals ---
        keyboard_total = sum(keyboard_stats.values())
        mouse_total = sum(mouse_stats.values())

        summary = self.query_one("#summary", SummaryPanel)
        summary.update_totals(keyboard_total, mouse_total, self.prev_totals,
                              self.totals_flash)

        now = monotonic()

        # --- Keyboard ---
        kb_table = self.build_keyboard_table(keyboard_stats, now)
        kb_panel = self.query_one("#kb_panel", TablePanel)
        kb_panel.update_table(kb_table)

        # --- Mouse ---
        ms_table = self.build_mouse_table(mouse_stats, now)
        ms_panel = self.query_one("#ms_panel", TablePanel)
        ms_panel.update_table(ms_table)

    def action_toggle_top_n(self) -> None:
        self.top_n_index = (self.top_n_index + 1) % len(TOP_N_OPTIONS)
        self.top_n = TOP_N_OPTIONS[self.top_n_index]

        top_n_widget = self.query_one("#top_n_display", Static)
        top_n_widget.update(
            f"Currently Displaying: {styled(str(self.top_n if self.top_n else 'All'), Theme.highlight)}")
        self.refresh_bindings()

    def action_toggle_debug(self) -> None:
        if self.debug_widget in self.status_row.children:
            # Remove it from the layout
            self.debug_widget.remove()
        else:
            # Mount it back
            self.status_row.mount(self.debug_widget)

    def action_scroll_up(self):
        self.kb_offset -= 1 if self.kb_offset > 0 else 0
        self.refresh_bindings()

    def action_scroll_down(self):
        self.kb_offset += 1
        self.refresh_bindings()

    def action_page_up(self):
        self.kb_offset -= self.kb_page_size
        self.refresh_bindings()

    def action_page_down(self):
        self.kb_offset += self.kb_page_size
        self.refresh_bindings()

    def action_sort(self):
        self.reversed_sort = not self.reversed_sort
        self.refresh_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Get current table stats
        total_rows = len(self.stats_ref.get("keyboard", {}))
        displayed_rows = total_rows if self.top_n is None else self.top_n
        max_offset = max(displayed_rows - self.kb_page_size, 0)

        if action in {"scroll_up", "page_up"} and self.kb_offset <= 0:
            return None
        if action in {"scroll_down", "page_down"} and self.kb_offset >= max_offset:
            return None

        return True

    def compute_kb_page_size(self) -> None:
        """Compute how many table rows fit in the keyboard panel."""

        panel = self.query_one("#kb_panel")

        # Total available height inside the panel widget
        available = panel.size.height

        PADDING = 5 + (0 if self.size_increased else 2)

        self.kb_page_size = max(available - PADDING, 1)

    def build_keyboard_table(self, keyboard_stats: dict, now: float) -> Table:
        """Return a Rich Table for keyboard stats with highlights."""

        # --- Build table ---
        kb_table = Table(expand=True, show_header=True,
                         header_style=Theme.highlight)
        kb_table.add_column("Key", style=Theme.header)
        kb_table.add_column("Count", justify="right", style=Theme.count)

        # ---- Compute flashes for all keys ----
        all_rows: list[tuple[str, int, str | None]] = []

        for raw_key, count in keyboard_stats.items():
            key = str(raw_key)

            style = get_flash_style(
                key,
                count,
                self.prev_kb_counts,
                self.kb_row_flash,
                now,
            )

            self.prev_kb_counts[key] = count
            all_rows.append((key, count, style))

        # ---- Sort by count ----
        all_rows.sort(key=lambda r: r[1], reverse=self.reversed_sort)

        # ---- Logically apply max table size ----
        if self.top_n is not None:
            all_rows = all_rows[: self.top_n]

        # ---- Clamp scrolling offset ----
        max_offset = max(len(all_rows) - self.kb_page_size, 0)
        self.kb_offset = max(0, min(self.kb_offset, max_offset))

        visible_rows = all_rows[self.kb_offset: self.kb_offset + self.kb_page_size]

        # ---- Phase 5: render visible window ONLY ----
        for key, count, style in visible_rows:
            kb_table.add_row(
                key,
                styled(str(count), style) if style else str(count)
            )

        return kb_table

    def build_mouse_table(self, mouse_stats: dict, now: float) -> Table:
        """Return a Rich Table for mouse stats with flashes on updated buttons."""
        # --- Build the table ---
        ms_table = Table(expand=True, show_header=True,
                         header_style=f"bold {Theme.highlight}")
        ms_table.add_column("Button", style=Theme.header)
        ms_table.add_column("Count", justify="right", style=Theme.count)

        for button, count in mouse_stats.items():
            button = str(button)
            style = get_flash_style(button, count, self.prev_ms_counts,
                                    self.ms_row_flash, now)
            ms_table.add_row(button, styled(str(count), style))

        return ms_table
