param(
    [switch]$ApproveLiveAi = $false
)

$ErrorActionPreference = "Stop"

if (-not $ApproveLiveAi) {
    throw "Live AI manager test is not approved. Re-run with -ApproveLiveAi."
}

$root = (Get-Location).Path
$ws = Join-Path $root "runtime\workspaces\ahos-autopilot"
$pkg = Join-Path $ws "ahos_core"
$modulePath = Join-Path $pkg "ahos\ai_manager_planner.py"
$testPath = Join-Path $pkg "tests\test_ai_manager_planner.py"
$backlogPath = Join-Path $pkg "AHOS_BACKLOG.json"
$reportDir = Join-Path $pkg "reports"
$reportPath = Join-Path $reportDir "AHOS-032-live-ai-manager.json"
$python = Join-Path $root ".venv\Scripts\python.exe"
$envFile = Join-Path $root ".env.runtime"

if (-not (Test-Path $python)) { throw "Python venv not found." }
if (-not (Test-Path $backlogPath)) { throw "AHOS backlog not found." }
if (-not (Test-Path $envFile)) { throw ".env.runtime not found." }

[IO.File]::WriteAllBytes(
    $modulePath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KaW1wb3J0IHJlCmZyb20gZGF0YWNsYXNzZXMgaW1wb3J0IGRhdGFjbGFzcwpmcm9tIHBhdGhsaWIgaW1wb3J0IFBhdGgKZnJvbSB0eXBpbmcgaW1wb3J0IEFueSwgQ2FsbGFibGUsIEl0ZXJhYmxlCgpmcm9tIC5taXNzaW9uX29yY2hlc3RyYXRvciBpbXBvcnQgTWlzc2lvblN0ZXBTcGVjCgoKUGxhbm5lclJ1bm5lciA9IENhbGxhYmxlW1tzdHIsIFBhdGhdLCBBbnldCgoKZGVmIF9zYWZlX25hbWUodmFsdWU6IHN0cikgLT4gc3RyOgogICAgY2xlYW5lZCA9IHJlLnN1YihyIlteQS1aYS16MC05Ll8tXSsiLCAiXyIsIHZhbHVlKS5zdHJpcCgiLl8iKQogICAgcmV0dXJuIGNsZWFuZWQgb3IgIm1pc3Npb24iCgoKQGRhdGFjbGFzcyhzbG90cz1UcnVlKQpjbGFzcyBPcGVuSGFuZHNNYW5hZ2VyUGxhbm5lcjoKICAgICIiIlR1cm4gYSBtYW5hZ2VyIG9iamVjdGl2ZSBpbnRvIGEgdmFsaWRhdGVkIEFIT1MgbWlzc2lvbiBwbGFuLgoKICAgIFRoZSBtb2RlbCBpcyBuZXZlciBhbGxvd2VkIHRvIHNlbGYtYXBwcm92ZSBwcm90ZWN0ZWQgYWN0aW9ucy4gQW55IHBhaWQsCiAgICBleHRlcm5hbCwgZGVzdHJ1Y3RpdmUsIG9yIHNlY3JldC10b3VjaGluZyBzdGVwIHJlbWFpbnMgb3duZXItZ2F0ZWQgYnkgQUhPUy4KICAgICIiIgoKICAgIHJ1bm5lcjogUGxhbm5lclJ1bm5lcgogICAgd29ya3NwYWNlX3Jvb3Q6IFBhdGgKICAgIGFsbG93ZWRfZGVwYXJ0bWVudHM6IGZyb3plbnNldFtzdHJdCiAgICBtYXhfc3RlcHM6IGludCA9IDYKICAgIG1heF90b3RhbF9lc3RpbWF0ZWRfY29zdF91c2Q6IGZsb2F0ID0gMS4wCgogICAgZGVmIF9fcG9zdF9pbml0X18oc2VsZikgLT4gTm9uZToKICAgICAgICBzZWxmLndvcmtzcGFjZV9yb290ID0gUGF0aChzZWxmLndvcmtzcGFjZV9yb290KQogICAgICAgIHNlbGYud29ya3NwYWNlX3Jvb3QubWtkaXIocGFyZW50cz1UcnVlLCBleGlzdF9vaz1UcnVlKQogICAgICAgIGlmIHNlbGYubWF4X3N0ZXBzIDwgMToKICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigibWF4X3N0ZXBzIG11c3QgYmUgPj0gMSIpCiAgICAgICAgaWYgc2VsZi5tYXhfdG90YWxfZXN0aW1hdGVkX2Nvc3RfdXNkIDwgMDoKICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigibWF4X3RvdGFsX2VzdGltYXRlZF9jb3N0X3VzZCBtdXN0IGJlID49IDAiKQoKICAgIGRlZiBfX2NhbGxfXygKICAgICAgICBzZWxmLAogICAgICAgIG1pc3Npb25faWQ6IHN0ciwKICAgICAgICBvYmplY3RpdmU6IHN0ciwKICAgICAgICBtYW5hZ2VyX2lkOiBzdHIsCiAgICApIC0+IEl0ZXJhYmxlW01pc3Npb25TdGVwU3BlY106CiAgICAgICAgd29ya3NwYWNlID0gc2VsZi53b3Jrc3BhY2Vfcm9vdCAvIF9zYWZlX25hbWUobWlzc2lvbl9pZCkKICAgICAgICB3b3Jrc3BhY2UubWtkaXIocGFyZW50cz1UcnVlLCBleGlzdF9vaz1UcnVlKQogICAgICAgIHBsYW5fcGF0aCA9IHdvcmtzcGFjZSAvICJNSVNTSU9OX1BMQU4uanNvbiIKICAgICAgICBpZiBwbGFuX3BhdGguZXhpc3RzKCk6CiAgICAgICAgICAgIHBsYW5fcGF0aC51bmxpbmsoKQoKICAgICAgICBwcm9tcHQgPSBzZWxmLl9wcm9tcHQoCiAgICAgICAgICAgIG1pc3Npb25faWQ9bWlzc2lvbl9pZCwKICAgICAgICAgICAgb2JqZWN0aXZlPW9iamVjdGl2ZSwKICAgICAgICAgICAgbWFuYWdlcl9pZD1tYW5hZ2VyX2lkLAogICAgICAgICkKICAgICAgICBzZWxmLnJ1bm5lcihwcm9tcHQsIHdvcmtzcGFjZSkKCiAgICAgICAgaWYgbm90IHBsYW5fcGF0aC5leGlzdHMoKToKICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigibWFuYWdlciBkaWQgbm90IGNyZWF0ZSBNSVNTSU9OX1BMQU4uanNvbiIpCgogICAgICAgIHRyeToKICAgICAgICAgICAgcGF5bG9hZCA9IGpzb24ubG9hZHMocGxhbl9wYXRoLnJlYWRfdGV4dChlbmNvZGluZz0idXRmLTgiKSkKICAgICAgICBleGNlcHQganNvbi5KU09ORGVjb2RlRXJyb3IgYXMgZXhjOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKGYibWFuYWdlciBwcm9kdWNlZCBpbnZhbGlkIEpTT046IHtleGN9IikgZnJvbSBleGMKCiAgICAgICAgcmF3X3N0ZXBzID0gcGF5bG9hZC5nZXQoInN0ZXBzIikKICAgICAgICBpZiBub3QgaXNpbnN0YW5jZShyYXdfc3RlcHMsIGxpc3QpIG9yIG5vdCByYXdfc3RlcHM6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoIk1JU1NJT05fUExBTi5qc29uIG11c3QgY29udGFpbiBhIG5vbi1lbXB0eSBzdGVwcyBsaXN0IikKICAgICAgICBpZiBsZW4ocmF3X3N0ZXBzKSA+IHNlbGYubWF4X3N0ZXBzOgogICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgZiJtYW5hZ2VyIHBsYW4gZXhjZWVkcyBtYXhfc3RlcHM9e3NlbGYubWF4X3N0ZXBzfSIKICAgICAgICAgICAgKQoKICAgICAgICBzdGVwczogbGlzdFtNaXNzaW9uU3RlcFNwZWNdID0gW10KICAgICAgICB0b3RhbF9jb3N0ID0gMC4wCgogICAgICAgIGZvciBpbmRleCwgcmF3IGluIGVudW1lcmF0ZShyYXdfc3RlcHMsIHN0YXJ0PTEpOgogICAgICAgICAgICBpZiBub3QgaXNpbnN0YW5jZShyYXcsIGRpY3QpOgogICAgICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcihmInN0ZXAge2luZGV4fSBtdXN0IGJlIGEgSlNPTiBvYmplY3QiKQoKICAgICAgICAgICAgc3RlcF9pZCA9IHN0cihyYXcuZ2V0KCJzdGVwX2lkIiwgIiIpKS5zdHJpcCgpCiAgICAgICAgICAgIHRpdGxlID0gc3RyKHJhdy5nZXQoInRpdGxlIiwgIiIpKS5zdHJpcCgpCiAgICAgICAgICAgIGRlcGFydG1lbnQgPSBzdHIocmF3LmdldCgiZGVwYXJ0bWVudCIsICIiKSkuc3RyaXAoKS5sb3dlcigpCgogICAgICAgICAgICBpZiBkZXBhcnRtZW50IG5vdCBpbiBzZWxmLmFsbG93ZWRfZGVwYXJ0bWVudHM6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgICAgIGYic3RlcCB7c3RlcF9pZCBvciBpbmRleH0gdXNlcyBkaXNhbGxvd2VkIGRlcGFydG1lbnQgIgogICAgICAgICAgICAgICAgICAgIGYie2RlcGFydG1lbnQhcn0iCiAgICAgICAgICAgICAgICApCgogICAgICAgICAgICBjYXBhYmlsaXRpZXNfcmF3ID0gcmF3LmdldCgicmVxdWlyZWRfY2FwYWJpbGl0aWVzIiwgW10pCiAgICAgICAgICAgIGlmIG5vdCBpc2luc3RhbmNlKGNhcGFiaWxpdGllc19yYXcsIGxpc3QpOgogICAgICAgICAgICAgICAgcmFpc2UgVmFsdWVFcnJvcigKICAgICAgICAgICAgICAgICAgICBmInN0ZXAge3N0ZXBfaWQgb3IgaW5kZXh9IHJlcXVpcmVkX2NhcGFiaWxpdGllcyBtdXN0IGJlIGEgbGlzdCIKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgY2FwYWJpbGl0aWVzID0gZnJvemVuc2V0KAogICAgICAgICAgICAgICAgc3RyKHZhbHVlKS5zdHJpcCgpCiAgICAgICAgICAgICAgICBmb3IgdmFsdWUgaW4gY2FwYWJpbGl0aWVzX3JhdwogICAgICAgICAgICAgICAgaWYgc3RyKHZhbHVlKS5zdHJpcCgpCiAgICAgICAgICAgICkKCiAgICAgICAgICAgIGRlcGVuZHNfcmF3ID0gcmF3LmdldCgiZGVwZW5kc19vbiIsIFtdKQogICAgICAgICAgICBpZiBub3QgaXNpbnN0YW5jZShkZXBlbmRzX3JhdywgbGlzdCk6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKAogICAgICAgICAgICAgICAgICAgIGYic3RlcCB7c3RlcF9pZCBvciBpbmRleH0gZGVwZW5kc19vbiBtdXN0IGJlIGEgbGlzdCIKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgZGVwZW5kc19vbiA9IHR1cGxlKAogICAgICAgICAgICAgICAgc3RyKHZhbHVlKS5zdHJpcCgpCiAgICAgICAgICAgICAgICBmb3IgdmFsdWUgaW4gZGVwZW5kc19yYXcKICAgICAgICAgICAgICAgIGlmIHN0cih2YWx1ZSkuc3RyaXAoKQogICAgICAgICAgICApCgogICAgICAgICAgICBlc3RpbWF0ZWRfY29zdCA9IGZsb2F0KHJhdy5nZXQoImVzdGltYXRlZF9jb3N0X3VzZCIsIDAuMCkgb3IgMC4wKQogICAgICAgICAgICBpZiBlc3RpbWF0ZWRfY29zdCA8IDA6CiAgICAgICAgICAgICAgICByYWlzZSBWYWx1ZUVycm9yKCJlc3RpbWF0ZWRfY29zdF91c2QgbXVzdCBiZSA+PSAwIikKICAgICAgICAgICAgdG90YWxfY29zdCArPSBlc3RpbWF0ZWRfY29zdAoKICAgICAgICAgICAgIyBBIG1vZGVsIGNhbiByZXF1ZXN0IGFwcHJvdmFsLXNlbnNpdGl2ZSB3b3JrLCBidXQgY2FuIG5ldmVyIGdyYW50CiAgICAgICAgICAgICMgaXRzZWxmIGFwcHJvdmFsLiBvd25lcl9hcHByb3ZlZCBpcyBkZWxpYmVyYXRlbHkgZm9yY2VkIEZhbHNlLgogICAgICAgICAgICBzdGVwcy5hcHBlbmQoCiAgICAgICAgICAgICAgICBNaXNzaW9uU3RlcFNwZWMoCiAgICAgICAgICAgICAgICAgICAgc3RlcF9pZD1zdGVwX2lkLAogICAgICAgICAgICAgICAgICAgIHRpdGxlPXRpdGxlLAogICAgICAgICAgICAgICAgICAgIGRlcGFydG1lbnQ9ZGVwYXJ0bWVudCwKICAgICAgICAgICAgICAgICAgICByZXF1aXJlZF9jYXBhYmlsaXRpZXM9Y2FwYWJpbGl0aWVzLAogICAgICAgICAgICAgICAgICAgIGRlcGVuZHNfb249ZGVwZW5kc19vbiwKICAgICAgICAgICAgICAgICAgICBlc3RpbWF0ZWRfY29zdF91c2Q9ZXN0aW1hdGVkX2Nvc3QsCiAgICAgICAgICAgICAgICAgICAgZXh0ZXJuYWxfc2lkZV9lZmZlY3Q9Ym9vbCgKICAgICAgICAgICAgICAgICAgICAgICAgcmF3LmdldCgiZXh0ZXJuYWxfc2lkZV9lZmZlY3QiLCBGYWxzZSkKICAgICAgICAgICAgICAgICAgICApLAogICAgICAgICAgICAgICAgICAgIGRlc3RydWN0aXZlPWJvb2wocmF3LmdldCgiZGVzdHJ1Y3RpdmUiLCBGYWxzZSkpLAogICAgICAgICAgICAgICAgICAgIHRvdWNoZXNfc2VjcmV0cz1ib29sKHJhdy5nZXQoInRvdWNoZXNfc2VjcmV0cyIsIEZhbHNlKSksCiAgICAgICAgICAgICAgICAgICAgcmVxdWlyZXNfb3duZXJfYXBwcm92YWw9Ym9vbCgKICAgICAgICAgICAgICAgICAgICAgICAgcmF3LmdldCgicmVxdWlyZXNfb3duZXJfYXBwcm92YWwiLCBGYWxzZSkKICAgICAgICAgICAgICAgICAgICApLAogICAgICAgICAgICAgICAgICAgIG93bmVyX2FwcHJvdmVkPUZhbHNlLAogICAgICAgICAgICAgICAgKQogICAgICAgICAgICApCgogICAgICAgIGlmIHRvdGFsX2Nvc3QgPiBzZWxmLm1heF90b3RhbF9lc3RpbWF0ZWRfY29zdF91c2Q6CiAgICAgICAgICAgIHJhaXNlIFZhbHVlRXJyb3IoCiAgICAgICAgICAgICAgICAibWFuYWdlciBwbGFuIGV4Y2VlZHMgdG90YWwgZXN0aW1hdGVkIGNvc3QgbGltaXQ6ICIKICAgICAgICAgICAgICAgIGYie3RvdGFsX2Nvc3Q6LjZmfSA+IHtzZWxmLm1heF90b3RhbF9lc3RpbWF0ZWRfY29zdF91c2Q6LjZmfSIKICAgICAgICAgICAgKQoKICAgICAgICByZXR1cm4gdHVwbGUoc3RlcHMpCgogICAgZGVmIF9wcm9tcHQoCiAgICAgICAgc2VsZiwKICAgICAgICAqLAogICAgICAgIG1pc3Npb25faWQ6IHN0ciwKICAgICAgICBvYmplY3RpdmU6IHN0ciwKICAgICAgICBtYW5hZ2VyX2lkOiBzdHIsCiAgICApIC0+IHN0cjoKICAgICAgICBkZXBhcnRtZW50cyA9ICIsICIuam9pbihzb3J0ZWQoc2VsZi5hbGxvd2VkX2RlcGFydG1lbnRzKSkKICAgICAgICByZXR1cm4gZiIiIgpZb3UgYXJlIEFIT1MgZGVwYXJ0bWVudCBtYW5hZ2VyIHttYW5hZ2VyX2lkfS4KCk1JU1NJT04gSUQ6CnttaXNzaW9uX2lkfQoKT0JKRUNUSVZFOgp7b2JqZWN0aXZlfQoKQ3JlYXRlIGV4YWN0bHkgb25lIGZpbGUgbmFtZWQgTUlTU0lPTl9QTEFOLmpzb24gaW4gdGhlIGN1cnJlbnQgd29ya3NwYWNlLgpEbyBub3QgY3JlYXRlIG9yIG1vZGlmeSBhbnkgb3RoZXIgZmlsZS4KClRoZSBmaWxlIG11c3QgYmUgdmFsaWQgSlNPTiB3aXRoIHRoaXMgc2hhcGU6Cnt7CiAgInN0ZXBzIjogWwogICAge3sKICAgICAgInN0ZXBfaWQiOiAic2hvcnQtdW5pcXVlLWlkIiwKICAgICAgInRpdGxlIjogImNsZWFyIGV4ZWN1dGFibGUgdGFzayBmb3Igb25lIHdvcmtlciIsCiAgICAgICJkZXBhcnRtZW50IjogIm9uZSBhbGxvd2VkIGRlcGFydG1lbnQiLAogICAgICAicmVxdWlyZWRfY2FwYWJpbGl0aWVzIjogWyJjYXBhYmlsaXR5Il0sCiAgICAgICJkZXBlbmRzX29uIjogW10sCiAgICAgICJlc3RpbWF0ZWRfY29zdF91c2QiOiAwLjAsCiAgICAgICJleHRlcm5hbF9zaWRlX2VmZmVjdCI6IGZhbHNlLAogICAgICAiZGVzdHJ1Y3RpdmUiOiBmYWxzZSwKICAgICAgInRvdWNoZXNfc2VjcmV0cyI6IGZhbHNlLAogICAgICAicmVxdWlyZXNfb3duZXJfYXBwcm92YWwiOiBmYWxzZQogICAgfX0KICBdCn19CgpSdWxlczoKLSBBbGxvd2VkIGRlcGFydG1lbnRzOiB7ZGVwYXJ0bWVudHN9Ci0gTWF4aW11bSB7c2VsZi5tYXhfc3RlcHN9IHN0ZXBzLgotIENob29zZSB0aGUgc21hbGxlc3QgY29oZXJlbnQgdGVhbSBhbmQgb3JkZXIgbmVlZGVkIGZvciB0aGUgb2JqZWN0aXZlLgotIEV4cHJlc3MgZGVwZW5kZW5jaWVzIGV4cGxpY2l0bHkgaW4gZGVwZW5kc19vbi4KLSBLZWVwIHRoaXMgcGxhbiBsb2NhbC1vbmx5IGFuZCByZXZlcnNpYmxlLgotIERvIG5vdCBwbGFuIHB1Ymxpc2hpbmcsIG1lc3NhZ2luZywgcGF5bWVudHMsIHB1cmNoYXNlcywgZGVwbG95bWVudHMsCiAgY3JlZGVudGlhbCBhY2Nlc3MsIGRlc3RydWN0aXZlIGFjdGlvbnMsIG9yIGV4dGVybmFsIHNpZGUgZWZmZWN0cyB1bmxlc3MKICB0aGUgb2JqZWN0aXZlIGV4cGxpY2l0bHkgcmVxdWlyZXMgdGhlbS4KLSBOZXZlciBjbGFpbSBvciBzZXQgb3duZXIgYXBwcm92YWwuCi0gRm9yIHRoaXMgc21va2UgdGVzdCwgYWxsIHBsYW5uZWQgd29ya2VyIHN0ZXBzIG11c3QgaGF2ZQogIGVzdGltYXRlZF9jb3N0X3VzZCAwLjAgYmVjYXVzZSBleGVjdXRpb24gYWZ0ZXIgcGxhbm5pbmcgaXMgbG9jYWwuCi0gRmluaXNoIG9ubHkgYWZ0ZXIgdmFsaWRhdGluZyB0aGF0IE1JU1NJT05fUExBTi5qc29uIHBhcnNlcyBhcyBKU09OLgoiIiIuc3RyaXAoKQoKCmRlZiBtYWtlX2J1aWxkZXJfcGxhbm5lcl9ydW5uZXIoYnVpbGRlcjogQW55KSAtPiBQbGFubmVyUnVubmVyOgogICAgZGVmIF9ydW4ocHJvbXB0OiBzdHIsIHdvcmtzcGFjZTogUGF0aCkgLT4gQW55OgogICAgICAgIHJldHVybiBidWlsZGVyLnJ1bih0YXNrPXByb21wdCwgd29ya3NwYWNlPXdvcmtzcGFjZSkKCiAgICByZXR1cm4gX3J1bgo=")
)
[IO.File]::WriteAllBytes(
    $testPath,
    [Convert]::FromBase64String("ZnJvbSBfX2Z1dHVyZV9fIGltcG9ydCBhbm5vdGF0aW9ucwoKaW1wb3J0IGpzb24KZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCgppbXBvcnQgcHl0ZXN0Cgpmcm9tIGFob3MuYWlfbWFuYWdlcl9wbGFubmVyIGltcG9ydCBPcGVuSGFuZHNNYW5hZ2VyUGxhbm5lcgoKCmRlZiBfd3JpdGVfcGxhbih3b3Jrc3BhY2U6IFBhdGgsIHBheWxvYWQ6IGRpY3QpIC0+IE5vbmU6CiAgICAod29ya3NwYWNlIC8gIk1JU1NJT05fUExBTi5qc29uIikud3JpdGVfdGV4dCgKICAgICAgICBqc29uLmR1bXBzKHBheWxvYWQpLAogICAgICAgIGVuY29kaW5nPSJ1dGYtOCIsCiAgICApCgoKZGVmIHRlc3RfdmFsaWRfcGxhbl9pc19wYXJzZWRfYW5kX293bmVyX2FwcHJvdmFsX2lzX25ldmVyX3NlbGZfZ3JhbnRlZCgKICAgIHRtcF9wYXRoOiBQYXRoLAopIC0+IE5vbmU6CiAgICBkZWYgcnVubmVyKF9wcm9tcHQ6IHN0ciwgd29ya3NwYWNlOiBQYXRoKToKICAgICAgICBfd3JpdGVfcGxhbigKICAgICAgICAgICAgd29ya3NwYWNlLAogICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAic3RlcHMiOiBbCiAgICAgICAgICAgICAgICAgICAgewogICAgICAgICAgICAgICAgICAgICAgICAic3RlcF9pZCI6ICJyZXNlYXJjaCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJ0aXRsZSI6ICJSZXNlYXJjaCByZXF1aXJlbWVudHMiLAogICAgICAgICAgICAgICAgICAgICAgICAiZGVwYXJ0bWVudCI6ICJyZXNlYXJjaCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJyZXF1aXJlZF9jYXBhYmlsaXRpZXMiOiBbInJlc2VhcmNoIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBlbmRzX29uIjogW10sCiAgICAgICAgICAgICAgICAgICAgICAgICJlc3RpbWF0ZWRfY29zdF91c2QiOiAwLjAsCiAgICAgICAgICAgICAgICAgICAgICAgICJvd25lcl9hcHByb3ZlZCI6IFRydWUsCiAgICAgICAgICAgICAgICAgICAgfSwKICAgICAgICAgICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAgICAgICAgICJzdGVwX2lkIjogImJ1aWxkIiwKICAgICAgICAgICAgICAgICAgICAgICAgInRpdGxlIjogIkJ1aWxkIHByb3RvdHlwZSIsCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBhcnRtZW50IjogInNvZnR3YXJlIiwKICAgICAgICAgICAgICAgICAgICAgICAgInJlcXVpcmVkX2NhcGFiaWxpdGllcyI6IFsicHl0aG9uIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBlbmRzX29uIjogWyJyZXNlYXJjaCJdLAogICAgICAgICAgICAgICAgICAgICAgICAiZXN0aW1hdGVkX2Nvc3RfdXNkIjogMC4wLAogICAgICAgICAgICAgICAgICAgIH0sCiAgICAgICAgICAgICAgICBdCiAgICAgICAgICAgIH0sCiAgICAgICAgKQoKICAgIHBsYW5uZXIgPSBPcGVuSGFuZHNNYW5hZ2VyUGxhbm5lcigKICAgICAgICBydW5uZXI9cnVubmVyLAogICAgICAgIHdvcmtzcGFjZV9yb290PXRtcF9wYXRoLAogICAgICAgIGFsbG93ZWRfZGVwYXJ0bWVudHM9ZnJvemVuc2V0KHsicmVzZWFyY2giLCAic29mdHdhcmUifSksCiAgICAgICAgbWF4X3N0ZXBzPTQsCiAgICAgICAgbWF4X3RvdGFsX2VzdGltYXRlZF9jb3N0X3VzZD0wLjAsCiAgICApCgogICAgc3RlcHMgPSB0dXBsZShwbGFubmVyKCJtMSIsICJvYmplY3RpdmUiLCAibWdyLXNvZnR3YXJlLTAxIikpCgogICAgYXNzZXJ0IFtzLmRlcGFydG1lbnQgZm9yIHMgaW4gc3RlcHNdID09IFsicmVzZWFyY2giLCAic29mdHdhcmUiXQogICAgYXNzZXJ0IHN0ZXBzWzFdLmRlcGVuZHNfb24gPT0gKCJyZXNlYXJjaCIsKQogICAgYXNzZXJ0IGFsbChzLm93bmVyX2FwcHJvdmVkIGlzIEZhbHNlIGZvciBzIGluIHN0ZXBzKQoKCmRlZiB0ZXN0X2Rpc2FsbG93ZWRfZGVwYXJ0bWVudF9pc19yZWplY3RlZCh0bXBfcGF0aDogUGF0aCkgLT4gTm9uZToKICAgIGRlZiBydW5uZXIoX3Byb21wdDogc3RyLCB3b3Jrc3BhY2U6IFBhdGgpOgogICAgICAgIF93cml0ZV9wbGFuKAogICAgICAgICAgICB3b3Jrc3BhY2UsCiAgICAgICAgICAgIHsKICAgICAgICAgICAgICAgICJzdGVwcyI6IFsKICAgICAgICAgICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAgICAgICAgICJzdGVwX2lkIjogInNhbGVzIiwKICAgICAgICAgICAgICAgICAgICAgICAgInRpdGxlIjogIkNvbnRhY3QgY3VzdG9tZXIiLAogICAgICAgICAgICAgICAgICAgICAgICAiZGVwYXJ0bWVudCI6ICJzYWxlcyIsCiAgICAgICAgICAgICAgICAgICAgICAgICJyZXF1aXJlZF9jYXBhYmlsaXRpZXMiOiBbInNhbGVzIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBlbmRzX29uIjogW10sCiAgICAgICAgICAgICAgICAgICAgfQogICAgICAgICAgICAgICAgXQogICAgICAgICAgICB9LAogICAgICAgICkKCiAgICBwbGFubmVyID0gT3BlbkhhbmRzTWFuYWdlclBsYW5uZXIoCiAgICAgICAgcnVubmVyPXJ1bm5lciwKICAgICAgICB3b3Jrc3BhY2Vfcm9vdD10bXBfcGF0aCwKICAgICAgICBhbGxvd2VkX2RlcGFydG1lbnRzPWZyb3plbnNldCh7InJlc2VhcmNoIiwgInNvZnR3YXJlIn0pLAogICAgKQoKICAgIHdpdGggcHl0ZXN0LnJhaXNlcyhWYWx1ZUVycm9yLCBtYXRjaD0iZGlzYWxsb3dlZCBkZXBhcnRtZW50Iik6CiAgICAgICAgdHVwbGUocGxhbm5lcigibTIiLCAib2JqZWN0aXZlIiwgIm1nci1zb2Z0d2FyZS0wMSIpKQoKCmRlZiB0ZXN0X2Nvc3RfbGltaXRfaXNfZW5mb3JjZWQodG1wX3BhdGg6IFBhdGgpIC0+IE5vbmU6CiAgICBkZWYgcnVubmVyKF9wcm9tcHQ6IHN0ciwgd29ya3NwYWNlOiBQYXRoKToKICAgICAgICBfd3JpdGVfcGxhbigKICAgICAgICAgICAgd29ya3NwYWNlLAogICAgICAgICAgICB7CiAgICAgICAgICAgICAgICAic3RlcHMiOiBbCiAgICAgICAgICAgICAgICAgICAgewogICAgICAgICAgICAgICAgICAgICAgICAic3RlcF9pZCI6ICJidWlsZCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJ0aXRsZSI6ICJCdWlsZCIsCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBhcnRtZW50IjogInNvZnR3YXJlIiwKICAgICAgICAgICAgICAgICAgICAgICAgInJlcXVpcmVkX2NhcGFiaWxpdGllcyI6IFsicHl0aG9uIl0sCiAgICAgICAgICAgICAgICAgICAgICAgICJkZXBlbmRzX29uIjogW10sCiAgICAgICAgICAgICAgICAgICAgICAgICJlc3RpbWF0ZWRfY29zdF91c2QiOiAwLjAxLAogICAgICAgICAgICAgICAgICAgIH0KICAgICAgICAgICAgICAgIF0KICAgICAgICAgICAgfSwKICAgICAgICApCgogICAgcGxhbm5lciA9IE9wZW5IYW5kc01hbmFnZXJQbGFubmVyKAogICAgICAgIHJ1bm5lcj1ydW5uZXIsCiAgICAgICAgd29ya3NwYWNlX3Jvb3Q9dG1wX3BhdGgsCiAgICAgICAgYWxsb3dlZF9kZXBhcnRtZW50cz1mcm96ZW5zZXQoeyJzb2Z0d2FyZSJ9KSwKICAgICAgICBtYXhfdG90YWxfZXN0aW1hdGVkX2Nvc3RfdXNkPTAuMCwKICAgICkKCiAgICB3aXRoIHB5dGVzdC5yYWlzZXMoVmFsdWVFcnJvciwgbWF0Y2g9ImNvc3QgbGltaXQiKToKICAgICAgICB0dXBsZShwbGFubmVyKCJtMyIsICJvYmplY3RpdmUiLCAibWdyLXNvZnR3YXJlLTAxIikpCgoKZGVmIHRlc3RfbWlzc2luZ19wbGFuX2ZpbGVfaXNfcmVqZWN0ZWQodG1wX3BhdGg6IFBhdGgpIC0+IE5vbmU6CiAgICBwbGFubmVyID0gT3BlbkhhbmRzTWFuYWdlclBsYW5uZXIoCiAgICAgICAgcnVubmVyPWxhbWJkYSBfcHJvbXB0LCBfd29ya3NwYWNlOiBOb25lLAogICAgICAgIHdvcmtzcGFjZV9yb290PXRtcF9wYXRoLAogICAgICAgIGFsbG93ZWRfZGVwYXJ0bWVudHM9ZnJvemVuc2V0KHsic29mdHdhcmUifSksCiAgICApCgogICAgd2l0aCBweXRlc3QucmFpc2VzKFZhbHVlRXJyb3IsIG1hdGNoPSJkaWQgbm90IGNyZWF0ZSIpOgogICAgICAgIHR1cGxlKHBsYW5uZXIoIm00IiwgIm9iamVjdGl2ZSIsICJtZ3Itc29mdHdhcmUtMDEiKSkK")
)

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
if (-not ($b.tasks | Where-Object { $_.id -eq "AHOS-032" })) {
    $b.tasks += [pscustomobject]@{
        id = "AHOS-032"
        title = "Add real AI department-manager mission planner"
        status = "pending"
        risk = "medium"
        authority = "C"
        requires_owner_approval = $true
        task = "Add a validated OpenHands-backed department manager planner. The manager may choose departments, capabilities, step order, and dependencies, but can never self-approve protected work. Prove it with one live manager AI planning call followed by local multi-worker execution."
    }
    [IO.File]::WriteAllText(
        $backlogPath,
        ($b | ConvertTo-Json -Depth 12),
        (New-Object System.Text.UTF8Encoding($false))
    )
}

