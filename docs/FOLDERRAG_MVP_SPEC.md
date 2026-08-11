# FolderRAG MVP Specification

## Problem Statement

I want a local RAG application that can index normal Windows folders once, detect file changes on later scans, and answer natural-language questions using the indexed documents as the source of truth. I do not want every question to rescan or re-embed every file, and I do not want the LLM to invent answers when the indexed evidence is weak.

The first implementation must stay small enough to complete as an end-to-end working MVP before adding advanced retrieval, desktop integration, broad file-format support, or unrelated infrastructure.

## Solution

Build a local-first FolderRAG application with a Python/FastAPI backend and a simple React + Vite + TypeScript frontend.

The first vertical slice will let the user register one or more local Windows folders by path, recursively scan supported files, extract and chunk their contents, embed final chunks locally, store them in persistent Qdrant Local storage, and track file/index state in SQLite so unchanged files are skipped on later scans.

The user can search all registered folders or one selected root folder. A query is embedded locally, relevant Qdrant candidates are retrieved, MMR selects a smaller diverse evidence set, and Ask mode sends only retrieved evidence to an OpenAI-compatible local LLM endpoint such as LM Studio. Search mode stops after retrieval and shows the evidence directly.

Answers must cite backend-controlled source metadata such as filenames, PDF page ranges, or text/code line ranges. If retrieval does not provide enough evidence, the backend must return an insufficient-information result instead of relying on the LLM to guess.

## User Stories

1. As a user, I want to register one or more Windows folders so that they become searchable knowledge sources.
2. As a user, I want recursive discovery so nested supported files are included automatically.
3. As a user, I want hidden files/folders, generated output, dependency/cache folders, lockfiles and common secret-bearing files skipped by default so retrieval stays clean and safe.
4. As a user, I want PDF, TXT, Markdown and Python supported in the first working build so the MVP covers documents and useful source code without excessive parser scope.
5. As a user, I want PDF page provenance and text/code line provenance so every result is traceable.
6. As a user, I want document text chunked semantically so retrieved chunks correspond to coherent topics.
7. As a user, I want Python indexed primarily as complete functions/methods so implementations are not arbitrarily split.
8. As a user, I want local embeddings so indexing does not depend on a cloud service.
9. As a user, I want vectors persisted locally so restarting FolderRAG does not require rebuilding the knowledge base.
10. As a user, I want registered folder and file state persisted so later scans can be incremental.
11. As a user, I want unchanged files skipped, changed files re-indexed, and deleted files removed from retrieval.
12. As a user, I want a failed file update to preserve the previous good index so transient failures do not destroy searchable data.
13. As a user, I want one failed file isolated so it does not abort an entire scan.
14. As a user, I want an unavailable root treated as offline rather than deleted so disconnected drives cannot wipe the index.
15. As a user, I want to search all folders or one selected root folder.
16. As a user, I want Search mode to show retrieved evidence without using the LLM.
17. As a user, I want Ask mode to generate an answer using only retrieved evidence.
18. As a user, I want MMR to reduce redundant evidence before context is sent to the LLM.
19. As a user, I want weak retrieval rejected before generation so unsupported questions are not answered confidently.
20. As a user, I want citations rendered from backend metadata rather than model-invented filenames/pages.
21. As a user, I want retrieved chunks, scores and source metadata visible in an evidence panel so I can understand the RAG pipeline.
22. As a user, I want LM Studio supported through an OpenAI-compatible generation interface.
23. As a user, I want Search mode to remain usable even if LM Studio is offline.
24. As a developer, I want extraction, chunking, embedding, indexing, retrieval, context construction and generation kept as explicit modules so the project teaches RAG rather than hiding it behind a large framework.
25. As a developer, I want deterministic fake providers in automated tests so core behavior can be verified without large models or LM Studio.
26. As a developer, I want one high-level end-to-end backend test seam so the main behavior is validated without brittle implementation-detail tests.

## Implementation Decisions

