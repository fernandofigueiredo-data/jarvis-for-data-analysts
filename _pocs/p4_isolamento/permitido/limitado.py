"""Executa um script com limite de memória (RLIMIT_AS) e de CPU (RLIMIT_CPU) — testa se o macOS respeita."""
import resource, runpy, sys
resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
try:
    resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30)); print("RLIMIT_AS aceito", file=sys.stderr)
except Exception as e:
    print("RLIMIT_AS recusado:", e, file=sys.stderr)
sys.argv = sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