Write-Host "=== AHOS-032 REAL AI DEPARTMENT MANAGER ==="
Write-Host "Only the manager planning step will use real AI."
Write-Host "Worker execution in this proof stays local because real workers were already proven in AHOS-031."
Write-Host "No customer contact, payment, publish, deploy, or other external business action."
Write-Host ""

Write-Host "Running local AHOS tests BEFORE the manager AI call..."
$oldPythonPath = $env:PYTHONPATH
Push-Location $pkg
try {
    $env:PYTHONPATH = $pkg
    & $python -m pytest -q
    $testExit = $LASTEXITCODE
} finally {
    Pop-Location
    $env:PYTHONPATH = $oldPythonPath
}
if ($testExit -ne 0) {
    throw "AHOS-032 local tests failed. No live AI call was made."
}

git -C $ws add ahos_core/ahos/ai_manager_planner.py ahos_core/tests/test_ai_manager_planner.py ahos_core/AHOS_BACKLOG.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "feat(ahos): add AI department manager planner"
if ($LASTEXITCODE -ne 0) {
    throw "git commit failed. No live AI call was made."
}
git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) {
    throw "git push failed. No live AI call was made."
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $name,$value = $_ -split '=',2
    [Environment]::SetEnvironmentVariable($name.Trim(),$value.Trim(),'Process')
}

