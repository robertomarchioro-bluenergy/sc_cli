"""
Star Command CLI — Punto di ingresso principale.
Carica la campagna, inizializza engine + officers + presenter,
e avvia il game loop.
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt, IntPrompt

# Engine
from src.engine.campaign import Campaign, CampaignState, load_campaign_state, save_campaign_state
from src.engine.difficulty import DifficultyConfig, DifficultyPreset
from src.engine.galaxy import Galaxy, CellContent
from src.engine.ship import Ship, ShipClass, SHIP_CLASS_STATS
from src.engine.systems import create_default_systems, RepairQueue
from src.engine.captain_log import CaptainLog, LogTrigger, check_log_triggers
from src.engine.game_loop import GameState, run_game_loop

# Officers
from src.officers import TacticalOfficer, EngineerOfficer, ScienceOfficer, MedicalOfficer
from src.officers.base_officer import InteractionMode
from src.officers.special.vulcan_ambassador import VulcanAmbassador

# Presentation
from src.presentation.cli_lcars import CLILcarsPresenter

# ── Costanti ────────────────────────────────────────────
DEFAULT_CAMPAIGN = Path(__file__).parent / "src" / "config" / "campaigns" / "crisis_of_korvath.yaml"
LOG_FORMAT = "%(asctime)s %(name)s [%(levelname)s] %(message)s"


def setup_logging(level_str: str) -> None:
    """Configura il logging globale — scrive su file, non su console."""
    level = getattr(logging, level_str.upper(), logging.INFO)
    log_file = Path(__file__).parent / "star_command.log"
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        filename=str(log_file),
        filemode="w",
    )
    # Silenzia il logging verboso di httpx (logga ogni singola HTTP request)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def create_anthropic_client(api_key: str | None):
    """Crea il client Anthropic se la API key è disponibile"""
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logging.warning("Pacchetto 'anthropic' non installato — ufficiali AI disabilitati")
        return None


def choose_difficulty(console: Console) -> DifficultyPreset:
    """Menu scelta difficolta"""
    console.print("\n[bold yellow]SELEZIONA DIFFICOLTA:[/bold yellow]")
    presets = list(DifficultyPreset)
    for i, p in enumerate(presets, 1):
        console.print(f"  [bold]{i}[/bold]. {p.value}")
    try:
        choice = IntPrompt.ask("[yellow]Scelta[/yellow]", default=2)
        idx = max(0, min(len(presets) - 1, choice - 1))
        return presets[idx]
    except (ValueError, EOFError):
        return DifficultyPreset.NORMAL


def choose_ship(console: Console) -> tuple[str, ShipClass]:
    """Menu scelta nave"""
    console.print("\n[bold yellow]SELEZIONA CLASSE NAVE:[/bold yellow]")
    classes = list(ShipClass)
    for i, sc in enumerate(classes, 1):
        stats = SHIP_CLASS_STATS[sc]
        console.print(
            f"  [bold]{i}[/bold]. {sc.value:20s} "
            f"Crew {stats.crew:>4}  Energy {stats.energy:>5.0f}  "
            f"Torpedoes {stats.torpedoes:>2}  Shields {stats.shields:>3.0f}"
        )
    try:
        choice = IntPrompt.ask("[yellow]Classe[/yellow]", default=1)
        idx = max(0, min(len(classes) - 1, choice - 1))
    except (ValueError, EOFError):
        idx = 0
    ship_class = classes[idx]

    try:
        name = Prompt.ask("[yellow]Nome della nave[/yellow]", default="USS Enterprise")
    except (EOFError, KeyboardInterrupt):
        name = "USS Enterprise"

    return name, ship_class


def create_officers(
    client, model: str, interaction_mode: InteractionMode,
    special_officers: list[str], ship_name: str,
) -> dict[str, object]:
    """Crea il roster completo degli ufficiali"""
    officers: dict[str, object] = {
        "tattico": TacticalOfficer.create_default(
            client=client, model=model, interaction_mode=interaction_mode,
        ),
        "ingegnere": EngineerOfficer.create_default(
            client=client, model=model, interaction_mode=interaction_mode,
        ),
        "scientifico": ScienceOfficer.create_default(
            client=client, model=model, interaction_mode=interaction_mode,
        ),
        "medico": MedicalOfficer.create_default(
            client=client, model=model, interaction_mode=interaction_mode,
        ),
    }

    if "ambasciatore_vulcaniano" in special_officers:
        officers["speciale"] = VulcanAmbassador.create_default(
            ship_name=ship_name, client=client, model=model,
        )

    return officers


def run_new_game(console: Console, presenter: CLILcarsPresenter, campaign_path: str) -> None:
    """Avvia una nuova partita dalla campagna specificata"""
    # Carica campagna
    campaign = Campaign()
    campaign.load_from_yaml(campaign_path)

    presenter.show_title_screen()
    console.print(f"\n[bold cyan]Campagna: {campaign.nome}[/bold cyan]")
    console.print(f"[dim]{campaign.descrizione}[/dim]")

    # Scegli difficolta e nave
    preset = choose_difficulty(console)
    difficulty = DifficultyConfig.from_preset(preset)
    ship_name, ship_class = choose_ship(console)

    # Crea nave
    ship = Ship.create(ship_name, ship_class)
    is_intrepid = ship_class == ShipClass.INTREPID
    systems = create_default_systems(is_intrepid=is_intrepid)
    repair_queue = RepairQueue()
    captain_log = CaptainLog()

    # Client API
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("STAR_COMMAND_OFFICER_MODEL", "claude-sonnet-4-20250514")
    mode_str = os.getenv("STAR_COMMAND_INTERACTION_MODE", "CONTEXT")
    try:
        interaction_mode = InteractionMode(mode_str)
    except ValueError:
        interaction_mode = InteractionMode.CONTEXT

    client = create_anthropic_client(api_key)
    if client is None:
        console.print("[yellow]API key non configurata — ufficiali AI disabilitati[/yellow]")

    # Stato campagna
    campaign_state = CampaignState(
        nome_campagna=campaign.nome,
        captain_name="Capitano",
        ship=ship,
        systems=systems,
        repair_queue=repair_queue,
        difficulty=difficulty,
        captain_log=captain_log,
        stardate=campaign.stardate_inizio,
    )

    # Loop missioni
    while True:
        mission = campaign.get_next_mission(campaign_state.missions_completed)
        if mission is None:
            console.print("\n[bold green]CAMPAGNA COMPLETATA![/bold green]")
            console.print("[dim]Tutte le missioni sono state portate a termine.[/dim]")
            break

        # Briefing missione
        presenter.show_mission_briefing(mission.to_dict())
        try:
            Prompt.ask("\n[dim]Premi INVIO per iniziare la missione[/dim]")
        except (EOFError, KeyboardInterrupt):
            break

        # Crea galassia per questa missione
        galaxy = Galaxy()
        galaxy.generate(mission.seed_galassia, mission.to_dict())

        # Posiziona nave al centro del quadrante (1,1)
        ship.position = (1, 1, 4, 4)
        galaxy.set_sector(1, 1, 4, 4, CellContent.SHIP)

        # Crea ufficiali
        officers = create_officers(
            client, model, interaction_mode,
            mission.consiglieri_speciali, ship_name,
        )

        # GameState
        game_state = GameState(
            ship=ship,
            galaxy=galaxy,
            systems=systems,
            repair_queue=repair_queue,
            difficulty=difficulty,
            captain_log=captain_log,
            mission=mission,
            stardate=campaign_state.stardate,
        )

        # Entry diario inizio missione
        check_log_triggers(
            trigger=LogTrigger.MISSION_START,
            event_data={"missione": mission.nome, "obiettivo": mission.obiettivo_testo},
            captain_log=captain_log,
            stardate=game_state.stardate,
            mission_id=mission.id,
            ship_name=ship_name,
            ship_class=ship_class,
            client=client,
            model=model,
        )

        # Game loop
        end_reason = run_game_loop(
            game_state=game_state,
            officers=officers,
            presenter=presenter,
            difficulty=difficulty,
            client=client,
            model=model,
        )

        # Fine missione
        victory = game_state.mission_completed
        presenter.show_game_over(end_reason, victory)

        if victory:
            campaign_state.missions_completed.append(mission.id)
            campaign_state.stardate = game_state.stardate

            # Rifornimento tra missioni
            resupply_msgs = campaign.apply_between_mission_resupply(campaign_state)
            presenter.show_resupply(resupply_msgs)

            # Salva stato
            save_campaign_state(campaign_state)
        else:
            console.print("\n[yellow]Missione fallita. Vuoi riprovare?[/yellow]")
            try:
                retry = Prompt.ask("[yellow]S/N[/yellow]", default="S")
                if retry.strip().lower() not in ("s", "si", "y", "yes"):
                    break
            except (EOFError, KeyboardInterrupt):
                break
            # Reset sistemi per retry
            systems = create_default_systems(is_intrepid=is_intrepid)
            repair_queue = RepairQueue()
            campaign_state.systems = systems
            campaign_state.repair_queue = repair_queue


def run_continue_game(console: Console, presenter: CLILcarsPresenter) -> None:
    """Continua una partita salvata"""
    state = load_campaign_state()
    if state is None:
        console.print("[yellow]Nessun salvataggio trovato.[/yellow]")
        return

    console.print(f"\n[bold cyan]Campagna: {state.nome_campagna}[/bold cyan]")
    console.print(f"[dim]SD {state.stardate:.2f} — Missioni completate: {len(state.missions_completed)}[/dim]")

    # Ricarica campagna per ottenere la prossima missione
    campaign = Campaign()
    campaign.load_from_yaml(str(DEFAULT_CAMPAIGN))

    # Client API
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("STAR_COMMAND_OFFICER_MODEL", "claude-sonnet-4-20250514")
    client = create_anthropic_client(api_key)

    mission = campaign.get_next_mission(state.missions_completed)
    if mission is None:
        console.print("[bold green]Campagna gia completata![/bold green]")
        return

    presenter.show_mission_briefing(mission.to_dict())
    console.print("[dim]Continua dal salvataggio...[/dim]")


def main() -> None:
    """Entry point principale"""
    load_dotenv()
    setup_logging(os.getenv("STAR_COMMAND_LOG_LEVEL", "INFO"))

    console = Console()
    presenter = CLILcarsPresenter(console)

    presenter.show_title_screen()
    console.print("[bold yellow]1[/bold yellow]. Nuova Partita")
    console.print("[bold yellow]2[/bold yellow]. Continua")
    console.print("[bold yellow]3[/bold yellow]. Esci")

    try:
        choice = IntPrompt.ask("\n[yellow]Scelta[/yellow]", default=1)
    except (EOFError, KeyboardInterrupt):
        return

    campaign_path = str(DEFAULT_CAMPAIGN)

    if choice == 1:
        run_new_game(console, presenter, campaign_path)
    elif choice == 2:
        run_continue_game(console, presenter)
    else:
        console.print("[dim]Arrivederci, Capitano.[/dim]")


if __name__ == "__main__":
    main()
