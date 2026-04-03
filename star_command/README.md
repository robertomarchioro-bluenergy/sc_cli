# Star Command CLI

Gioco di strategia spaziale a turni ispirato a Star Trek, giocabile da terminale.
Ufficiali AI alimentati da Claude forniscono consigli contestuali che influenzano il gameplay.

## Requisiti

- Python >= 3.10 (oppure 3.9 con `from __future__ import annotations`)
- Dipendenze: `pip install -r requirements.txt`
- API key Anthropic (opzionale — il gioco funziona anche senza, con ufficiali AI disabilitati)

## Avvio rapido

```bash
cd star_command
cp .env.example .env   # configura ANTHROPIC_API_KEY
pip install -r requirements.txt
python main.py
```

## Architettura

```
star_command/
├── main.py                          # Entry point
├── src/
│   ├── engine/                      # Motore di gioco
│   │   ├── ship.py                  # Modello nave (7 classi)
│   │   ├── systems.py               # Sistemi di bordo con degrado esponenziale
│   │   ├── galaxy.py                # Mappa galattica 8x8 con fog of war
│   │   ├── combat.py                # Combattimento a turni + AI nemica
│   │   ├── navigation.py            # Warp e impulso con tabella consumi
│   │   ├── command_parser.py        # Parser NLP ibrido (regex + menu)
│   │   ├── captain_log.py           # Diario del Capitano (manuale + AI)
│   │   ├── campaign.py              # Gestore campagna YAML
│   │   ├── difficulty.py            # 4 preset di difficolta
│   │   └── game_loop.py             # Loop principale
│   ├── officers/                    # Ufficiali AI (un agente Claude per ruolo)
│   │   ├── base_officer.py          # ABC con trust, morale, bonus specie
│   │   ├── tactical.py              # Worf — combattimento
│   │   ├── engineer.py              # Scott — sistemi e riparazioni
│   │   ├── science.py               # T'Pol — scansioni e analisi
│   │   ├── medical.py               # Crusher — equipaggio e morale
│   │   └── special/
│   │       └── vulcan_ambassador.py # T'Vek — diplomazia (missione M04)
│   ├── presentation/                # Interfaccia terminale
│   │   ├── base_presenter.py        # ABC presenter
│   │   └── cli_lcars.py             # Implementazione Rich LCARS
│   └── config/campaigns/
│       └── crisis_of_korvath.yaml   # Campagna: 4 missioni
└── tests/                           # 262 test pytest
```

## Campagna: La Crisi di Korvath

| Missione | Nome | Obiettivo |
|----------|------|-----------|
| M01 | Pattuglia di Frontiera | Elimina 3 navi Klingon |
| M02 | Il Prezzo della Vittoria | Scorta la SS Copernicus |
| M03 | Ombre nel Silenzio | Investiga sparizione pattuglia Sigma-7 |
| M04 | L'Ambasciatore di Vulcano | Recupera dati o stringi alleanza Klingon |

## Classi nave

| Classe | Crew | Energia | Siluri | Specialita |
|--------|------|---------|--------|------------|
| Constitution | 430 | 5000 | 20 | +10% morale |
| Constitution Refit | 430 | 5500 | 22 | +10% morale |
| Galaxy | 1014 | 8000 | 35 | Bassa manovrabilita |
| Sovereign | 855 | 7500 | 40 | -20% danno ricevuto |
| Defiant | 50 | 3000 | 72 | +50% siluri, +20% scudi |
| Intrepid | 141 | 3600 | 25 | +30% sensori, +10 computer |
| Excelsior | 750 | 6000 | 30 | -20% consumo dilithium |

## Sistema Trust

Gli ufficiali AI hanno un livello di fiducia (trust) che evolve:
- **Consiglio seguito**: +2 trust
- **Consiglio ignorato**: -1 trust
- **5 consigli ignorati consecutivi**: -10 morale personale dell'ufficiale
- Sotto 20% morale: l'ufficiale diventa quasi silenzioso

## Test

```bash
cd star_command
py -m pytest tests/ -v
```