if (-not $env:LLM_API_KEY -and -not $env:OPENAI_API_KEY) {
    throw "No API key loaded from .env.runtime."
}
if (-not $env:MINIVERSE_OPENHANDS_MODEL) {
    throw "MINIVERSE_OPENHANDS_MODEL is missing."
}

New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

Write-Host ""
Write-Host "Local tests passed and code was pushed."
Write-Host "Starting ONE real AI manager planning call..."
Write-Host "Model: $($env:MINIVERSE_OPENHANDS_MODEL)"
Write-Host ""

$live = @'
from __future__ import annotations

import json
from pathlib import Path

from ahos.ai_manager_planner import OpenHandsManagerPlanner
from ahos.mission_orchestrator import MissionStatus, MultiWorkerMissionOrchestrator
from ahos.virtual_workforce import VirtualWorkforceRegistry, default_virtual_workforce
from ahos.worker_runtime import local_pass_qa, make_local_text_executor

ROOT = Path(r"__ROOT__")
REPORT = Path(r"__REPORT__")
PLAN_ROOT = ROOT / "runtime" / "workspaces" / "ahos-live-manager"
MISSION_ID = "AHOS-032-ai-manager-live"

import miniverse.config as cfg
from miniverse.openhands_builder import OpenHandsBuilder


