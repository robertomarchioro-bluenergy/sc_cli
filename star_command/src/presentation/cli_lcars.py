"""
Presenter CLI con tema LCARS (Star Trek) basato su Rich.
Schermo fisso con clear prima di ogni turno.
Mappa a due livelli: panoramica galattica + griglia settori 8x8.
"""
from __future__ import annotations

import os

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt
from rich import box

from .base_presenter import BasePresenter
from ..engine.command_parser import get_contextual_menu

# Palette LCARS-inspired
LCARS_COLORS = {
    "red": "bold red",
    "green": "bold green",
    "blue": "bold blue",
    "cyan": "bold cyan",
    "amber": "bold yellow",
    "yellow": "yellow",
    "magenta": "bold magenta",
    "white": "bold white",
    "dim": "dim white",
}

# Colori per contenuto celle mappa
CELL_STYLES = {
    "*": "yellow",        # stella
    "B": "bold green",    # base stellare
    "K": "bold red",      # klingon
    "R": "bold magenta",  # romulano
    "!": "bold red",      # borg
    "X": "bold red",      # silenziosi
    "W": "dim yellow",    # relitto
    "?": "bold cyan",     # anomalia
    "~": "dim cyan",      # nebula
    "P": "bold blue",     # pianeta
    "E": "bold white",    # nave giocatore
    "\u00b7": "dim white",  # vuoto (·)
}

# Emoji/simboli per sistemi status
STATUS_ICONS = {
    "NOMINALE": "[green]OK[/green]",
    "DEGRADATO": "[yellow]!![/yellow]",
    "CRITICO": "[red]XX[/red]",
    "OFFLINE": "[bold red]--[/bold red]",
}

# Colori per ruoli ufficiali
OFFICER_COLORS = {
    "tattico": "red",
    "ingegnere": "yellow",
    "scientifico": "blue",
    "medico": "cyan",
    "speciale": "magenta",
}


