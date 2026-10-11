# Holding repair runtime

The holding brain observes failed tasks and queues bounded repair proposals. Coding repair proposals include both the OpenRouter and local Ollama adapters and their focused tests, so the local worker can repair its actual adapter without removing the cloud adapter or shrinking the original owner task. Dispatch does not approve or publish changes. Coding repair contract revision 2 uses BRAIN-CODING-EXHAUSTED-V2. A historical V1 repair retains its original scope and evidence without silent mutation; the V2 proposal is queued once and deduplicated on subsequent cycles, even when exhausted. Department repair remains V1. Revisions change only when the implementation explicitly changes the repair contract; failed repair tasks never create recursive repair loops.

## Queue publication

Coding queue updates write and flush a complete temporary JSON file under the queue lock before atomic publication. Windows existing-file publication uses ReplaceFileW to preserve destination metadata and ACLs; initial publication and other platforms use os.replace. Transient Windows access/sharing errors (5, 32, 33) receive bounded retries for at most two seconds. Persistent failures propagate without truncating or deleting the live queue; investigate the actual file handle or access restriction before retrying work. This behavior does not grant permissions or provide sandbox isolation.

## Department diagnostics

Department provider failures persist controlled categories (`auth`, `network`,
`malformed`, `http`, `rate_limit`) and validated HTTP status codes rather than
remote response bodies or arbitrary exception messages. Successful drafts clear
previous diagnostic fields. HTTP 429 keeps the existing provider cooldown and
does not consume ordinary attempts; other failures retain bounded retries.
Diagnostics improve repair evidence but do not prove operational department
execution or production readiness.