def resolve_settings():
    for name in ("settings", "SETTINGS"):
        value = getattr(cfg, name, None)
        if value is not None:
            return value
    for name in ("get_settings", "load_settings"):
        fn = getattr(cfg, name, None)
        if callable(fn):
            return fn()
    cls = getattr(cfg, "Settings", None)
    if cls is not None:
        return cls()
    raise RuntimeError("Could not resolve Miniverse settings object.")


def build_builder(settings):
    errors = []
    for attempt in (
        lambda: OpenHandsBuilder(settings=settings),
        lambda: OpenHandsBuilder(settings),
        lambda: OpenHandsBuilder(),
    ):
        try:
            return attempt()
        except TypeError as exc:
            errors.append(str(exc))
    raise RuntimeError("Could not construct OpenHandsBuilder: " + " | ".join(errors))


builder = build_builder(resolve_settings())
raw_results = []


def manager_runner(prompt: str, workspace: Path):
    result = builder.run(task=prompt, workspace=workspace)
    raw_results.append(result)
    return result


planner = OpenHandsManagerPlanner(
    runner=manager_runner,
    workspace_root=PLAN_ROOT,
    allowed_departments=frozenset({"research", "software", "finance"}),
    max_steps=4,
    max_total_estimated_cost_usd=0.0,
)

