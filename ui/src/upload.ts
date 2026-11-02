// Arquivo arrastado (ou escolhido) no painel vai para o daemon, que o grava em data/arquivos e o abre num turno.
import { useJarvis } from './store'
import { wsUrl } from './ws'

const EXTENSOES = ['.csv', '.tsv']

/** Corpo cru, sem multipart. Só quando o painel é servido pelo daemon: a API não libera CORS. */
export async function uploadFile(file: File) {
  const status = useJarvis.getState().setUploadStatus
  useJarvis.getState().setDataOpen(true)
  if (!EXTENSOES.some((e) => file.name.toLowerCase().endsWith(e))) {
    status(`Só arquivos ${EXTENSOES.join(' ou ')}.`)
    return
  }
  if (new URL(wsUrl).host !== location.host) {
    status('Envio de arquivo só funciona no painel servido pelo Jarvis (porta 8787).')
    return
  }
  status(`Enviando ${file.name}…`)
  try {
    const r = await fetch(`./api/upload?nome=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: file,
    })
    const body = await r.json().catch(() => ({}))
    status(r.ok ? `${body.arquivo} enviado. O Jarvis está abrindo…` : `Não foi enviado: ${body.erro ?? r.status}`)
  } catch {
    status('Não foi enviado: o Jarvis não respondeu.')
  }
}

/** Soltar um arquivo em qualquer lugar do painel envia o primeiro. */
export function listenForDrops() {
  const temArquivo = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes('Files')
  window.addEventListener('dragover', (e) => {
    if (temArquivo(e)) e.preventDefault() // sem isso o navegador abre o arquivo no lugar do painel
  })
  window.addEventListener('drop', (e) => {
    if (!temArquivo(e)) return
    e.preventDefault()
    const file = e.dataTransfer?.files[0]
    if (file) void uploadFile(file)
  })
}
