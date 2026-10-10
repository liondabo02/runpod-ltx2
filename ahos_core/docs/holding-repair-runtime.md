# Holding repair runtime

The holding brain observes failed tasks and queues bounded repair proposals. Coding repair proposals include both the OpenRouter and local Ollama adapters and their focused tests, so the local worker can repair its actual adapter without removing the cloud adapter or shrinking the original owner task. Dispatch does not approve or publish changes. Existing repair IDs remain deduplicated; an already persisted V1 repair retains its original scope and is not silently rewritten.

## Queue publication

Coding queue updates write and flush a complete temporary JSON file under the queue lock before atomic publication. Windows existing-file publication uses ReplaceFileW to preserve destination metadata and ACLs; initial publication and other platforms use os.replace. Transient Windows access/sharing errors (5, 32, 33) receive bounded retries for at most two seconds. Persistent failures propagate without truncating or deleting the live queue; investigate the actual file handle or access restriction before retrying work. This behavior does not grant permissions or provide sandbox isolation.
