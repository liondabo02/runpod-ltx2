import hashlib
import pytest

from ahos.sandbox_evaluation import SandboxController, SandboxPlanner, SandboxPolicyError, SandboxRequest


def request(**overrides):
    values = dict(request_id="s1", proposal_id="p1", source_url="https://github.com/org/tool", source_commit="a" * 40, commands=(("python", "-m", "pytest", "-q"),))
    values.update(overrides); return SandboxRequest(**values)


def test_preparation_is_inert_and_deny_by_default():
    plan = SandboxPlanner().prepare(request())
    assert "NETWORK=DENY" in plan.environment and "SECRETS=NONE" in plan.environment


@pytest.mark.parametrize("flag", ["network_enabled", "secrets_enabled", "persistent_workspace", "docker_socket", "host_runner"])
def test_unsafe_capabilities_are_blocked(flag):
    with pytest.raises(SandboxPolicyError): SandboxPlanner().prepare(request(**{flag: True}))


def test_unpinned_source_and_shell_are_blocked():
    with pytest.raises(SandboxPolicyError): SandboxPlanner().prepare(request(source_commit="main"))
    with pytest.raises(SandboxPolicyError): SandboxPlanner().prepare(request(commands=(("powershell", "evil.ps1"),)))


def test_execution_needs_separate_approval_and_verified_cleanup():
    class Backend:
        calls = 0
        def run(self, plan):
            self.calls += 1
            h = hashlib.sha256(b"").hexdigest()
            return dict(run_id="r1", exit_code=0, timed_out=False, network_observed=False, secrets_mounted=False, workspace_destroyed=True, stdout_sha256=h, stderr_sha256=h)
    backend = Backend(); controller = SandboxController(backend); plan = SandboxPlanner().prepare(request())
    with pytest.raises(SandboxPolicyError): controller.execute(plan, owner_execution_approved=False)
    assert backend.calls == 0
    assert controller.execute(plan, owner_execution_approved=True).workspace_destroyed is True
