# FolderRAG

Local-first retrieval-augmented generation over normal Windows folders.

FolderRAG incrementally indexes local documents and source code, retrieves relevant evidence for natural-language questions, and uses a local OpenAI-compatible LLM endpoint such as LM Studio to produce grounded answers with traceable sources.

## Status

Greenfield project. The first MVP scope is defined in `docs/FOLDERRAG_MVP_SPEC.md`.

## First vertical slice

`register folder -> scan/index -> search -> Ask -> grounded answer + sources`
