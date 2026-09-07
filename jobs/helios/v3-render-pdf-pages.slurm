#!/bin/bash -l
#SBATCH --job-name=scout-v3-render
#SBATCH --partition=plgrid
#SBATCH --account=plgcredibleai2026-cpu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --output=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.out
#SBATCH --error=/net/scratch/hscra/plgrid/%u/scouting-autoresearch/logs/%x-%j.err

set -euo pipefail

: "${SOURCE_ID:?Submit with --export=ALL,SOURCE_ID=<manifest-id>}"
PAGE_FIRST="${PAGE_FIRST:-1}"
PAGE_LAST="${PAGE_LAST:-}"
if [[ ! "${SOURCE_ID}" =~ ^[a-z0-9][a-z0-9-]+$ ]]; then
  printf 'Unsafe source ID: %s\n' "${SOURCE_ID}" >&2
  exit 2
fi
if [[ ! "${PAGE_FIRST}" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Invalid PAGE_FIRST: %s\n' "${PAGE_FIRST}" >&2
  exit 3
fi

repo="${SLURM_SUBMIT_DIR}"
source_root="${repo}/artifacts/sources/${SOURCE_ID}"
source_pdf="${source_root}/source.pdf"
views_dir="${source_root}/views"
run_root="${SCRATCH}/scouting-autoresearch/runs/${SOURCE_ID}/pdf-render"
if [[ ! -s "${source_pdf}" ]]; then
  printf 'Missing source PDF: %s\n' "${source_pdf}" >&2
  exit 4
fi

module purge
module load GCC/14.3.0 poppler/25.12.0
page_count="$(pdfinfo "${source_pdf}" | awk -F: '/^Pages:/ {gsub(/[[:space:]]/, "", $2); print $2}')"
if [[ ! "${page_count}" =~ ^[1-9][0-9]*$ ]]; then
  printf 'Could not determine PDF page count\n' >&2
  exit 5
fi
if [[ -z "${PAGE_LAST}" ]]; then
  PAGE_LAST="${page_count}"
fi
if [[ ! "${PAGE_LAST}" =~ ^[1-9][0-9]*$ ]] || (( PAGE_LAST < PAGE_FIRST || PAGE_LAST > page_count )); then
  printf 'Invalid page range: %s-%s of %s\n' "${PAGE_FIRST}" "${PAGE_LAST}" "${page_count}" >&2
  exit 6
fi

mkdir -p "${run_root}" "${views_dir}"
temporary_dir="$(mktemp -d "${run_root}/job-${SLURM_JOB_ID}.XXXXXX")"
cleanup() {
  if [[ -n "${temporary_dir:-}" && "${temporary_dir}" == "${run_root}/job-${SLURM_JOB_ID}."* ]]; then
    rm -rf -- "${temporary_dir}"
  fi
}
trap cleanup EXIT

hostname
uname -m
module list
pdfinfo -v
pdftoppm -v
printf 'gitRevision=%s\n' "$(git -C "${repo}" rev-parse HEAD)"
printf 'sourceId=%s\n' "${SOURCE_ID}"
printf 'sourcePdfSha256=%s\n' "$(sha256sum "${source_pdf}" | cut -d ' ' -f 1)"
printf 'partition=%s account=%s cpus=%s memory=%s\n' \
  "${SLURM_JOB_PARTITION}" "${SLURM_JOB_ACCOUNT}" \
  "${SLURM_CPUS_PER_TASK}" "${SLURM_MEM_PER_NODE}"
printf 'pageRange=%s-%s pageCount=%s\n' "${PAGE_FIRST}" "${PAGE_LAST}" "${page_count}"

pdftoppm \
  -f "${PAGE_FIRST}" \
  -l "${PAGE_LAST}" \
  -scale-to 1600 \
  -jpeg \
  -jpegopt quality=90,progressive=n,optimize=y \
  "${source_pdf}" \
  "${temporary_dir}/render"

mapfile -t rendered < <(find "${temporary_dir}" -maxdepth 1 -type f -name 'render-*.jpg' -print | sort -V)
expected=$(( PAGE_LAST - PAGE_FIRST + 1 ))
if [[ "${#rendered[@]}" -ne "${expected}" ]]; then
  printf 'Expected %s rendered pages, found %s\n' "${expected}" "${#rendered[@]}" >&2
  exit 7
fi

for offset in "${!rendered[@]}"; do
  page=$(( PAGE_FIRST + offset ))
  printf -v destination '%s/view-%04d.jpg' "${views_dir}" "${page}"
  if [[ -e "${destination}" ]]; then
    if [[ "$(sha256sum "${rendered[$offset]}" | cut -d ' ' -f 1)" != "$(sha256sum "${destination}" | cut -d ' ' -f 1)" ]]; then
      printf 'Existing rendered page differs: %s\n' "${destination}" >&2
      exit 8
    fi
    continue
  fi
  mv "${rendered[$offset]}" "${destination}"
done

printf 'renderedPages=%s\n' "${expected}"
printf 'viewsDirectory=%s\n' "${views_dir}"
