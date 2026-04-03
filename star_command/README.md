# Star Command CLI

Gioco di strategia spaziale a turni ispirato a Star Trek, giocabile interamente da terminale.
Ogni ufficiale di bordo e un agente AI alimentato da Claude che fornisce consigli contestuali
in base al proprio ruolo, personalita e livello di fiducia verso il Capitano.

---

## Indice

1. [Deploy e installazione](#deploy-e-installazione)
2. [Configurazione](#configurazione)
3. [Avvio del gioco](#avvio-del-gioco)
4. [Come si gioca](#come-si-gioca)
5. [Comandi disponibili](#comandi-disponibili)
6. [Meccaniche di gioco](#meccaniche-di-gioco)
7. [Personalizzazione](#personalizzazione)
8. [Architettura](#architettura)
9. [Test](#test)

---

## Deploy e installazione

### Requisiti di sistema

- **Python** >= 3.9 (consigliato 3.10+)
- **pip** per la gestione dei pacchetti
- Un terminale con supporto colori (Windows Terminal, iTerm2, qualsiasi terminale Linux)
- **API key Anthropic** (opzionale — senza di essa il gioco funziona ma gli ufficiali AI sono disabilitati)

### Installazione locale

```bash
# 1. Clona il repository
git clone https://github.com/robertomarchioro-bluenergy/sc_cli.git
cd sc_cli/star_command

# 2. Crea un virtual environment (consigliato)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. Installa le dipendenze
pip install -r requirements.txt
```

### Dipendenze

| Pacchetto | Versione | Scopo |
|-----------|----------|-------|
| `anthropic` | >= 0.49.0 | Client API Claude per ufficiali AI e diario |
| `rich` | >= 13.0.0 | Interfaccia terminale LCARS (pannelli, tabelle, colori) |
| `pyyaml` | >= 6.0.0 | Caricamento campagne da file YAML |
| `python-dotenv` | >= 1.0.0 | Lettura variabili ambiente da `.env` |
| `pytest` | >= 8.0.0 | Framework di test |
| `pytest-mock` | >= 3.0.0 | Mock per i test |

### Deploy su server / Docker

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY star_command/ .
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]
```

Per eseguire in Docker:
```bash
docker build -t star-command .
docker run -it --env-file star_command/.env star-command
```

> **Nota**: il gioco richiede un terminale interattivo (`-it`), non puo girare in background.

---

## Configurazione

Copia il file di esempio e personalizza:

```bash
cp .env.example .env
```

### Variabili ambiente (.env)

| Variabile | Default | Descrizione |
|-----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(nessuno)* | La tua API key Anthropic. Senza di essa gli ufficiali AI non parlano |
| `STAR_COMMAND_OFFICER_MODEL` | `claude-sonnet-4-20250514` | Modello Claude per gli ufficiali AI |
| `STAR_COMMAND_LOG_MODEL` | `claude-sonnet-4-20250514` | Modello Claude per le entry automatiche del diario |
| `STAR_COMMAND_INTERACTION_MODE` | `CONTEXT` | Modalita interazione ufficiali (vedi sotto) |
| `STAR_COMMAND_LOG_LEVEL` | `INFO` | Livello di log (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

### Modalita di interazione ufficiali

| Modalita | Comportamento |
|----------|---------------|
| `CONTEXT` | L'ufficiale parla automaticamente solo quando il contesto e rilevante per il suo ruolo (default) |
| `BRIDGE_ACTIVE` | L'ufficiale commenta ogni singolo turno |
| `ON_CALL` | L'ufficiale parla solo se chiamato esplicitamente dal Capitano |
| `EMERGENCY_ONLY` | L'ufficiale interviene solo in situazioni critiche (risorse < 20%) |

---

## Avvio del gioco

```bash
cd star_command
python main.py
```

All'avvio viene mostrato il menu principale:

```
1. Nuova Partita    — inizia la campagna dall'inizio
2. Continua         — riprendi da un salvataggio automatico
3. Esci
```

### Nuova Partita

1. **Scegli la difficolta** (Esploratore / Ufficiale / Comandante / Capitano Kirk)
2. **Scegli la classe nave** tra le 7 disponibili
3. **Dai un nome alla tua nave** (default: USS Enterprise)
4. Viene mostrato il briefing della prima missione
5. Premi INVIO per iniziare

---

## Come si gioca

### Il turno di gioco

Ogni turno segue questa sequenza:

1. **Bridge** — viene visualizzato lo stato completo della nave (scafo, scudi, energia, risorse, posizione)
2. **Ufficiale di turno** — l'ufficiale competente per il contesto corrente offre un consiglio
3. **Comando del Capitano** — scrivi un comando in italiano o inglese
4. **Esecuzione** — il comando viene eseguito e gli effetti applicati
5. **Riparazioni** — la coda riparazioni avanza di un tick
6. **Turno nemico** — se ci sono nemici, attaccano o si muovono
7. **Verifica fine** — controlla condizioni di vittoria o sconfitta

### Contesti di gioco

Il gioco cambia dinamicamente in base alla situazione:

| Contesto | Attivazione | Ufficiale attivo |
|----------|-------------|------------------|
| **NAVIGATION** | Nessun nemico, nessuna anomalia | Scientifico |
| **COMBAT** | Nemici rilevati nel settore | Tattico |
| **DOCKED** | Attraccati a una base stellare | Ingegnere |
| **AFTER_LOSS** | Perdite nell'equipaggio al turno precedente | Medico |
| **EXPLORATION** | Anomalia rilevata nella posizione | Scientifico |
| **DIPLOMACY** | Contatto diplomatico attivo | Speciale (Ambasciatore) |

### La mappa galattica

La galassia e una griglia **8x8 quadranti**, ciascuno contenente una sotto-griglia **8x8 settori**.
La posizione si esprime come `Q(riga,colonna) S(riga,colonna)`.

La mappa ha un sistema di **fog of war**:
- **UNKNOWN** — nessuna informazione
- **ADJACENT** — conteggi parziali (quadranti adiacenti a quelli visitati)
- **NEBULA_OBSCURED** — solo conteggio totale, nessun dettaglio tipo
- **SCANNED** — visibilita completa
- **CURRENT** — quadrante in cui ti trovi (sempre aggiornato)

### Simboli sulla mappa

| Simbolo | Significato |
|---------|-------------|
| `E` | La tua nave |
| `K` | Nave Klingon |
| `R` | Nave Romulana |
| `!` | Cubo/sfera Borg |
| `X` | I Silenziosi |
| `B` | Base stellare Federazione |
| `*` | Stella (ostacolo navigazione) |
| `?` | Anomalia non identificata |
| `~` | Nebula (oscura sensori) |
| `P` | Pianeta |
| `W` | Relitto con tracce Silenziosi |

---

## Comandi disponibili

I comandi si scrivono in **italiano o inglese**, in linguaggio naturale. Il parser riconosce
varianti e sinonimi. Digita `?` per il menu contestuale.

### Combattimento

| Comando | Effetto |
|---------|---------|
| `spara faser 500` | Colpo faser con 500 unita di energia |
| `fire phaser 300` | Equivalente inglese |
| `spara siluro` | Lancia siluro fotone (richiede conferma) |
| `scudi max` / `shields full` | Scudi al massimo |
| `scudi 75` | Imposta scudi al 75% |

### Navigazione

| Comando | Effetto |
|---------|---------|
| `warp 3` | Viaggio a warp 3 (tra quadranti) |
| `impulso 5 3` | Movimento impulso al settore (5,3) del quadrante corrente |
| `scan` | Scansione del quadrante corrente |
| `mappa` / `map` | Visualizza mappa galattica |

### Tabella consumi warp

| Velocita | Energia | Dilithium | Portata |
|----------|---------|-----------|---------|
| Impulso | 100/settore | 0 | 1 settore |
| Warp 1 | 200 | 1 | 1 quadrante |
| Warp 3 | 500 | 3 | 3 quadranti |
| Warp 6 | 1200 | 8 | 6 quadranti |
| Warp 9 (emergenza) | 2000 | 15 | 9 quadranti |

### Informazioni

| Comando | Effetto |
|---------|---------|
| `stato nave` / `status` | Stato completo della nave |
| `sistemi` / `systems` | Diagnostica sistemi di bordo |
| `missione` | Mostra obiettivi correnti |
| `diario` | Mostra il diario del Capitano |
| `diario: testo libero` | Aggiunge nota manuale al diario |
| `export log` | Esporta il diario su file di testo |
| `?` | Menu comandi disponibili |

### Ufficiali

| Comando | Effetto |
|---------|---------|
| `rapporto tattico` | Consulta l'Ufficiale Tattico |
| `rapporto ingegnere` | Consulta l'Ingegnere Capo |
| `rapporto scientifico` | Consulta l'Ufficiale Scientifico |
| `rapporto medico` | Consulta il Medico di Bordo |
| `riunione equipaggio` | Convoca riunione — tutti parlano (richiede conferma) |

### Stazione e riparazioni

| Comando | Effetto |
|---------|---------|
| `attracco` / `dock` | Attracca a una base stellare adiacente |
| `ripara sensori` | Aggiunge il sistema alla coda riparazioni |
| `ripara motori_warp` | Ripara i motori warp |

---

## Meccaniche di gioco

### Sistemi di bordo

Ogni sistema ha un'integrita da 0% a 100% con degrado esponenziale:

| Integrita | Stato | Penalty | Effetto |
|-----------|-------|---------|---------|
| > 50% | NOMINALE | 0.00 | Funzionamento normale |
| 20-50% | DEGRADATO | 0.09-0.46 | Prestazioni ridotte progressivamente |
| 1-19% | CRITICO | 0.46-0.99 | Funzionamento molto compromesso |
| 0% | OFFLINE | 1.00 | Sistema non funzionante |

La formula di penalty e: `((50 - integrita) / 50) ^ 1.5` quando l'integrita e sotto il 50%.

**Sistemi disponibili**: motori warp, motori impulso, computer puntamento, scudo deflettore,
lanciasiluri, sensori, comunicazioni, medicina di bordo, supporto vitale
(+ bio_neural_gel solo per classe Intrepid).

### Combattimento

- I **faser** consumano energia e la probabilita di colpire dipende da: integrita computer di puntamento, distanza, morale, e se hai seguito il consiglio del Tattico (+15%)
- I **siluri** non consumano energia ma sono limitati. Penetrano il 30% degli scudi nemici
- I **Borg** adattano la resistenza ai faser dopo 2 colpi (fino al 90% di resistenza)
- I **Romulani** si ritirano sotto il 30% scafo e possono tendere imboscate nelle nebule
- I **Klingon** non si ritirano mai
- I **Silenziosi** sono passivi nelle prime missioni (M01-M02) e diventano letali da M03

### Ufficiali AI e sistema Trust

Ogni ufficiale ha un **trust** (0-100) e un **morale personale** (0-100):

- **Consiglio seguito** (fai quello che suggerisce): +2 trust
- **Consiglio ignorato**: -1 trust
- **5 consigli ignorati consecutivi**: -10 morale personale
- **Morale < 50%**: bonus meccanici dimezzati
- **Morale < 20%**: l'ufficiale diventa quasi silenzioso (nessun bonus)

Gli ufficiali hanno anche **bonus di specie** che influenzano il gameplay:

| Specie | Bonus |
|--------|-------|
| Klingon | +25% danno combattimento, rifiuta la ritirata |
| Vulcaniano | +20% scansioni, +15% targeting, -20% recupero morale altrui |
| Betazoide | +30% recupero morale, rileva inganni, -10% combattimento |
| Andoriano | +15% tattica posizionale, +10% manovre evasive |
| Trill | +10% a tutti i modificatori |
| Umano | +5% in situazioni nuove |
| Bajoriano | +15% resilienza morale |
| Ferengi | Negozia rifornimenti, conosce rotte commerciali |

### Rifornimento tra missioni

Dopo ogni missione completata:
- Energia: +60% del massimo di classe
- Dilithium: +30% del massimo
- Siluri: nessun rifornimento
- Morale: +10 punti fissi
- Sistemi sotto 70%: riparati a 70%

### Salvataggio

Il gioco salva automaticamente ogni 10 turni nella cartella `saves/`.
Per continuare una partita, scegli "Continua" dal menu principale.

---

## Personalizzazione

### Creare una nuova campagna

Le campagne sono file YAML in `src/config/campaigns/`. Crea un nuovo file seguendo
questa struttura:

```yaml
campagna:
  nome: "Nome della tua campagna"
  descrizione: "Descrizione breve"
  stardate_inizio: 2400.0
  difficolta_default: NORMAL    # EASY, NORMAL, HARD, DOOM
  nave_suggerita: Constitution  # qualsiasi classe da ShipClass

  missioni:
    - id: M01
      nome: "Nome missione"
      descrizione_narrativa: |
        Testo narrativo che appare nel briefing.
        Puo essere su piu righe.
      obiettivo_testo: "Testo breve dell'obiettivo"
      obiettivi:
        - {tipo: distruggi_nemici, specie: klingon, quantita: 5}
        # oppure:
        - {tipo: scorta, bersaglio: nome_nave, destinazione: starbase_X}
        - {tipo: investigazione, bersaglio: nome_target}
        - {tipo: recupero_dati, bersaglio: nome_oggetto}
        - {tipo: sopravvivenza}
      deadline_stardate: 2401.0
      nemici:
        - {tipo: klingon, quantita: 3}
        - {tipo: romulani, quantita: 2}
        - {tipo: borg, quantita: 1}
        - {tipo: silenti, quantita: 2}
      basi_stellari: 2
      seed_galassia: 42           # seed per generazione procedurale (stesso seed = stessa mappa)
      consiglieri_speciali: []    # oppure: [ambasciatore_vulcaniano]
      silenti_eventi:
        - {tipo: lettura_anomala, settore: [3, 5], nota: "testo"}
        - {tipo: relitto_trovabile, settore: [7, 2], descrizione: "testo"}
        - {tipo: primo_contatto}
        - {tipo: rivelazione_nome}
      vittoria_alternativa: null
      # oppure:
      vittoria_alternativa:
        tipo: diplomatica
        condizione: "Descrizione condizione"
        bonus: "+20 morale, +30 dilithium"
      prerequisito: null          # oppure: M01_completata
```

Per usare la nuova campagna, modifica il percorso in `main.py` alla riga `DEFAULT_CAMPAIGN`.

### Aggiungere una nuova classe nave

In `src/engine/ship.py`:

1. Aggiungi un valore all'enum `ShipClass`:
```python
class ShipClass(Enum):
    # ...classi esistenti...
    NOVA = "Nova"
```

2. Aggiungi le stats nella tabella `SHIP_CLASS_STATS`:
```python
ShipClass.NOVA: ShipClassStats(
    crew=80, energy=3500, shields=90, torpedoes=15, dilithium=80,
    sensor_range_modifier=1.20,  # buona per l'esplorazione
),
```

3. In `src/engine/captain_log.py`, aggiungi il tono narrativo per il diario:
```python
ShipClass.NOVA: "VOY",  # o "TOS", "TNG", "DS9"
```

### Aggiungere un nuovo ufficiale speciale

1. Crea un file in `src/officers/special/`, es. `ferengi_trader.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from ..base_officer import Officer, OfficerRole, OfficerSpecies, InteractionMode

@dataclass
class FerengiTrader(Officer):
    role: OfficerRole = field(default=OfficerRole.SPECIAL, init=False)
    species: OfficerSpecies = field(default=OfficerSpecies.FERENGI, init=False)

    def get_domain_state(self, full_game_state: dict) -> dict:
        ship = full_game_state.get("ship", {})
        return {
            "dilithium": ship.get("dilithium", 0),
            "energy": ship.get("energy", 0),
            "docked": full_game_state.get("docked", False),
        }

    def get_system_prompt(self) -> str:
        return (
            "Sei un commerciante Ferengi a bordo. "
            "Ragioni sempre in termini di profitto e risorse. "
            "Citi le Regole dell'Acquisizione. "
            "Rispondi in 2-4 frasi."
        )

    def _is_active_in_context(self, context: str) -> bool:
        return context == "DOCKED"

    @classmethod
    def create_default(cls, client=None, model="claude-sonnet-4-20250514"):
        return cls(
            name="Quark", rank="Consulente Commerciale",
            _client=client, _model=model,
        )
```

2. Aggiungi il nome nel YAML della missione:
```yaml
consiglieri_speciali: [commerciante_ferengi]
```

3. Aggiungi la creazione in `main.py` nella funzione `create_officers()`:
```python
if "commerciante_ferengi" in special_officers:
    from src.officers.special.ferengi_trader import FerengiTrader
    officers["speciale"] = FerengiTrader.create_default(client=client, model=model)
```

### Aggiungere un nuovo tipo di nemico

In `src/engine/galaxy.py`, aggiungi il simbolo nell'enum `CellContent`:
```python
CARDASSIAN = "C"
```

In `src/engine/combat.py`:
1. Aggiungi le stats base in `calcola_colpo_nemico()` (dizionari `base_accuracy` e `base_damage`)
2. Crea la funzione AI `cardassian_ai()`
3. Registrala nel dispatcher `get_enemy_action()`

In `src/engine/galaxy.py`, mappa il tipo nella funzione `generate()`:
```python
content_map["cardassiani"] = CellContent.CARDASSIAN
```

### Modificare la difficolta

In `src/engine/difficulty.py`, puoi:
- Modificare i valori dei 4 preset esistenti
- Aggiungere un nuovo preset nell'enum e nella tabella
- Ogni valore e un moltiplicatore dove `1.0` = baseline

| Parametro | Effetto di un valore alto |
|-----------|--------------------------|
| `enemy_accuracy` | Nemici colpiscono piu spesso |
| `enemy_aggression` | Nemici attaccano piu frequentemente |
| `resource_drain` | Energia e dilithium si consumano piu in fretta |
| `stardate_pressure` | Lo stardate avanza piu velocemente |
| `repair_speed` | Riparazioni piu veloci (valore alto = piu facile) |
| `torpedo_scarcity` | Meno siluri alle basi |
| `officer_ai_quality` | Consigli migliori dagli ufficiali (valore alto = piu facile) |
| `morale_decay` | Morale scende piu in fretta dopo le perdite |

### Personalizzare l'interfaccia

Il presenter si trova in `src/presentation/cli_lcars.py`. Puoi modificare:

- **Colori LCARS**: dizionario `LCARS_COLORS` (usa nomi colore Rich)
- **Colori celle mappa**: dizionario `CELL_STYLES`
- **Colori ufficiali**: dizionario `OFFICER_COLORS`
- **Larghezza barre**: parametro `width` nella funzione `_bar()`
- **ASCII art titolo**: metodo `show_title_screen()`

Per creare un presenter completamente diverso (es. web), implementa tutti i metodi
della classe `BasePresenter` in `src/presentation/base_presenter.py`.

---

## Architettura

```
star_command/
├── main.py                          # Entry point e flusso campagna
├── pyproject.toml                   # Config progetto e pytest
├── requirements.txt                 # Dipendenze Python
├── .env.example                     # Template variabili ambiente
├── src/
│   ├── engine/                      # Motore di gioco (nessuna dipendenza UI)
│   │   ├── ship.py                  # Modello nave (7 classi con stats)
│   │   ├── systems.py               # 10 sistemi di bordo con degrado esponenziale
│   │   ├── galaxy.py                # Mappa 8x8 quadranti con fog of war
│   │   ├── combat.py                # Combattimento + 4 AI nemiche deterministiche
│   │   ├── navigation.py            # Warp e impulso con tabella consumi
│   │   ├── command_parser.py        # Parser NLP ibrido regex + menu contestuali
│   │   ├── captain_log.py           # Diario del Capitano (manuale + Claude AI)
│   │   ├── campaign.py              # Gestore campagna YAML + salvataggio
│   │   ├── difficulty.py            # 4 preset di difficolta
│   │   └── game_loop.py             # Loop principale con Protocol interfaces
│   ├── officers/                    # Ufficiali AI (agenti Claude, uno per ruolo)
│   │   ├── base_officer.py          # ABC con trust, morale, bonus specie
│   │   ├── tactical.py              # Worf (Klingon) — combattimento
│   │   ├── engineer.py              # Scott (Umano) — sistemi e riparazioni
│   │   ├── science.py               # T'Pol (Vulcaniana) — scansioni e analisi
│   │   ├── medical.py               # Crusher (Umana) — equipaggio e morale
│   │   └── special/
│   │       └── vulcan_ambassador.py # T'Vek — diplomazia (iniettato da M04)
│   ├── presentation/                # Layer UI disaccoppiato tramite Protocol
│   │   ├── base_presenter.py        # ABC con contratto dei 10 metodi
│   │   └── cli_lcars.py             # Implementazione Rich con tema LCARS
│   └── config/campaigns/
│       └── crisis_of_korvath.yaml   # Campagna inclusa: 4 missioni
└── tests/                           # 262 test pytest
    ├── conftest.py
    ├── test_engine/                  # Test per tutti i moduli engine
    ├── test_officers/                # Test trust, bonus, interazione
    └── test_presentation/            # Test rendering e output
```

I tre layer (Engine, Officers, Presentation) comunicano solo tramite `dict` serializzati
e Protocol interfaces, garantendo disaccoppiamento totale.

---

## Test

```bash
cd star_command
python -m pytest tests/ -v
```

Per eseguire solo una categoria:
```bash
python -m pytest tests/test_engine/ -v          # solo engine
python -m pytest tests/test_officers/ -v         # solo officers
python -m pytest tests/test_presentation/ -v     # solo presentation
python -m pytest tests/ -k "combat" -v           # solo test con "combat" nel nome
```
