# WQ MCP Brain

MCP Server for [WorldQuant Brain](https://platform.worldquantbrain.com/) alpha factor mining. Provides Claude Code (and any MCP-compatible client) with direct access to WQ Brain data research, expression construction, backtest simulation, and factor iteration.

## Architecture

```
tools/        — MCP thin wrappers (zero business logic)
models/       — Pydantic data contracts (input/output validation)
core/         — Pure business logic (no MCP dependency)
  api_client.py       WQ HTTP communication + auth + rate limiting
  queue_manager.py    FIFO queue with 3-concurrent enforcement
  research_service.py Dataset/operator/setting file queries
  expression_service.py  Expression validation + fingerprinting
  knowledge_service.py   Knowledge base JSON read/write
  web_service.py         DuckDuckGo search + webpage fetch
```

## Quick Start

```bash
# 1. Configure credentials
cp .env.example .env
# Edit .env with your BRAIN_USERNAME and BRAIN_PASSWORD

# 2. Run with Claude Code
# The .mcp.json automatically registers the wq-* tools:
#   wq_list_datasets, wq_validate_expression, wq_submit_factor, etc.
```

## Requirements

- Python >= 3.12
- A WorldQuant Brain account
- `uv` (recommended) or pip

## Dependencies

- `mcp` — Model Context Protocol SDK
- `pydantic` — Data validation
- `requests` — HTTP client
- `beautifulsoup4` / `lxml` — HTML parsing
- `ddgs` — DuckDuckGo search

## Configuration

| Env Var | Required | Description |
|---------|----------|-------------|
| `BRAIN_USERNAME` | Yes | WQ Brain username |
| `BRAIN_PASSWORD` | Yes | WQ Brain password |
| `HTTP_PROXY` | No | Proxy for DuckDuckGo searches |
| `HTTPS_PROXY` | No | Proxy for DuckDuckGo searches |

## Dataset Cache

This repo does **not** ship with cached WQ dataset definitions. To populate:

```bash
# Use the datafields_store.py from the original AlphaMiningV2 project:
# python pipeline/datafields_store.py --dataset-id <dataset_id>
```

Or simply run research tools and they will show whatever is locally cached in `datafields_cache/`.

## License

MIT
