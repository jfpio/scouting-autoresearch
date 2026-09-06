#!/bin/bash -l
#SBATCH --job-name=scout-sevin-contact
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/sevin-iiif-full-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/sevin-iiif-full-%j.err

set -euo pipefail

module purge
module load GCCcore/14.3.0 ImageMagick/7.1.2-7

task_repo="${SLURM_SUBMIT_DIR}"
source_dir="${SCRATCH}/scouting-autoresearch/sources/chamarande-1934"
run_root="${SCRATCH}/scouting-autoresearch/runs/chamarande-1934"
result_dir="${run_root}/iiif-contact-full/${SLURM_JOB_ID}"
expected_view_count=188
expected_pagination_sha256=48989b68bd51b00725dbf336f5fbfcbff3d3fe38fc4585078665b8c4daf74277
pagination_path="${source_dir}/pagination.xml"

mkdir -p "${run_root}"
temporary_dir="$(mktemp -d "${run_root}/iiif-thumbnails.XXXXXX")"

cleanup() {
  if [[ -n "${temporary_dir:-}" && "${temporary_dir}" == "${run_root}/iiif-thumbnails."* ]]; then
    rm -rf -- "${temporary_dir}"
  fi
}
trap cleanup EXIT

mapfile -t page_images < <(
  find "${source_dir}" -maxdepth 1 -type f -name 'f*-1200.jpg' -print | sort -V
)
if [[ "${#page_images[@]}" -ne "${expected_view_count}" ]]; then
  printf 'Expected %s IIIF views, found %s\n' \
    "${expected_view_count}" "${#page_images[@]}" >&2
  exit 2
fi

for expected_number in $(seq 1 "${expected_view_count}"); do
  expected_path="${source_dir}/f${expected_number}-1200.jpg"
  if [[ ! -s "${expected_path}" ]]; then
    printf 'Missing or empty expected view: %s\n' "${expected_path}" >&2
    exit 3
  fi
done

if [[ ! -s "${pagination_path}" ]]; then
  printf 'Missing or empty pagination cache: %s\n' "${pagination_path}" >&2
  exit 4
fi
observed_pagination_sha256="$(sha256sum "${pagination_path}" | cut -d ' ' -f 1)"
if [[ "${observed_pagination_sha256}" != "${expected_pagination_sha256}" ]]; then
  printf 'Pagination hash changed: expected %s, observed %s\n' \
    "${expected_pagination_sha256}" "${observed_pagination_sha256}" >&2
  exit 5
fi

mkdir -p "${result_dir}"

hostname
uname -m
module list
printf 'revision=%s\n' "$(git -C "${task_repo}" rev-parse HEAD)"
printf 'partition=%s account=%s cpus=%s memory=%s\n' \
  "${SLURM_JOB_PARTITION}" "${SLURM_JOB_ACCOUNT}" \
  "${SLURM_CPUS_PER_TASK}" "${SLURM_MEM_PER_NODE}"
magick -version
/usr/bin/python3 --version

/usr/bin/python3 - "${pagination_path}" "${temporary_dir}/printed-order.tsv" <<'PY'
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

source = Path(sys.argv[1])
destination = Path(sys.argv[2])
data = source.read_bytes()
upper = data.upper()
if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
    raise SystemExit("pagination XML contains a forbidden declaration")
root = ET.fromstring(data)
rows = []
for page in root.findall("./pages/page"):
    view = int(page.findtext("ordre") or "")
    printed = page.findtext("numero") or ""
    if printed.isdigit():
        rows.append((int(printed), view))
rows.sort()
expected = list(range(9, 142))
if [printed for printed, _ in rows] != expected:
    raise SystemExit("numeric printed pages are incomplete, duplicated, or outside 9-141")
destination.write_text(
    "".join(f"{printed}\t{view}\n" for printed, view in rows),
    encoding="utf-8",
)
PY

for page_image in "${page_images[@]}"; do
  page_name="$(basename "${page_image}" .jpg)"
  magick "${page_image}" -thumbnail '220x285>' "${temporary_dir}/${page_name}.jpg"
done

mapfile -t thumbnails < <(
  find "${temporary_dir}" -maxdepth 1 -type f -name 'f*-1200.jpg' -print | sort -V
)
if [[ "${#thumbnails[@]}" -ne "${expected_view_count}" ]]; then
  printf 'Expected %s thumbnails, found %s\n' \
    "${expected_view_count}" "${#thumbnails[@]}" >&2
  exit 6
fi

mkdir -p "${temporary_dir}/printed"
while IFS=$'\t' read -r printed_page view_number; do
  printf -v printed_label '%03d' "${printed_page}"
  ln -s \
    "${temporary_dir}/f${view_number}-1200.jpg" \
    "${temporary_dir}/printed/p${printed_label}-f${view_number}.jpg"
done < "${temporary_dir}/printed-order.tsv"
mapfile -t printed_thumbnails < <(
  find "${temporary_dir}/printed" -maxdepth 1 -type l -name 'p*-f*.jpg' -print | sort
)
if [[ "${#printed_thumbnails[@]}" -ne 133 ]]; then
  printf 'Expected 133 numeric printed-page thumbnails, found %s\n' \
    "${#printed_thumbnails[@]}" >&2
  exit 7
fi

magick montage \
  "${thumbnails[@]}" \
  -set label '%t' \
  -pointsize 12 \
  -tile 10x \
  -geometry '220x285+4+16>' \
  -background white \
  "${result_dir}/contact-sheet-view-order.jpg"

magick montage \
  "${printed_thumbnails[@]}" \
  -set label '%t' \
  -pointsize 12 \
  -tile 10x \
  -geometry '220x285+4+16>' \
  -background white \
  "${result_dir}/contact-sheet-printed-order.jpg"

identify \
  "${result_dir}/contact-sheet-view-order.jpg" \
  "${result_dir}/contact-sheet-printed-order.jpg"
sha256sum \
  "${result_dir}/contact-sheet-view-order.jpg" \
  "${result_dir}/contact-sheet-printed-order.jpg"
printf 'renderedPages=%s\n' "${#thumbnails[@]}"
printf 'numericPrintedPages=%s\n' "${#printed_thumbnails[@]}"
printf 'resultDirectory=%s\n' "${result_dir}"
