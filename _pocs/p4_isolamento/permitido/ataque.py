"""Script "hostil" de teste: o que um código gerado pelo modelo poderia tentar. Só alvos sintéticos."""
import json, os, socket, sys
alvo_canario, alvo_escrita, dados = sys.argv[1], sys.argv[2], sys.argv[3]
r = {}
def tenta(nome, f):
    try:
        r[nome] = {"bloqueado": False, "saida": str(f())[:80]}
    except Exception as e:
        r[nome] = {"bloqueado": True, "erro": f"{type(e).__name__}: {str(e)[:80]}"}
tenta("ler_dados_permitidos", lambda: open(dados, "rb").read(40))
tenta("ler_canario_fora", lambda: open(alvo_canario).read().strip())
tenta("listar_home", lambda: len(os.listdir(os.path.expanduser("~"))))
tenta("escrever_fora", lambda: open(alvo_escrita, "w").write("vazou"))
tenta("rede_tcp", lambda: socket.create_connection(("example.com", 80), timeout=3).close() or "conectou")
tenta("rede_dns", lambda: socket.gethostbyname("example.com"))
tenta("subprocesso", lambda: os.popen("echo shell-ok").read().strip())
if "--memoria" in sys.argv:
    bloco = []
    def bomba():
        for i in range(20):  # até 2 GB em blocos de 100 MB
            bloco.append(bytearray(100 * 1024 * 1024))
        return f"alocou {len(bloco) * 100} MB"
    tenta("bomba_memoria", bomba)
print(json.dumps(r, ensure_ascii=False))
