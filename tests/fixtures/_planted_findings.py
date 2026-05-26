# Planted findings to exercise agent-guard on a real PR.
# This file is intentionally bad — it exists only to validate the dogfood
# workflow's end-to-end sticky-comment behavior. Do not import it.

from totally_made_up_pkg import sparkle  # hallucination.unresolved-import

AWS_KEY = "AKIAIOSFODNN7EXAMPLE"          # secrets.aws-access-key


def run_user_input(cmd: str) -> object:
    return eval(cmd)                       # dangerous.eval-call


_ = sparkle  # silence "unused import" — though that's the least of this file's problems

# Additional planted finding to test idempotency:
import subprocess
subprocess.run("ls", shell=True)   # dangerous.subprocess-shell-true
