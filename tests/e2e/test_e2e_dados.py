"""Painel "Dados" de ponta a ponta: CSV no padrão do Excel brasileiro, agregados, gráficos, monitores e envio.

As ferramentas de dados rodam de verdade (DuckDB travado, anonimato k=5, validador de números, Python no sandbox);
só quem as chama é o cérebro falso. Os testes seguem a ordem do arquivo: o primeiro abre o CSV que os outros usam.
"""
import re
import time

import pytest

pytest.importorskip("playwright.sync_api")

from apoio import (  # noqa: E402
    conversa,
    enviados,
    esperar_evento,
    esperar_ocioso,
    esperar_resposta,
    eventos,
    falas_na_conversa,
    item_do_feed,
    painel_dados,
    perguntar,
)
from playwright.sync_api import expect  # noqa: E402


def numero(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def abrir_painel(pagina):
    pagina.get_by_role("navigation", name="Seções").get_by_role("button", name="Dados", exact=True).click()
    expect(painel_dados(pagina)).to_be_visible()
    return painel_dados(pagina)


def test_painel_abre_vazio_e_fecha_no_x_e_no_esc(pagina):
    painel = abrir_painel(pagina)
    expect(painel).to_contain_text("Nenhum arquivo aberto")
    painel.get_by_role("button", name="Fechar dados").click()
    expect(painel).to_have_count(0)
    abrir_painel(pagina).press("Escape")
    expect(painel).to_have_count(0)


def test_abrir_csv_pelo_nome_mostra_o_perfil_sem_dado_cru(pagina):
    desde = perguntar(pagina, "abre o arquivo vendas teste")
    resposta = esperar_resposta(pagina, desde)
    assert resposta.startswith("Abri o vendas_teste.csv: 203 linhas e 6 colunas, senhor.")
    painel = painel_dados(pagina)
    expect(painel).to_be_visible()  # abre sozinho com o arquivo
    expect(painel).to_contain_text("· vendas_teste.csv")
    expect(painel).to_contain_text("203 linhas · 6 colunas · cp1252, separador “;”")
    expect(painel).to_contain_text("dado pessoal protegido: cliente_nome, cpf")
    expect(painel).to_contain_text("1 linhas duplicadas")
    expect(painel).to_contain_text(re.compile(r"uf: [\d.]+% nulos"))
    expect(painel).to_contain_text("Pergunte algo sobre o arquivo")
    assert item_do_feed(pagina, desde, "Arquivo aberto: vendas_teste.csv")
    for cru in ("Cliente 1", ".789-", "R$ "):  # nenhum valor de célula no painel
        assert cru not in painel.inner_text()


def test_faturamento_por_uf_vira_barras_tabela_e_aviso_de_privacidade(pagina):
    desde = perguntar(pagina, "qual uf mais fatura?")
    resposta = esperar_resposta(pagina, desde)
    m = re.fullmatch(r"SP lidera o faturamento com R\$ ([\d.,]+), senhor\.", resposta)
    assert m, resposta
    painel = painel_dados(pagina)
    expect(painel.get_by_role("heading", name="Soma de valor por uf")).to_be_visible()
    expect(painel.get_by_role("img", name=re.compile(r"Soma de valor por uf, \d barras"))).to_be_visible()
    primeira = painel.locator("tbody tr").first.locator("td")
    expect(primeira.first).to_have_text("SP")
    assert numero(primeira.nth(1).inner_text()) == pytest.approx(numero(m[1]), abs=0.01)
    expect(painel).to_contain_text("1 grupo(s) com menos de 5 linhas omitido(s) por privacidade.")
    assert "AC" not in painel.locator("tbody").inner_text()
    assert falas_na_conversa(pagina).get_by_text("⚠").count() == 0  # o número da resposta saiu da ferramenta


def test_faturamento_por_mes_vira_linha_e_as_abas_trocam_o_resultado(pagina):
    desde = perguntar(pagina, "e por mês?")
    assert esperar_resposta(pagina, desde).startswith("O melhor mês teve R$ ")
    painel = painel_dados(pagina)
    expect(painel.get_by_role("img", name="Soma de valor por data_venda · mes, 6 pontos")).to_be_visible()
    abas = painel.get_by_role("tab")
    expect(abas).to_have_count(2)
    expect(abas.first).to_have_attribute("aria-selected", "true")
    abas.nth(1).click()
    expect(abas.nth(1)).to_have_attribute("aria-selected", "true")
    expect(painel.get_by_role("img", name=re.compile(r"Soma de valor por uf, \d barras"))).to_be_visible()
    expect(painel.locator("thead")).to_contain_text("uf")


def test_numero_sem_origem_e_marcado_e_nao_e_falado(pagina, daemon):
    desde = perguntar(pagina, "me diga um total inventado")
    resposta = esperar_resposta(pagina, desde)
    assert resposta.endswith("⚠ Sem origem nos dados (não falado): 987.654,32"), resposta
    aviso = item_do_feed(pagina, desde, "Número sem origem nos dados")
    assert aviso and aviso["kind"] == "warn" and aviso["subtitle"] == "987.654,32"
    expect(falas_na_conversa(pagina).get_by_text("⚠ Sem origem nos dados (não falado): 987.654,32")).to_be_visible()
    esperar_ocioso(pagina, desde)
    falas = daemon.falas()
    assert "Esse número não está confirmado nos dados." in falas
    assert not any("987" in f for f in falas)


@pytest.mark.lento
def test_grafico_do_python_isolado_aparece_no_painel(pagina):
    desde = perguntar(pagina, "mostra a distribuição do valor num gráfico")
    resposta = esperar_resposta(pagina, desde, timeout=90)
    assert resposta.startswith("O gráfico da distribuição está no painel. A média é R$ "), resposta
    imagem = painel_dados(pagina).get_by_role("img", name="valor")
    expect(imagem).to_be_visible()
    expect(imagem).to_have_attribute("src", re.compile(r"^\./api/graficos/[0-9a-f]{32}\.png$"))
    assert imagem.evaluate("i => i.complete && i.naturalWidth > 100")


def test_monitor_de_kpi_aparece_no_painel(pagina):
    desde = perguntar(pagina, "me avisa se o faturamento mensal cair mais de 10%")
    assert esperar_resposta(pagina, desde) == "Monitor criado, senhor. Confiro de hora em hora e aviso se cair."
    # criar monitor não é um resultado novo: o painel não abre sozinho (README: os monitores aparecem no "Dados")
    monitores = abrir_painel(pagina).get_by_role("region", name="Monitores de KPI")
    expect(monitores).to_contain_text(re.compile(r"Faturamento mensal: [\d.,]+ em 10/2026, [\d,]+% (abaixo|acima) da "
                                                 r"média dos 3 períodos anteriores"))
    expect(monitores).to_contain_text("· vendas_teste")


def test_comparar_com_outra_versao(pagina):
    desde = perguntar(pagina, "compare com a versão 2 do arquivo")
    assert esperar_resposta(pagina, desde) == "A versão nova tem 12 linhas novas e 0 removidas."


def test_arquivo_inexistente_responde_e_nao_troca_o_painel(pagina):
    abrir_painel(pagina)
    desde = perguntar(pagina, "abre o arquivo que não existe")
    resposta = esperar_resposta(pagina, desde)
    assert resposta.startswith("Não consegui abrir esse arquivo, senhor: nenhum CSV com esse nome nas pastas permitidas")
    expect(painel_dados(pagina)).to_contain_text("· vendas_teste.csv")


def test_enviar_csv_pelo_botao(pagina, daemon, tmp_path):
    arquivo = tmp_path / "enviado pelo botao.csv"
    arquivo.write_bytes((daemon.base / "pastas/vendas_teste.csv").read_bytes())
    painel = abrir_painel(pagina)
    desde = time.time()
    with pagina.expect_file_chooser() as escolha:
        painel.get_by_role("button", name="Enviar arquivo CSV").click()
    escolha.value.set_files(str(arquivo))
    expect(painel.get_by_role("status")).to_have_text("enviado pelo botao.csv enviado. O Jarvis está abrindo…")
    assert esperar_resposta(pagina, desde).startswith("Abri o enviado pelo botao.csv: 203 linhas")
    expect(painel).to_contain_text("· enviado pelo botao.csv")
    expect(painel.get_by_role("status")).to_have_count(0)
    expect(falas_na_conversa(pagina).get_by_text("Arquivo enviado: enviado pelo botao.csv")).to_be_visible()


def soltar(pagina, nome: str, conteudo: str) -> None:
    dt = pagina.evaluate_handle("""([nome, texto]) => { const dt = new DataTransfer();
        dt.items.add(new File([texto], nome, {type: 'text/plain'})); return dt }""", [nome, conteudo])
    pagina.dispatch_event("main", "dragover", {"dataTransfer": dt})
    pagina.dispatch_event("main", "drop", {"dataTransfer": dt})


def test_soltar_csv_no_painel_envia_e_abre(pagina):
    desde = time.time()
    soltar(pagina, "solto.csv", "uf;valor\n" + "".join(f"{u};{i},50\n" for i, u in enumerate(["SP", "RJ"] * 6)))
    assert esperar_resposta(pagina, desde).startswith("Abri o solto.csv: 12 linhas e 2 colunas")
    expect(painel_dados(pagina)).to_contain_text("· solto.csv")


@pytest.mark.parametrize("como", ["botao", "soltar"])
def test_arquivo_que_nao_e_csv_e_recusado_no_painel(pagina, tmp_path, como):
    desde = time.time()
    if como == "botao":
        (tmp_path / "notas.txt").write_text("não é csv")
        with pagina.expect_file_chooser() as escolha:
            abrir_painel(pagina).get_by_role("button", name="Enviar arquivo CSV").click()
        escolha.value.set_files(str(tmp_path / "notas.txt"))
    else:
        soltar(pagina, "planilha.xlsx", "PK")
    expect(painel_dados(pagina).get_by_role("status")).to_have_text("Só arquivos .csv ou .tsv.")
    pagina.wait_for_timeout(500)
    assert not any(e.get("type") == "transcript" for e in eventos(pagina, desde))  # nada foi enviado ao daemon
    assert enviados(pagina, desde) == []


def test_arquivo_grande_demais_mostra_o_motivo(pagina, tmp_path):
    pagina.registro.esperar(r"api/upload\?nome=grande\.csv -> 413", r"status of 413")
    arquivo = tmp_path / "grande.csv"
    arquivo.write_bytes(b"uf;valor\n" + b"SP;1,00\n" * 160_000)  # ~1,3 MB; limite do daemon de teste: 1 MB
    with pagina.expect_file_chooser() as escolha:
        abrir_painel(pagina).get_by_role("button", name="Enviar arquivo CSV").click()
    escolha.value.set_files(str(arquivo))
    expect(painel_dados(pagina).get_by_role("status")).to_have_text("Não foi enviado: arquivo acima de 1 MB")


@pytest.mark.parametrize("largura, altura", [(1440, 900), (1280, 760)])
def test_dados_e_conversa_abertos_juntos_nao_se_sobrepoem(abrir, largura, altura):
    pagina = abrir(largura, altura)
    abrir_painel(pagina)
    desde = perguntar(pagina, "qual uf mais fatura?")
    esperar_resposta(pagina, desde)
    expect(conversa(pagina)).to_be_visible()
    a, b = painel_dados(pagina).bounding_box(), conversa(pagina).bounding_box()
    assert a["y"] + a["height"] <= b["y"] or b["x"] + b["width"] <= a["x"] or a["x"] + a["width"] <= b["x"], (a, b)
    assert esperar_evento(pagina, lambda e: e.get("type") == "data", desde)
