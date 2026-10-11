# Exact file placement — modular functionality blocks

All paths are relative to the **one** repository root `EnviroSync/`. The terminal must open in this root when running repository-level scripts.

```text
EnviroSync/
├── .github/workflows/tests.yml             # GitHub CI, no AWS credentials
├── .env.example                            # safe configuration template
├── .gitattributes
├── .gitignore                              # protects secrets, envs, generated data
├── README.md                               # primary setup
├── pyproject.toml                          # one editable Python install for blocks 1B+2
├── requirements.txt                        # points to pyproject extras
├── conftest.py                             # shared fake-S3 fixtures for both Python blocks
├── docs/                                   # current cross-block documentation
│   ├── STRUCTURE.md
│   ├── SETUP_WINDOWS.md
│   ├── MIGRATION.md
│   ├── TEST_PLAN.md
│   ├── NEW_MILESTONE_CONTRACT.md
│   └── historical/                         # previous-layout docs (reference only)
├── milestones/
│   ├── __init__.py
│   ├── milestone_1a_infrastructure/          # one feature: AWS prerequisites
│   │   ├── README.md
│   │   └── docs/EXISTING_RESOURCES.md
│   ├── milestone_1b_federation/              # one feature: environmental data federation
│   │   ├── README.md
│   │   ├── cli.py
│   │   ├── config/settings.py
│   │   ├── common/serialization.py
│   │   ├── ingestion/weather.py
│   │   ├── ingestion/local.py
│   │   ├── storage/s3.py
│   │   ├── catalog/service.py
│   │   ├── federation/service.py
│   │   ├── examples/chennai-daily-weather.json
│   │   ├── examples/london-daily-weather.json
│   │   ├── tests/test_weather.py
│   │   ├── tests/test_federation.py
│   │   ├── tests/test_cli_and_safety.py
│   │   └── docs/historical/                # original Milestone 1B documentation
│   ├── milestone_2_api/                    # one feature: read-only HTTP gateway
│   │   ├── README.md
│   │   ├── app.py
│   │   ├── routes.py
│   │   ├── services.py
│   │   ├── dependencies.py
│   │   ├── errors.py
│   │   ├── tests/test_api.py
│   │   ├── tests/test_modular_integration.py
│   │   ├── tests/test_block_architecture.py
│   │   └── docs/historical/                # original Milestone 2 documentation
│   └── milestone_3_frontend/               # one feature: React UI (provisional milestone label)
│       ├── README.md
│       ├── index.html
│       ├── package.json
│       ├── vite.config.js
│       └── src/
│           ├── main.jsx
│           ├── App.jsx
│           ├── styles.css
│           ├── components/{Icon,SeriesChart,StatusPanel}.jsx
│           └── lib/{api,dates,format}.mjs   # plus corresponding *.test.mjs
└── scripts/                                # orchestration, no duplicated feature logic
    ├── setup.ps1
    ├── setup-frontend.ps1
    ├── start-api.ps1
    ├── start-frontend.ps1
    ├── check.ps1
    ├── check-fullstack.ps1
    └── smoke-live-api.ps1
```

The milestone 1A folder documents already existing AWS resources and intentionally contains no AWS creation scripts. The `milestone_3_frontend` name is a repository grouping choice, **not** a claim of a previously delivered formal Milestone 3. It uses HTTP to communicate with Milestone 2 rather than importing Python. All Python blocks share one virtual environment, defined from the root only.

**Important:** `milestones/milestone_1b_federation/docs/historical/` and `milestones/milestone_2_api/docs/historical/` retain original code references which use old import paths. Consult them for background only; the current README and `docs/SETUP_WINDOWS.md` are authoritative for commands.
