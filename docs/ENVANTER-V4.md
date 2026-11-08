# AHOS V4 — Faz 0 Envanteri

- Üretim: 2026-11-07T00:27:39
- Branch/HEAD: `feature/agent-control-plane` · `9eb4748cdc41`
- Departman: **17** · İşçi: **81**
- Çalışan servisler: ahos.daemon, cognition_sync, collective_loop, control_center, office_server, research_loop

## Bileşen sınıflandırması

| Bileşen | Durum | Test | Kanıt |
|---|---|---|---|
| `worker_mind` | test edildi | test_worker_mind.py | tests: test_worker_mind.py |
| `cognitive_memory` | test edildi | test_cognitive_memory.py, test_cognitive_memory_v4.py | tests: test_cognitive_memory.py, test_cognitive_memory_v4.py |
| `memory_vault` | test edildi | test_memory_vault.py | tests: test_memory_vault.py |
| `cognition` | test edildi | test_cognition.py | tests: test_cognition.py |
| `agent_growth` | test edildi | test_agent_growth.py | tests: test_agent_growth.py |
| `self_learning` | test edildi | test_self_learning_rotation.py | tests: test_self_learning_rotation.py |
| `learning_feedback` | test edildi | test_learning_feedback.py | tests: test_learning_feedback.py |
| `consensus` | mevcut | — | 3 import referansı |
| `commune` | mevcut | — | 4 import referansı |
| `queue_drain` | test edildi | test_queue_drain.py | tests: test_queue_drain.py |
| `queue_budget` | mevcut | — | 5 import referansı |
| `autonomous_company` | test edildi | test_autonomous_company.py | tests: test_autonomous_company.py |
| `initiative` | test edildi | test_initiative.py | tests: test_initiative.py |
| `improvement_cycle` | test edildi | test_improvement_cycle.py | tests: test_improvement_cycle.py |
| `owner_auth` | test edildi | test_owner_auth.py | tests: test_owner_auth.py |
| `panel_auth` | test edildi | test_panel_auth.py | tests: test_panel_auth.py |
| `control_center` | test edildi | test_control_center.py | tests: test_control_center.py |
| `daemon` | test edildi | test_daemon.py, test_daemon_live.py | tests: test_daemon.py, test_daemon_live.py |
| `knowledge` | mevcut | — | 8 import referansı |
| `research_store` | mevcut | — | 1 import referansı |
| `llm_executor` | test edildi | test_llm_executor.py | tests: test_llm_executor.py |
| `premium` | test edildi | test_premium.py | tests: test_premium.py |
| `office_3d` | test edildi | test_office_3d.py | tests: test_office_3d.py |
| `office_server` | yarim | — | test/import kanıtı yok |
| `research_loop` | yarim | — | test/import kanıtı yok |
| `cognition_sync` | yarim | — | test/import kanıtı yok |
| `collective_loop` | yarim | — | test/import kanıtı yok |
| `cognition_init` | yarim | — | test/import kanıtı yok |
| `eval_learning` | yarim | — | test/import kanıtı yok |
| `acceptance_advanced` | yarim | — | test/import kanıtı yok |

## Runtime kanıtı

- Zihin dosyası: **96** · bilişsel profil: **81**
- `plan_scores` dolu işçi: **42**
- Kanıtlı profil: **34** · kanıtsız: **47**
- Öğrenme kaydı: **7274** · araştırma: **238** · bilgi belgesi: **238**
- Sahip kurulumu: **False** · oturum: **0** · denetim satırı: **2**
- Memory vault: **2** · son: `vault-20261106T230337Z-41da47f9`

## Kuyruk

```json
{
  "missions": {
    "blocked": 43,
    "cancelled": 1378,
    "completed": 4015,
    "failed": 13
  },
  "triggers": [
    "ahos_pending_insert_cap",
    "ahos_pending_update_cap",
    "ahos_completed_result_guard_update",
    "ahos_completed_result_guard_insert"
  ]
}
```
