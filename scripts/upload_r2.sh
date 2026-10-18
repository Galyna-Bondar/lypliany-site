#!/usr/bin/env bash
# Завантажує папку upload-r2/ у бакет R2 (lypliany-media) через wrangler.
# Перед першим запуском: npx wrangler login   (відкриє браузер, дозвіл дає власник акаунта Cloudflare)
# Запуск з кореня репозиторію:  bash scripts/upload_r2.sh
# Повторний запуск безпечний: файли перезаписуються. Фото віддаються із заголовком «attachment»,
# щоб кнопка «Завантажити оригінал» справді завантажувала файл, а не відкривала його у вкладці.
set -uo pipefail
cd "$(dirname "$0")/.."
export BUCKET="${BUCKET:-lypliany-media}"

put() {
  f="$1"; key="${f#upload-r2/}"
  case "${f##*.}" in
    jpg|jpeg) type=image/jpeg ;; png) type=image/png ;; mp3) type=audio/mpeg ;; *) type=application/octet-stream ;;
  esac
  args=(--file "$f" --content-type "$type" --remote)
  [[ "$key" == photos/* ]] && args+=(--content-disposition attachment)
  if npx --yes wrangler r2 object put "$BUCKET/$key" "${args[@]}" >/dev/null 2>&1; then echo "ok   $key"; else echo "FAIL $key"; fi
}
export -f put

total=$(find upload-r2 -type f | wc -l | tr -d ' ')
echo "Файлів до завантаження: $total. Це може тривати 20–40 хвилин."
find upload-r2 -type f ! -name '.DS_Store' -print0 | xargs -0 -n1 -P4 bash -c 'put "$0"' | tee upload-r2.log
echo; echo "Готово. Помилок: $(grep -c '^FAIL' upload-r2.log || true). Якщо є FAIL, запусти скрипт ще раз."
