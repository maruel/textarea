#!/usr/bin/env bash
set -euo pipefail

script_dir="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly script_dir
project_dir="$(CDPATH='' cd -- "${script_dir}/.." && pwd)"
readonly project_dir
output="${script_dir}/textarea-screenshot.webp"
readonly output
readonly screenshot_width=1400
readonly screenshot_height=920
readonly titlebar_height=40
readonly outer_padding=72
readonly corner_radius=18
readonly frame_width="${screenshot_width}"
readonly frame_height=$((screenshot_height + titlebar_height))
readonly canvas_width=$((frame_width + outer_padding * 2))
readonly canvas_height=$((frame_height + outer_padding * 2))
sample=$'# Plain text, clear thoughts\n\nA quiet space for notes, ideas, and words that matter.\n\n## Keep it simple\n\n- Write without distractions\n- Share with a link\n- Dictate at the caret\n'
readonly sample

for command in chromium magick node; do
	if ! command -v "${command}" >/dev/null; then
		printf 'Missing required command: %s\n' "${command}" >&2
		exit 1
	fi
done

work_dir="$(mktemp -d -- "${script_dir}/.screenshot.XXXXXX")"
readonly work_dir
trap 'rm -rf -- "${work_dir}"' EXIT

hash="$(node -e 'process.stdout.write(require("zlib").deflateRawSync(Buffer.from(process.argv[1])).toString("base64url"))' "${sample}")"
readonly hash
png="${work_dir}/textarea-screenshot.png"
content="${work_dir}/content.png"
frame="${work_dir}/frame.png"
shadow="${work_dir}/shadow.png"
webp="${work_dir}/textarea-screenshot.webp"

chromium \
	--headless=new \
	--no-sandbox \
	--disable-gpu \
	--force-color-profile=srgb \
	--virtual-time-budget=1000 \
	--window-size="${screenshot_width},${screenshot_height}" \
	--screenshot="${png}" \
	"file://${project_dir}/public/index.html#${hash}"

magick "${png}" \
	\( -size "${screenshot_width}x${screenshot_height}" xc:none \
		-fill '#ffffff' \
		-draw "roundrectangle 0,0 $((screenshot_width - 1)),$((screenshot_height - 1)) ${corner_radius},${corner_radius}" \) \
	-alpha off \
	-compose CopyOpacity \
	-composite \
	"${content}"
magick \
	-size "${frame_width}x${frame_height}" xc:none \
	-fill '#ffffff' \
	-draw "roundrectangle 0,0 $((frame_width - 1)),$((frame_height - 1)) ${corner_radius},${corner_radius}" \
	-fill '#f6f6f6' \
	-draw "roundrectangle 0,0 $((frame_width - 1)),$((titlebar_height * 2 - 1)) ${corner_radius},${corner_radius}" \
	"${content}" -geometry "+0+${titlebar_height}" -composite \
	-stroke '#d1d1d6' -strokewidth 1 \
	-draw "line 0,${titlebar_height} ${frame_width},${titlebar_height}" \
	-fill '#ff5f57' -stroke none -draw 'circle 16,20 22,20' \
	-fill '#febc2e' -draw 'circle 36,20 42,20' \
	-fill '#28c840' -draw 'circle 56,20 62,20' \
	-fill '#333333' -font DejaVu-Sans -pointsize 13 -gravity North \
	-annotate +0+13 'Textarea' \
	"${frame}"
magick "${frame}" \
	\( +clone -background '#1f2937' -shadow 40x14+0+16 \) \
	+swap -background none -layers merge +repage \
	"${shadow}"
magick \
	-size "${canvas_width}x${canvas_height}" radial-gradient:'#ffffff-#e9ecff' \
	"${shadow}" -gravity center -composite \
	-strip -quality 88 \
	"${webp}"
mv -- "${webp}" "${output}"
