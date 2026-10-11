from ahos.department_structure import CORE_DEPARTMENTS
from ahos.holding_knowledge import knowledge_snapshot, knowledge_context, RESOURCE_GROUPS


def test_complete_departments_and_owner_intent():
    snapshot = knowledge_snapshot()
    assert {d['id'] for d in snapshot['departments']} == set(CORE_DEPARTMENTS)
    assert all(d['workers'] and d['capabilities'] for d in snapshot['departments'])
    assert snapshot['products']['animation_studio']['department'] == 'creative'
    assert 'Kurdish Kurmanci' in snapshot['products']['animation_studio']['languages']
    assert any('revenue-producing' in goal for goal in snapshot['owner_goals'])
    assert all(c['production_allowed'] is False for c in snapshot['integration_candidates'])


def test_all_department_overview_and_tools_survive_bounded_retrieval():
    context = knowledge_context('fix software bug', limit=6500)
    assert len(context) <= 6500
    for department in CORE_DEPARTMENTS:
        assert department in context
    for group in RESOURCE_GROUPS.values():
        for name in group['names']:
            assert name in context
    assert 'live execution' not in context or 'not implied' in context
    assert 'different states' in context
    assert 'Gemini CLI consumer-login task is closed' in context


def test_studio_task_retrieves_specific_rules():
    context = knowledge_context('animation_studio voices multilingual screenplay cast', limit=6500)
    assert 'No adult fallback for children' in context
    assert 'S01E002' in context
    assert 'Historical request, not proof of delivery' in context
    assert 'ages 2' in context


def test_near_full_task_is_never_displaced_by_knowledge():
    assert knowledge_context('task', limit=10) == ''
    assert len(knowledge_context('task', limit=4000)) <= 4000
