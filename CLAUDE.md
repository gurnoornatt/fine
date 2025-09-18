# KodeKlip - Surgical Code Context Management Tool

## Project Overview
KodeKlip (kk) is a command-line utility designed to combat "context bloat" in LLM interactions by providing surgical precision in code context management. Instead of relying on automated context providers (MCPs) that dump irrelevant code and degrade model performance, KodeKlip gives developers explicit control over their LLM context.

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

## Core Commands
- `kk add <repo_url>` - Clone library into local knowledge base
- `kk list` - View all cached libraries and their index status
- `kk update` - Keep local libraries up-to-date
- `kk find <alias> "<query>"` - Instant ripgrep-powered search
- `kk index <alias>` - Pre-process library for semantic search
- `kk find -i --semantic` - Interactive session with TUI selection

## Technical Stack
- **Language**: Python + Typer (for rapid development)
- **Database**: SQLite + SQLModel (zero-config local state)
- **Git Operations**: GitPython
- **Search**: ripgrep (Rust) for speed
- **TUI**: Textual + Rich for superior UX
- **Semantic Search**: tree-sitter + FAISS + SentenceTransformers
- **Packaging**: poetry/uv + pipx

## Development Phases
1. **Foundation**: Basic repo management and keyword search
2. **Interactive TUI**: Two-pane selection interface with clipboard integration
3. **Semantic Search**: AI-powered code understanding and search
4. **Public Launch**: Testing, documentation, and community release

## Philosophy
"CLIs are better because they give the developer explicit control. KodeKlip professionalizes the superior manual workflow of git clone + grep that smart developers are already adopting."

This tool transforms the clumsy "copy-paste" workflow into a fluid, professional experience that makes LLMs smarter, not dumber.