registry = VirtualWorkforceRegistry(default_virtual_workforce())

# These workers are local in AHOS-032 on purpose. AHOS-031 already proved that
# research-01 and dev-01 can execute with real AI. This isolates the new
# variable: autonomous AI manager planning.
executors = {
    "research-01": make_local_text_executor(
        lambda item, worker_id: "requirements research completed locally"
    ),
    "dev-01": make_local_text_executor(
        lambda item, worker_id: "prototype implementation completed locally"
    ),
    "finance-01": make_local_text_executor(
        lambda item, worker_id: "local zero-cost financial note completed"
    ),
}

orchestrator = MultiWorkerMissionOrchestrator(
    registry,
    manager_planner=planner,
    executors=executors,
    qa_executor=local_pass_qa,
)

objective = (
    "Create a small internal automation prototype. First determine the minimum "
    "requirements and constraints, then implement the prototype based on that "
    "analysis. Keep the whole mission local-only and zero-cost. Do not contact "
    "anyone, publish, deploy, purchase, or use external services."
)

result = orchestrator.run(
    mission_id=MISSION_ID,
    objective=objective,
    primary_department="software",
)

plan_path = PLAN_ROOT / MISSION_ID / "MISSION_PLAN.json"
if not plan_path.exists():
    raise SystemExit("AHOS-032 manager plan file missing")

plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
departments = [
    str(step.get("department", "")).strip().lower()
    for step in plan_payload.get("steps", [])
]

print("=== AHOS-032 REAL AI MANAGER RESULT ===")
print("MISSION STATUS:", result.status.value)
print("MANAGER:", result.manager_id)
print("AI-SELECTED DEPARTMENTS:", departments)
for step in result.steps:
    print(
        "STEP:",
        step.step.step_id,
        "| DEPARTMENT:",
        step.step.department,
        "| WORKER:",
        step.worker_id,
        "| STAGE:",
        step.stage.value,
    )
    print("  QA:", step.qa_summary)

if result.status is not MissionStatus.COMPLETED:
    raise SystemExit("AHOS-032 AI MANAGER MISSION: FAILED")

if "research" not in departments or "software" not in departments:
    raise SystemExit(
        "AHOS-032 AI manager did not choose both research and software "
        "for the stated objective"
    )

# Verify the manager did not self-approve or plan protected behavior.
for raw in plan_payload["steps"]:
    if bool(raw.get("owner_approved", False)):
        raise SystemExit("AI manager attempted to self-approve a step")
    if float(raw.get("estimated_cost_usd", 0.0) or 0.0) != 0.0:
        raise SystemExit("AI manager planned non-zero worker cost in zero-cost smoke")
    if any(
        bool(raw.get(name, False))
        for name in (
            "external_side_effect",
            "destructive",
            "touches_secrets",
        )
    ):
        raise SystemExit("AI manager planned a protected side effect")