- Backend: Python + FastAPI.
- Frontend: React + Vite + TypeScript.
- Frontend development port: `5174`.
- Local-first, single-user MVP only.
- No LangChain or LlamaIndex in the first implementation.
- Keep explicit module boundaries for extraction, chunking, embeddings, vector storage, indexing, retrieval, context selection, prompt construction and generation.
- Folder sources have stable logical IDs and Windows paths. Overlapping registered roots are rejected.
- Manual Windows path entry is sufficient for the first vertical slice.
- Recursive discovery skips hidden files/folders, common build/generated/dependency/cache directories, generated lockfiles and common secret-bearing files.
- Initial formats: PDF, TXT, Markdown and Python.
- PDF extraction uses `pypdf` and retains page provenance. Image-only PDFs with no useful extracted text are reported as unsupported.
- TXT/Markdown retain line ranges. Markdown heading context may enrich embedding input while display text remains original.
- Document/prose chunking uses a structure-aware semantic strategy.
- `BAAI/bge-small-en-v1.5` is the lightweight semantic-boundary model.
- Initial semantic chunk limits: approximately 150 minimum / 500 target / 900 maximum tokens.
- Semantic chunk overlap is percentage-based; initial default is 10% and remains configurable.
- Python code uses complete function/method chunks where practical, enriched with file/class/function context and exact source line provenance.
- Final retrieval embeddings use `pplx-embed-v1-4B` locally.
- Initial vector representation uses the agreed full 2560 dimensions and cosine similarity.
- Embedding device selection is `auto`: CUDA when available, CPU fallback, with configuration override.
- Models are lazy-loaded and reused through a small model-management boundary.
- Qdrant Local Mode is the persistent vector store.
- Use one Qdrant collection for the first MVP, with folder/document/chunk metadata used for filtering and citations.
- SQLite stores registered folders, document/index state, hashes/timestamps and indexing bookkeeping.
- SQLAlchemy 2.x provides a thin persistence layer.
- Alembic is deferred until the initial schema stabilizes.
- File-change detection first uses path/size/modification metadata and SHA-256 confirmation when needed.
- Modified-file replacement is atomic: old vectors remain until the new version indexes successfully.
- Missing files are removed only after a successful root enumeration. An unavailable root never triggers mass deletion.
- Qdrant stores chunk text together with retrieval metadata.
- Retrieval default: up to 20 Qdrant candidates, then MMR selects at most 8 evidence chunks.
- Search-all uses no root filter; selected-folder search filters by root ID.
- Evidence gating happens before generation. The threshold is configurable; formal calibration is deferred until after the working vertical slice.
- The LLM sees only the resolved question and selected evidence, not vector scores or internal diagnostics.
- Source IDs are backend-generated and final citations are rendered from retrieved metadata.
- The generation provider is OpenAI-compatible with LM Studio as the default local endpoint.
- Search mode performs retrieval only. Ask mode performs retrieval, evidence gating, context construction and generation.
- Runtime data is local and untracked. SQLite, Qdrant data, indexed content, local paths, model caches, chat state and secrets must not be committed.
- Intended normal runtime storage is Windows Local AppData, with configuration override.
- Use typed application configuration plus environment variables.

## Testing Decisions

- Primary test seam: externally visible folder-index-and-query behavior through the backend.
- A high-level test creates a temporary folder, writes fixture files, registers/scans it, persists state in temporary SQLite/Qdrant storage and queries through the backend service/API seam.
- Automated tests use deterministic fake embedding and fake generation providers.
- Acceptance behavior must verify:
  - new file indexes;
  - unchanged file is skipped;
  - modified file replaces old indexed content;
  - deleted file disappears from retrieval after a valid scan;
  - unavailable roots do not delete indexed content;
  - root-folder filtering excludes unrelated sources;
  - retrieval returns correct provenance;
  - weak/no evidence does not generate a fabricated answer.
- PDF fixtures verify page provenance.
- TXT/Markdown/Python fixtures verify line provenance.
- Python fixtures verify function-level chunk behavior.
- MMR behavior is tested with intentionally overlapping candidates.
- Prefer high-level behavior tests over brittle private implementation tests.
- Manual smoke testing validates the real Windows/CUDA stack, `pplx-embed-v1-4B`, persistent Qdrant and LM Studio.

## Out of Scope

Deferred until after the first end-to-end path works:

- DOCX/PPTX/XLSX.
- OCR and scanned-PDF recognition.
- Full multi-language Tree-sitter code parsing.
- Structured JSON/YAML/TOML chunkers.
- Native Windows folder picker.
- Automatic filesystem watching or startup scans.
- Duplicate-document deduplication.
- BM25/hybrid retrieval.
- Cross-encoder reranking.
- Advanced code-neighbor expansion, class/module overview retrieval and exact symbol boosting.
- Subfolder-level scope.
- Conversation-aware query rewriting and persistent multi-thread chat if they threaten completion of the first slice.
- SSE/token streaming.
- Click-to-open source files and document previews.
- Formal retrieval benchmark dashboard and automatic evidence-threshold calibration.
- Embedding-model migration UI.
- Alembic migration workflow until schema stabilizes.
- Redis, Celery, separate worker infrastructure, cloud vector databases, Supabase, authentication, cloud deployment and multi-user functionality.

## Further Notes

- Public target repository: `JaydenWNG/FolderRAG`.
- Target environment is Windows with a strong CUDA-capable GPU; CPU fallback remains supported by the embedding abstraction.
- The existing local LM Studio setup is the intended generator.
- Retrieved documents are the factual source of truth; the LLM is only the explanation/generation layer.
- First implementation goal: `register folder -> scan/index -> search -> Ask -> grounded answer + traceable sources`.
- Advanced features should be added only after that vertical slice works reliably.
