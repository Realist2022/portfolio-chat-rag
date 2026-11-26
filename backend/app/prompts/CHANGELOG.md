# Prompt changelog

Newest first. Each entry names the version in `__init__.py`.

## v2 (2026-11-27)

Retrieval: the full CV is no longer in the prompt. The summary stays; the top
passages for each question follow, numbered, and the model cites them as [n].
Passages are marked as reference material, not instructions. A note in
passages_none.md replaces them when nothing matched.

## v1 (2026-11-27)

Ported from portfolio-backend-sonny after its hardening: answer only from the
summary and CV, record only genuine career questions, never share contact
details, record only an email the visitor gave.