class CLILcarsPresenter(BasePresenter):
    """Implementazione CLI con tema LCARS usando Rich — schermo fisso"""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        # Buffer per messaggi del turno corrente (mostrati sotto il bridge)
        self._messages: list[str] = []

    def render_bridge(self, game_state: dict) -> None:
        """Pulisce lo schermo e ridisegna il bridge completo"""
        # Pulisci schermo — la UI rimane fissa
        self.console.clear()

        ship = game_state["ship"]
        ctx = game_state.get("context", "NAVIGATION")

        # Header con stardate e contesto
        header = Text()
        header.append("LCARS ", style="bold yellow")
        header.append(f"// SD {game_state['stardate']:.2f}", style="bold white")
        header.append(f"  [{ctx}]", style=_context_style(ctx))
        header.append(f"  T{game_state.get('turn_number', 0)}", style="dim")

        # Tabella stato nave compatta
        table = Table(
            box=box.ROUNDED,
            border_style="yellow",
            show_header=False,
            padding=(0, 1),
            expand=True,
        )
        table.add_column("label", style="bold yellow", width=14)
        table.add_column("value", ratio=1)

        table.add_row(
            "NAVE",
            f"[bold white]{ship['name']}[/bold white] ({ship['ship_class']})",
        )
        table.add_row("SCAFO", _bar(ship["hull_pct"], 100, "green", "red"))
        table.add_row("SCUDI", _bar(ship["shields_pct"], 150, "cyan", "red"))
        table.add_row(
            "ENERGIA",
            _bar(ship["energy"], ship["energy_max"], "blue", "red")
            + f"  [dim]{ship['energy']:.0f}/{ship['energy_max']:.0f}[/dim]",
        )
        table.add_row(
            "RISORSE",
            f"Siluri [bold]{ship['torpedoes']}[/bold]/{ship['torpedoes_max']}  "
            f"Dilithium [bold]{ship['dilithium']}[/bold]/{ship['dilithium_max']}",
        )
        table.add_row(
            "EQUIPAGGIO",
            f"[bold]{ship['crew']}[/bold]/{ship['crew_max']}  "
            f"Morale {_bar(ship['morale_pct'], 100, 'green', 'yellow')}",
        )
        table.add_row(
            "POSIZIONE",
            f"Q({ship['position'][0]},{ship['position'][1]}) "
            f"S({ship['position'][2]},{ship['position'][3]})",
        )

        # Missione
        mission_line = ""
        if game_state.get("mission_nome"):
            mission_line = (
                f"[bold]{game_state['mission_nome']}[/bold] — "
                f"{game_state.get('mission_obiettivo', '')}"
                f"  [dim]Deadline SD {game_state.get('deadline_stardate', '?')}[/dim]"
            )

        # Nemici nel settore
        enemies = game_state.get("enemies", [])
        enemy_line = ""
        if enemies:
            types = [e.get("enemy_type", "?") for e in enemies]
            enemy_line = f"[bold red]NEMICI: {', '.join(types)} ({len(enemies)})[/bold red]"

        # Pannello bridge
        self.console.print(Panel(
            table,
            title=f"[bold yellow]{header}[/bold yellow]",
            subtitle=mission_line or None,
            border_style="yellow",
            box=box.DOUBLE,
        ))

        if enemy_line:
            self.console.print(f"  {enemy_line}")

        # Mostra messaggi accumulati dal turno precedente
        if self._messages:
            self.console.print()
            for msg in self._messages:
                self.console.print(msg)
            self._messages.clear()

    def show_officer_message(self, officer_name: str, role: str, message: str, trust: float) -> None:
        """Mostra il messaggio dell'ufficiale in un pannello colorato"""
        color = OFFICER_COLORS.get(role, "white")
        trust_bar = _bar(trust, 100, "green", "red", width=10)

        self.console.print(Panel(
            f"[white]{message}[/white]",
            title=f"[bold {color}]{officer_name}[/bold {color}] [{role.upper()}]",
            subtitle=f"Trust {trust_bar} {trust:.0f}%",
            border_style=color,
            box=box.ROUNDED,
            padding=(0, 2),
        ))

    def show_narrative_short(self, text: str, color: str) -> None:
        """Mostra un breve messaggio narrativo — bufferizzato per il prossimo render"""
        style = LCARS_COLORS.get(color, "white")
        self._messages.append(f"  [{style}]{text}[/{style}]")
        # Stampa anche subito per comandi che non causano re-render
        self.console.print(f"  [{style}]{text}[/{style}]")

    def show_narrative_long(self, text: str, title: str) -> None:
        """Mostra un blocco narrativo in pannello"""
        self.console.print(Panel(
            text,
            title=f"[bold cyan]{title}[/bold cyan]",
            border_style="cyan",
            box=box.DOUBLE,
            padding=(1, 2),
        ))

    def show_map_overlay(self, galaxy_state: dict, ship_position: tuple) -> None:
        """
        Mappa a due livelli:
        1. Panoramica galattica 8x8 quadranti (conteggi)
        2. Griglia settori 8x8 del quadrante corrente (cella per cella)
        """
        self.console.clear()
        quadrants = galaxy_state.get("quadrants", [])
        q_row, q_col, s_row, s_col = ship_position

        # ── LIVELLO 1: panoramica galattica ──
        gal_table = Table(
            title="[bold yellow]MAPPA GALATTICA[/bold yellow]",
            box=box.HEAVY,
            border_style="yellow",
            show_header=True,
            header_style="bold yellow",
            padding=(0, 0),
        )
        gal_table.add_column("", style="bold yellow", width=3)
        for c in range(1, 9):
            gal_table.add_column(str(c), width=8, justify="center")

        for r in range(8):
            row_cells: list[str] = []
            for c in range(8):
                q_data = quadrants[r][c]
                vis = q_data.get("visibility", "UNKNOWN")
                is_current = (r + 1, c + 1) == (q_row, q_col)

                if vis == "UNKNOWN":
                    cell = "[dim]  ???  [/dim]"
                elif vis == "NEBULA_OBSCURED":
                    total = sum(
                        1 for srow in q_data.get("sectors", [])
                        for s in srow if s != "\u00b7"
                    )
                    cell = f"[dim cyan] ~{total:>2}~  [/dim cyan]"
                else:
                    cell = _render_quadrant_summary(q_data)

                # Evidenzia quadrante corrente
                if is_current:
                    cell = f"[on dark_green]{cell}[/on dark_green]"

                row_cells.append(cell)
            gal_table.add_row(str(r + 1), *row_cells)

        self.console.print(gal_table)
        self.console.print(
            "  [dim]K=Klingon R=Romulano !=Borg X=Silenti B=Base "
            "*=Stella ?=Anomalia ~=Nebula P=Pianeta E=Nave[/dim]"
        )

        # ── LIVELLO 2: griglia settori del quadrante corrente ──
        self.console.print()
        current_q = quadrants[q_row - 1][q_col - 1]
        sectors = current_q.get("sectors", [])

        sec_table = Table(
            title=f"[bold cyan]QUADRANTE ({q_row},{q_col}) — SETTORI[/bold cyan]",
            box=box.HEAVY,
            border_style="cyan",
            show_header=True,
            header_style="bold cyan",
            padding=(0, 0),
        )
        sec_table.add_column("", style="bold cyan", width=2)
        for c in range(1, 9):
            sec_table.add_column(str(c), width=3, justify="center")

        for r_idx, row in enumerate(sectors):
            row_cells = []
            for c_idx, cell_val in enumerate(row):
                is_ship = (r_idx + 1 == s_row and c_idx + 1 == s_col)
                if is_ship:
                    # Posizione nave — sempre evidenziata
                    row_cells.append("[bold white on dark_green]E[/bold white on dark_green]")
                else:
                    style = CELL_STYLES.get(cell_val, "dim white")
                    # Mostra il simbolo o punto per vuoto
                    display = cell_val if cell_val != "\u00b7" else "\u00b7"
                    row_cells.append(f"[{style}]{display}[/{style}]")
            sec_table.add_row(str(r_idx + 1), *row_cells)

        self.console.print(sec_table)

        # Premi per continuare
        self.console.print()
        try:
            Prompt.ask("[dim]Premi INVIO per tornare al bridge[/dim]")
        except (EOFError, KeyboardInterrupt):
            pass

    def show_systems_overlay(self, systems_state: dict, repair_queue: list) -> None:
        """Mostra stato sistemi di bordo in tabella"""
        table = Table(
            title="[bold yellow]SISTEMI DI BORDO[/bold yellow]",
            box=box.ROUNDED,
            border_style="yellow",
            show_header=True,
            header_style="bold",
        )
        table.add_column("Sistema", style="bold", width=22)
        table.add_column("Integrita", width=20, justify="center")
        table.add_column("Stato", width=10, justify="center")
        table.add_column("Penalty", width=10, justify="right")

        for sys_name, sys_data in systems_state.items():
            integrity = sys_data["integrity"]
            if integrity > 50:
                status_str = "NOMINALE"
            elif integrity > 19:
                status_str = "DEGRADATO"
            elif integrity > 0:
                status_str = "CRITICO"
            else:
                status_str = "OFFLINE"

            status_icon = STATUS_ICONS.get(status_str, "?")
            bar = _bar(integrity, 100, "green", "red", width=15)

            if integrity >= 50.0:
                penalty = 0.0
            else:
                penalty = ((50.0 - integrity) / 50.0) ** 1.5

            table.add_row(
                sys_name,
                bar,
                status_icon,
                f"{penalty:.2f}" if penalty > 0 else "[green]0.00[/green]",
            )

        self.console.print()
        self.console.print(table)

        if repair_queue:
            rq_table = Table(
                title="[bold green]CODA RIPARAZIONI[/bold green]",
                box=box.SIMPLE,
                border_style="green",
            )
            rq_table.add_column("Sistema", width=22)
            rq_table.add_column("Priorita", width=10, justify="center")
            rq_table.add_column("Progresso", width=15, justify="center")

            for job in repair_queue:
                rq_table.add_row(
                    job.get("system", "?"),
                    str(job.get("priority", "?")),
                    _bar(job.get("progress", 0), 100, "green", "yellow", width=10),
                )
            self.console.print(rq_table)

    def show_captain_log_overlay(self, entries: list) -> None:
        """Mostra il diario del capitano"""
        if not entries:
            self.console.print("  [dim]Nessuna voce nel diario del Capitano.[/dim]")
            return

        table = Table(
            title="[bold cyan]DIARIO DEL CAPITANO[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("SD", width=8, justify="right")
        table.add_column("Tipo", width=10, justify="center")
        table.add_column("Testo", ratio=1)

        for entry in entries[-15:]:
            sd = f"{entry.get('stardate', 0):.2f}"
            tipo = entry.get("tipo", entry.get("type", "?"))
            text = entry.get("testo", entry.get("text", ""))
            table.add_row(sd, tipo, text)

        self.console.print()
        self.console.print(table)

    def show_contextual_menu(self, context: str) -> str:
        """Mostra il menu contestuale per il contesto corrente"""
        menu_items = get_contextual_menu(context)

        table = Table(
            title=f"[bold yellow]COMANDI DISPONIBILI [{context}][/bold yellow]",
            box=box.SIMPLE,
            border_style="yellow",
            show_header=False,
            padding=(0, 2),
        )
        table.add_column("Comando", style="bold cyan", width=28)
        table.add_column("Descrizione", style="white")

        for cmd, desc in menu_items:
            table.add_row(cmd, desc)

        self.console.print()
        self.console.print(table)
        return ""

    def get_captain_input(self) -> str:
        """Legge il comando dal Capitano con prompt LCARS"""
        self.console.print()
        try:
            return Prompt.ask("[bold yellow]CAPITANO[/bold yellow]")
        except (EOFError, KeyboardInterrupt):
            return ""

    def show_confirm(self, message: str) -> bool:
        """Chiede conferma S/N"""
        try:
            answer = Prompt.ask(f"[bold yellow]{message}[/bold yellow]")
            return answer.strip().lower() in ("s", "si", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    # ── Schermate speciali ────────────────────────────

    def show_title_screen(self) -> None:
        """Mostra la schermata titolo"""
        self.console.clear()
        title_art = """
[bold yellow]
    _____ _______       _____     _____ ____  __  __ __  __          _   _ _____
   / ____|__   __|/\\   |  __ \\   / ____/ __ \\|  \\/  |  \\/  |   /\\  | \\ | |  __ \\
  | (___    | |  /  \\  | |__) | | |   | |  | | \\  / | \\  / |  /  \\ |  \\| | |  | |
   \\___ \\   | | / /\\ \\ |  _  /  | |   | |  | | |\\/| | |\\/| | / /\\ \\| . ` | |  | |
   ____) |  | |/ ____ \\| | \\ \\  | |___| |__| | |  | | |  | |/ ____ \\ |\\  | |__| |
  |_____/   |_/_/    \\_\\_|  \\_\\  \\_____\\____/|_|  |_|_|  |_/_/    \\_\\_| \\_|_____/
[/bold yellow]
[dim]  Un gioco CLI di strategia spaziale ispirato a Star Trek[/dim]
[dim]  Ufficiali AI alimentati da Claude | Engine procedurale[/dim]
"""
        self.console.print(title_art)

    def show_mission_briefing(self, mission: dict) -> None:
        """Mostra il briefing della missione"""
        self.console.print()
        self.console.print(Panel(
            f"[white]{mission.get('descrizione_narrativa', '')}[/white]\n\n"
            f"[bold]Obiettivo:[/bold] {mission.get('obiettivo_testo', '')}\n"
            f"[bold]Deadline:[/bold] SD {mission.get('deadline_stardate', '?')}",
            title=f"[bold cyan]BRIEFING: {mission.get('nome', 'Missione')}[/bold cyan]",
            subtitle=f"[dim]Missione {mission.get('id', '?')}[/dim]",
            border_style="cyan",
            box=box.DOUBLE,
            padding=(1, 3),
        ))

    def show_game_over(self, reason: str, victory: bool) -> None:
        """Mostra la schermata di fine partita"""
        self.console.clear()
        color = "green" if victory else "red"
        title = "MISSIONE COMPLETATA" if victory else "MISSIONE FALLITA"

        self.console.print()
        self.console.print(Panel(
            f"[bold {color}]{reason}[/bold {color}]",
            title=f"[bold {color}]{title}[/bold {color}]",
            border_style=color,
            box=box.DOUBLE,
            padding=(1, 3),
        ))

    def show_resupply(self, messages: list[str]) -> None:
        """Mostra il rifornimento tra missioni"""
        text = "\n".join(f"  {msg}" for msg in messages)
        self.console.print(Panel(
            text,
            title="[bold green]RIFORNIMENTO[/bold green]",
            border_style="green",
            box=box.ROUNDED,
        ))


# ── Funzioni helper private ─────────────────────────────


def _bar(value: float, max_val: float, color_ok: str, color_low: str, width: int = 20) -> str:
    """Genera una barra ASCII colorata"""
    if max_val <= 0:
        return "[dim]N/A[/dim]"
    pct = max(0.0, min(1.0, value / max_val))
    filled = int(pct * width)
    empty = width - filled

    if pct > 0.5:
        color = color_ok
    elif pct > 0.2:
        color = "yellow"
    else:
        color = color_low

    bar_str = f"[{color}]{'|' * filled}[/{color}][dim]{'.' * empty}[/dim]"
    pct_str = f" {pct * 100:.0f}%"
    return bar_str + pct_str


def _context_style(context: str) -> str:
    """Restituisce lo stile Rich per il contesto"""
    styles = {
        "COMBAT": "bold red",
        "NAVIGATION": "bold cyan",
        "DOCKED": "bold green",
        "AFTER_LOSS": "bold yellow",
        "EXPLORATION": "bold blue",
        "DIPLOMACY": "bold magenta",
    }
    return styles.get(context, "white")


def _render_quadrant_summary(q_data: dict) -> str:
    """Renderizza il riassunto di un quadrante nella panoramica galattica"""
    sectors = q_data.get("sectors", [])
    counts: dict[str, int] = {}
    for row in sectors:
        for cell in row:
            if cell != "\u00b7":
                counts[cell] = counts.get(cell, 0) + 1

    # Mostra solo entita importanti (nemici, basi, anomalie)
    parts = []
    for sym in ("K", "R", "!", "X", "B", "?"):
        if sym in counts:
            style = CELL_STYLES.get(sym, "white")
            parts.append(f"[{style}]{sym}{counts[sym]}[/{style}]")

    return " ".join(parts) if parts else "[dim]  \u00b7  [/dim]"
