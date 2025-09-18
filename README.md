# KodeKlip 🔪

> Surgical Code Context Management Tool - Fight context bloat with precision code extraction

KodeKlip is a command-line tool designed to combat "context bloat" in LLM interactions by providing surgical precision in code context management. Instead of relying on automated context providers that dump irrelevant code and degrade model performance, KodeKlip gives developers explicit control over their LLM context.

## The Problem

- **Context Bloat**: MCPs indiscriminately dump large, irrelevant chunks of code into LLM prompts
- **Degraded Performance**: LLMs get confused by noise, leading to less accurate responses
- **Wasted Resources**: Context window waste increases costs and reduces efficiency

## The Solution

A lightning-fast CLI tool that:
- Manages a local cache of critical libraries and codebases
- Provides instant keyword and semantic search capabilities
- Offers interactive TUI for surgical context selection
- Formats and copies precise code snippets to clipboard

## Quick Start

```bash
# Install KodeKlip
pip install kodeklip

# Add a repository to your local knowledge base
kk add https://github.com/python/cpython python

# Search for specific patterns
kk find python "async def"

# Interactive search with TUI
kk find python "database" -i

# Index repository for semantic search
kk index python
kk find python "connection pool" --semantic
```

## Core Commands

- `kk add <repo_url> <alias>` - Clone library into local knowledge base
- `kk list` - View cached libraries and their index status
- `kk update` - Keep local libraries up-to-date
- `kk find <alias> "<query>"` - Instant ripgrep-powered search
- `kk index <alias>` - Pre-process library for semantic search
- `kk find -i --semantic` - Interactive session with TUI selection

## Philosophy

"CLIs are better because they give the developer explicit control. KodeKlip professionalizes the superior manual workflow of git clone + grep that smart developers are already adopting."

This tool transforms the clumsy "copy-paste" workflow into a fluid, professional experience that makes LLMs smarter, not dumber.

## Development Status

🚧 **Alpha** - Core functionality in development

## License

MIT License - see LICENSE file for details.