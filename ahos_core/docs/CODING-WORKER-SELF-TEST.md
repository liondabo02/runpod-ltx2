# CODING-WORKER SELF-TEST

This document explains the operating model of the OpenRouter coding worker:

- The worker runs in an isolated Git worktree, ensuring that all source files are separate from the main repository and cannot affect other branches or worktrees.
- Only tests that have been pre‑approved by the AHOS supervisor may be executed. Unapproved tests are blocked and will cause the run to fail.
- Every integration step, including test execution and any code changes, must receive explicit owner approval before it can be merged. The worker never proceeds to integration without that approval.

The self‑test verifies that the worktree isolation, test whitelist, and approval workflow are correctly configured.