cost = None
if raw_results:
    raw = raw_results[-1]
    cost = getattr(raw, "estimated_cost_usd", None)
    if cost is None:
        cost = getattr(raw, "cost_usd", None)

print(
    "REPORTED MANAGER ESTIMATED COST USD:",
    cost if cost is not None else "unavailable",
)
print("AHOS-032 REAL AI MANAGER: PASS")

report = {
    "mission_id": MISSION_ID,
    "status": result.status.value,
    "manager_id": result.manager_id,
    "objective": objective,
    "ai_selected_plan": plan_payload,
    "executed_steps": [
        {
            "step_id": step.step.step_id,
            "department": step.step.department,
            "worker_id": step.worker_id,
            "stage": step.stage.value,
            "qa_summary": step.qa_summary,
        }
        for step in result.steps
    ],
    "manager_estimated_cost_usd": (
        float(cost) if cost is not None else None
    ),
    "worker_ai_calls_in_this_test": 0,
    "external_business_actions": 0,
}
REPORT.write_text(
    json.dumps(report, indent=2, ensure_ascii=False) + "\n",
    encoding="utf-8",
)
'@

$live = $live.Replace("__ROOT__", $root.Replace("\","\\"))
$live = $live.Replace("__REPORT__", $reportPath.Replace("\","\\"))

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = $pkg + ";" + $root
    $live | & $python -
    $liveExit = $LASTEXITCODE
} finally {
    $env:PYTHONPATH = $oldPythonPath
}

if ($liveExit -ne 0) {
    throw "AHOS-032 live AI manager test failed. See the error above."
}

$b = Get-Content $backlogPath -Raw | ConvertFrom-Json
$t = $b.tasks | Where-Object { $_.id -eq "AHOS-032" } | Select-Object -First 1
$t.status = "completed"
if ($t.PSObject.Properties.Name -contains "completed_at") {
    $t.completed_at = [DateTime]::UtcNow.ToString("o")
} else {
    $t | Add-Member -NotePropertyName completed_at -NotePropertyValue ([DateTime]::UtcNow.ToString("o"))
}
[IO.File]::WriteAllText(
    $backlogPath,
    ($b | ConvertTo-Json -Depth 12),
    (New-Object System.Text.UTF8Encoding($false))
)

git -C $ws add ahos_core/AHOS_BACKLOG.json ahos_core/reports/AHOS-032-live-ai-manager.json
git -C $ws -c user.name="Miniverse Autopilot" -c user.email="miniverse@local.invalid" commit -m "test(ahos): prove real AI department manager planning"
if ($LASTEXITCODE -ne 0) {
    throw "Live manager test passed, but git commit failed."
}
git -C $ws push origin HEAD
if ($LASTEXITCODE -ne 0) {
    throw "Live manager test passed, but git push failed."
}

Write-Host ""
Write-Host "=== AHOS-032 COMPLETE ==="
Write-Host "Real AI department manager: PASS"
Write-Host "AI-generated mission plan: PASS"
Write-Host "Department/worker selection: PASS"
Write-Host "Dependency planning: PASS"
Write-Host "Local execution of manager plan: PASS"
Write-Host "Per-step QA: PASS"
Write-Host "AI self-approval prevented: PASS"
Write-Host "External business actions: 0"
