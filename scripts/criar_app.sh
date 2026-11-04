#!/bin/bash
# Cria ~/Applications/Jarvis.app: um clique abre o Jarvis no Terminal, na pasta deste repositório.
# O Terminal é quem pede Microfone e Monitoramento de Entrada, então as permissões ficam com ele.
# Uso: scripts/criar_app.sh [destino]   (padrão: ~/Applications)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${1:-$HOME/Applications}"
APP="$DESTINO/Jarvis.app"
PORTA="$(grep -E '^JARVIS_PORT=' "$REPO/.env" 2>/dev/null | cut -d= -f2 || true)"
PORTA="${PORTA:-8787}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$DESTINO"
cat > "$TMP/Jarvis.applescript" <<EOF
-- Abre o Jarvis no Terminal; se ele já estiver aberto, só avisa.
set rodando to false
try
	do shell script "/usr/sbin/lsof -nP -iTCP:$PORTA -sTCP:LISTEN"
	set rodando to true
end try

if rodando then
	display notification "O Jarvis já está aberto." with title "Jarvis"
else
	tell application "Terminal"
		activate
		do script "cd " & quoted form of "$REPO" & " && uv run jarvis"
	end tell
end if
EOF
rm -rf "$APP"
osacompile -o "$APP" "$TMP/Jarvis.applescript"

# Ícone: o favicon do painel com margem, como os ícones do macOS
(cd "$TMP" && qlmanage -t -s 1024 -o "$TMP" "$REPO/ui/public/favicon.svg" >/dev/null 2>&1)
sips -z 824 824 "$TMP/favicon.svg.png" --out "$TMP/base.png" >/dev/null
sips --padToHeightWidth 1024 1024 "$TMP/base.png" --out "$TMP/icone.png" >/dev/null
mkdir "$TMP/Jarvis.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$TMP/icone.png" --out "$TMP/Jarvis.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s * 2)) $((s * 2)) "$TMP/icone.png" --out "$TMP/Jarvis.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$TMP/Jarvis.iconset" -o "$APP/Contents/Resources/applet.icns"
rm -f "$APP/Contents/Resources/Assets.car"
/usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$APP/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.jarvis.launcher" "$APP/Contents/Info.plist" 2>/dev/null \
  || /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.jarvis.launcher" "$APP/Contents/Info.plist"
codesign --force --deep -s - "$APP" 2>/dev/null
touch "$APP"

echo "Criado: $APP (abre $REPO na porta $PORTA)"
echo "Arraste-o para o Dock. No primeiro clique, o macOS pede para o Jarvis controlar o Terminal: aceite."
